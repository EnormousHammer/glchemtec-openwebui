#!/usr/bin/env python3
"""
Monitor Render service status and events in real-time.
Run this while testing to see deployment/build events.
"""

import time
import requests
import json
from datetime import datetime

# Configuration
RENDER_API_BASE = "https://api.render.com/v1"
SERVICE_ID = "srv-d5li9q7gi27c738ts6ug"
API_KEY = "rnd_v09UaSigC2P2SF4yRIeZ7fC4RmMB"

def get_service_status():
    """Get current service status."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    
    try:
        url = f"{RENDER_API_BASE}/services/{SERVICE_ID}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error getting status: {e}")
    return None

def get_recent_events(limit=5):
    """Get recent events."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    
    try:
        url = f"{RENDER_API_BASE}/services/{SERVICE_ID}/events"
        params = {"limit": limit}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("events", [])
    except Exception as e:
        print(f"Error getting events: {e}")
    return []

def format_event(event):
    """Format event for display."""
    if isinstance(event, dict):
        event_data = event.get("event", event)
        event_type = event_data.get("type", "unknown")
        timestamp = event_data.get("timestamp", "")
        details = event_data.get("details", {})
        
        # Format timestamp
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime("%H:%M:%S")
            else:
                time_str = "N/A"
        except:
            time_str = timestamp[:19] if timestamp else "N/A"
        
        # Format based on type
        if event_type == "deploy_ended":
            status = details.get("deployStatus", "unknown")
            return f"[{time_str}] Deploy {status.upper()}"
        elif event_type == "build_ended":
            status = details.get("buildStatus", "unknown")
            return f"[{time_str}] Build {status.upper()}"
        elif event_type == "deploy_started":
            return f"[{time_str}] Deploy STARTED"
        elif event_type == "build_started":
            return f"[{time_str}] Build STARTED"
        else:
            return f"[{time_str}] {event_type}"
    
    return str(event)

def main():
    """Monitor service."""
    print("=" * 80)
    print("Render Service Monitor - glchemtec-openwebui")
    print("=" * 80)
    print("Monitoring service status and events...")
    print("Press Ctrl+C to stop\n")
    
    last_events = set()
    
    try:
        while True:
            # Get service status
            service_data = get_service_status()
            if service_data:
                service = service_data.get("service", {})
                status = service.get("suspendedInitiator", "active")
                service_type = service.get("type", "web")
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Service Status: {status.upper()} ({service_type})")
            
            # Get recent events
            events = get_recent_events(limit=3)
            current_events = {str(e) for e in events}
            
            # Show new events
            new_events = current_events - last_events
            if new_events:
                print("\n--- New Events ---")
                for event_str in new_events:
                    # Find the actual event object
                    for event in events:
                        if str(event) == event_str:
                            print(f"  {format_event(event)}")
                            break
                print("---\n")
            
            last_events = current_events
            
            # Wait before next check
            time.sleep(10)  # Check every 10 seconds
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
