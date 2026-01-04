"""
Admin Configuration Router - Zone Management & Audit Logs
Provides endpoints for managing parking zones and viewing audit logs.
"""

import json
import cv2
import io
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import aiosqlite

from app.config import get_settings
from app.routers.auth import get_current_admin, UserInfo

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["Admin Configuration"])

# Database path
DB_PATH = settings.data_dir.parent / "backend" / "traffic.db"

# Video source for snapshots (can be overridden)
VIDEO_SOURCE = None


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ZoneCreate(BaseModel):
    zone_type: str  # 'red' (no parking) or 'yellow' (loading)
    coordinates: List[List[float]]  # [[x1,y1], [x2,y2], ...]
    label: Optional[str] = None
    active: bool = True


class ZoneUpdate(BaseModel):
    zone_type: Optional[str] = None
    coordinates: Optional[List[List[float]]] = None
    label: Optional[str] = None
    active: Optional[bool] = None


class ZoneResponse(BaseModel):
    id: int
    zone_type: str
    coordinates: List[List[float]]
    label: Optional[str]
    active: bool
    created_at: str
    updated_at: str


class AuditLogResponse(BaseModel):
    id: int
    admin_username: str
    action: str
    details: Optional[str]
    timestamp: str


class StatsResponse(BaseModel):
    total_zones: int
    active_zones: int
    total_violations_today: int
    total_drivers: int
    pending_fines: float


# =============================================================================
# DATABASE HELPERS
# =============================================================================

async def ensure_tables():
    """Ensure required tables exist."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS parking_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_type TEXT NOT NULL,
                coordinates TEXT NOT NULL,
                label TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def log_action(username: str, action: str, details: str = None):
    """Log an admin action to the audit trail."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO audit_logs (admin_username, action, details) VALUES (?, ?, ?)",
            (username, action, details)
        )
        await db.commit()


# =============================================================================
# ZONE MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/zones", summary="Get all parking zones")
async def get_zones(
    active_only: bool = Query(False, description="Filter to only active zones"),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Fetch all parking zone configurations.
    Returns zone coordinates for drawing on video feed.
    """
    await ensure_tables()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        if active_only:
            cursor = await db.execute(
                "SELECT * FROM parking_zones WHERE active = 1 ORDER BY id"
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM parking_zones ORDER BY id"
            )
        
        rows = await cursor.fetchall()
        
        zones = []
        for row in rows:
            zones.append({
                "id": row["id"],
                "zone_type": row["zone_type"],
                "coordinates": json.loads(row["coordinates"]),
                "label": row["label"],
                "active": bool(row["active"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"])
            })
        
        return {"zones": zones}


@router.post("/zones", response_model=ZoneResponse, summary="Create a new parking zone")
async def create_zone(
    zone: ZoneCreate,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Create a new parking zone.
    The zone will be immediately active for violation detection.
    """
    await ensure_tables()
    
    # Map frontend zone types to backend storage types
    zone_type_map = {
        'no_parking': 'red',
        'loading': 'yellow',
        'handicap': 'blue',
        'red': 'red',
        'yellow': 'yellow',
        'blue': 'blue'
    }
    
    mapped_type = zone_type_map.get(zone.zone_type)
    if not mapped_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="zone_type must be 'no_parking', 'loading', 'handicap', 'red', or 'yellow'"
        )
    
    if len(zone.coordinates) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone must have at least 3 coordinate points"
        )
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            """INSERT INTO parking_zones (zone_type, coordinates, label, active)
               VALUES (?, ?, ?, ?)""",
            (zone.zone_type, json.dumps(zone.coordinates), zone.label, int(zone.active))
        )
        await db.commit()
        
        zone_id = cursor.lastrowid
        
        # Fetch the created zone
        cursor = await db.execute(
            "SELECT * FROM parking_zones WHERE id = ?",
            (zone_id,)
        )
        row = await cursor.fetchone()
    
    # Log the action
    await log_action(
        user.identifier,
        "zone_create",
        f"Zone ID: {zone_id}, Type: {zone.zone_type}, Label: {zone.label}"
    )
    
    # TODO: Update running detector instance
    # This would notify the YOLO detector to reload zones
    
    return ZoneResponse(
        id=row["id"],
        zone_type=row["zone_type"],
        coordinates=json.loads(row["coordinates"]),
        label=row["label"],
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"])
    )


@router.put("/zones/{zone_id}", response_model=ZoneResponse, summary="Update a parking zone")
async def update_zone(
    zone_id: int,
    zone: ZoneUpdate,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Update an existing parking zone.
    Changes are applied immediately to the detection system.
    """
    await ensure_tables()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if zone exists
        cursor = await db.execute(
            "SELECT * FROM parking_zones WHERE id = ?",
            (zone_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        # Build update query dynamically
        updates = []
        params = []
        
        if zone.zone_type is not None:
            if zone.zone_type not in ['red', 'yellow']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="zone_type must be 'red' or 'yellow'"
                )
            updates.append("zone_type = ?")
            params.append(zone.zone_type)
        
        if zone.coordinates is not None:
            if len(zone.coordinates) < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Zone must have at least 3 coordinate points"
                )
            updates.append("coordinates = ?")
            params.append(json.dumps(zone.coordinates))
        
        if zone.label is not None:
            updates.append("label = ?")
            params.append(zone.label)
        
        if zone.active is not None:
            updates.append("active = ?")
            params.append(int(zone.active))
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(zone_id)
            
            await db.execute(
                f"UPDATE parking_zones SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await db.commit()
        
        # Fetch updated zone
        cursor = await db.execute(
            "SELECT * FROM parking_zones WHERE id = ?",
            (zone_id,)
        )
        row = await cursor.fetchone()
    
    # Log the action
    await log_action(
        user.identifier,
        "Updated Zone",
        f"Zone ID: {zone_id}"
    )
    
    return ZoneResponse(
        id=row["id"],
        zone_type=row["zone_type"],
        coordinates=json.loads(row["coordinates"]),
        label=row["label"],
        active=bool(row["active"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"])
    )


@router.delete("/zones/{zone_id}", summary="Delete a parking zone")
async def delete_zone(
    zone_id: int,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Delete a parking zone.
    The zone will be immediately removed from detection.
    """
    await ensure_tables()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id FROM parking_zones WHERE id = ?",
            (zone_id,)
        )
        existing = await cursor.fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found"
            )
        
        await db.execute("DELETE FROM parking_zones WHERE id = ?", (zone_id,))
        await db.commit()
    
    # Log the action
    await log_action(
        user.identifier,
        "Deleted Zone",
        f"Zone ID: {zone_id}"
    )
    
    return {"message": "Zone deleted successfully", "zone_id": zone_id}


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================

