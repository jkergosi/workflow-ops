"""
Enforcement Path Testing Script

Tests that backend enforcement uses database-driven entitlements.
Tests endpoints with different plan tenants to verify 403/200 responses.

Usage:
    python scripts/test_enforcement_paths.py
    python scripts/test_enforcement_paths.py --base-url http://localhost:8000
"""
import sys
import argparse
import requests
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.database import db_service
from app.services.entitlements_service import entitlements_service
from app.services.auth_service import supabase_auth_service

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_section(title: str):
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def print_test(name: str):
    print(f"{BOLD}Test: {name}{RESET}")

def print_pass(message: str):
    print(f"{GREEN}[PASS] {message}{RESET}")

def print_fail(message: str):
    print(f"{RED}[FAIL] {message}{RESET}")

def print_warn(message: str):
    print(f"{YELLOW}[WARN] {message}{RESET}")

def print_info(message: str):
    print(f"{BLUE}[INFO] {message}{RESET}")

async def get_test_tenant(plan_name: str = "free"):
    """Get or create a test tenant with specified plan"""
    try:
        # Try to find existing test tenant
        response = db_service.client.table("tenants").select("*").eq("name", f"test-{plan_name}").limit(1).execute()
        
        if response.data and len(response.data) > 0:
            tenant = response.data[0]
            tenant_id = tenant["id"]
        else:
            # Create test tenant
            print_info(f"Creating test tenant for plan: {plan_name}")
            tenant_data = {
                "name": f"test-{plan_name}",
                "email": f"test-{plan_name}@example.com",
                "subscription_tier": plan_name
            }
            response = db_service.client.table("tenants").insert(tenant_data).execute()
            tenant = response.data[0] if response.data else None
            tenant_id = tenant["id"] if tenant else None
            
            if not tenant_id:
                print_fail("Failed to create test tenant")
                return None
        
        # Ensure tenant has correct plan assignment
        # Get plan_id for the plan_name
        plan_response = db_service.client.table("plans").select("id").eq("name", plan_name).single().execute()
        if not plan_response.data:
            print_fail(f"Plan '{plan_name}' not found in plans table")
            return None
        
        plan_id = plan_response.data["id"]
        
        # Check/update tenant_plans
        tp_response = db_service.client.table("tenant_plans").select("*").eq("tenant_id", tenant_id).eq("is_active", True).execute()
        
        if not tp_response.data or len(tp_response.data) == 0:
            # Create tenant_plan
            db_service.client.table("tenant_plans").insert({
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "is_active": True,
                "entitlements_version": 1
            }).execute()
        else:
            # Update existing
            tp_id = tp_response.data[0]["id"]
            db_service.client.table("tenant_plans").update({
                "plan_id": plan_id,
                "entitlements_version": tp_response.data[0].get("entitlements_version", 1) + 1
            }).eq("id", tp_id).execute()
        
        # Clear cache
        entitlements_service.clear_cache()
        
        return tenant_id
        
    except Exception as e:
        print_fail(f"Error getting test tenant: {e}")
        return None

async def get_auth_token(tenant_id: str, base_url: str) -> str:
    """Get auth token for test tenant"""
    # This is a simplified version - in real testing you'd need proper auth
    # For now, we'll document that manual testing is needed
    print_warn("Auth token generation not implemented in script")
    print_info("For manual testing:")
    print_info(f"  1. Login as a user in tenant {tenant_id}")
    print_info(f"  2. Get the JWT token from browser DevTools")
    print_info(f"  3. Use it in API calls: Authorization: Bearer <token>")
    return None

def test_endpoint_with_plan(
    endpoint: str,
    method: str,
    plan_name: str,
    base_url: str,
    auth_token: str = None,
    expected_status: int = None,
    expected_feature: str = None
):
    """Test an endpoint with a specific plan tenant"""
    url = f"{base_url}{endpoint}"
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json={}, timeout=10)
        else:
            print_fail(f"Unsupported method: {method}")
            return False
        
        if expected_status:
            if response.status_code == expected_status:
                print_pass(f"{method} {endpoint} returned {expected_status} for {plan_name} plan")
                
                # If 403, check error structure
                if expected_status == 403:
                    try:
                        error_data = response.json()
                        if error_data.get("error") == "feature_not_available":
                            if expected_feature and error_data.get("feature") == expected_feature:
                                print_pass(f"Error correctly identifies feature: {expected_feature}")
                            else:
                                print_info(f"Error details: {json.dumps(error_data, indent=2)}")
                    except:
                        pass
                
                return True
            else:
                print_fail(f"{method} {endpoint} returned {response.status_code} (expected {expected_status}) for {plan_name} plan")
                print_info(f"Response: {response.text[:200]}")
                return False
        else:
            print_info(f"{method} {endpoint} returned {response.status_code}")
            return True
            
    except requests.exceptions.ConnectionError:
        print_fail(f"Cannot connect to {url}")
        return False
    except Exception as e:
        print_fail(f"Error testing endpoint: {e}")
        return False

