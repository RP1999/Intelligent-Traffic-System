"""
Firestore database helper – async CRUD functions.
Drop-in replacement for the old SQLite-based database.py.
All functions keep the same signatures so existing callers need zero changes.
"""
import asyncio
import json
import time
from typing import List, Dict, Any, Optional

from google.cloud.firestore_v1 import FieldFilter

from app.db.firestore_client import get_db, Collections
from app.parking.parking_detector import ParkingZone, ParkingViolation, ZoneType


# ---------------------------------------------------------------------------
# Initialisation (no-op – Firestore collections auto-create)
# ---------------------------------------------------------------------------

async def init_db(db_path: Optional[str] = None):
    """Verify Firestore connectivity. Collections are created on first write."""
    _ = get_db()
    print("✅ Firestore connection verified")


# --------------------- Zones ---------------------

async def insert_zone(zone: ParkingZone, db_path: Optional[str] = None):
    db = get_db()
    await db.collection(Collections.ZONES).document(zone.zone_id).set({
        "zone_id": zone.zone_id,
        "name": zone.name,
        "polygon": json.dumps(zone.polygon),
        "zone_type": zone.zone_type.value,
        "max_duration_sec": zone.max_duration_sec,
        "color": json.dumps(list(zone.color)),
        "active": zone.active,
    })


async def list_zones(db_path: Optional[str] = None) -> List[ParkingZone]:
    db = get_db()
    zones: List[ParkingZone] = []
    async for doc in db.collection(Collections.ZONES).stream():
        d = doc.to_dict()
        polygon = json.loads(d.get("polygon", "[]"))
        color = tuple(json.loads(d.get("color", "[0,255,0]")))
        try:
            zt = ZoneType(d.get("zone_type"))
        except Exception:
            zt = ZoneType.NO_PARKING
        zones.append(ParkingZone(
            zone_id=d["zone_id"],
            name=d.get("name", ""),
            polygon=[tuple(p) for p in polygon],
            zone_type=zt,
            max_duration_sec=d.get("max_duration_sec", 0),
            color=color,
            active=d.get("active", True),
        ))
    return zones


async def delete_zone(zone_id: str, db_path: Optional[str] = None) -> bool:
    db = get_db()
    await db.collection(Collections.ZONES).document(zone_id).delete()
    return True


# --------------------- Violations ---------------------

async def insert_violation(v: ParkingViolation, db_path: Optional[str] = None):
    db = get_db()
    await db.collection(Collections.VIOLATIONS).document(v.violation_id).set({
        "violation_id": v.violation_id,
        "track_id": v.track_id,
        "zone_id": v.zone_id,
        "zone_name": v.zone_name,
        "zone_type": v.zone_type.value if v.zone_type else None,
        "start_time": v.start_time,
        "end_time": v.end_time,
        "duration_sec": v.duration_sec,
        "license_plate": v.license_plate,
        "snapshot_path": v.snapshot_path,
        "fine_amount": v.fine_amount,
        "status": v.status,
    })


async def list_violations(limit: int = 100, db_path: Optional[str] = None) -> List[ParkingViolation]:
    db = get_db()
    violations: List[ParkingViolation] = []
    query = (
        db.collection(Collections.VIOLATIONS)
        .order_by("start_time", direction="DESCENDING")
        .limit(limit)
    )
    async for doc in query.stream():
        d = doc.to_dict()
        try:
            zt = ZoneType(d["zone_type"]) if d.get("zone_type") else None
        except Exception:
            zt = None
        violations.append(ParkingViolation(
            violation_id=d["violation_id"],
            track_id=d.get("track_id"),
            zone_id=d.get("zone_id"),
            zone_name=d.get("zone_name"),
            zone_type=zt,
            start_time=float(d["start_time"]) if d.get("start_time") else None,
            end_time=float(d["end_time"]) if d.get("end_time") else None,
            duration_sec=float(d.get("duration_sec", 0)),
            license_plate=d.get("license_plate"),
            snapshot_path=d.get("snapshot_path"),
            fine_amount=float(d.get("fine_amount", 0)),
            status=d.get("status"),
        ))
    return violations


