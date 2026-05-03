"""
IoT Junction Integration Service

This module keeps an optional background sync loop that:
1) fetches latest 4-way junction status from AWS DynamoDB,
2) applies priority + signal rules in backend,
3) mirrors latest status into Firestore for the rest of the system.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from app.config import get_settings
from app.db.firestore_client import Collections, get_db

logger = logging.getLogger(__name__)

LANE_ORDER = ("north", "south", "east", "west")


class IotJunctionService:
    """Synchronizes AWS DynamoDB lane data into backend + Firestore state."""

    def __init__(self):
        self.settings = get_settings()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._latest_lock = asyncio.Lock()
        self._latest_status: Optional[Dict[str, Any]] = None

        self._dynamodb_table = None

    async def start_background_sync(self):
        """Start periodic DynamoDB -> Firestore sync loop."""
        if not self.settings.iot_junction_sync_enabled:
            logger.info("[IOT] Junction sync disabled by config")
            return

        if not (self.settings.iot_dynamodb_table or "").strip():
            logger.info("[IOT] Junction sync not started: IOT_DYNAMODB_TABLE is not configured")
            return

        if self._task and not self._task.done():
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_sync_loop(), name="iot-junction-sync")
        logger.info("[IOT] Junction sync started (interval=%ss)", self.settings.iot_junction_poll_interval_sec)

    async def stop_background_sync(self):
        """Stop periodic sync loop gracefully."""
        if not self._task:
            return

        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("[IOT] Junction sync stopped")

    async def _run_sync_loop(self):
        """Periodic sync task."""
        interval = max(2, int(self.settings.iot_junction_poll_interval_sec))

        while not self._stop_event.is_set():
            try:
                await self.sync_once()
            except Exception as exc:
                logger.warning("[IOT] Background sync error: %s", exc)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def get_latest_status(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Return latest processed status, optionally forcing a fresh fetch."""
        if force_refresh:
            return await self.sync_once()

        async with self._latest_lock:
            if self._latest_status:
                return dict(self._latest_status)

        # Try one fetch if cache is empty.
        status = await self.sync_once()
        if status:
            return status

        # Final fallback: read Firestore cached status.
        cached = await self._load_firestore_latest()
        if not cached:
            return None
        return self._normalize_cached_status(cached)

    def normalize_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Public wrapper used by router to normalize history records."""
        return self._normalize_cached_status(status)

    async def sync_once(self) -> Optional[Dict[str, Any]]:
        """Fetch latest DynamoDB item, map logic, and mirror to Firestore."""
        raw_item = await self._fetch_latest_dynamodb_item()
        if not raw_item:
            cached = await self._load_firestore_latest()
            if cached:
                cached = self._normalize_cached_status(cached)
                async with self._latest_lock:
                    self._latest_status = dict(cached)
            return cached

        status = self._map_item_to_status(raw_item)

        if self.settings.iot_junction_firestore_sync_enabled:
            await self._sync_to_firestore(status)

        async with self._latest_lock:
            self._latest_status = dict(status)

        return status

    async def _fetch_latest_dynamodb_item(self) -> Optional[Dict[str, Any]]:
        """Fetch latest item from DynamoDB using query, then fallback to scan."""
        return await asyncio.to_thread(self._fetch_latest_dynamodb_item_sync)

    def _fetch_latest_dynamodb_item_sync(self) -> Optional[Dict[str, Any]]:
        table = self._get_dynamodb_table()
        if table is None:
            logger.error("[IOT] Cannot fetch DynamoDB data: table not configured or connection failed")
            logger.error("[IOT] Please check AWS credentials and IOT_DYNAMODB_TABLE in your .env file")
            return None

        partition_key = self.settings.iot_dynamodb_junction_key
        sort_key = self.settings.iot_dynamodb_sort_key
        junction_id = self.settings.iot_dynamodb_junction_id

        # Primary path for real schema:
        # - partition key: deviceId
        # - sort key: timestamp
        # - known device id: ESP8266-A4CF12F38
        if partition_key and sort_key and junction_id:
            try:
                from boto3.dynamodb.conditions import Key

                response = table.query(
                    KeyConditionExpression=Key(partition_key).eq(junction_id),
                    ScanIndexForward=False,
                    Limit=1,
                )
                items = response.get("Items", [])
                if items:
                    return items[0]
            except Exception as exc:
                logger.warning("[IOT] DynamoDB query failed, fallback to scan: %s", exc)

        # Fallback: scan table and choose max timestamp item.
        try:
            max_items = max(1, int(self.settings.iot_dynamodb_scan_limit))
            response = table.scan(Limit=max_items)
            items = list(response.get("Items", []))

            while "LastEvaluatedKey" in response and len(items) < max_items:
                remaining = max_items - len(items)
                response = table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    Limit=max(1, remaining),
                )
                items.extend(response.get("Items", []))

            if not items:
                return None

            timestamp_field = self.settings.iot_dynamodb_timestamp_field

            # Prefer configured junction id if present in scanned data.
            if junction_id:
                filtered = [
                    i for i in items
                    if str(i.get(partition_key, "")).strip() == str(junction_id).strip()
                ]
                if filtered:
                    items = filtered

            items.sort(
                key=lambda i: self._timestamp_sort_value(
                    i.get(timestamp_field) or i.get("timestamp") or i.get("created_at")
                ),
                reverse=True,
            )
            return items[0]
        except Exception as exc:
            logger.warning("[IOT] DynamoDB scan failed: %s", exc)
            return None

    def _get_dynamodb_table(self):
        """Lazy-create DynamoDB table handle (boto3)."""
        if self._dynamodb_table is not None:
            return self._dynamodb_table

        table_name = (self.settings.iot_dynamodb_table or "").strip()
        if not table_name:
            logger.error("[IOT] DynamoDB table name not configured. Set IOT_DYNAMODB_TABLE in .env file")
            return None

        try:
            import boto3

            session_kwargs: Dict[str, Any] = {}
            if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
            if self.settings.aws_session_token:
                session_kwargs["aws_session_token"] = self.settings.aws_session_token

            session = boto3.session.Session(**session_kwargs)
            resource = session.resource("dynamodb", region_name=self.settings.aws_region)
            self._dynamodb_table = resource.Table(table_name)
            return self._dynamodb_table
        except Exception as exc:
            logger.warning("[IOT] Failed to initialize DynamoDB client: %s", exc)
            return None

    def _map_item_to_status(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Map real DynamoDB schema into dashboard response shape.

        Real schema:
        - lane1, lane2, lane3, lane4 (vehicle counts)
        - emergency (boolean, applies only to lane1)

        Direction mapping (per source system):
        - lane1 -> south
        - lane2 -> east
        - lane3 -> north
        - lane4 -> west
        """
        lane1_count = max(0, self._as_int(item.get("lane1"), 0))
        lane2_count = max(0, self._as_int(item.get("lane2"), 0))
        lane3_count = max(0, self._as_int(item.get("lane3"), 0))
        lane4_count = max(0, self._as_int(item.get("lane4"), 0))
        emergency_flag = self._as_bool(item.get("emergency"))

        south_density = str(item.get("density1", "EMPTY")).upper()
        east_density = str(item.get("density2", "EMPTY")).upper()
        north_density = str(item.get("density3", "EMPTY")).upper()
        west_density = str(item.get("density4", "EMPTY")).upper()

        emergency_queue = item.get("emergency_queue", [])
        state = self._as_int(item.get("state"), 0)
        rfid_total_reads = self._as_int(item.get("rfid_total_reads"), 0)
        rfid_emergency_detects = self._as_int(item.get("rfid_emergency_detects"), 0)

        counts = {
            "north": lane3_count,
            "south": lane1_count,
            "east": lane2_count,
            "west": lane4_count,
        }
        emergencies = {
            "north": False,
            "south": emergency_flag,
            "east": False,
            "west": False,
        }

        priority_lane, priority_reason = self._select_priority_lane(counts, emergency_flag)
        lights = self._compute_lights(priority_lane, priority_reason)

        source_ts = (
            item.get(self.settings.iot_dynamodb_timestamp_field)
            or item.get("timestamp")
            or item.get("created_at")
        )
        junction_id = str(item.get(self.settings.iot_dynamodb_junction_key) or item.get("device_id") or self.settings.iot_dynamodb_junction_id or "junction_1")

        return self._to_native_value({
            "junction_id": junction_id,
            "north_count": counts["north"],
            "south_count": counts["south"],
            "east_count": counts["east"],
            "west_count": counts["west"],
            "north_density": north_density,
            "south_density": south_density,
            "east_density": east_density,
            "west_density": west_density,
            "emergency_queue": emergency_queue,
            "state": state,
            "rfid_total_reads": rfid_total_reads,
            "rfid_emergency_detects": rfid_emergency_detects,
            "north_emergency": emergencies["north"],
            "south_emergency": emergencies["south"],
            "east_emergency": emergencies["east"],
            "west_emergency": emergencies["west"],
            "north_light": lights["north"],
            "south_light": lights["south"],
            "east_light": lights["east"],
            "west_light": lights["west"],
            "priority_lane": priority_lane,
            "priority_reason": priority_reason,
            "timestamp": source_ts,
            "source": "aws_dynamodb",
            "synced_at": self._to_iso_timestamp(datetime.now(timezone.utc)),
        })

    def _select_priority_lane(
        self,
        counts: Dict[str, int],
        south_emergency: bool,
    ) -> Tuple[str, str]:
        """Priority rules: lane1(south) emergency first, else highest among all lanes."""
        if south_emergency:
            return "south", "emergency"

        # Tie-break follows upstream lane order: lane1(south), lane2(east), lane3(north), lane4(west)
        active_lanes = ("south", "east", "north", "west")
        lane = max(
            active_lanes,
            key=lambda l: (counts.get(l, 0), -active_lanes.index(l)),
        )
        return lane, "highest_vehicle_count"

    def _compute_lights(self, target_lane: str, reason: str) -> Dict[str, str]:
        """Compute deterministic light state for mapped 4-lane input."""
        lights = {lane: "red" for lane in LANE_ORDER}

        if reason == "emergency":
            lights["south"] = "green"
            return lights

        if target_lane not in ("north", "south", "east", "west"):
            target_lane = "south"

        lights[target_lane] = "green"
        return lights

    async def _sync_to_firestore(self, status: Dict[str, Any]):
        """Mirror latest status to Firestore and append optional history."""
        db = get_db()
        safe_status = self._to_native_value(status)
        junction_id = str(safe_status.get("junction_id", "junction_1"))

        await db.collection(Collections.IOT_JUNCTION_STATUS).document(junction_id).set(safe_status)

        if self.settings.iot_junction_history_enabled:
            doc_id = self._history_doc_id(junction_id, str(safe_status.get("timestamp", "")))
            await db.collection(Collections.JUNCTION_HISTORY).document(doc_id).set(safe_status)

    async def _load_firestore_latest(self) -> Optional[Dict[str, Any]]:
        """Load latest mirrored status from Firestore cache."""
        db = get_db()

        preferred_id = (self.settings.iot_dynamodb_junction_id or "").strip()
        if preferred_id:
            doc = await db.collection(Collections.IOT_JUNCTION_STATUS).document(preferred_id).get()
            if doc.exists:
                return doc.to_dict()

        # Fallback to any document if preferred junction does not exist.
        q = db.collection(Collections.IOT_JUNCTION_STATUS).limit(1)
        async for doc in q.stream():
            return doc.to_dict()

        return None

    def _normalize_cached_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Return normalized status in dashboard mapping shape.

        Also supports legacy cached docs and remaps them to:
        lane1->south, lane2->east, lane3->north, lane4->west.
        """
        normalized = dict(status)

        south_count = max(0, self._as_int(normalized.get("south_count", normalized.get("lane1")), 0))
        east_count = max(0, self._as_int(normalized.get("east_count", normalized.get("lane2")), 0))
        north_count = max(0, self._as_int(normalized.get("north_count", normalized.get("lane3")), 0))
        west_count = max(0, self._as_int(normalized.get("west_count", normalized.get("lane4")), 0))
        south_emergency = self._as_bool(normalized.get("south_emergency", normalized.get("emergency")))

        south_density = str(normalized.get("south_density", normalized.get("density1", "EMPTY"))).upper()
        east_density = str(normalized.get("east_density", normalized.get("density2", "EMPTY"))).upper()
        north_density = str(normalized.get("north_density", normalized.get("density3", "EMPTY"))).upper()
        west_density = str(normalized.get("west_density", normalized.get("density4", "EMPTY"))).upper()

        emergency_queue = normalized.get("emergency_queue", [])
        state = self._as_int(normalized.get("state"), 0)
        rfid_total_reads = self._as_int(normalized.get("rfid_total_reads"), 0)
        rfid_emergency_detects = self._as_int(normalized.get("rfid_emergency_detects"), 0)

        counts = {
            "north": north_count,
            "south": south_count,
            "east": east_count,
            "west": west_count,
        }

        priority_lane = str(normalized.get("priority_lane") or "").lower().strip()
        priority_reason = str(normalized.get("priority_reason") or "").lower().strip()
        if priority_lane not in ("north", "south", "east", "west"):
            priority_lane, priority_reason = self._select_priority_lane(counts, south_emergency)
        if priority_reason not in ("emergency", "highest_vehicle_count"):
            priority_reason = "emergency" if south_emergency else "highest_vehicle_count"

        lights = self._compute_lights(priority_lane, priority_reason)
        junction_id = str(
            normalized.get("junction_id")
            or normalized.get(self.settings.iot_dynamodb_junction_key)
            or normalized.get("device_id")
            or self.settings.iot_dynamodb_junction_id
            or "junction_1"
        )

        timestamp_value = normalized.get(
            "timestamp",
            normalized.get(self.settings.iot_dynamodb_timestamp_field, normalized.get("created_at")),
        )
        if timestamp_value is None:
            timestamp_value = self._to_iso_timestamp(datetime.now(timezone.utc))

        return self._to_native_value({
            "junction_id": junction_id,
            "north_count": north_count,
            "south_count": south_count,
            "east_count": east_count,
            "west_count": west_count,
            "north_density": north_density,
            "south_density": south_density,
            "east_density": east_density,
            "west_density": west_density,
            "emergency_queue": emergency_queue,
            "state": state,
            "rfid_total_reads": rfid_total_reads,
            "rfid_emergency_detects": rfid_emergency_detects,
            "north_emergency": False,
            "south_emergency": south_emergency,
            "east_emergency": False,
            "west_emergency": False,
            "north_light": lights["north"],
            "south_light": lights["south"],
            "east_light": lights["east"],
            "west_light": lights["west"],
            "priority_lane": priority_lane,
            "priority_reason": priority_reason,
            "timestamp": timestamp_value,
            "source": str(normalized.get("source") or "firestore_cache"),
            "synced_at": str(normalized.get("synced_at") or self._to_iso_timestamp(datetime.now(timezone.utc))),
        })

    @staticmethod
    def _history_doc_id(junction_id: str, timestamp: str) -> str:
        raw = f"{junction_id}_{timestamp or 'no_ts'}"
        safe = []
        for ch in raw:
            safe.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
        return "".join(safe)[:240]

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float, Decimal)):
            return int(value)
        try:
            return int(str(value).strip())
        except Exception:
            return default

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            return bool(int(value))
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _to_native_value(value: Any) -> Any:
        """Convert DynamoDB/SDK values (e.g. Decimal) into JSON/Firestore-safe types."""
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        if isinstance(value, dict):
            return {str(k): IotJunctionService._to_native_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [IotJunctionService._to_native_value(v) for v in value]
        return value

    @staticmethod
    def _timestamp_sort_value(raw: Any) -> float:
        if isinstance(raw, datetime):
            dt = raw
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()

        if isinstance(raw, (int, float, Decimal)):
            return float(raw)

        if raw is None:
            return 0.0

        text = str(raw).strip()
        if not text:
            return 0.0

        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return 0.0

    @staticmethod
    def _to_iso_timestamp(raw: Any) -> str:
        if isinstance(raw, datetime):
            dt = raw
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        if isinstance(raw, (int, float, Decimal)):
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")

        if raw is None:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        text = str(raw).strip()
        if not text:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return text


@lru_cache()
def get_iot_junction_service() -> IotJunctionService:
    """Return singleton IoT junction service instance."""
    return IotJunctionService()
