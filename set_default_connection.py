#!/usr/bin/env python3
"""
Set OpenWebUI default OpenAI connection to use localhost:8000 proxy.
Modifies SQLite database directly to ensure connection persists.
"""
import os
import sys
import sqlite3
import json
from pathlib import Path

def set_default_connection():
    """Set default OpenAI connection in OpenWebUI SQLite database."""
    proxy_url = os.environ.get("OPENAI_API_BASE_URLS", "http://localhost:8000/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    # OpenWebUI database location
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # If database doesn't exist yet, OpenWebUI will create it
    # We'll set it after OpenWebUI initializes
    if not DB_FILE.exists():
        print(f"[CONFIG] Database not found yet, will be set after OpenWebUI initializes")
        print(f"[CONFIG] OPENAI_API_BASE_URLS={proxy_url} is set - OpenWebUI should use this")
        return
    
    try:
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        
        # Check if connections table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='connection'")
        if not cursor.fetchone():
            print(f"[CONFIG] Connections table not found yet")
            conn.close()
            return
        
        # Check for existing OpenAI connection
        cursor.execute("SELECT id, data FROM connection WHERE type = 'openai' OR name LIKE '%openai%' LIMIT 1")
        row = cursor.fetchone()
        
        connection_data = {
            "base_url": proxy_url,
            "api_key": api_key,
            "models": []
        }
        
        if row:
            # Update existing connection
            conn_id, existing_data = row
            try:
                data = json.loads(existing_data) if existing_data else {}
            except:
                data = {}
            data.update(connection_data)
            
            cursor.execute(
                "UPDATE connection SET data = ?, base_url = ? WHERE id = ?",
                (json.dumps(data), proxy_url, conn_id)
            )
            print(f"[CONFIG] Updated existing OpenAI connection to: {proxy_url}")
        else:
            # Create new connection
            import uuid
            conn_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO connection (id, name, type, data, base_url) VALUES (?, ?, ?, ?, ?)",
                (conn_id, "OpenAI (Proxy)", "openai", json.dumps(connection_data), proxy_url)
            )
            print(f"[CONFIG] Created new OpenAI connection: {proxy_url}")
        
        conn.commit()
        conn.close()
        print(f"[CONFIG] Default OpenAI connection set to: {proxy_url}")
        
    except Exception as e:
        print(f"[CONFIG] Error accessing database: {e}", file=sys.stderr)
        print(f"[CONFIG] OPENAI_API_BASE_URLS={proxy_url} is set - OpenWebUI should use this via env var")

if __name__ == "__main__":
    try:
        set_default_connection()
    except Exception as e:
        print(f"[CONFIG] Error: {e}", file=sys.stderr)
        sys.exit(0)
