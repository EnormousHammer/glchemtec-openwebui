#!/usr/bin/env python3
"""
Script to retrieve and analyze Render service logs.
Requires Render API key.
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Render API configuration
RENDER_API_BASE = "https://api.render.com/v1"
SERVICE_NAME = "glchemtec-openwebui"  # Update if different
SERVICE_ID = "srv-d5li9q7gi27c738ts6ug"  # Known service ID for glchemtec-openwebui

# Default API key (can be overridden by environment variable)
DEFAULT_API_KEY = "rnd_v09UaSigC2P2SF4yRIeZ7fC4RmMB"

def get_api_key() -> Optional[str]:
    """Get Render API key from environment, file, or use default."""
    # Try environment variable first
    api_key = os.environ.get("RENDER_API_KEY")
    
    # Try reading from RENDER_API_KEY.md file
    if not api_key:
        try:
            if os.path.exists("RENDER_API_KEY.md"):
                with open("RENDER_API_KEY.md", "r") as f:
                    content = f.read()
                    # Extract key from file (look for pattern)
                    import re
                    match = re.search(r'`([^`]+)`', content)
                    if match:
                        api_key = match.group(1)
        except Exception:
            pass
    
    # Use default if available
    if not api_key and 'DEFAULT_API_KEY' in globals():
        api_key = DEFAULT_API_KEY
    
    # Last resort: prompt user
    if not api_key:
        print("RENDER_API_KEY not found in environment or file.")
        print("Get your API key from: https://dashboard.render.com/account/api-keys")
        api_key = input("Enter your Render API key (or press Enter to skip): ").strip()
        if not api_key:
            return None
    
    return api_key

def get_service_id(api_key: str) -> Optional[str]:
    """Get service ID from service name."""
    # If we have a hardcoded service ID, use it
    if 'SERVICE_ID' in globals() and SERVICE_ID:
        print(f"Using known service ID: {SERVICE_ID}")
        return SERVICE_ID
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        # List all services
        response = requests.get(f"{RENDER_API_BASE}/services", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, list):
            services = data
        elif isinstance(data, dict) and "services" in data:
            services = data["services"]
        else:
            print(f"Unexpected API response format: {type(data)}")
            print(f"Response: {data}")
            services = []
        
        # Find our service (case-insensitive, exact or partial match)
        target_lower = SERVICE_NAME.lower().strip()
        best_match = None
        best_score = 0
        
        for service in services:
            # Handle different service object structures
            if isinstance(service, dict):
                service_name = str(service.get("name") or "").strip()
                service_id = service.get("id") or service.get("service", {}).get("id")
            else:
                continue
                
            if not service_name or not service_id:
                continue
                
            service_name_lower = service_name.lower().strip()
            
            # Score matches (exact match = highest priority)
            score = 0
            if service_name_lower == target_lower:
                score = 100  # Exact match
            elif target_lower in service_name_lower:
                score = 50   # Contains target
            elif service_name_lower in target_lower:
                score = 45   # Target contains service name
            elif "openwebui" in service_name_lower and "glchemtec" in service_name_lower:
                score = 30   # Has both keywords
            elif "openwebui" in service_name_lower:
                score = 20   # Has openwebui
            
            if score > best_score:
                best_score = score
                best_match = (service_name, service_id)
        
        if best_match:
            print(f"Found matching service: {best_match[0]} (ID: {best_match[1]})")
            return best_match[1]
        
        # Fallback: just return first service if we have one
        if services and len(services) > 0:
            first_service = services[0]
            if isinstance(first_service, dict):
                service_id = first_service.get("id") or first_service.get("service", {}).get("id")
                service_name = first_service.get("name", "Unknown")
                if service_id:
                    print(f"Using first available service: {service_name} (ID: {service_id})")
                    return service_id
        
        print(f"Service '{SERVICE_NAME}' not found.")
        print("Available services:")
        for service in services[:10]:  # Show first 10
            name = service.get('name') or service.get('service', {}).get('name', 'Unknown')
            service_id = service.get('id') or service.get('service', {}).get('id', 'Unknown')
            print(f"  - {name} (ID: {service_id})")
        
        # Auto-select first service if only one, or first OpenWebUI-related
        if len(services) == 1:
            service_id = services[0].get('id') or services[0].get('service', {}).get('id')
            if service_id:
                print(f"\nAuto-selecting only available service: {services[0].get('name', 'Unknown')}")
                return service_id
        
        # Try to find any service with "web" in the type
        for service in services:
            service_type = service.get('type', '').lower()
            if 'web' in service_type:
                service_id = service.get('id') or service.get('service', {}).get('id')
                if service_id:
                    print(f"\nAuto-selecting web service: {service.get('name', 'Unknown')}")
                    return service_id
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching services: {e}")
        return None

def get_logs(api_key: str, service_id: str, limit: int = 100) -> List[Dict]:
    """Retrieve logs from Render service."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    # Try different API endpoints
    endpoints = [
        f"{RENDER_API_BASE}/services/{service_id}/logs",
        f"{RENDER_API_BASE}/services/{service_id}/logs?limit={limit}",
        f"https://api.render.com/v1/services/{service_id}/logs?limit={limit}&tail=true",
    ]
    
    for url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("logs", data.get("data", []))
                return []
        except requests.exceptions.RequestException:
            continue
    
    # If all endpoints fail, return empty
    return []

