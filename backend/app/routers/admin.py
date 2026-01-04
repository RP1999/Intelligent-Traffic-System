"""
Admin API Router - Protected endpoints for admin dashboard
Requires JWT authentication with admin role.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
import aiosqlite

from app.config import get_settings
from app.routers.auth import get_current_admin, UserInfo
from app.fuzzy.traffic_controller import get_four_way_controller

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# Database path
DB_PATH = settings.db_path


# =============================================================================
# VIDEO SNAPSHOT FOR ZONE EDITOR
# =============================================================================

@router.get("/video/snapshot", summary="Get video snapshot for zone editor")
async def get_admin_video_snapshot(user: UserInfo = Depends(get_current_admin)):
    """
    Get a CLEAN snapshot from the video feed for the Zone Editor.
    This returns a frame WITHOUT detection boxes or zone overlays.
    Lazy-starts the video worker if not already running.
    """
    # Import here to avoid circular imports
    from app.routers.video import _video_state, start_video_worker
    
    # Lazy start: Start worker if not running
    if not _video_state.running:
        start_video_worker()
        # Wait up to 15 seconds for first frame (YOLO models take time to load)
        for _ in range(150):  # Max 15 seconds (model loading can take 5-10s)
            await asyncio.sleep(0.1)
            if _video_state.get_snapshot() is not None:
                break
    
    snapshot = _video_state.get_snapshot()
    
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No snapshot available yet. Video stream starting...")
    
    return Response(
        content=snapshot,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
    )


@router.post("/video/snapshot/refresh", summary="Refresh zone editor snapshot")
async def refresh_admin_video_snapshot(user: UserInfo = Depends(get_current_admin)):
    """
    Request a fresh clean snapshot for Zone Editor.
    Captures the next video frame as a clean image without any overlays.
    """
    from app.routers.video import _video_state
    
    _video_state.request_new_snapshot()
    
    # Wait for new snapshot (max 2 seconds)
    for _ in range(20):
        await asyncio.sleep(0.1)
        if _video_state.raw_frame_captured:
            break
    
    return {"status": "refreshed", "message": "New clean snapshot captured"}


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class DashboardStats(BaseModel):
    violations_today: int
    violations_this_week: int
    average_risk_score: float
    current_traffic_level: str
    active_junctions: int
    total_vehicles_today: int
    pending_fines: float
    emergency_mode: bool


class ViolationDetail(BaseModel):
    violation_id: str
    driver_id: str
    license_plate: Optional[str]
    violation_type: str
    timestamp: str
    location: Optional[str]
    fine_amount: float
    points_deducted: int
    evidence_path: Optional[str]
    notes: Optional[str]


class DriverSummary(BaseModel):
    driver_id: str
    current_score: int
    total_violations: int
    total_fines: float
    last_violation: Optional[str]


class EmergencyResponse(BaseModel):
    status: str
    message: str
    affected_junctions: List[str]
    timestamp: str


# =============================================================================
# DASHBOARD STATISTICS
# =============================================================================

@router.get("/dashboard/stats", response_model=DashboardStats, summary="Get dashboard statistics")
async def get_dashboard_stats(user: UserInfo = Depends(get_current_admin)):
    """
    Get comprehensive dashboard statistics including:
    - Violations count (today and week)
    - Average risk score across all drivers
    - Traffic level estimation
    - Active junction count
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Violations today (timestamp is REAL unix epoch)
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM driver_violations WHERE date(timestamp, 'unixepoch', 'localtime') >= ?",
            (today,)
        )
        violations_today = (await cursor.fetchone())["count"]
        
        # Violations this week
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM driver_violations WHERE date(timestamp, 'unixepoch', 'localtime') >= ?",
            (week_ago,)
        )
        violations_week = (await cursor.fetchone())["count"]
        
        # Average risk score (from drivers table)
        cursor = await db.execute(
            "SELECT AVG(current_score) as avg_score FROM drivers"
        )
        avg_score_row = await cursor.fetchone()
        avg_score = avg_score_row["avg_score"] if avg_score_row["avg_score"] else 100.0
        
        # Get junction safety score (kept as is)
        cursor = await db.execute(
            """SELECT name FROM sqlite_master 
               WHERE type='table' AND name='junction_safety'"""
        )
        junction_table_exists = await cursor.fetchone()
        
        traffic_level = "normal"
        current_risk = 50.0
        
        if junction_table_exists:
            cursor = await db.execute(
                """SELECT safety_score FROM junction_safety 
                   ORDER BY updated_at DESC LIMIT 1"""
            )
            junction = await cursor.fetchone()
            if junction:
                current_risk = 100 - junction["safety_score"]
                if current_risk > 70:
                    traffic_level = "high"
                elif current_risk > 40:
                    traffic_level = "moderate"
                else:
                    traffic_level = "low"
        
        # Count pending fines
        cursor = await db.execute(
            "SELECT SUM(fine_amount) as total FROM driver_violations WHERE fine_amount > 0"
        )
        pending_fines_row = await cursor.fetchone()
        pending_fines = pending_fines_row["total"] if pending_fines_row["total"] else 0.0
        
        # Check emergency mode (kept as is)
        cursor = await db.execute(
            """SELECT name FROM sqlite_master 
               WHERE type='table' AND name='emergency_status'"""
        )
        emergency_table_exists = await cursor.fetchone()
        emergency_mode = False
        
        if emergency_table_exists:
            cursor = await db.execute(
                "SELECT active FROM emergency_status ORDER BY id DESC LIMIT 1"
            )
            status = await cursor.fetchone()
            emergency_mode = bool(status["active"]) if status else False
        
        return DashboardStats(
            violations_today=violations_today,
            violations_this_week=violations_week,
            average_risk_score=round(100 - avg_score, 2),  # Convert to risk percentage
            current_traffic_level=traffic_level,
            active_junctions=1,  # TODO: Count from junction_safety table
            total_vehicles_today=violations_today * 10,  # Estimate
            pending_fines=pending_fines,
            emergency_mode=emergency_mode,
        )


