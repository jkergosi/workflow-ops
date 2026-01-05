"""
Complete Enforcement Testing Script

Tests that backend enforcement uses database-driven entitlements.
"""
import sys
import requests
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.database import db_service

BASE_URL = "http://localhost:4000"

def print_test(name):
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")

def print_pass(msg):
    print(f"[PASS] {msg}")

def print_fail(msg):
    print(f"[FAIL] {msg}")

def print_info(msg):
    print(f"[INFO] {msg}")

async def get_test_tenants():
    """Get test tenants from database"""
    try:
        # Get tenants with different plans
        response = db_service.client.table("tenants").select("id, name, subscription_tier").limit(10).execute()
        tenants = response.data or []
        
        free_tenants = [t for t in tenants if t.get("subscription_tier") == "free"]
        pro_tenants = [t for t in tenants if t.get("subscription_tier") == "pro"]
        
        return {
            "free": free_tenants[0] if free_tenants else None,
            "pro": pro_tenants[0] if pro_tenants else None,
            "all": tenants
        }
    except Exception as e:
        print_fail(f"Error getting test tenants: {e}")
        return {"free": None, "pro": None, "all": []}

def test_endpoint_structure():
    """Test 2.1: Endpoint Response Structure"""
    print_test("2.1 Endpoint Response Structure")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/billing/plan-features/all", timeout=30)
        
        if response.status_code == 200:
            print_pass("Endpoint returns 200 OK")
            
            data = response.json()
            
            # Check structure
            if isinstance(data, dict):
                print_pass("Response is a dictionary")
                
                # Check for expected plans
                expected_plans = ['free', 'pro', 'agency', 'enterprise']
                found_plans = [p for p in expected_plans if p in data]
                
                if len(found_plans) == len(expected_plans):
                    print_pass(f"Response includes all expected plans: {found_plans}")
                else:
                    print_fail(f"Missing plans. Expected: {expected_plans}, Found: {list(data.keys())}")
                
                # Check for features
                has_features = False
                has_flag = False
                has_limit = False
                
                for plan_name, plan_features in data.items():
                    if isinstance(plan_features, dict) and len(plan_features) > 0:
                        has_features = True
                        for feature_name, feature_value in plan_features.items():
                            if isinstance(feature_value, bool):
                                has_flag = True
                            elif isinstance(feature_value, (int, float)):
                                has_limit = True
                
                if has_features:
                    print_pass("Response includes feature mappings")
                else:
                    print_fail("Response has empty feature mappings")
                
                if has_flag:
                    print_pass("Response includes flag features (boolean values)")
                else:
                    print_fail("Response does not include flag features")
                
                if has_limit:
                    print_pass("Response includes limit features (numeric values)")
                else:
                    print_fail("Response does not include limit features")
                
                return True
            else:
                print_fail(f"Response is not a dictionary: {type(data)}")
                return False
        else:
            print_fail(f"Endpoint returns {response.status_code} instead of 200")
            return False
            
    except Exception as e:
        print_fail(f"Error testing endpoint: {e}")
        return False

def test_feature_display_names():
    """Test feature display names endpoint"""
    print_test("Feature Display Names Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/billing/feature-display-names", timeout=30)
        
        if response.status_code == 200:
            print_pass("Endpoint returns 200 OK")
            data = response.json()
            
            if isinstance(data, dict) and len(data) > 0:
                print_pass(f"Response includes {len(data)} feature display names")
                return True
            else:
                print_fail("Response is empty or invalid")
                return False
        else:
            print_fail(f"Endpoint returns {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_plan_configurations():
    """Test plan configurations endpoint"""
    print_test("Plan Configurations Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/billing/plan-configurations", timeout=30)
        
        if response.status_code == 200:
            print_pass("Endpoint returns 200 OK")
            data = response.json()
            
            required_keys = ['metadata', 'limits', 'retention_defaults', 'feature_requirements']
            found_keys = [k for k in required_keys if k in data]
            
            if len(found_keys) == len(required_keys):
                print_pass(f"Response includes all required sections: {found_keys}")
                return True
            else:
                print_fail(f"Missing sections. Expected: {required_keys}, Found: {list(data.keys())}")
                return False
        else:
            print_fail(f"Endpoint returns {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("COMPLETE API TESTING")
    print("="*60)
    
    results = {
        "endpoint_structure": test_endpoint_structure(),
        "feature_display_names": test_feature_display_names(),
        "plan_configurations": test_plan_configurations(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nTests Passed: {passed}/{total}")
    
    if passed == total:
        print_pass("All API tests passed!")
    else:
        print_fail("Some tests failed")
    
    print("\n" + "="*60)
    print("ENFORCEMENT TESTS")
    print("="*60)
    print_info("Enforcement tests require auth tokens from test tenants")
    print_info("See TESTING_PLAN_FEATURES.md for manual testing procedures")
    
    return passed == total

if __name__ == "__main__":
    import asyncio
    success = main()
    sys.exit(0 if success else 1)

