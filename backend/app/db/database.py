"""
Simple SQLite database helper using aiosqlite for async access.
Creates tables for `zones`, `violations`, and `drivers` and provides helper CRUD functions.
"""
import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

import aiosqlite

from app.config import get_settings
from app.parking.parking_detector import ParkingZone, ParkingViolation, ZoneType

settings = get_settings()

DB_SCHEMA = {
    "zones": (
        "CREATE TABLE IF NOT EXISTS zones ("
        "zone_id TEXT PRIMARY KEY,"
        "name TEXT,"
        "polygon TEXT,"
        "zone_type TEXT,"
        "max_duration_sec REAL,"
        "color TEXT,"
        "active INTEGER"
        ")"
    ),
    "violations": (
        "CREATE TABLE IF NOT EXISTS violations ("
        "violation_id TEXT PRIMARY KEY,"
        "track_id INTEGER,"
        "zone_id TEXT,"
        "zone_name TEXT,"
        "zone_type TEXT,"
        "start_time REAL,"
        "end_time REAL,"
        "duration_sec REAL,"
        "license_plate TEXT,"
        "snapshot_path TEXT,"
        "fine_amount REAL,"
        "status TEXT"
        ")"
    ),
    "drivers": (
        "CREATE TABLE IF NOT EXISTS drivers ("
        "driver_id TEXT PRIMARY KEY,"
        "current_score INTEGER DEFAULT 100,"
        "total_violations INTEGER DEFAULT 0,"
        "total_fines REAL DEFAULT 0.0,"
        "created_at REAL,"
        "updated_at REAL"
        ")"
    ),
    "driver_violations": (
        "CREATE TABLE IF NOT EXISTS driver_violations ("
        "violation_id TEXT PRIMARY KEY,"
        "driver_id TEXT,"
        "violation_type TEXT,"
        "timestamp REAL,"
        "location TEXT,"
        "points_deducted INTEGER,"
        "fine_amount REAL,"
        "license_plate TEXT,"
        "snapshot_path TEXT,"
        "notes TEXT,"
        "FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)"
        ")"
    ),
    "parking_zones": (
        "CREATE TABLE IF NOT EXISTS parking_zones ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "zone_type TEXT NOT NULL,"  # 'red' (no parking) or 'yellow' (loading)
        "coordinates TEXT NOT NULL,"  # JSON string: [[x1,y1], [x2,y2], ...]
        "label TEXT,"
        "active INTEGER DEFAULT 1,"
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    ),
    "audit_logs": (
        "CREATE TABLE IF NOT EXISTS audit_logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "admin_username TEXT NOT NULL,"
        "action TEXT NOT NULL,"
        "details TEXT,"
        "timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    ),
}



async def init_db(db_path: Optional[str] = None):
    """Initialize the SQLite DB and create required tables."""
    if db_path is None:
        db_path = str(settings.db_path)
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # Enable foreign keys (future tables may use them)
        await db.execute("PRAGMA foreign_keys = ON;")
        for name, sql in DB_SCHEMA.items():
            await db.execute(sql)
        await db.commit()


# --------------------- Zones ---------------------
async def insert_zone(zone: ParkingZone, db_path: Optional[str] = None):
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO zones (zone_id, name, polygon, zone_type, max_duration_sec, color, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                zone.zone_id,
                zone.name,
                json.dumps(zone.polygon),
                zone.zone_type.value,
                zone.max_duration_sec,
                json.dumps(list(zone.color)),
                1 if zone.active else 0,
            ),
        )
        await db.commit()


async def list_zones(db_path: Optional[str] = None) -> List[ParkingZone]:
    if db_path is None:
        db_path = str(settings.db_path)
    zones = []
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT zone_id, name, polygon, zone_type, max_duration_sec, color, active FROM zones") as cursor:
            async for row in cursor:
                zone_id, name, polygon_json, zone_type, max_duration_sec, color_json, active = row
                polygon = json.loads(polygon_json)
                color = tuple(json.loads(color_json))
                # Convert zone_type string to ZoneType enum if possible
                try:
                    zt = ZoneType(zone_type)
                except Exception:
                    zt = ZoneType.NO_PARKING
                zones.append(
                    ParkingZone(
                        zone_id=zone_id,
                        name=name,
                        polygon=[tuple(p) for p in polygon],
                        zone_type=zt,
                        max_duration_sec=max_duration_sec,
                        color=color,
                        active=bool(active),
                    )
                )
    return zones


async def delete_zone(zone_id: str, db_path: Optional[str] = None) -> bool:
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
        await db.commit()
        return True


# --------------------- Violations ---------------------
async def insert_violation(v: ParkingViolation, db_path: Optional[str] = None):
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO violations (violation_id, track_id, zone_id, zone_name, zone_type, start_time, end_time, duration_sec, license_plate, snapshot_path, fine_amount, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                v.violation_id,
                v.track_id,
                v.zone_id,
                v.zone_name,
                v.zone_type.value if v.zone_type else None,
                v.start_time,
                v.end_time,
                v.duration_sec,
                v.license_plate,
                v.snapshot_path,
                v.fine_amount,
                v.status,
            ),
        )
        await db.commit()