async def get_violation(violation_id: str, db_path: Optional[str] = None) -> Optional[ParkingViolation]:
    db = get_db()
    doc = await db.collection(Collections.VIOLATIONS).document(violation_id).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    try:
        zt = ZoneType(d["zone_type"]) if d.get("zone_type") else None
    except Exception:
        zt = None
    return ParkingViolation(
        violation_id=d["violation_id"],
        track_id=d.get("track_id"),
        zone_id=d.get("zone_id"),
        zone_name=d.get("zone_name"),
        zone_type=zt,
        start_time=float(d["start_time"]) if d.get("start_time") else None,
        end_time=float(d["end_time"]) if d.get("end_time") else None,
        duration_sec=float(d.get("duration_sec", 0)),
        license_plate=d.get("license_plate"),
        snapshot_path=d.get("snapshot_path"),
        fine_amount=float(d.get("fine_amount", 0)),
        status=d.get("status"),
    )


async def update_violation_status(violation_id: str, status: str = "resolved",
                                  end_time: float = None, db_path: Optional[str] = None):
    db = get_db()
    update: Dict[str, Any] = {"status": status}
    if end_time is not None:
        update["end_time"] = end_time
    await db.collection(Collections.VIOLATIONS).document(violation_id).update(update)


# --------------------- Drivers ---------------------

async def insert_driver(driver_id: str, current_score: int = 100, total_violations: int = 0,
                        total_fines: float = 0.0, created_at: float = None,
                        updated_at: float = None, db_path: Optional[str] = None):
    """Insert or update a driver record."""
    db = get_db()
    now = time.time()
    await db.collection(Collections.DRIVERS).document(driver_id).set({
        "driver_id": driver_id,
        "current_score": current_score,
        "total_violations": total_violations,
        "total_fines": total_fines,
        "created_at": created_at or now,
        "updated_at": updated_at or now,
    })