def analyze_logs(logs: List[Dict]) -> Dict:
    """Analyze logs for errors and issues."""
    analysis = {
        "total_logs": len(logs),
        "errors": [],
        "warnings": [],
        "startup_issues": [],
        "filter_issues": [],
        "import_errors": [],
        "database_errors": [],
        "proxy_issues": []
    }
    
    error_keywords = ["error", "exception", "traceback", "failed", "failure"]
    warning_keywords = ["warning", "warn"]
    startup_keywords = ["starting", "startup", "initialization"]
    filter_keywords = ["filter", "export-filter", "ppt-pdf-vision"]
    import_keywords = ["import", "modulenotfound", "importerror"]
    db_keywords = ["database", "db", "sql", "migration"]
    proxy_keywords = ["proxy", "8000", "uvicorn", "responses_proxy"]
    
    for log_entry in logs:
        message = log_entry.get("message", "").lower()
        level = log_entry.get("level", "").lower()
        
        # Check for errors
        if any(keyword in message for keyword in error_keywords) or level == "error":
            analysis["errors"].append(log_entry)
            
            # Categorize errors
            if any(keyword in message for keyword in import_keywords):
                analysis["import_errors"].append(log_entry)
            if any(keyword in message for keyword in db_keywords):
                analysis["database_errors"].append(log_entry)
            if any(keyword in message for keyword in filter_keywords):
                analysis["filter_issues"].append(log_entry)
            if any(keyword in message for keyword in proxy_keywords):
                analysis["proxy_issues"].append(log_entry)
        
        # Check for warnings
        if any(keyword in message for keyword in warning_keywords) or level == "warning":
            analysis["warnings"].append(log_entry)
        
        # Check for startup issues
        if any(keyword in message for keyword in startup_keywords):
            if any(err in message for err in error_keywords):
                analysis["startup_issues"].append(log_entry)
    
    return analysis

def print_analysis(analysis: Dict):
    """Print analysis results."""
    print("\n" + "=" * 80)
    print("LOG ANALYSIS RESULTS")
    print("=" * 80)
    
    print(f"\nTotal logs analyzed: {analysis['total_logs']}")
    
    # Errors
    if analysis["errors"]:
        print(f"\n[CRITICAL] Found {len(analysis['errors'])} error(s):")
        for i, error in enumerate(analysis["errors"][:10], 1):  # Show first 10
            timestamp = error.get("timestamp", "N/A")
            message = error.get("message", "")[:200]  # Truncate long messages
            print(f"  {i}. [{timestamp}] {message}")
        if len(analysis["errors"]) > 10:
            print(f"  ... and {len(analysis['errors']) - 10} more errors")
    else:
        print("\n[OK] No errors found")
    
    # Import errors
    if analysis["import_errors"]:
        print(f"\n[ISSUE] Found {len(analysis['import_errors'])} import error(s):")
        for error in analysis["import_errors"][:5]:
            print(f"  - {error.get('message', '')[:150]}")
    
    # Database errors
    if analysis["database_errors"]:
        print(f"\n[ISSUE] Found {len(analysis['database_errors'])} database error(s):")
        for error in analysis["database_errors"][:5]:
            print(f"  - {error.get('message', '')[:150]}")
    
    # Filter issues
    if analysis["filter_issues"]:
        print(f"\n[ISSUE] Found {len(analysis['filter_issues'])} filter-related error(s):")
        for error in analysis["filter_issues"][:5]:
            print(f"  - {error.get('message', '')[:150]}")
    
    # Proxy issues
    if analysis["proxy_issues"]:
        print(f"\n[ISSUE] Found {len(analysis['proxy_issues'])} proxy-related error(s):")
        for error in analysis["proxy_issues"][:5]:
            print(f"  - {error.get('message', '')[:150]}")
    
    # Startup issues
    if analysis["startup_issues"]:
        print(f"\n[ISSUE] Found {len(analysis['startup_issues'])} startup error(s):")
        for error in analysis["startup_issues"][:5]:
            print(f"  - {error.get('message', '')[:150]}")
    
    # Warnings
    if analysis["warnings"]:
        print(f"\n[WARNING] Found {len(analysis['warnings'])} warning(s):")
        for warning in analysis["warnings"][:5]:
            print(f"  - {warning.get('message', '')[:150]}")
    
    print("\n" + "=" * 80)

