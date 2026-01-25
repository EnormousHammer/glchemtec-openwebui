#!/usr/bin/env python3
"""
Test script to verify all filters can be loaded and serialized properly.
This simulates what OpenWebUI does when listing functions.
"""

import sys
import traceback
import json
from pathlib import Path

def test_filter_import(filter_name, filter_path):
    """Test importing a filter module."""
    try:
        # Import the filter
        spec = __import__(filter_name, fromlist=['Filter'])
        Filter = getattr(spec, 'Filter')
        print(f"[OK] {filter_name}: Import successful")
        return Filter
    except Exception as e:
        print(f"[FAIL] {filter_name}: Import failed - {e}")
        traceback.print_exc()
        return None

def test_filter_instantiation(Filter, filter_name):
    """Test creating an instance of the filter."""
    try:
        instance = Filter()
        print(f"[OK] {filter_name}: Instantiation successful")
        return instance
    except Exception as e:
        print(f"[FAIL] {filter_name}: Instantiation failed - {e}")
        traceback.print_exc()
        return None

def test_filter_methods(instance, filter_name):
    """Test that filter has required methods."""
    required_methods = ['inlet', 'outlet', 'stream']
    missing = []
    for method in required_methods:
        if not hasattr(instance, method):
            missing.append(method)
        elif not callable(getattr(instance, method)):
            missing.append(f"{method} (not callable)")
    
    if missing:
        print(f"[FAIL] {filter_name}: Missing methods - {missing}")
        return False
    else:
        print(f"[OK] {filter_name}: All required methods present")
        return True

def test_valves_serialization(instance, filter_name):
    """Test that Valves can be serialized to JSON (what OpenWebUI does)."""
    try:
        valves = instance.valves
        
        # Test model_dump (Pydantic v2)
        valves_dict = valves.model_dump()
        print(f"[OK] {filter_name}: Valves.model_dump() successful")
        
        # Test model_json_schema (what OpenWebUI uses for UI)
        schema = valves.model_json_schema()
        print(f"[OK] {filter_name}: Valves.model_json_schema() successful")
        
        # Test JSON serialization
        json_str = json.dumps(valves_dict)
        print(f"[OK] {filter_name}: JSON serialization successful")
        
        return True
    except Exception as e:
        print(f"[FAIL] {filter_name}: Valves serialization failed - {e}")
        traceback.print_exc()
        return False

def test_filter_metadata(instance, filter_name):
    """Test that filter has proper metadata."""
    try:
        # Check if filter has valves attribute
        if not hasattr(instance, 'valves'):
            print(f"[FAIL] {filter_name}: No 'valves' attribute")
            return False
        
        # Check if valves is a Pydantic model
        from pydantic import BaseModel
        if not isinstance(instance.valves, BaseModel):
            print(f"[FAIL] {filter_name}: 'valves' is not a Pydantic model")
            return False
        
        print(f"[OK] {filter_name}: Metadata check passed")
        return True
    except Exception as e:
        print(f"[FAIL] {filter_name}: Metadata check failed - {e}")
        traceback.print_exc()
        return False

def main():
    """Test all filters."""
    filters_to_test = [
        ('export_filter', 'export_filter.py'),
        ('ppt_pdf_filter', 'ppt_pdf_filter.py'),
        ('sharepoint_import_filter', 'sharepoint_import_filter.py'),
        ('document_filter', 'document_filter.py'),
    ]
    
    results = {}
    
    print("=" * 60)
    print("Testing All Filters")
    print("=" * 60)
    
    for filter_name, filter_path in filters_to_test:
        print(f"\n--- Testing {filter_name} ---")
        
        # Check file exists
        if not Path(filter_path).exists():
            print(f"[FAIL] {filter_name}: File not found - {filter_path}")
            results[filter_name] = False
            continue
        
        # Test import
        Filter = test_filter_import(filter_name, filter_path)
        if not Filter:
            results[filter_name] = False
            continue
        
        # Test instantiation
        instance = test_filter_instantiation(Filter, filter_name)
        if not instance:
            results[filter_name] = False
            continue
        
        # Test methods
        if not test_filter_methods(instance, filter_name):
            results[filter_name] = False
            continue
        
        # Test metadata
        if not test_filter_metadata(instance, filter_name):
            results[filter_name] = False
            continue
        
        # Test serialization (critical for OpenWebUI)
        if not test_valves_serialization(instance, filter_name):
            results[filter_name] = False
            continue
        
        results[filter_name] = True
        print(f"[OK] {filter_name}: ALL TESTS PASSED")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for filter_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {filter_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[OK] All filters passed all tests!")
        return 0
    else:
        print("\n[FAIL] Some filters failed tests. Check output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
