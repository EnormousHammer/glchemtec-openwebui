#!/usr/bin/env python3
"""
Fix SQLite database to use WAL mode to prevent locking issues.
This must run before OpenWebUI starts accessing the database.
"""
import sqlite3
import time
from pathlib import Path

def fix_database_wal():
    """Set database to WAL mode to allow concurrent reads."""
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    # Wait for database to exist (OpenWebUI creates it on first startup)
    max_wait = 60
    for i in range(max_wait):
        if DB_FILE.exists():
            break
        time.sleep(1)
    
    if not DB_FILE.exists():
        print("[DB-FIX] Database not found yet - will be set to WAL when it's created")
        return False
    
    try:
        # Connect with timeout and WAL mode
        conn = sqlite3.connect(str(DB_FILE), timeout=30.0, check_same_thread=False)
        
        # Set WAL mode (allows concurrent reads, prevents locks)
        conn.execute("PRAGMA journal_mode=WAL")
        result = conn.execute("PRAGMA journal_mode").fetchone()
        
        if result and result[0].upper() == "WAL":
            print(f"[DB-FIX] Database set to WAL mode successfully")
            conn.close()
            return True
        else:
            print(f"[DB-FIX] WARNING: Could not set WAL mode, got: {result}")
            conn.close()
            return False
            
    except Exception as e:
        print(f"[DB-FIX] ERROR setting WAL mode: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run multiple times to ensure it sticks (OpenWebUI might reset it)
    for i in range(3):
        if fix_database_wal():
            break
        time.sleep(2)
