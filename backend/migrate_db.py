"""
Database Migration Script for Intelligent Traffic Management System
=====================================================================
Adds new tables for Members 1, 2, 3, and 4 features without deleting existing data.

Usage:
    python migrate_db.py

Tables Added:
- dynamic_fines (Member 1: Dynamic Fine Calculation)
- grace_period_warnings (Member 1: Grace Period System)
- junction_safety (Member 2: LiveSafeScore)
- lane_weaving_events (Member 2: Lane Weaving Detection)
- community_alerts (Member 2: Community Feedback)
- emergency_overrides (Member 3: Emergency Mode Logging)
- signal_timing_history (Member 3: Fuzzy Logic Decisions)
- risk_scores (Member 4: Accident Risk Prediction)
- abnormal_behavior_log (Member 4: Behavior Detection)
- incident_reports (Member 4: Auto-Generated Incidents)
- admin_users (Flutter Web Authentication)
- driver_users (Flutter Mobile Authentication)
- driver_notifications (Push Notifications)
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent / "traffic.db"


def get_connection():
    """Get database connection."""
    return sqlite3.connect(str(DB_PATH))


def table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def create_member1_tables(cursor):
    """
    Member 1: Dynamic Fines & Parking Violations
    - dynamic_fines: Stores calculated fines with breakdown
    - grace_period_warnings: Tracks pre-violation warnings
    """
    
    # Dynamic Fines Table
    if not table_exists(cursor, 'dynamic_fines'):
        cursor.execute("""
            CREATE TABLE dynamic_fines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                violation_id INTEGER NOT NULL,
                zone_type TEXT NOT NULL,
                base_penalty REAL NOT NULL,
                duration_seconds INTEGER NOT NULL,
                duration_penalty REAL NOT NULL,
                traffic_impact INTEGER NOT NULL,
                impact_penalty REAL NOT NULL,
                total_fine REAL NOT NULL,
                payment_status TEXT DEFAULT 'unpaid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (violation_id) REFERENCES violations(id)
            )
        """)
        print("[OK] Created table: dynamic_fines")
    else:
        print("[SKIP] Table already exists: dynamic_fines")
    
    # Grace Period Warnings Table
    if not table_exists(cursor, 'grace_period_warnings'):
        cursor.execute("""
            CREATE TABLE grace_period_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                plate_number TEXT,
                zone_type TEXT NOT NULL,
                warning_start TIMESTAMP NOT NULL,
                warning_level INTEGER DEFAULT 1,
                vehicle_moved BOOLEAN DEFAULT FALSE,
                violation_recorded BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: grace_period_warnings")
    else:
        print("[SKIP] Table already exists: grace_period_warnings")


