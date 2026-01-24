#!/usr/bin/env python3
"""
Production-safe script to enforce OpenAI connection to localhost:8000 proxy.
Runs continuously to ensure connection never resets - critical for production.
"""
import os
import sys
import time
import sqlite3
import json
from pathlib import Path

PROXY_URL = os.environ.get("OPENAI_API_BASE_URLS", "http://localhost:8000/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "")

def enforce_connection():
    """Enforce OpenAI connection in database - production safe."""
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    if not DB_FILE.exists():
        return False
    
    try:
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        
        # Check if connection table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='connection'")
        if not cursor.fetchone():
            conn.close()
            return False
        
        connection_data = json.dumps({
            "base_url": PROXY_URL,
            "api_key": API_KEY,
            "models": []
        })
        
        # Check current connection
        cursor.execute("SELECT id, base_url FROM connection WHERE type = 'openai' LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            conn_id, current_url = row
            if current_url != PROXY_URL:
                # Connection was reset - fix it immediately
                cursor.execute(
                    "UPDATE connection SET data = ?, base_url = ? WHERE id = ?",
                    (connection_data, PROXY_URL, conn_id)
                )
                conn.commit()
                print(f"[CONFIG] ⚠️ Connection was reset to '{current_url}' - FIXED to: {PROXY_URL}")
                conn.close()
                return True
            # Already correct, no action needed
            conn.close()
            return True
        else:
            # No connection exists - create it
            import uuid
            cursor.execute(
                "INSERT INTO connection (id, name, type, data, base_url) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "OpenAI (Proxy)", "openai", connection_data, PROXY_URL)
            )
            conn.commit()
            print(f"[CONFIG] Created OpenAI connection: {PROXY_URL}")
            conn.close()
            return True
        
    except Exception as e:
        print(f"[CONFIG] Error: {e}", file=sys.stderr)
        return False

def main():
    """Run continuously to enforce connection - production safe."""
    print(f"[CONFIG] Starting connection enforcer - will keep {PROXY_URL} set")
    
    # Initial wait for database
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    for i in range(60):
        if DB_FILE.exists():
            break
        time.sleep(1)
    
    if not DB_FILE.exists():
        print(f"[CONFIG] Database not found after 60s")
        return
    
    # Wait for table
    time.sleep(5)
    
    # Set initial connection
    enforce_connection()
    
    # Run continuously - check every 2 minutes to prevent resets
    while True:
        time.sleep(120)  # Check every 2 minutes
        enforce_connection()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"[CONFIG] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
