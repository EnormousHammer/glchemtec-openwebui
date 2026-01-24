#!/usr/bin/env python3
"""
Set OpenWebUI default OpenAI connection to use localhost:8000 proxy.
This runs on startup to ensure the connection is always configured correctly.
"""
import os
import sys
import json
from pathlib import Path

# OpenWebUI data directory
DATA_DIR = Path("/app/backend/data")
CONNECTIONS_FILE = DATA_DIR / "connections.json"

def set_default_connection():
    """Set default OpenAI connection to localhost:8000 if not already set."""
    proxy_url = os.environ.get("OPENAI_API_BASE_URLS", "http://localhost:8000/v1")
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing connections or create new
    connections = []
    if CONNECTIONS_FILE.exists():
        try:
            with open(CONNECTIONS_FILE, "r") as f:
                connections = json.load(f)
        except:
            connections = []
    
    # Check if OpenAI connection already exists
    openai_conn = None
    for conn in connections:
        if conn.get("type") == "openai" or "openai" in conn.get("name", "").lower():
            openai_conn = conn
            break
    
    # Update or create OpenAI connection
    if openai_conn:
        openai_conn["base_url"] = proxy_url
        openai_conn["api_key"] = os.environ.get("OPENAI_API_KEY", "")
        print(f"[CONFIG] Updated existing OpenAI connection to: {proxy_url}")
    else:
        connections.append({
            "id": "default-openai",
            "name": "OpenAI (Proxy)",
            "type": "openai",
            "base_url": proxy_url,
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "models": []
        })
        print(f"[CONFIG] Created new OpenAI connection: {proxy_url}")
    
    # Save connections
    with open(CONNECTIONS_FILE, "w") as f:
        json.dump(connections, f, indent=2)
    
    print(f"[CONFIG] Default OpenAI connection set to: {proxy_url}")

if __name__ == "__main__":
    try:
        set_default_connection()
    except Exception as e:
        print(f"[CONFIG] Error setting default connection: {e}", file=sys.stderr)
        # Don't fail startup if this fails
        sys.exit(0)