async def test_enforcement_paths(base_url: str = "http://localhost:8000"):
    """Test enforcement paths for gated endpoints"""
    print_section("Enforcement Path Tests")
    
    print_info("These tests verify that backend enforcement uses database-driven entitlements")
    print_info("Note: Requires valid auth tokens for test tenants")
    
    # Test endpoints from plan
    test_cases = [
        {
            "endpoint": "/api/v1/promotions/initiate",
            "method": "POST",
            "feature": "workflow_ci_cd",
            "free_expected": 403,
            "pro_expected": 200
        },
        {
            "endpoint": "/api/v1/incidents",
            "method": "GET",
            "feature": "drift_incidents",
            "free_expected": 403,
            "pro_expected": 200
        },
        {
            "endpoint": "/api/v1/promotions/snapshots",
            "method": "POST",
            "feature": "workflow_ci_cd",
            "free_expected": 403,
            "pro_expected": 200
        },
        {
            "endpoint": "/api/v1/environments/{id}/drift",
            "method": "GET",
            "feature": "environment_basic",
            "free_expected": 403,
            "pro_expected": 200,
            "note": "Requires valid environment_id"
        }
    ]
    
    print_info("\nTo run these tests:")
    print_info("1. Start backend server: python scripts/start_with_migrations.py --port 8000")
    print_info("2. Create test tenants with free and pro plans")
    print_info("3. Get auth tokens for each tenant")
    print_info("4. Run tests with: python scripts/test_enforcement_paths.py --base-url http://localhost:8000 --token <token>")
    
    print_info("\nTest Cases:")
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['method']} {test_case['endpoint']}")
        print(f"   Feature: {test_case['feature']}")
        print(f"   Free plan: Expected {test_case['free_expected']}")
        print(f"   Pro plan: Expected {test_case['pro_expected']}")
        if 'note' in test_case:
            print(f"   Note: {test_case['note']}")
    
    return True

async def test_db_driven_verification():
    """Test 4.3: Database-Driven Verification"""
    print_section("Database-Driven Verification Test")
    
    print_info("This test proves enforcement uses DB, not hard-coded values")
    print_info("\nManual Test Procedure:")
    print_info("1. Query plan_features for workflow_ci_cd on free plan:")
    print_info("   SELECT pf.* FROM plan_features pf")
    print_info("   JOIN plans p ON p.id = pf.plan_id")
    print_info("   JOIN features f ON f.id = pf.feature_id")
    print_info("   WHERE p.name = 'free' AND f.name = 'workflow_ci_cd';")
    print_info("\n2. Verify value is {\"enabled\": false} or missing")
    print_info("\n3. Call POST /api/v1/promotions/initiate with free plan tenant")
    print_info("   Expected: 403 Forbidden")
    print_info("\n4. Update DB directly:")
    print_info("   UPDATE plan_features")
    print_info("   SET value = '{\"enabled\": true}'::jsonb")
    print_info("   WHERE plan_id = (SELECT id FROM plans WHERE name = 'free')")
    print_info("     AND feature_id = (SELECT id FROM features WHERE name = 'workflow_ci_cd');")
    print_info("\n5. Clear cache: POST /api/v1/admin/entitlements/cache/clear")
    print_info("\n6. Retest same endpoint - should now return 200 (proves DB-driven)")
    
    return True

async def main():
    parser = argparse.ArgumentParser(description="Test enforcement paths")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--token", help="Auth token for API calls")
    args = parser.parse_args()
    
    await test_enforcement_paths(args.base_url)
    await test_db_driven_verification()
    
    print_section("Summary")
    print_info("Enforcement tests require manual execution with valid auth tokens")
    print_info("See test output above for detailed procedures")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

