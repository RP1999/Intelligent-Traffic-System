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
from google.cloud.firestore_v1 import FieldFilter

from app.config import get_settings
from app.db.firestore_client import get_db, Collections
from app.routers.auth import get_current_admin, UserInfo

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["Admin Configuration"])

# Video source for snapshots (can be overridden)
VIDEO_SOURCE = None


def _reload_zones_in_detector():
    """Reload parking zones from Firestore into the live detection system."""
    try:
        from app.routers.video import load_zones_from_db_sync
        load_zones_from_db_sync()
    except Exception as e:
        print(f"[ZONES] Warning: Could not reload zones in detector: {e}")


def _coords_to_firestore(coords: List[List[float]]) -> List[dict]:
    """Convert [[x,y], ...] to [{x:,y:}, ...] — Firestore forbids nested arrays."""
    return [{"x": p[0], "y": p[1]} for p in coords]


def _coords_from_firestore(raw) -> List[List[float]]:
    """Convert Firestore stored coords back to [[x,y], ...] format."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not raw:
        return []
    # Already in dict format {x:, y:}
    if isinstance(raw[0], dict):
        return [[p["x"], p["y"]] for p in raw]
    # Legacy nested-array format (shouldn't happen in Firestore, but handle gracefully)
    return [[float(p[0]), float(p[1])] for p in raw]


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
    id: str
    zone_type: str
    coordinates: List[List[float]]
    label: Optional[str]
    active: bool
    created_at: str
    updated_at: str


class AuditLogResponse(BaseModel):
    id: str
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


class StopLineConfig(BaseModel):
    """Configuration for the red light stop line."""
    y_position: float = 0.6  # Ratio from top (0-1)
    x_start: float = 0.0     # Left boundary as ratio (0-1)
    x_end: float = 0.5       # Right boundary as ratio (0-1) - only main lane
    active: bool = True


class StopLineResponse(BaseModel):
    y_position: float
    x_start: float
    x_end: float
    active: bool
    updated_at: str


# =============================================================================
# DATABASE HELPERS
# =============================================================================

async def ensure_tables():
    """No-op for Firestore — collections are auto-created."""
    pass


async def log_action(username: str, action: str, details: str = None):
    """Log an admin action to the audit trail."""
    db = get_db()
    await db.collection(Collections.AUDIT_LOGS).add({
        "admin_username": username,
        "action": action,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    })


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

    db = get_db()
    q = db.collection(Collections.PARKING_ZONES)
    if active_only:
        q = q.where(filter=FieldFilter("active", "==", True))

    zones = []
    async for doc in q.stream():
        row = doc.to_dict()
        coords = _coords_from_firestore(row.get("coordinates", []))
        zones.append({
            "id": doc.id,
            "zone_type": row.get("zone_type", ""),
            "coordinates": coords,
            "label": row.get("label"),
            "active": bool(row.get("active", True)),
            "created_at": str(row.get("created_at", "")),
            "updated_at": str(row.get("updated_at", "")),
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

    db = get_db()
    now = datetime.now().isoformat()
    doc_ref = await db.collection(Collections.PARKING_ZONES).add({
        "zone_type": zone.zone_type,
        "coordinates": _coords_to_firestore(zone.coordinates),
        "label": zone.label,
        "active": zone.active,
        "created_at": now,
        "updated_at": now,
    })
    zone_id = doc_ref[1].id if isinstance(doc_ref, tuple) else doc_ref.id

    # Log the action
    await log_action(
        user.identifier,
        "zone_create",
        f"Zone ID: {zone_id}, Type: {zone.zone_type}, Label: {zone.label}"
    )

    # Immediately reload zones in the detection system
    _reload_zones_in_detector()

    return ZoneResponse(
        id=zone_id,
        zone_type=zone.zone_type,
        coordinates=zone.coordinates,
        label=zone.label,
        active=zone.active,
        created_at=now,
        updated_at=now,
    )


@router.put("/zones/{zone_id}", response_model=ZoneResponse, summary="Update a parking zone")
async def update_zone(
    zone_id: str,
    zone: ZoneUpdate,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Update an existing parking zone.
    Changes are applied immediately to the detection system.
    """
    await ensure_tables()

    db = get_db()
    doc_ref = db.collection(Collections.PARKING_ZONES).document(zone_id)
    doc = await doc_ref.get()

    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )

    updates = {"updated_at": datetime.now().isoformat()}

    if zone.zone_type is not None:
        if zone.zone_type not in ['red', 'yellow']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="zone_type must be 'red' or 'yellow'"
            )
        updates["zone_type"] = zone.zone_type

    if zone.coordinates is not None:
        if len(zone.coordinates) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zone must have at least 3 coordinate points"
            )
        updates["coordinates"] = _coords_to_firestore(zone.coordinates)

    if zone.label is not None:
        updates["label"] = zone.label

    if zone.active is not None:
        updates["active"] = zone.active

    await doc_ref.update(updates)

    # Fetch updated zone
    updated_doc = await doc_ref.get()
    row = updated_doc.to_dict()

    await log_action(user.identifier, "Updated Zone", f"Zone ID: {zone_id}")

    # Immediately reload zones in the detection system
    _reload_zones_in_detector()

    coords = _coords_from_firestore(row.get("coordinates", []))

    return ZoneResponse(
        id=zone_id,
        zone_type=row.get("zone_type", ""),
        coordinates=coords,
        label=row.get("label"),
        active=bool(row.get("active", True)),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )


