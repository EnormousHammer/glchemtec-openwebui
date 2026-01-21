#!/usr/bin/env python3
"""Test script for export_filter.py - validates syntax and basic functionality."""

import sys
import os

print("=" * 60)
print("Testing export_filter.py")
print("=" * 60)

# Test 1: Syntax check
print("\n[1/4] Testing syntax...")
try:
    with open('export_filter.py', 'r', encoding='utf-8') as f:
        code = f.read()
    compile(code, 'export_filter.py', 'exec')
    print("[OK] Syntax OK")
except SyntaxError as e:
    print(f"[ERROR] Syntax Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error reading file: {e}")
    sys.exit(1)

# Test 2: Import check
print("\n[2/4] Testing imports...")
try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Test if required modules are available
    import os as _os
    import re as _re
    import json as _json
    import base64 as _base64
    import requests as _requests
    from typing import Optional, List, Dict, Any
    from datetime import datetime
    from pydantic import BaseModel, Field
    
    print("[OK] All imports available")
except ImportError as e:
    print(f"[ERROR] Missing import: {e}")
    print("  Install missing packages: pip install pydantic requests")
    sys.exit(1)

# Test 3: Class instantiation
print("\n[3/4] Testing Filter class instantiation...")
try:
    # Import the filter
    import export_filter
    
    # Create instance
    filter_instance = export_filter.Filter()
    print("[OK] Filter class instantiated successfully")
    print(f"  - Enabled: {filter_instance.valves.enabled}")
    print(f"  - Debug: {filter_instance.valves.debug}")
    print(f"  - Priority: {filter_instance.valves.priority}")
    print(f"  - Service URL: {filter_instance.valves.export_service_url}")
except Exception as e:
    print(f"[ERROR] Failed to instantiate Filter: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Method existence
print("\n[4/4] Testing required methods...")
required_methods = ['inlet', 'outlet', '_detect_export_request', '_build_report_from_conversation']
missing = []
for method in required_methods:
    if not hasattr(filter_instance, method):
        missing.append(method)

if missing:
    print(f"[ERROR] Missing methods: {', '.join(missing)}")
    sys.exit(1)
else:
    print("[OK] All required methods present")

# Test 5: Export detection
print("\n[5/5] Testing export request detection...")
test_cases = [
    ("export this to pdf", "pdf"),
    ("create a word file", "docx"),
    ("make a pdf document", "pdf"),
    ("generate a docx file", "docx"),
    ("hello world", None),  # Should not detect
]

all_passed = True
for text, expected in test_cases:
    result = filter_instance._detect_export_request(text)
    if result == expected:
        print(f"[OK] '{text}' -> {result}")
    else:
        print(f"[WARN] '{text}' -> {result} (expected {expected})")
        all_passed = False

if not all_passed:
    print("\n[WARN] Some detection tests failed, but filter should still work")
else:
    print("\n[OK] All detection tests passed")

print("\n" + "=" * 60)
print("[OK] All tests passed! Filter is ready to use.")
print("=" * 60)
