"""
Database Verification Script
Checks the SQLite database and TTS warnings to verify the system is working.
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from app.config import get_settings

# Paths
BACKEND_DIR = Path(__file__).parent
settings = get_settings()
DB_PATH = settings.db_path
TTS_WARNINGS_DIR = BACKEND_DIR / "app" / "tts" / "warnings"


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_database():
    """Check the SQLite database for violations and driver scores."""
    print_header("DATABASE CHECK")
    
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("   The system may not have recorded any violations yet.")
        return
    
    print(f"✅ Database found: {DB_PATH}")
    print(f"   Size: {DB_PATH.stat().st_size / 1024:.1f} KB")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n📋 Tables in database: {[t[0] for t in tables]}")
        
        # Check driver_violations table
        print_header("DRIVER VIOLATIONS (Last 5)")
        
        try:
            # Query driver_violations
            cursor.execute("""
                SELECT * FROM driver_violations 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            violations = cursor.fetchall()
            
            if violations:
                # Get column names
                cursor.execute("PRAGMA table_info(driver_violations)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"   Columns: {columns}")
                print()
                
                for i, row in enumerate(violations, 1):
                    row_dict = dict(zip(columns, row))
                    # Format timestamp for display
                    if 'timestamp' in row_dict and isinstance(row_dict['timestamp'], (int, float)):
                        row_dict['timestamp'] = datetime.fromtimestamp(row_dict['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                    print(f"   [{i}] {row_dict}")
            else:
                print("   No driver violations recorded yet.")
                print("   Tip: Let a vehicle sit in a parking zone for 15+ seconds, or simulate an emergency.")
        except sqlite3.OperationalError as e:
            print(f"   ⚠️ driver_violations table issue: {e}")
            print("   The system might be using 'violations' table instead.")
            
            # Fallback: Check violations table just in case
            try:
                print("\n   Checking fallback 'violations' table:")
                cursor.execute("SELECT * FROM violations LIMIT 5")
                data = cursor.fetchall()
                if data:
                    print(f"   Found {len(data)} records in 'violations'.")
                else:
                    print("   'violations' table exists but is empty.")
            except:
                pass
        
        # Check drivers table
        print_header("DRIVERS / SCORES (Last 5)")
        
        try:
            cursor.execute("""
                SELECT * FROM drivers 
                ORDER BY updated_at DESC 
                LIMIT 5
            """)
            drivers = cursor.fetchall()
            
            if drivers:
                cursor.execute("PRAGMA table_info(drivers)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"   Columns: {columns}")
                print()
                
                for i, row in enumerate(drivers, 1):
                    data = dict(zip(columns, row))
                    score = data.get('current_score', data.get('score', 'N/A'))
                    driver_id = data.get('driver_id', data.get('id', 'Unknown'))
                    print(f"   [{i}] Driver: {driver_id} | Score: {score}")
            else:
                print("   No driver records yet.")
        except sqlite3.OperationalError as e:
            print(f"   ⚠️ Drivers table issue: {e}")
        
        # Get statistics
        print_header("STATISTICS")
        
        try:
            cursor.execute("SELECT COUNT(*) FROM driver_violations")
            violation_count = cursor.fetchone()[0]
            print(f"   Total driver violations: {violation_count}")
        except:
             # Fallback
            try:
                cursor.execute("SELECT COUNT(*) FROM violations")
                violation_count = cursor.fetchone()[0]
                print(f"   Total 'raw' violations: {violation_count}")
            except:
                print("   Could not count violations")
        
        try:
            cursor.execute("SELECT COUNT(*) FROM drivers")
            driver_count = cursor.fetchone()[0]
            print(f"   Total drivers: {driver_count}")
        except:
            print("   Could not count drivers")
        
        try:
            cursor.execute("SELECT COUNT(*) FROM drivers WHERE current_score < 100")
            penalized_count = cursor.fetchone()[0]
            print(f"   Penalized drivers (score < 100): {penalized_count}")
        except:
            pass
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")


def check_tts_warnings():
    """Check the TTS warnings directory for generated audio files."""
    print_header("TTS WARNINGS CHECK")
    
    print(f"📁 Warnings directory: {TTS_WARNINGS_DIR}")
    
    if not TTS_WARNINGS_DIR.exists():
        print("❌ Warnings directory does not exist.")
        print("   TTS may not have generated any warnings yet.")
        print("   Run: python backend/app/tts/tts_service.py to test")
        return
    
    # Count audio files
    mp3_files = list(TTS_WARNINGS_DIR.glob("*.mp3"))
    wav_files = list(TTS_WARNINGS_DIR.glob("*.wav"))
    all_audio = mp3_files + wav_files
    
    print(f"✅ Directory exists")
    print(f"   MP3 files: {len(mp3_files)}")
    print(f"   WAV files: {len(wav_files)}")
    print(f"   Total audio files: {len(all_audio)}")
    
    if all_audio:
        print("\n   Recent files:")
        # Sort by modification time, newest first
        sorted_files = sorted(all_audio, key=lambda f: f.stat().st_mtime, reverse=True)
        
        for f in sorted_files[:5]:
            size = f.stat().st_size
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"      - {f.name} ({size} bytes) [{mtime}]")
        
        if len(sorted_files) > 5:
            print(f"      ... and {len(sorted_files) - 5} more files")
    else:
        print("\n   No audio files generated yet.")
        print("   Trigger a parking warning to generate audio.")


def check_scoring_engine():
    """Check if the scoring engine is working in memory."""
    print_header("SCORING ENGINE (In-Memory)")
    
    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from app.scoring import get_scoring_engine
        
        engine = get_scoring_engine()
        
        print(f"✅ Scoring engine loaded")
        print(f"   Initial score setting: {engine.initial_score}")
        print(f"   Drivers in memory: {len(engine.drivers)}")
        
        if engine.drivers:
            print("\n   In-memory driver scores:")
            for driver_id, driver in list(engine.drivers.items())[:5]:
                print(f"      - {driver_id}: {driver.current_score} pts ({driver.risk_level})")
        
        stats = engine.get_statistics()
        print(f"\n   Statistics: {stats}")
        
    except Exception as e:
        print(f"⚠️ Could not load scoring engine: {e}")


def main():
    """Run all checks."""
    print("\n" + "🔍" * 30)
    print("  INTELLIGENT TRAFFIC MANAGEMENT SYSTEM")
    print("  Database & TTS Verification Script")
    print("🔍" * 30)
    
    check_database()
    check_tts_warnings()
    check_scoring_engine()
    
    print_header("SUMMARY")
    print("""
   To trigger violations:
   1. Open http://127.0.0.1:8000/detect in browser
   2. Watch for vehicles in the video
   3. Vehicles that stay still for 5+ seconds get a WARNING
   4. Vehicles that stay still for 15+ seconds get a VIOLATION
   
   The RED BOXES on screen indicate NO PARKING zones.
   Vehicles inside these zones will trigger warnings/violations.
   Watch the console for [PENALTY] and [AUDIO] messages.
    """)


if __name__ == "__main__":
    main()