# =============================================================================
# VIOLATION MANAGEMENT
# =============================================================================

@router.get("/violations", summary="Get all violations")
async def get_all_violations(
    user: UserInfo = Depends(get_current_admin),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    violation_type: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Get paginated list of all violations with optional filters.
    Admin only endpoint.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Build query with filters
        # driver_violations columns: violation_id, driver_id, violation_type, timestamp, location, points_deducted, fine_amount, license_plate, snapshot_path, notes
        query = """SELECT violation_id, driver_id, violation_type, fine_amount,
                          timestamp, location, snapshot_path, notes, points_deducted
                   FROM driver_violations WHERE 1=1"""
        params = []
        
        if violation_type:
            query += " AND violation_type = ?"
            params.append(violation_type)
        
        if date_from:
            query += " AND date(timestamp, 'unixepoch', 'localtime') >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND date(timestamp, 'unixepoch', 'localtime') <= ?"
            params.append(date_to)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM driver_violations WHERE 1=1"
        if violation_type:
            count_query += f" AND violation_type = '{violation_type}'"
        
        cursor = await db.execute(count_query)
        total = (await cursor.fetchone())["count"]
        
        # Add pagination
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        violations = await cursor.fetchall()
        
        return {
            "violations": [
                {
                    "violation_id": str(v["violation_id"]),
                    "driver_id": v["driver_id"],
                    "license_plate": v["driver_id"],  # Use driver_id as license plate
                    "violation_type": v["violation_type"],
                    "timestamp": datetime.fromtimestamp(v["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": v["location"] or "Unknown",
                    "fine_amount": v["fine_amount"] or 0,
                    "points_deducted": v["points_deducted"] or 0,
                    "evidence_path": v["snapshot_path"],
                    "notes": v["notes"] or "",
                    "status": "pending", # driver_violations table does not have a status column
                }
                for v in violations
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters_applied": {
                "violation_type": violation_type,
                "date_from": date_from,
                "date_to": date_to,
            }
        }


@router.get("/violations/{violation_id}", summary="Get violation details")
async def get_violation_details(
    violation_id: str,
    user: UserInfo = Depends(get_current_admin),
):  
    """Get detailed information about a specific violation."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            """SELECT * FROM driver_violations WHERE violation_id = ?""",
            (violation_id,)
        )
        violation = await cursor.fetchone()
        
        if not violation:
            raise HTTPException(status_code=404, detail="Violation not found")
        
        # Return formatted response matching the driver_violations schema
        return {
            "violation_id": str(violation["violation_id"]),
            "driver_id": violation["driver_id"],
            "license_plate": violation["driver_id"],
            "violation_type": violation["violation_type"],
            "timestamp": datetime.fromtimestamp(violation["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
            "location": violation["location"] or "Unknown",
            "fine_amount": violation["fine_amount"] or 0,
            "points_deducted": violation["points_deducted"] or 0,
            "severity": "medium",  # Calculated or static, as driver_violations table does not have a severity column
            "status": "pending", # driver_violations table does not have a status column
            "evidence_path": violation["snapshot_path"],
            "notes": violation["notes"]
        }


@router.delete("/violations/{violation_id}", summary="Delete a violation")
async def delete_violation(
    violation_id: str,
    user: UserInfo = Depends(get_current_admin),
):
    """Delete a violation record (admin only)."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM driver_violations WHERE violation_id = ?",
            (violation_id,)
        )
        await db.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Violation not found")
    
    return {"status": "deleted", "violation_id": violation_id}


# =============================================================================
# DRIVER MANAGEMENT
# =============================================================================

@router.get("/drivers", summary="Get all drivers")
async def get_all_drivers(
    user: UserInfo = Depends(get_current_admin),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="current_score", description="Sort by: current_score, total_violations, total_fines"),
    order: str = Query(default="asc", description="Order: asc, desc"),
):
    """Get paginated list of all drivers with their scores."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Validate sort_by
        valid_sorts = ["current_score", "total_violations", "total_fines", "driver_id"]
        if sort_by not in valid_sorts:
            sort_by = "current_score"
        
        order_dir = "DESC" if order.lower() == "desc" else "ASC"
        
        # Join with driver_users to get name and phone
        # Note: driver_users table is not defined in database.py, proceeding with assumption it exists or optional
        # Using LEFT JOIN assuming driver_users might not exist or match
        try:
            cursor = await db.execute(f"""
                SELECT d.driver_id, d.current_score, d.total_violations, d.total_fines, d.updated_at,
                       du.name, du.phone
                FROM drivers d
                LEFT JOIN driver_users du ON d.driver_id = du.plate_number
                ORDER BY d.{sort_by} {order_dir}
                LIMIT ? OFFSET ?
            """, (limit, offset))
            drivers = await cursor.fetchall()
        except aiosqlite.OperationalError:
             # Fallback if driver_users table is missing
            cursor = await db.execute(f"""
                SELECT d.driver_id, d.current_score, d.total_violations, d.total_fines, d.updated_at,
                       'Unknown Driver' as name, 'N/A' as phone
                FROM drivers d
                ORDER BY d.{sort_by} {order_dir}
                LIMIT ? OFFSET ?
            """, (limit, offset))
            drivers = await cursor.fetchall()
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM drivers")
        total = (await cursor.fetchone())["count"]
        
        return {
            "drivers": [
                {
                    "driver_id": d["driver_id"],
                    "name": d["name"] or "Unknown Driver",
                    "phone": d["phone"],
                    "current_score": d["current_score"],
                    "total_violations": d["total_violations"],
                    "total_fines": d["total_fines"],
                    "last_violation": datetime.fromtimestamp(d["updated_at"]).strftime("%Y-%m-%d %H:%M:%S") if d["updated_at"] else None,
                    "risk_level": get_risk_level(d["current_score"]),
                }
                for d in drivers
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/drivers/{driver_id}", summary="Get driver details")
async def get_driver_details(
    driver_id: str,
    user: UserInfo = Depends(get_current_admin),
):
    """Get detailed information about a specific driver."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Get driver info with user details
        try:
            cursor = await db.execute(
                """SELECT d.*, du.name, du.phone
                   FROM drivers d
                   LEFT JOIN driver_users du ON d.driver_id = du.plate_number
                   WHERE d.driver_id = ?""",
                (driver_id,)
            )
            driver = await cursor.fetchone()
        except aiosqlite.OperationalError:
            cursor = await db.execute(
                """SELECT d.*, 'Unknown Driver' as name, 'N/A' as phone
                   FROM drivers d
                   WHERE d.driver_id = ?""",
                (driver_id,)
            )
            driver = await cursor.fetchone()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        # Get violations
        cursor = await db.execute(
            """SELECT violation_id, violation_type, timestamp, fine_amount, location
               FROM driver_violations WHERE driver_id = ?
               ORDER BY timestamp DESC LIMIT 20""",
            (driver_id,)
        )
        violations = await cursor.fetchall()
        
        return {
            "driver_id": driver["driver_id"],
            "name": driver["name"] or "Unknown Driver",
            "phone": driver["phone"],
            "current_score": driver["current_score"],
            "total_violations": driver["total_violations"],
            "total_fines": driver["total_fines"],
            "last_violation": datetime.fromtimestamp(driver["updated_at"]).strftime("%Y-%m-%d %H:%M:%S") if driver["updated_at"] else None,
            "recent_violations": [
                {
                    "violation_id": str(v["violation_id"]),
                    "violation_type": v["violation_type"],
                    "timestamp": datetime.fromtimestamp(v["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "fine_amount": v["fine_amount"] or 0,
                    "location": v["location"],
                }
                for v in violations
            ],
        }


# =============================================================================
# EMERGENCY CONTROL
# =============================================================================

@router.post("/emergency/trigger", response_model=EmergencyResponse, summary="Trigger emergency mode")
async def trigger_emergency(
    junction_id: str = Query(default="main", description="Junction to trigger emergency for"),
    emergency_type: str = Query(default="ambulance", description="Type: ambulance, fire, police"),
    lane: str = Query(default="north", description="Lane to force GREEN"),
):
    """
    Trigger emergency mode for a junction.
    This simulates an ambulance/emergency vehicle approach.
    All signals will be set to allow emergency vehicle passage.
    """
    # Activate emergency mode on the traffic controller
    controller = get_four_way_controller()
    if controller:
        controller.activate_emergency_mode(lane=lane)
        print(f"[ADMIN] 🚑 Emergency mode activated - Lane: {lane}")
    else:
        print(f"[ADMIN] ⚠️ Traffic controller not available for emergency mode")
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Create emergency_status table if not exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS emergency_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                junction_id TEXT NOT NULL,
                emergency_type TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                triggered_by TEXT,
                triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)
        
        # Insert new emergency
        await db.execute(
            """INSERT INTO emergency_status (junction_id, emergency_type, triggered_by)
               VALUES (?, ?, ?)""",
            (junction_id, emergency_type, "admin")
        )
        await db.commit()
    
    return EmergencyResponse(
        status="triggered",
        message=f"Emergency mode activated for {emergency_type} at junction {junction_id}",
        affected_junctions=[junction_id],
        timestamp=datetime.now().isoformat(),
    )


@router.post("/emergency/clear", summary="Clear emergency mode")
async def clear_emergency(
    user: UserInfo = Depends(get_current_admin),
    junction_id: str = Query(default="main"),
):
    """Clear emergency mode and return to normal operation."""
    # Deactivate emergency mode on the traffic controller
    controller = get_four_way_controller()
    if controller:
        controller.deactivate_emergency_mode()
        print(f"[ADMIN] ✅ Emergency mode deactivated by {user.identifier}")
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """UPDATE emergency_status 
               SET active = 0, resolved_at = CURRENT_TIMESTAMP
               WHERE junction_id = ? AND active = 1""",
            (junction_id,)
        )
        await db.commit()
    
    return {
        "status": "cleared",
        "message": f"Emergency mode cleared for junction {junction_id}",
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get("/analytics/violation-trends", summary="Get violation trends")
async def get_violation_trends(
    user: UserInfo = Depends(get_current_admin),
    days: int = Query(default=7, le=30),
):
    """Get violation trends over the specified number of days."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Get daily counts by type
        cursor = await db.execute(
            """SELECT DATE(timestamp) as date, violation_type, COUNT(*) as count
               FROM violations
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp), violation_type
               ORDER BY date""",
            (start_date,)
        )
        daily_counts = await cursor.fetchall()
        
        # Organize by date
        trends = {}
        for row in daily_counts:
            date = row["date"]
            if date not in trends:
                trends[date] = {"date": date, "total": 0, "by_type": {}}
            trends[date]["by_type"][row["violation_type"]] = row["count"]
            trends[date]["total"] += row["count"]
        
        return {
            "period_days": days,
            "start_date": start_date,
            "trends": list(trends.values()),
        }


@router.get("/analytics/hotspots", summary="Get violation hotspots")
async def get_violation_hotspots(
    user: UserInfo = Depends(get_current_admin),
):
    """Get locations with highest violation counts."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            """SELECT location, COUNT(*) as violation_count,
                      SUM(fine_amount) as total_fines
               FROM violations
               WHERE location IS NOT NULL
               GROUP BY location
               ORDER BY violation_count DESC
               LIMIT 10"""
        )
        hotspots = await cursor.fetchall()
        
        return {
            "hotspots": [
                {
                    "location": h["location"],
                    "violation_count": h["violation_count"],
                    "total_fines": h["total_fines"],
                }
                for h in hotspots
            ]
        }


def get_risk_level(score: int) -> str:
    """Get risk level string from score."""
    if score >= 90:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 50:
        return "fair"
    elif score >= 30:
        return "poor"
    else:
        return "critical"