async def get_driver(driver_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a driver by ID."""
    db = get_db()
    doc = await db.collection(Collections.DRIVERS).document(driver_id).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    return {
        "driver_id": d.get("driver_id", doc.id),
        "current_score": d.get("current_score", 100),
        "total_violations": d.get("total_violations", 0),
        "total_fines": d.get("total_fines", 0.0),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


async def list_drivers(limit: int = 100, order_by: str = "current_score",
                       ascending: bool = False, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all drivers with optional sorting."""
    db = get_db()
    allowed = {"current_score", "total_violations", "total_fines", "created_at", "updated_at", "driver_id"}
    if order_by not in allowed:
        order_by = "current_score"
    direction = "ASCENDING" if ascending else "DESCENDING"
    query = (
        db.collection(Collections.DRIVERS)
        .order_by(order_by, direction=direction)
        .limit(limit)
    )
    drivers: List[Dict[str, Any]] = []
    async for doc in query.stream():
        d = doc.to_dict()
        drivers.append({
            "driver_id": d.get("driver_id", doc.id),
            "current_score": d.get("current_score", 100),
            "total_violations": d.get("total_violations", 0),
            "total_fines": d.get("total_fines", 0.0),
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        })
    return drivers


async def update_driver_score(driver_id: str, current_score: int, total_violations: int,
                              total_fines: float, db_path: Optional[str] = None):
    """Update driver score and violation stats."""
    db = get_db()
    await db.collection(Collections.DRIVERS).document(driver_id).update({
        "current_score": current_score,
        "total_violations": total_violations,
        "total_fines": total_fines,
        "updated_at": time.time(),
    })


async def delete_driver(driver_id: str, db_path: Optional[str] = None) -> bool:
    """Delete a driver and their violation records."""
    db = get_db()
    # Delete driver violations first
    viol_query = (
        db.collection(Collections.DRIVER_VIOLATIONS)
        .where(filter=FieldFilter("driver_id", "==", driver_id))
    )
    async for doc in viol_query.stream():
        await doc.reference.delete()
    await db.collection(Collections.DRIVERS).document(driver_id).delete()
    return True


async def get_driver_count(db_path: Optional[str] = None) -> int:
    """Get total count of drivers."""
    db = get_db()
    count = 0
    async for _ in db.collection(Collections.DRIVERS).select([]).stream():
        count += 1
    return count


# --------------------- Driver Violations ---------------------

async def insert_driver_violation(violation_id: str, driver_id: str, violation_type: str,
                                  timestamp: float, location: str = None, points_deducted: int = 0,
                                  fine_amount: float = 0.0, license_plate: str = None,
                                  snapshot_path: str = None, notes: str = "",
                                  db_path: Optional[str] = None):
    """Insert a driver violation record."""
    db = get_db()
    await db.collection(Collections.DRIVER_VIOLATIONS).document(violation_id).set({
        "violation_id": violation_id,
        "driver_id": driver_id,
        "violation_type": violation_type,
        "timestamp": timestamp,
        "location": location,
        "points_deducted": points_deducted,
        "fine_amount": fine_amount,
        "license_plate": license_plate,
        "snapshot_path": snapshot_path,
        "notes": notes,
    })


async def list_driver_violations(driver_id: str, limit: int = 50,
                                 db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List violations for a specific driver."""
    db = get_db()
    query = (
        db.collection(Collections.DRIVER_VIOLATIONS)
        .where(filter=FieldFilter("driver_id", "==", driver_id))
        .order_by("timestamp", direction="DESCENDING")
        .limit(limit)
    )
    violations: List[Dict[str, Any]] = []
    async for doc in query.stream():
        d = doc.to_dict()
        violations.append({
            "violation_id": d.get("violation_id", doc.id),
            "driver_id": d.get("driver_id"),
            "violation_type": d.get("violation_type"),
            "timestamp": d.get("timestamp"),
            "location": d.get("location"),
            "points_deducted": d.get("points_deducted", 0),
            "fine_amount": d.get("fine_amount", 0),
            "license_plate": d.get("license_plate"),
            "snapshot_path": d.get("snapshot_path"),
            "notes": d.get("notes"),
        })
    return violations


# --------------------- Driver Statistics ---------------------

async def get_driver_statistics(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Get overall driver statistics."""
    db = get_db()
    drivers_data: List[Dict[str, Any]] = []
    async for doc in db.collection(Collections.DRIVERS).stream():
        drivers_data.append(doc.to_dict())

    total_drivers = len(drivers_data)
    if total_drivers == 0:
        return {
            "total_drivers": 0, "average_score": 0, "total_violations": 0,
            "total_fines": 0, "high_risk_count": 0,
        }

    scores = [d.get("current_score", 100) for d in drivers_data]
    avg_score = sum(scores) / total_drivers
    total_violations = sum(d.get("total_violations", 0) for d in drivers_data)
    total_fines = sum(d.get("total_fines", 0) for d in drivers_data)
    high_risk = sum(1 for s in scores if s < 50)

    dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "critical": 0}
    for s in scores:
        if s >= 90:
            dist["excellent"] += 1
        elif s >= 70:
            dist["good"] += 1
        elif s >= 50:
            dist["fair"] += 1
        elif s >= 30:
            dist["poor"] += 1
        else:
            dist["critical"] += 1

    return {
        "total_drivers": total_drivers,
        "average_score": round(avg_score, 1),
        "min_score": min(scores),
        "max_score": max(scores),
        "total_violations": total_violations,
        "total_fines": round(total_fines, 2),
        "high_risk_count": high_risk,
        "risk_distribution": dist,
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def schedule_coroutine(coro):
    """Run a coroutine from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        loop.create_task(coro)
    else:
        asyncio.run(coro)


__all__ = [
    "init_db",
    "insert_zone", "list_zones", "delete_zone",
    "insert_violation", "list_violations", "get_violation", "update_violation_status",
    "insert_driver", "get_driver", "list_drivers", "update_driver_score",
    "delete_driver", "get_driver_count",
    "insert_driver_violation", "list_driver_violations",
    "get_driver_statistics",
    "schedule_coroutine",
]