@router.get("/logs", summary="Get audit logs")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    page: int = Query(1, ge=1, description="Page number"),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Fetch the audit trail of admin actions.
    Returns most recent logs first.
    """
    await ensure_tables()
    
    # Calculate offset from page if provided
    actual_offset = (page - 1) * limit if page > 1 else offset
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Get total count for pagination
        count_cursor = await db.execute("SELECT COUNT(*) FROM audit_logs")
        count_row = await count_cursor.fetchone()
        total_count = count_row[0] if count_row else 0
        total_pages = max(1, (total_count + limit - 1) // limit)
        
        cursor = await db.execute(
            """SELECT * FROM audit_logs 
               ORDER BY timestamp DESC 
               LIMIT ? OFFSET ?""",
            (limit, actual_offset)
        )
        rows = await cursor.fetchall()
        
        logs = []
        for row in rows:
            logs.append({
                "id": row["id"],
                "admin_username": row["admin_username"],
                "action": row["action"],
                "details": row["details"],
                "timestamp": str(row["timestamp"])
            })
        
        return {
            "logs": logs,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
        }


# =============================================================================
# VIDEO SNAPSHOT ENDPOINT
# =============================================================================

@router.get("/video/snapshot", summary="Get video snapshot for zone drawing")
async def get_video_snapshot(
    source: Optional[str] = Query(None, description="Video source path or URL"),
    user: UserInfo = Depends(get_current_admin)
):
    """
    Capture a single frame from the video source.
    Returns a JPEG image that can be used to draw zones on.
    """
    # Try different video sources
    video_source = source or VIDEO_SOURCE
    
    if video_source is None:
        # Try to find a sample video in the data directory
        video_dir = settings.data_dir / "videos"
        if video_dir.exists():
            videos = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))
            if videos:
                video_source = str(videos[0])
    
    if video_source is None:
        # Return a placeholder image with grid
        import numpy as np
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)  # Dark gray background
        
        # Draw grid
        for x in range(0, 1280, 80):
            cv2.line(img, (x, 0), (x, 720), (50, 50, 50), 1)
        for y in range(0, 720, 80):
            cv2.line(img, (0, y), (1280, y), (50, 50, 50), 1)
        
        # Add text
        cv2.putText(
            img, "No Video Source - Draw Zones Here",
            (400, 360), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2
        )
        
        _, buffer = cv2.imencode('.jpg', img)
        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg",
            headers={"Content-Disposition": "inline; filename=snapshot.jpg"}
        )
    
    # Open video and capture frame
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to open video source: {video_source}"
        )
    
    try:
        ret, frame = cap.read()
        if not ret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to capture frame from video"
            )
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg",
            headers={"Content-Disposition": "inline; filename=snapshot.jpg"}
        )
    finally:
        cap.release()


# =============================================================================
# DASHBOARD STATS ENDPOINT
# =============================================================================

@router.get("/stats", response_model=StatsResponse, summary="Get dashboard statistics")
async def get_dashboard_stats(
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get statistics for the admin dashboard.
    """
    await ensure_tables()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Total zones
        cursor = await db.execute("SELECT COUNT(*) FROM parking_zones")
        total_zones = (await cursor.fetchone())[0]
        
        # Active zones
        cursor = await db.execute("SELECT COUNT(*) FROM parking_zones WHERE active = 1")
        active_zones = (await cursor.fetchone())[0]
        
        # Today's violations - use timestamp column that exists
        today_violations = 0
        try:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM violations 
                WHERE date(start_time, 'unixepoch') = date('now')
            """)
            today_violations = (await cursor.fetchone())[0]
        except Exception:
            # Fallback if violations table has different schema or doesn't exist
            today_violations = 0
        
        # Total drivers
        total_drivers = 0
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM drivers")
            total_drivers = (await cursor.fetchone())[0]
        except Exception:
            try:
                cursor = await db.execute("SELECT COUNT(*) FROM driver_users")
                total_drivers = (await cursor.fetchone())[0]
            except Exception:
                total_drivers = 0
        
        # Pending fines (from violations)
        pending_fines = 0.0
        try:
            cursor = await db.execute("""
                SELECT COALESCE(SUM(fine_amount), 0) FROM violations 
                WHERE status = 'pending'
            """)
            pending_fines = (await cursor.fetchone())[0] or 0.0
        except Exception:
            pending_fines = 0.0
    
    return StatsResponse(
        total_zones=total_zones,
        active_zones=active_zones,
        total_violations_today=today_violations,
        total_drivers=total_drivers,
        pending_fines=pending_fines
    )
