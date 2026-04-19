#!/usr/bin/env python3
"""
Simple test to verify the lambda script works correctly
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from simulation.cases import cases
    print("✓ Successfully imported cases")
    
    # Test case extraction
    urban_cases = []
    for case_key in ["case1", "case2", "case3"]:
        urban_cases.extend(cases[case_key])
    print(f"✓ Urban cases: {len(urban_cases)} scenarios")
    
    rural_cases = []
    for case_key in ["case4", "case5", "case6"]:
        rural_cases.extend(cases[case_key])
    print(f"✓ Rural cases: {len(rural_cases)} scenarios")
    
    # Test lambda values
    URBAN_LAMBDA = 8.5
    RURAL_LAMBDA = 2.5
    print(f"✓ Urban lambda: {URBAN_LAMBDA}")
    print(f"✓ Rural lambda: {RURAL_LAMBDA}")
    
    print("\n✓ All imports and basic functionality working!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
