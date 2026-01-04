"""
Community API Router - Public endpoints for community awareness
Some endpoints require admin authentication for creating/broadcasting alerts.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Body
from pydantic import BaseModel
import aiosqlite

from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/community", tags=["Community"])

# Database path
DB_PATH = settings.data_dir.parent / "backend" / "traffic.db"


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class JunctionScore(BaseModel):
    junction_id: str
    junction_name: str
    current_score: int
    risk_level: str
    last_updated: str
    active_alerts: int
    traffic_level: str


class CommunityAlert(BaseModel):
    alert_id: int
    alert_type: str  # 'high_risk', 'emergency', 'congestion', 'accident'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    junction_id: str
    timestamp: str
    expires_at: Optional[str]
    anonymous: bool = True


class TrafficSummary(BaseModel):
    junction_id: str
    current_density: str
    estimated_wait_time: int  # seconds
    signal_phase: str
    last_updated: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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


def get_traffic_level(density: float) -> str:
    """Get traffic level from density."""
    if density < 0.3:
        return "low"
    elif density < 0.6:
        return "moderate"
    elif density < 0.8:
        return "high"
    else:
        return "congested"


# =============================================================================
# JUNCTION SAFETY SCORE (PUBLIC)
# =============================================================================

@router.get("/junction-score", response_model=JunctionScore, summary="Get junction safety score")
async def get_junction_score(
    junction_id: str = Query(default="main", description="Junction identifier"),
):
    """
    Get the current LiveSafeScore for a junction.
    This is a public endpoint for community awareness.
    
    The score represents overall junction safety from 0-100:
    - 90-100: Excellent (very safe)
    - 70-89: Good (safe)
    - 50-69: Fair (caution advised)
    - 30-49: Poor (high risk)
    - 0-29: Critical (avoid if possible)
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if junction_safety table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='junction_safety'"
        )
        table_exists = await cursor.fetchone()
        
        current_score = 85  # Default score
        traffic_level = "moderate"
        updated_at = datetime.now().isoformat()
        
        if table_exists:
            cursor = await db.execute(
                """SELECT current_score, traffic_density, updated_at 
                   FROM junction_safety 
                   WHERE junction_id = ?
                   ORDER BY updated_at DESC LIMIT 1""",
                (junction_id,)
            )
            result = await cursor.fetchone()
            if result:
                current_score = result["current_score"]
                traffic_level = get_traffic_level(result["traffic_density"] or 0.5)
                updated_at = result["updated_at"]
        
        # Count active alerts
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='community_alerts'"
        )
        alerts_table_exists = await cursor.fetchone()
        
        active_alerts = 0
        if alerts_table_exists:
            cursor = await db.execute(
                """SELECT COUNT(*) as count FROM community_alerts 
                   WHERE junction_id = ? AND (expires_at IS NULL OR expires_at > ?)""",
                (junction_id, datetime.now().isoformat())
            )
            active_alerts = (await cursor.fetchone())["count"]
        
        return JunctionScore(
            junction_id=junction_id,
            junction_name=f"Junction {junction_id.upper()}",
            current_score=current_score,
            risk_level=get_risk_level(current_score),
            last_updated=updated_at,
            active_alerts=active_alerts,
            traffic_level=traffic_level,
        )


