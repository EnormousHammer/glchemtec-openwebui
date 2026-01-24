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

def discover_schema(cursor):
    """Discover actual database schema - no guessing."""
    print("[CONFIG] Discovering database schema...")
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in cursor.fetchall()]
    print(f"[CONFIG] Found tables: {all_tables}")
    
    # Find connection-related tables
    connection_tables = [t for t in all_tables if 'connection' in t.lower() or 'api' in t.lower()]
    
    for table_name in connection_tables:
        print(f"[CONFIG] Examining table: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # Log full schema
        print(f"[CONFIG] Schema for {table_name}:")
        for col in columns:
            print(f"[CONFIG]   - {col[1]} ({col[2]})")
        
        # Check if this looks like a connection table
        col_names = [col[1] for col in columns]
        if 'type' in col_names or 'connection_type' in col_names:
            return table_name, col_names
    
    return None, None

def enforce_connection():
    """Enforce OpenAI connection - discovers actual schema first."""
    DATA_DIR = Path("/app/backend/data")
    DB_FILE = DATA_DIR / "webui.db"
    
    if not DB_FILE.exists():
        print(f"[CONFIG] Database not found: {DB_FILE}")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        
        # Discover actual schema
        table_name, columns = discover_schema(cursor)
        
        if not table_name:
            print("[CONFIG] No connection table found. Cannot set connection.")
            conn.close()
            return False
        
        # Build query based on actual columns
        connection_data = json.dumps({
            "base_url": PROXY_URL,
            "api_key": API_KEY,
            "models": []
        })
        
        # Find type column
        type_col = "type" if "type" in columns else ("connection_type" if "connection_type" in columns else None)
        if not type_col:
            print(f"[CONFIG] No type column found in {table_name}. Columns: {columns}")
            conn.close()
            return False
        
        # Delete existing OpenAI connections
        cursor.execute(f"DELETE FROM {table_name} WHERE {type_col} = 'openai'")
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"[CONFIG] Removed {deleted} existing OpenAI connection(s)")
        
        # Build INSERT based on actual columns
        import uuid
        conn_id = str(uuid.uuid4())
        
        # Determine which columns to use
        insert_cols = []
        insert_vals = []
        
        if "id" in columns:
            insert_cols.append("id")
            insert_vals.append(conn_id)
        
        if "name" in columns:
            insert_cols.append("name")
            insert_vals.append("OpenAI (Proxy)")
        
        insert_cols.append(type_col)
        insert_vals.append("openai")
        
        if "data" in columns:
            insert_cols.append("data")
            insert_vals.append(connection_data)
        
        if "base_url" in columns:
            insert_cols.append("base_url")
            insert_vals.append(PROXY_URL)
        elif "baseUrl" in columns:
            insert_cols.append("baseUrl")
            insert_vals.append(PROXY_URL)
        elif "url" in columns:
            insert_cols.append("url")
            insert_vals.append(PROXY_URL)
        
        # Execute INSERT
        placeholders = ", ".join(["?"] * len(insert_vals))
        col_names = ", ".join(insert_cols)
        query = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
        
        print(f"[CONFIG] Executing: {query}")
        print(f"[CONFIG] Values: {insert_vals}")
        
        cursor.execute(query, insert_vals)
        conn.commit()
        print(f"[CONFIG] ✅ Connection enforced: {PROXY_URL}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"[CONFIG] Error: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
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