def save_logs_to_file(logs: List[Dict], filename: str = "render_logs.json"):
    """Save logs to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, default=str)
        print(f"\n[OK] Logs saved to {filename}")
    except Exception as e:
        print(f"\n[ERROR] Failed to save logs: {e}")

def main():
    """Main function."""
    print("=" * 80)
    print("Render Logs Retriever and Analyzer")
    print("=" * 80)
    
    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("\n[ERROR] API key required. Exiting.")
        print("\nTo get your API key:")
        print("1. Go to https://dashboard.render.com/account/api-keys")
        print("2. Create a new API key")
        print("3. Set it as environment variable: export RENDER_API_KEY=your_key")
        sys.exit(1)
    
    # Get service ID
    print(f"\n[1/3] Finding service '{SERVICE_NAME}'...")
    service_id = get_service_id(api_key)
    if not service_id:
        print("\n[ERROR] Could not find service. Exiting.")
        sys.exit(1)
    print(f"[OK] Found service ID: {service_id}")
    
    # Get logs
    print(f"\n[2/3] Retrieving logs for service {service_id}...")
    logs = get_logs(api_key, service_id, limit=200)
    if not logs:
        print("[WARNING] No logs retrieved.")
        print("  - Service might not be running")
        print("  - Service might not have generated logs yet")
        print("  - API endpoint might be different")
        print("\nTrying alternative log retrieval method...")
        
        # Try alternative: get service status and events
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
            
            # Get service details
            service_url = f"{RENDER_API_BASE}/services/{service_id}"
            service_response = requests.get(service_url, headers=headers, timeout=10)
            if service_response.status_code == 200:
                service_data = service_response.json()
                print(f"[INFO] Service Status: {service_data.get('service', {}).get('suspendedInitiator', 'active')}")
                print(f"[INFO] Service Type: {service_data.get('service', {}).get('type', 'unknown')}")
            
            # Try events endpoint
            events_url = f"{RENDER_API_BASE}/services/{service_id}/events"
            events_response = requests.get(events_url, headers=headers, timeout=10)
            if events_response.status_code == 200:
                events_data = events_response.json()
                if isinstance(events_data, list):
                    events = events_data
                elif isinstance(events_data, dict):
                    events = events_data.get("events", [])
                else:
                    events = []
                
                if events:
                    print(f"[OK] Retrieved {len(events)} events")
                    # Convert events to log format
                    logs = []
                    for e in events[:50]:  # Last 50 events
                        if isinstance(e, dict):
                            msg = e.get("message", str(e))
                            timestamp = e.get("createdAt", e.get("timestamp", ""))
                        else:
                            msg = str(e)
                            timestamp = ""
                        logs.append({"message": msg, "timestamp": timestamp})
        except Exception as e:
            print(f"[ERROR] Alternative method failed: {e}")
            import traceback
            print(traceback.format_exc())
        
        if not logs:
            print("\n[INFO] No logs available. Check Render dashboard manually.")
            sys.exit(0)
    
    print(f"[OK] Retrieved {len(logs)} log entries")
    
    # Analyze logs
    print(f"\n[3/3] Analyzing logs...")
    analysis = analyze_logs(logs)
    print_analysis(analysis)
    
    # Save logs
    save_logs_to_file(logs)
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if analysis["import_errors"]:
        print("\n[FIX] Import errors detected:")
        print("  - Check requirements.txt has all needed packages")
        print("  - Verify Dockerfile installs requirements correctly")
    
    if analysis["filter_issues"]:
        print("\n[FIX] Filter errors detected:")
        print("  - Check filter files for syntax errors")
        print("  - Verify all imports are available")
        print("  - Consider temporarily disabling filters")
    
    if analysis["proxy_issues"]:
        print("\n[FIX] Proxy service issues detected:")
        print("  - Check if port 8000 is available")
        print("  - Verify openai_responses_proxy.py has no errors")
        print("  - Check start.sh is starting proxy correctly")
    
    if analysis["database_errors"]:
        print("\n[FIX] Database errors detected:")
        print("  - Check database permissions")
        print("  - Verify environment variables are set")
        print("  - Consider resetting database if needed")
    
    if not any([analysis["errors"], analysis["warnings"], analysis["startup_issues"]]):
        print("\n[OK] No critical issues found in logs!")
        print("  - Check Render dashboard for service status")
        print("  - Verify service is actually running")
        print("  - Check if 500 error is from a specific endpoint")

if __name__ == "__main__":
    main()