@router.get("/junction-scores", summary="Get all junction scores")
async def get_all_junction_scores():
    """Get safety scores for all monitored junctions."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='junction_safety'"
        )
        table_exists = await cursor.fetchone()
        
        junctions = []
        
        if table_exists:
            cursor = await db.execute(
                """SELECT junction_id, current_score, traffic_density, updated_at 
                   FROM junction_safety"""
            )
            rows = await cursor.fetchall()
            
            for row in rows:
                junctions.append({
                    "junction_id": row["junction_id"],
                    "current_score": row["current_score"],
                    "risk_level": get_risk_level(row["current_score"]),
                    "traffic_level": get_traffic_level(row["traffic_density"] or 0.5),
                    "last_updated": row["updated_at"],
                })
        
        # Add default if no junctions found
        if not junctions:
            junctions.append({
                "junction_id": "main",
                "current_score": 85,
                "risk_level": "good",
                "traffic_level": "moderate",
                "last_updated": datetime.now().isoformat(),
            })
        
        return {"junctions": junctions}


# =============================================================================
# COMMUNITY ALERTS (PUBLIC)
# =============================================================================

@router.get("/alerts", summary="Get community alerts")
async def get_community_alerts(
    junction_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None, description="Filter: low, medium, high, critical"),
    limit: int = Query(default=20, le=50),
):
    """
    Get anonymized community alerts for public awareness.
    No personal or vehicle-identifying information is included.
    
    Alert types:
    - high_risk: High-risk driving behavior detected
    - emergency: Emergency vehicle approaching
    - congestion: Traffic congestion warning
    - accident: Accident reported
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if community_alerts table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='community_alerts'"
        )
        table_exists = await cursor.fetchone()
        
        alerts = []
        
        if table_exists:
            query = """SELECT id, alert_type, severity, message, junction_id, timestamp, expires_at
                       FROM community_alerts 
                       WHERE (expires_at IS NULL OR expires_at > ?)"""
            params = [datetime.now().isoformat()]
            
            if junction_id:
                query += " AND junction_id = ?"
                params.append(junction_id)
            
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            for row in rows:
                alerts.append({
                    "alert_id": row["id"],
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "message": row["message"],
                    "junction_id": row["junction_id"],
                    "timestamp": row["timestamp"],
                    "expires_at": row["expires_at"],
                })
        
        # Generate sample alerts if none exist (for demo)
        if not alerts:
            now = datetime.now()
            sample_alerts = [
                {
                    "alert_id": 1,
                    "alert_type": "high_risk",
                    "severity": "medium",
                    "message": "Multiple lane weaving incidents detected in the area. Drive carefully.",
                    "junction_id": junction_id or "main",
                    "timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                },
                {
                    "alert_id": 2,
                    "alert_type": "congestion",
                    "severity": "low",
                    "message": "Moderate traffic congestion expected during peak hours.",
                    "junction_id": junction_id or "main",
                    "timestamp": (now - timedelta(hours=1)).isoformat(),
                    "expires_at": (now + timedelta(hours=2)).isoformat(),
                },
            ]
            alerts = sample_alerts
        
        return {
            "alerts": alerts,
            "total": len(alerts),
            "generated_at": datetime.now().isoformat(),
        }


# =============================================================================
# TRAFFIC INFORMATION (PUBLIC)
# =============================================================================

@router.get("/traffic-summary", response_model=TrafficSummary, summary="Get traffic summary")
async def get_traffic_summary(
    junction_id: str = Query(default="main"),
):
    """
    Get current traffic summary for a junction.
    Includes density level and estimated wait times.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Get latest junction data
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='junction_safety'"
        )
        table_exists = await cursor.fetchone()
        
        density = 0.4
        signal_phase = "normal"
        
        if table_exists:
            cursor = await db.execute(
                """SELECT traffic_density, updated_at 
                   FROM junction_safety WHERE junction_id = ?
                   ORDER BY updated_at DESC LIMIT 1""",
                (junction_id,)
            )
            result = await cursor.fetchone()
            if result:
                density = result["traffic_density"] or 0.4
        
        # Check emergency status
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='emergency_status'"
        )
        emergency_exists = await cursor.fetchone()
        
        if emergency_exists:
            cursor = await db.execute(
                "SELECT active FROM emergency_status WHERE junction_id = ? AND active = 1",
                (junction_id,)
            )
            if await cursor.fetchone():
                signal_phase = "emergency"
        
        # Estimate wait time based on density
        wait_time = int(density * 120)  # 0-120 seconds based on density
        
        return TrafficSummary(
            junction_id=junction_id,
            current_density=get_traffic_level(density),
            estimated_wait_time=wait_time,
            signal_phase=signal_phase,
            last_updated=datetime.now().isoformat(),
        )


@router.get("/violation-stats", summary="Get public violation statistics")
async def get_public_violation_stats(
    junction_id: Optional[str] = Query(default=None),
    days: int = Query(default=7, le=30),
):
    """
    Get anonymized violation statistics for community awareness.
    No driver or vehicle information is included.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Get violation counts by type
        cursor = await db.execute(
            """SELECT violation_type, COUNT(*) as count
               FROM violations
               WHERE timestamp >= ?
               GROUP BY violation_type
               ORDER BY count DESC""",
            (start_date,)
        )
        by_type = await cursor.fetchall()
        
        # Get daily totals
        cursor = await db.execute(
            """SELECT DATE(timestamp) as date, COUNT(*) as count
               FROM violations
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)
               ORDER BY date""",
            (start_date,)
        )
        daily = await cursor.fetchall()
        
        # Total count
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM violations WHERE timestamp >= ?",
            (start_date,)
        )
        total = (await cursor.fetchone())["count"]
        
        return {
            "period_days": days,
            "total_violations": total,
            "by_type": {row["violation_type"]: row["count"] for row in by_type},
            "daily_counts": [{"date": row["date"], "count": row["count"]} for row in daily],
            "message": "Drive safely! These statistics help improve road safety for everyone.",
        }


# =============================================================================
# SAFETY TIPS (PUBLIC)
# =============================================================================

@router.get("/safety-tips", summary="Get safety tips")
async def get_safety_tips():
    """Get contextual safety tips based on current conditions."""
    return {
        "tips": [
            {
                "id": 1,
                "category": "general",
                "tip": "Always maintain a safe following distance of at least 3 seconds.",
            },
            {
                "id": 2,
                "category": "lane_discipline",
                "tip": "Use turn signals at least 100 meters before changing lanes.",
            },
            {
                "id": 3,
                "category": "parking",
                "tip": "Never park in handicapped zones without proper authorization.",
            },
            {
                "id": 4,
                "category": "speed",
                "tip": "Reduce speed in areas with high pedestrian activity.",
            },
            {
                "id": 5,
                "category": "emergency",
                "tip": "Always yield to emergency vehicles and move to the side of the road.",
            },
        ],
        "featured_tip": "Your SafeScore affects insurance premiums. Drive responsibly!",
    }