async def list_violations(limit: int = 100, db_path: Optional[str] = None) -> List[ParkingViolation]:
    if db_path is None:
        db_path = str(settings.db_path)
    violations: List[ParkingViolation] = []
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT violation_id, track_id, zone_id, zone_name, zone_type, start_time, end_time, duration_sec, license_plate, snapshot_path, fine_amount, status FROM violations ORDER BY start_time DESC LIMIT ?", (limit,)) as cursor:
            async for row in cursor:
                violation_id, track_id, zone_id, zone_name, zone_type, start_time, end_time, duration_sec, license_plate, snapshot_path, fine_amount, status = row
                try:
                    zt = ZoneType(zone_type) if zone_type else None
                except Exception:
                    zt = None
                violations.append(
                    ParkingViolation(
                        violation_id=violation_id,
                        track_id=track_id,
                        zone_id=zone_id,
                        zone_name=zone_name,
                        zone_type=zt,
                        start_time=float(start_time) if start_time else None,
                        end_time=float(end_time) if end_time else None,
                        duration_sec=float(duration_sec) if duration_sec else 0.0,
                        license_plate=license_plate,
                        snapshot_path=snapshot_path,
                        fine_amount=float(fine_amount) if fine_amount else 0.0,
                        status=status,
                    )
                )
    return violations


async def get_violation(violation_id: str, db_path: Optional[str] = None) -> Optional[ParkingViolation]:
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT violation_id, track_id, zone_id, zone_name, zone_type, start_time, end_time, duration_sec, license_plate, snapshot_path, fine_amount, status FROM violations WHERE violation_id = ?", (violation_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            violation_id, track_id, zone_id, zone_name, zone_type, start_time, end_time, duration_sec, license_plate, snapshot_path, fine_amount, status = row
            try:
                zt = ZoneType(zone_type) if zone_type else None
            except Exception:
                zt = None
            return ParkingViolation(
                violation_id=violation_id,
                track_id=track_id,
                zone_id=zone_id,
                zone_name=zone_name,
                zone_type=zt,
                start_time=float(start_time) if start_time else None,
                end_time=float(end_time) if end_time else None,
                duration_sec=float(duration_sec) if duration_sec else 0.0,
                license_plate=license_plate,
                snapshot_path=snapshot_path,
                fine_amount=float(fine_amount) if fine_amount else 0.0,
                status=status,
            )


async def update_violation_status(violation_id: str, status: str = "resolved", end_time: float = None, db_path: Optional[str] = None):
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE violations SET status = ?, end_time = ? WHERE violation_id = ?",
            (status, end_time, violation_id),
        )
        await db.commit()


# --------------------- Drivers ---------------------
async def insert_driver(driver_id: str, current_score: int = 100, total_violations: int = 0,
                        total_fines: float = 0.0, created_at: float = None, updated_at: float = None,
                        db_path: Optional[str] = None):
    """Insert or update a driver record."""
    import time
    if db_path is None:
        db_path = str(settings.db_path)
    now = time.time()
    if created_at is None:
        created_at = now
    if updated_at is None:
        updated_at = now
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO drivers (driver_id, current_score, total_violations, total_fines, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (driver_id, current_score, total_violations, total_fines, created_at, updated_at),
        )
        await db.commit()


async def get_driver(driver_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a driver by ID."""
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT driver_id, current_score, total_violations, total_fines, created_at, updated_at FROM drivers WHERE driver_id = ?",
            (driver_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "driver_id": row[0],
                "current_score": row[1],
                "total_violations": row[2],
                "total_fines": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }


async def list_drivers(limit: int = 100, order_by: str = "current_score", ascending: bool = False,
                       db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all drivers with optional sorting."""
    if db_path is None:
        db_path = str(settings.db_path)
    order = "ASC" if ascending else "DESC"
    # Validate order_by to prevent SQL injection
    allowed_columns = {"current_score", "total_violations", "total_fines", "created_at", "updated_at", "driver_id"}
    if order_by not in allowed_columns:
        order_by = "current_score"
    
    drivers = []
    async with aiosqlite.connect(db_path) as db:
        query = f"SELECT driver_id, current_score, total_violations, total_fines, created_at, updated_at FROM drivers ORDER BY {order_by} {order} LIMIT ?"
        async with db.execute(query, (limit,)) as cursor:
            async for row in cursor:
                drivers.append({
                    "driver_id": row[0],
                    "current_score": row[1],
                    "total_violations": row[2],
                    "total_fines": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                })
    return drivers


async def update_driver_score(driver_id: str, current_score: int, total_violations: int,
                              total_fines: float, db_path: Optional[str] = None):
    """Update driver score and violation stats."""
    import time
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE drivers SET current_score = ?, total_violations = ?, total_fines = ?, updated_at = ? WHERE driver_id = ?",
            (current_score, total_violations, total_fines, time.time(), driver_id),
        )
        await db.commit()


