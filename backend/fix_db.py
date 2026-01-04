import aiosqlite
import asyncio

async def fix_all():
    db = await aiosqlite.connect('traffic.db')
    
    # List all tables
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = await cursor.fetchall()
    print('Existing tables:', [t[0] for t in tables])
    
    # Create drivers table if not exists
    await db.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id TEXT PRIMARY KEY,
            current_score INTEGER DEFAULT 100,
            total_violations INTEGER DEFAULT 0,
            total_fines REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('Created/verified drivers table')
    
    # Create driver_users table if not exists  
    await db.execute('''
        CREATE TABLE IF NOT EXISTS driver_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plate_number TEXT,
            name TEXT,
            license_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    print('Created/verified driver_users table')
    
    # Create admin_users table if not exists
    await db.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    print('Created/verified admin_users table')
    
    # Create violations table if not exists
    await db.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT,
            violation_type TEXT,
            severity INTEGER DEFAULT 1,
            fine_amount REAL DEFAULT 0,
            location TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT,
            video_path TEXT,
            processed INTEGER DEFAULT 0,
            FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
        )
    ''')
    print('Created/verified violations table')
    
    await db.commit()
    
    # Verify all tables
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = await cursor.fetchall()
    print('Final tables:', [t[0] for t in tables])
    
    await db.close()
    print('All database tables fixed!')

asyncio.run(fix_all())