def create_member2_tables(cursor):
    """
    Member 2: Junction Safety Scoring
    - junction_safety: LiveSafeScore data
    - lane_weaving_events: Detected weaving incidents
    - community_alerts: Anonymized community notifications
    """
    
    # Junction Safety Table
    if not table_exists(cursor, 'junction_safety'):
        cursor.execute("""
            CREATE TABLE junction_safety (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                junction_id TEXT NOT NULL DEFAULT 'main',
                safety_score INTEGER NOT NULL CHECK(safety_score >= 0 AND safety_score <= 100),
                last_violation_type TEXT,
                last_violation_severity INTEGER,
                violations_last_hour INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert default junction
        cursor.execute("""
            INSERT INTO junction_safety (junction_id, safety_score) VALUES ('main', 100)
        """)
        print("[OK] Created table: junction_safety (with default junction)")
    else:
        print("[SKIP] Table already exists: junction_safety")
    
    # Lane Weaving Events Table
    if not table_exists(cursor, 'lane_weaving_events'):
        cursor.execute("""
            CREATE TABLE lane_weaving_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                plate_number TEXT,
                avg_x_velocity REAL NOT NULL,
                direction_changes INTEGER NOT NULL,
                duration_frames INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: lane_weaving_events")
    else:
        print("[SKIP] Table already exists: lane_weaving_events")
    
    # Community Alerts Table
    if not table_exists(cursor, 'community_alerts'):
        cursor.execute("""
            CREATE TABLE community_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                junction_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                safety_score_at_time INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: community_alerts")
    else:
        print("[SKIP] Table already exists: community_alerts")


def create_member3_tables(cursor):
    """
    Member 3: Adaptive Traffic Signals
    - emergency_overrides: Logs emergency mode activations
    - signal_timing_history: Fuzzy logic decision history
    """
    
    # Emergency Overrides Table
    if not table_exists(cursor, 'emergency_overrides'):
        cursor.execute("""
            CREATE TABLE emergency_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_type TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                lane TEXT NOT NULL DEFAULT 'north',
                override_start TIMESTAMP NOT NULL,
                override_end TIMESTAMP,
                duration_seconds INTEGER,
                signal_state_before TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: emergency_overrides")
    else:
        print("[SKIP] Table already exists: emergency_overrides")
    
    # Signal Timing History Table
    if not table_exists(cursor, 'signal_timing_history'):
        cursor.execute("""
            CREATE TABLE signal_timing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lane TEXT NOT NULL,
                vehicle_count INTEGER NOT NULL,
                traffic_level TEXT NOT NULL,
                green_duration INTEGER NOT NULL,
                yellow_duration INTEGER NOT NULL DEFAULT 3,
                red_duration INTEGER NOT NULL,
                emergency_mode BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: signal_timing_history")
    else:
        print("[SKIP] Table already exists: signal_timing_history")


def create_member4_tables(cursor):
    """
    Member 4: Accident Risk Prediction
    - risk_scores: Vehicle risk score calculations
    - abnormal_behavior_log: Detected dangerous behaviors
    - incident_reports: Auto-generated incident records
    """
    
    # Risk Scores Table
    if not table_exists(cursor, 'risk_scores'):
        cursor.execute("""
            CREATE TABLE risk_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                plate_number TEXT,
                risk_score REAL NOT NULL CHECK(risk_score >= 0 AND risk_score <= 100),
                speed_factor REAL NOT NULL,
                violation_history_factor REAL NOT NULL,
                risk_level TEXT NOT NULL,
                current_speed REAL,
                speed_limit REAL DEFAULT 60.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: risk_scores")
    else:
        print("[SKIP] Table already exists: risk_scores")
    
    # Abnormal Behavior Log Table
    if not table_exists(cursor, 'abnormal_behavior_log'):
        cursor.execute("""
            CREATE TABLE abnormal_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                plate_number TEXT,
                behavior_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: abnormal_behavior_log")
    else:
        print("[SKIP] Table already exists: abnormal_behavior_log")
    
    # Incident Reports Table
    if not table_exists(cursor, 'incident_reports'):
        cursor.execute("""
            CREATE TABLE incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_type TEXT NOT NULL,
                risk_score_at_time REAL,
                vehicles_involved TEXT,
                description TEXT,
                evidence_path TEXT,
                auto_generated BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: incident_reports")
    else:
        print("[SKIP] Table already exists: incident_reports")


def create_user_tables(cursor):
    """
    User Authentication Tables for Flutter Apps
    - admin_users: Web dashboard authentication
    - driver_users: Mobile app authentication
    - driver_notifications: Push notification queue
    """
    
    # Admin Users Table
    if not table_exists(cursor, 'admin_users'):
        cursor.execute("""
            CREATE TABLE admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert default admin user (password: admin123)
        # In production, use proper password hashing!
        cursor.execute("""
            INSERT INTO admin_users (username, password_hash, role) 
            VALUES ('admin', 'admin123', 'admin')
        """)
        print("[OK] Created table: admin_users (with default admin)")
    else:
        print("[SKIP] Table already exists: admin_users")
    
    # Driver Users Table
    if not table_exists(cursor, 'driver_users'):
        cursor.execute("""
            CREATE TABLE driver_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT,
                license_number TEXT,
                vehicle_plates TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Created table: driver_users")
    else:
        print("[SKIP] Table already exists: driver_users")
    
    # Driver Notifications Table
    if not table_exists(cursor, 'driver_notifications'):
        cursor.execute("""
            CREATE TABLE driver_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (driver_id) REFERENCES driver_users(id)
            )
        """)
        print("[OK] Created table: driver_notifications")
    else:
        print("[SKIP] Table already exists: driver_notifications")


def run_migration():
    """Run the complete database migration."""
    print("=" * 60)
    print("DATABASE MIGRATION - Intelligent Traffic Management System")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    if not DB_PATH.exists():
        print("[WARNING] Database file not found. Creating new database...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"Existing tables: {existing_tables}\n")
        
        print("-" * 60)
        print("MEMBER 1: Dynamic Fines & Parking Violations")
        print("-" * 60)
        create_member1_tables(cursor)
        
        print()
        print("-" * 60)
        print("MEMBER 2: Junction Safety Scoring")
        print("-" * 60)
        create_member2_tables(cursor)
        
        print()
        print("-" * 60)
        print("MEMBER 3: Adaptive Traffic Signals")
        print("-" * 60)
        create_member3_tables(cursor)
        
        print()
        print("-" * 60)
        print("MEMBER 4: Accident Risk Prediction")
        print("-" * 60)
        create_member4_tables(cursor)
        
        print()
        print("-" * 60)
        print("USER AUTHENTICATION TABLES")
        print("-" * 60)
        create_user_tables(cursor)
        
        # Commit all changes
        conn.commit()
        
        # Show final table list
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        final_tables = [row[0] for row in cursor.fetchall()]
        
        print()
        print("=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"\nTotal tables: {len(final_tables)}")
        print("Tables:")
        for t in final_tables:
            print(f"  - {t}")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