# =============================================================================
# ALERT MANAGEMENT (Admin Protected)
# =============================================================================

class CreateAlertRequest(BaseModel):
    """Request model for creating a community alert."""
    alert_type: str  # 'high_risk', 'emergency', 'congestion', 'accident', 'construction'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    junction_id: str = "main"
    expires_in_hours: Optional[int] = 24  # Auto-expire after N hours


class BroadcastAlertRequest(BaseModel):
    """Request model for broadcasting an alert to all junctions."""
    alert_type: str
    severity: str
    message: str
    expires_in_hours: Optional[int] = 12


@router.post("/alerts", summary="Create a community alert")
async def create_community_alert(
    request: CreateAlertRequest,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """
    Create a new community alert.
    Requires admin API key for authorization.
    
    Alert types:
    - high_risk: High-risk driving behavior detected in area
    - emergency: Emergency situation (accident, fire, etc.)
    - congestion: Traffic congestion warning
    - accident: Accident reported
    - construction: Road construction/maintenance
    """
    # Simple API key validation (in production, use proper auth)
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    # Validate alert_type
    valid_types = ['high_risk', 'emergency', 'congestion', 'accident', 'construction', 'info']
    if request.alert_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid alert_type. Must be one of: {valid_types}")
    
    # Validate severity
    valid_severities = ['low', 'medium', 'high', 'critical']
    if request.severity not in valid_severities:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Must be one of: {valid_severities}")
    
    now = datetime.now()
    expires_at = None
    if request.expires_in_hours:
        expires_at = (now + timedelta(hours=request.expires_in_hours)).isoformat()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Ensure table exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS community_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                junction_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                created_by TEXT
            )
        """)
        
        cursor = await db.execute(
            """INSERT INTO community_alerts 
               (alert_type, severity, message, junction_id, timestamp, expires_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (request.alert_type, request.severity, request.message, 
             request.junction_id, now.isoformat(), expires_at, "admin")
        )
        await db.commit()
        alert_id = cursor.lastrowid
    
    return {
        "status": "created",
        "alert_id": alert_id,
        "alert_type": request.alert_type,
        "severity": request.severity,
        "message": request.message,
        "junction_id": request.junction_id,
        "expires_at": expires_at,
        "timestamp": now.isoformat(),
    }


@router.post("/alerts/broadcast", summary="Broadcast alert to all junctions")
async def broadcast_alert(
    request: BroadcastAlertRequest,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """
    Broadcast an alert to all monitored junctions.
    Requires admin API key for authorization.
    
    This creates the same alert for all junctions simultaneously.
    """
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    now = datetime.now()
    expires_at = None
    if request.expires_in_hours:
        expires_at = (now + timedelta(hours=request.expires_in_hours)).isoformat()
    
    # Get all junction IDs
    junction_ids = ["main"]  # Default
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        
        # Check if junction_safety table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='junction_safety'"
        )
        if await cursor.fetchone():
            cursor = await db.execute("SELECT DISTINCT junction_id FROM junction_safety")
            rows = await cursor.fetchall()
            if rows:
                junction_ids = [r["junction_id"] for r in rows]
        
        # Create alerts table if needed
        await db.execute("""
            CREATE TABLE IF NOT EXISTS community_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                junction_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                created_by TEXT
            )
        """)
        
        # Insert alert for each junction
        created_ids = []
        for junction_id in junction_ids:
            cursor = await db.execute(
                """INSERT INTO community_alerts 
                   (alert_type, severity, message, junction_id, timestamp, expires_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (request.alert_type, request.severity, request.message, 
                 junction_id, now.isoformat(), expires_at, "admin_broadcast")
            )
            created_ids.append(cursor.lastrowid)
        
        await db.commit()
    
    return {
        "status": "broadcast",
        "alert_ids": created_ids,
        "junctions_affected": junction_ids,
        "alert_type": request.alert_type,
        "severity": request.severity,
        "message": request.message,
        "expires_at": expires_at,
        "timestamp": now.isoformat(),
    }


@router.delete("/alerts/{alert_id}", summary="Delete a community alert")
async def delete_community_alert(
    alert_id: int,
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """Delete a specific community alert."""
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM community_alerts WHERE id = ?",
            (alert_id,)
        )
        await db.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"status": "deleted", "alert_id": alert_id}


@router.post("/alerts/clear-expired", summary="Clear all expired alerts")
async def clear_expired_alerts(
    admin_key: str = Query(..., description="Admin API key for authorization"),
):
    """Remove all expired community alerts from the database."""
    if admin_key != "itms-admin-2024":
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    now = datetime.now().isoformat()
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM community_alerts WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,)
        )
        await db.commit()
        deleted_count = cursor.rowcount
    
    return {
        "status": "cleared",
        "deleted_count": deleted_count,
        "timestamp": now,
    }


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def init_community_tables():
    """Initialize community-related database tables."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS community_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                junction_id TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                created_by TEXT
            )
        """)
        await db.commit()
