"""
IoT Junction Integration Router

Admin-protected endpoints for AWS DynamoDB -> Firestore synced 4-way junction data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.firestore_client import Collections, get_db
from app.routers.auth import UserInfo, get_current_admin
from app.services.iot_junction_service import get_iot_junction_service

router = APIRouter(prefix="/admin/iot/junction", tags=["IoT Junction Integration"])


class IotJunctionStatusResponse(BaseModel):
    junction_id: str

    north_count: int = Field(ge=0)
    south_count: int = Field(ge=0)
    east_count: int = Field(ge=0)
    west_count: int = Field(ge=0)

    north_density: str = "EMPTY"
    south_density: str = "EMPTY"
    east_density: str = "EMPTY"
    west_density: str = "EMPTY"

    north_emergency: bool
    south_emergency: bool
    east_emergency: bool
    west_emergency: bool

    north_light: str
    south_light: str
    east_light: str
    west_light: str

    priority_lane: str
    priority_reason: str

    emergency_queue: list = []
    state: int = 0
    rfid_total_reads: int = 0
    rfid_emergency_detects: int = 0

    timestamp: Any
    source: str
    synced_at: str


def _history_sort_value(doc: dict) -> float:
    """Sort helper that handles DynamoDB numeric timestamp and ISO strings."""
    raw = doc.get("timestamp")
    if isinstance(raw, (int, float, Decimal)):
        return float(raw)

    if isinstance(raw, datetime):
        return raw.timestamp()

    text = str(raw or "").strip()
    if not text:
        synced_text = str(doc.get("synced_at") or "").strip()
        if not synced_text:
            return 0.0
        try:
            synced_dt = datetime.fromisoformat(synced_text.replace("Z", "+00:00"))
            return synced_dt.timestamp()
        except ValueError:
            return 0.0

    try:
        return float(text)
    except ValueError:
        pass

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return 0.0


@router.get("/latest", response_model=IotJunctionStatusResponse, summary="Get latest IoT junction status")
async def get_latest_iot_junction_status(
    force_refresh: bool = Query(default=False, description="Fetch immediately from DynamoDB before returning"),
    user: UserInfo = Depends(get_current_admin),
):
    service = get_iot_junction_service()
    status = await service.get_latest_status(force_refresh=force_refresh)
    if not status:
        raise HTTPException(
            status_code=503, 
            detail="No IoT junction data available. Please check AWS DynamoDB configuration in backend .env file."
        )
    return status


@router.post("/sync", response_model=IotJunctionStatusResponse, summary="Trigger manual IoT sync")
async def sync_iot_junction_now(user: UserInfo = Depends(get_current_admin)):
    service = get_iot_junction_service()
    status = await service.sync_once()
    if not status:
        raise HTTPException(
            status_code=503, 
            detail="Unable to sync IoT data from DynamoDB. Please check AWS configuration and table name."
        )
    return status


@router.get("/history", summary="Get recent IoT junction history")
async def get_iot_junction_history(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserInfo = Depends(get_current_admin),
):
    db = get_db()
    service = get_iot_junction_service()
    docs = []

    # Pull recent records and sort in Python to avoid strict index dependencies.
    q = db.collection(Collections.JUNCTION_HISTORY).limit(min(limit * 3, 500))
    async for doc in q.stream():
        docs.append(service.normalize_status(doc.to_dict() or {}))

    docs.sort(key=_history_sort_value, reverse=True)
    docs = docs[:limit]

    return {
        "items": docs,
        "count": len(docs),
    }
