#!/usr/bin/env python3
"""
Background script to set OpenAI connection after OpenWebUI starts.
Runs in background and waits for database to be ready.
"""
import os
import sys
import time
import sqlite3
import json
from pathlib import Path

def set_connection():
    """Set OpenAI connection in database once it's ready."""
    proxy_url = os.environ.get("OPENAI_API_BASE_URLS", "http://localhost:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    # Wait up to 60 seconds for database to be created
    for i in range(60):
        if DB_FILE.exists():
            break
        time.sleep(1)
    
    if not DB_FILE.exists():
        print(f"[CONFIG] Database not found after 60s, skipping connection setup")
        return
    
    # Wait a bit more for table to be created
    time.sleep(5)
    
    try:
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        
        # Check if connection table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='connection'")
        if not cursor.fetchone():
            print(f"[CONFIG] Connection table not ready yet")
            conn.close()
            return
        
        # Set connection
        connection_data = json.dumps({
            "base_url": proxy_url,
            "api_key": api_key,
            "models": []
        })
        
        # Update or insert
        cursor.execute("SELECT id FROM connection WHERE type = 'openai' LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            cursor.execute(
                "UPDATE connection SET data = ?, base_url = ? WHERE type = 'openai'",
                (connection_data, proxy_url)
            )
            print(f"[CONFIG] Updated OpenAI connection to: {proxy_url}")
        else:
            import uuid
            cursor.execute(
                "INSERT INTO connection (id, name, type, data, base_url) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "OpenAI (Proxy)", "openai", connection_data, proxy_url)
            )
            print(f"[CONFIG] Created OpenAI connection: {proxy_url}")
        
        conn.commit()
        conn.close()
        print(f"[CONFIG] Connection configured successfully")
        
    except Exception as e:
        print(f"[CONFIG] Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    set_connection()