async def delete_driver(driver_id: str, db_path: Optional[str] = None) -> bool:
    """Delete a driver and their violation records."""
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM driver_violations WHERE driver_id = ?", (driver_id,))
        await db.execute("DELETE FROM drivers WHERE driver_id = ?", (driver_id,))
        await db.commit()
        return True


async def get_driver_count(db_path: Optional[str] = None) -> int:
    """Get total count of drivers."""
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM drivers") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# --------------------- Driver Violations ---------------------
async def insert_driver_violation(violation_id: str, driver_id: str, violation_type: str,
                                   timestamp: float, location: str = None, points_deducted: int = 0,
                                   fine_amount: float = 0.0, license_plate: str = None,
                                   snapshot_path: str = None, notes: str = "",
                                   db_path: Optional[str] = None):
    """Insert a driver violation record."""
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO driver_violations (violation_id, driver_id, violation_type, timestamp, location, points_deducted, fine_amount, license_plate, snapshot_path, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (violation_id, driver_id, violation_type, timestamp, location, points_deducted, fine_amount, license_plate, snapshot_path, notes),
        )
        await db.commit()


async def list_driver_violations(driver_id: str, limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List violations for a specific driver."""
    if db_path is None:
        db_path = str(settings.db_path)
    violations = []
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT violation_id, driver_id, violation_type, timestamp, location, points_deducted, fine_amount, license_plate, snapshot_path, notes FROM driver_violations WHERE driver_id = ? ORDER BY timestamp DESC LIMIT ?",
            (driver_id, limit)
        ) as cursor:
            async for row in cursor:
                violations.append({
                    "violation_id": row[0],
                    "driver_id": row[1],
                    "violation_type": row[2],
                    "timestamp": row[3],
                    "location": row[4],
                    "points_deducted": row[5],
                    "fine_amount": row[6],
                    "license_plate": row[7],
                    "snapshot_path": row[8],
                    "notes": row[9],
                })
    return violations


async def get_driver_statistics(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Get overall driver statistics."""
    if db_path is None:
        db_path = str(settings.db_path)
    async with aiosqlite.connect(db_path) as db:
        # Total drivers
        async with db.execute("SELECT COUNT(*) FROM drivers") as cursor:
            total_drivers = (await cursor.fetchone())[0]
        
        if total_drivers == 0:
            return {
                "total_drivers": 0,
                "average_score": 0,
                "total_violations": 0,
                "total_fines": 0,
                "high_risk_count": 0,
            }
        
        # Aggregates
        async with db.execute("SELECT AVG(current_score), SUM(total_violations), SUM(total_fines), MIN(current_score), MAX(current_score) FROM drivers") as cursor:
            row = await cursor.fetchone()
            avg_score = row[0] or 0
            total_violations = row[1] or 0
            total_fines = row[2] or 0
            min_score = row[3] or 0
            max_score = row[4] or 0
        
        # High-risk count (score < 50)
        async with db.execute("SELECT COUNT(*) FROM drivers WHERE current_score < 50") as cursor:
            high_risk = (await cursor.fetchone())[0]
        
        # Risk distribution
        async with db.execute("""
            SELECT 
                SUM(CASE WHEN current_score >= 90 THEN 1 ELSE 0 END) as excellent,
                SUM(CASE WHEN current_score >= 70 AND current_score < 90 THEN 1 ELSE 0 END) as good,
                SUM(CASE WHEN current_score >= 50 AND current_score < 70 THEN 1 ELSE 0 END) as fair,
                SUM(CASE WHEN current_score >= 30 AND current_score < 50 THEN 1 ELSE 0 END) as poor,
                SUM(CASE WHEN current_score < 30 THEN 1 ELSE 0 END) as critical
            FROM drivers
        """) as cursor:
            dist = await cursor.fetchone()
        
        return {
            "total_drivers": total_drivers,
            "average_score": round(avg_score, 1),
            "min_score": min_score,
            "max_score": max_score,
            "total_violations": total_violations,
            "total_fines": round(total_fines, 2),
            "high_risk_count": high_risk,
            "risk_distribution": {
                "excellent": dist[0] or 0,
                "good": dist[1] or 0,
                "fair": dist[2] or 0,
                "poor": dist[3] or 0,
                "critical": dist[4] or 0,
            }
        }



# A helper to run a coroutine in case it's called from sync callback
def schedule_coroutine(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        loop.create_task(coro)
    else:
        # If not running, schedule on a new event loop
        asyncio.run(coro)


__all__ = [
    "init_db",
    "insert_zone",
    "list_zones",
    "delete_zone",
    "insert_violation",
    "list_violations",
    "get_violation",
    "update_violation_status",
    "insert_driver",
    "get_driver",
    "list_drivers",
    "update_driver_score",
    "delete_driver",
    "get_driver_count",
    "insert_driver_violation",
    "list_driver_violations",
    "get_driver_statistics",
    "schedule_coroutine",
]