@router.delete("/zones/{zone_id}", summary="Delete a parking zone")
async def delete_zone(
    zone_id: str,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Delete a parking zone.
    The zone will be immediately removed from detection.
    """
    await ensure_tables()

    db = get_db()
    doc = await db.collection(Collections.PARKING_ZONES).document(zone_id).get()

    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found"
        )

    await db.collection(Collections.PARKING_ZONES).document(zone_id).delete()

    await log_action(user.identifier, "Deleted Zone", f"Zone ID: {zone_id}")

    # Immediately reload zones in the detection system
    _reload_zones_in_detector()

    return {"message": "Zone deleted successfully", "zone_id": zone_id}


# =============================================================================
# STOP LINE CONFIGURATION ENDPOINTS
# =============================================================================

# Default stop line config document ID
STOP_LINE_DOC_ID = "main_stop_line"


def _reload_stop_line_in_detector():
    """Reload stop line configuration into the live detection system."""
    try:
        from app.detection.yolo_detector import load_stop_line_config
        load_stop_line_config()
    except Exception as e:
        print(f"[STOP_LINE] Warning: Could not reload stop line in detector: {e}")


@router.get("/stop-line", response_model=StopLineResponse, summary="Get stop line configuration")
async def get_stop_line_config(
    user: UserInfo = Depends(get_current_admin)
):
    """
    Get the current red light stop line configuration.
    Defines the y position and x boundaries for the monitored lane.
    """
    db = get_db()
    doc = await db.collection(Collections.CONFIG).document(STOP_LINE_DOC_ID).get()
    
    if doc.exists:
        data = doc.to_dict()
        return StopLineResponse(
            y_position=data.get("y_position", 0.6),
            x_start=data.get("x_start", 0.0),
            x_end=data.get("x_end", 1.0),
            active=data.get("active", True),
            updated_at=str(data.get("updated_at", "")),
        )
    else:
        # Return defaults
        return StopLineResponse(
            y_position=0.6,
            x_start=0.0,
            x_end=1.0,
            active=True,
            updated_at="",
        )


@router.put("/stop-line", response_model=StopLineResponse, summary="Update stop line configuration")
async def update_stop_line_config(
    config: StopLineConfig,
    user: UserInfo = Depends(get_current_admin)
):
    """
    Update the red light stop line configuration.
    
    - y_position: Vertical position as ratio (0=top, 1=bottom). Default 0.6.
    - x_start: Left boundary as ratio (0=left edge). Default 0.0.
    - x_end: Right boundary as ratio (1=right edge). Default 0.5 for main lane only.
    - active: Whether red light detection is enabled.
    
    Only vehicles within the x_start to x_end horizontal range will be
    checked for red light violations. This prevents false positives from
    vehicles in opposite lanes.
    """
    db = get_db()
    
    # Validate ranges
    if not (0 <= config.y_position <= 1):
        raise HTTPException(status_code=400, detail="y_position must be between 0 and 1")
    if not (0 <= config.x_start <= 1):
        raise HTTPException(status_code=400, detail="x_start must be between 0 and 1")
    if not (0 <= config.x_end <= 1):
        raise HTTPException(status_code=400, detail="x_end must be between 0 and 1")
    if config.x_start >= config.x_end:
        raise HTTPException(status_code=400, detail="x_start must be less than x_end")
    
    now = datetime.now().isoformat()
    
    await db.collection(Collections.CONFIG).document(STOP_LINE_DOC_ID).set({
        "y_position": config.y_position,
        "x_start": config.x_start,
        "x_end": config.x_end,
        "active": config.active,
        "updated_at": now,
    })
    
    await log_action(
        user.identifier, 
        "Updated Stop Line", 
        f"Y: {config.y_position:.2f}, X: {config.x_start:.2f}-{config.x_end:.2f}"
    )
    
    # Reload in detector
    _reload_stop_line_in_detector()
    
    return StopLineResponse(
        y_position=config.y_position,
        x_start=config.x_start,
        x_end=config.x_end,
        active=config.active,
        updated_at=now,
    )


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

    actual_offset = (page - 1) * limit if page > 1 else offset

    db = get_db()

    # Get all audit logs ordered by timestamp desc
    all_logs = []
    q = db.collection(Collections.AUDIT_LOGS).order_by("timestamp", direction="DESCENDING")
    async for doc in q.stream():
        row = doc.to_dict()
        all_logs.append({
            "id": doc.id,
            "admin_username": row.get("admin_username", ""),
            "action": row.get("action", ""),
            "details": row.get("details"),
            "timestamp": str(row.get("timestamp", "")),
        })

    total_count = len(all_logs)
    total_pages = max(1, (total_count + limit - 1) // limit)
    page_logs = all_logs[actual_offset: actual_offset + limit]

    return {
        "logs": page_logs,
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

    db = get_db()

    # Total zones
    total_zones = 0
    active_zones = 0
    async for doc in db.collection(Collections.PARKING_ZONES).stream():
        total_zones += 1
        if doc.to_dict().get("active", True):
            active_zones += 1

    # Today's violations
    today = datetime.now().strftime("%Y-%m-%d")
    today_violations = 0
    try:
        q = db.collection(Collections.VIOLATIONS).where(
            filter=FieldFilter("timestamp", ">=", today)
        )
        async for _ in q.stream():
            today_violations += 1
    except Exception:
        today_violations = 0

    # Total drivers
    total_drivers = 0
    async for _ in db.collection(Collections.DRIVERS).stream():
        total_drivers += 1

    # Pending fines
    pending_fines = 0.0
    try:
        q = db.collection(Collections.VIOLATIONS).where(
            filter=FieldFilter("status", "==", "pending")
        )
        async for doc in q.stream():
            pending_fines += doc.to_dict().get("fine_amount", 0) or 0
    except Exception:
        pending_fines = 0.0

    return StatsResponse(
        total_zones=total_zones,
        active_zones=active_zones,
        total_violations_today=today_violations,
        total_drivers=total_drivers,
        pending_fines=pending_fines,
    )


# =============================================================================
# TTS TEST ENDPOINT
# =============================================================================

@router.post("/tts/test", summary="Test TTS audio playback")
async def test_tts_playback(
    message: str = Query(default="Testing audio playback system.", description="Message to speak"),
    user: UserInfo = Depends(get_current_admin),
):
    """
    Test the TTS (Text-to-Speech) system by generating and playing an audio message.
    This helps diagnose audio playback issues.
    """
    from app.tts.tts_service import get_tts_service, is_tts_paused, WARNINGS_DIR
    
    tts = get_tts_service()
    
    # Get TTS status
    status_info = {
        "tts_paused": is_tts_paused(),
        "edge_tts_available": tts._edge_tts_available,
        "pyttsx3_available": tts._pyttsx3_available,
        "warnings_dir": str(WARNINGS_DIR),
        "warnings_count": tts.get_warning_count(),
    }
    
    # Try to generate and play
    import time
    timestamp = int(time.time())
    filename = f"test_audio_{timestamp}"
    
    try:
        filepath = tts.generate_warning(
            message,
            filename=filename,
            play_immediately=True
        )
        
        if filepath:
            status_info["generated_file"] = str(filepath)
            status_info["file_size"] = filepath.stat().st_size if filepath.exists() else 0
            status_info["status"] = "success"
            status_info["message"] = "Audio generated and playback initiated"
        else:
            status_info["status"] = "failed"
            status_info["message"] = "Failed to generate audio file"
    except Exception as e:
        status_info["status"] = "error"
        status_info["error"] = str(e)
    
    await log_action(user.username, "tts_test", f"Tested TTS: {message[:50]}...")
    
    return status_info
