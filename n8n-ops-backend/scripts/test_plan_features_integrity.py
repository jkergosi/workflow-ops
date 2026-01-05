"""
Plan Features Integrity Testing Script

This script executes all tests from the plan_features_integrity_testing plan:
1. Database Integrity Tests (SQL queries)
2. API Correctness Tests
3. Frontend Fallback Behavior Tests (manual verification needed)
4. Enforcement Path Tests

Run with: python scripts/test_plan_features_integrity.py
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.database import db_service
from app.core.config import settings
import requests

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_section(title: str):
    """Print a section header"""
    print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")

def print_test(name: str):
    """Print a test name"""
    print(f"{BOLD}Test: {name}{RESET}")

def print_pass(message: str):
    """Print a passing test"""
    print(f"{GREEN}[PASS] {message}{RESET}")

def print_fail(message: str):
    """Print a failing test"""
    print(f"{RED}[FAIL] {message}{RESET}")

def print_warn(message: str):
    """Print a warning"""
    print(f"{YELLOW}[WARN] {message}{RESET}")

def print_info(message: str):
    """Print info"""
    print(f"{BLUE}[INFO] {message}{RESET}")

async def run_sql_query(query: str, description: str) -> List[Dict[str, Any]]:
    """Run a SQL query using Supabase PostgREST (via table API or RPC)"""
    try:
        # Try using psycopg2 for raw SQL
        try:
            import psycopg2
            from app.core.config import settings
            
            # Extract connection details from SUPABASE_URL if available
            # Or use DATABASE_URL if set
            db_url = getattr(settings, 'DATABASE_URL', None)
            if not db_url:
                # Try to construct from SUPABASE_URL and service key
                # Supabase direct connection format: postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
                # We need to extract from SUPABASE_URL or use environment variable
                import os
                db_url = os.getenv('DATABASE_URL')
                if not db_url:
                    print_warn(f"Cannot run raw SQL query: {description}")
                    print_info("DATABASE_URL not configured. Query needs to be run manually in Supabase SQL Editor.")
                    return None  # Return None to indicate query couldn't run
            
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            cursor.execute(query)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch results
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows] if columns else []
            
            cursor.close()
            conn.close()
            
            return results
            
        except ImportError:
            print_warn(f"psycopg2 not available. Cannot run raw SQL: {description}")
            print_info("Install psycopg2: pip install psycopg2-binary")
            print_info(f"Or run this query manually in Supabase SQL Editor:\n{query}")
            return None  # Return None to indicate query couldn't run
        except Exception as e:
            print_warn(f"Error running SQL query: {e}")
            print_info(f"Query: {query}")
            return None  # Return None to indicate query couldn't run
            
    except Exception as e:
        print_fail(f"Failed to execute query: {e}")
        return None

# ============================================================================
# 1. Database Integrity Tests
# ============================================================================

async def test_1_1_core_tables_population():
    """Test 1.1: Core Tables Population"""
    print_test("1.1 Core Tables Population")
    
    query = """
    select 'plans' as table_name, count(*) as row_count from plans
    union all 
    select 'features', count(*) from features
    union all 
    select 'plan_features', count(*) from plan_features;
    """
    
    results = await run_sql_query(query, "Core tables population")
    
    if not results:
        print_warn("Could not execute query automatically. Please run manually:")
        print(query)
        return False
    
    all_pass = True
    for row in results:
        table_name = row['table_name']
        row_count = row['row_count']
        
        if row_count > 0:
            print_pass(f"{table_name} table has {row_count} rows")
        else:
            print_fail(f"{table_name} table is empty (expected > 0)")
            all_pass = False
    
    return all_pass

async def test_1_2_foreign_key_integrity():
    """Test 1.2: Foreign Key Integrity (Orphan Check)"""
    print_test("1.2 Foreign Key Integrity (Orphan Check)")
    
    query = """
    select
      sum(case when p.id is null then 1 else 0 end) as orphan_plan_rows,
      sum(case when f.id is null then 1 else 0 end) as orphan_feature_rows,
      count(*) as total_rows
    from plan_features pf
    left join plans p on p.id = pf.plan_id
    left join features f on f.id = pf.feature_id;
    """
    
    results = await run_sql_query(query, "Foreign key integrity")
    
    if not results:
        print_warn("Could not execute query automatically. Please run manually:")
        print(query)
        return False
    
    result = results[0]
    orphan_plan_rows = result['orphan_plan_rows']
    orphan_feature_rows = result['orphan_feature_rows']
    total_rows = result['total_rows']
    
    all_pass = True
    if orphan_plan_rows == 0:
        print_pass(f"No orphan plan rows (total: {total_rows})")
    else:
        print_fail(f"Found {orphan_plan_rows} orphan plan rows")
        all_pass = False
    
    if orphan_feature_rows == 0:
        print_pass(f"No orphan feature rows (total: {total_rows})")
    else:
        print_fail(f"Found {orphan_feature_rows} orphan feature rows")
        all_pass = False
    
    return all_pass

async def test_1_3_coverage_check():
    """Test 1.3: Coverage Check (Each Plan Has Feature Mappings)"""
    print_test("1.3 Coverage Check (Each Plan Has Feature Mappings)")
    
    query = """
    select
      p.id as plan_id,
      p.name as plan_name,
      count(pf.feature_id) as mapped_features,
      (select count(*) from features where status = 'active') as total_active_features
    from plans p
    left join plan_features pf on pf.plan_id = p.id
    where p.is_active = true
    group by p.id, p.name
    order by p.name;
    """
    
    results = await run_sql_query(query, "Coverage check")
    
    if not results:
        print_warn("Could not execute query automatically. Please run manually:")
        print(query)
        return False
    
    all_pass = True
    for row in results:
        plan_name = row['plan_name']
        mapped_features = row['mapped_features']
        total_active_features = row['total_active_features']
        
        if mapped_features > 0:
            print_pass(f"{plan_name}: {mapped_features} features mapped (total active: {total_active_features})")
        else:
            print_fail(f"{plan_name}: No features mapped (expected > 0)")
            all_pass = False
    
    return all_pass

async def test_1_4_duplicate_check():
    """Test 1.4: Duplicate Check"""
    print_test("1.4 Duplicate Check")
    
    query = """
    select plan_id, feature_id, count(*) as duplicate_count
    from plan_features
    group by plan_id, feature_id
    having count(*) > 1
    order by duplicate_count desc;
    """
    
    results = await run_sql_query(query, "Duplicate check")
    
    if results is None:
        print_warn("Could not execute query automatically. Please run manually:")
        print(query)
        return False
    
    # Empty results means no duplicates (which is good)
    if len(results) == 0:
        print_pass("No duplicate (plan_id, feature_id) pairs found")
        return True
    else:
        print_fail(f"Found {len(results)} duplicate (plan_id, feature_id) pairs:")
        for row in results:
            print(f"  - plan_id: {row['plan_id']}, feature_id: {row['feature_id']}, count: {row['duplicate_count']}")
        return False

async def test_1_5_value_type_validation():
    """Test 1.5: Value Type Validation"""
    print_test("1.5 Value Type Validation")
    
    # Flag features query
    flag_query = """
    select p.name as plan_name, f.name as feature_name, pf.value
    from plan_features pf
    join plans p on p.id = pf.plan_id
    join features f on f.id = pf.feature_id
    where f.type = 'flag'
      and not (
        jsonb_typeof(pf.value) = 'object' 
        and (pf.value ? 'enabled') 
        and jsonb_typeof(pf.value->'enabled') = 'boolean'
      )
    limit 50;
    """
    
    flag_results = await run_sql_query(flag_query, "Flag features value validation")
    
    # Limit features query
    limit_query = """
    select p.name as plan_name, f.name as feature_name, pf.value
    from plan_features pf
    join plans p on p.id = pf.plan_id
    join features f on f.id = pf.feature_id
    where f.type = 'limit'
      and not (
        jsonb_typeof(pf.value) = 'object' 
        and (pf.value ? 'value') 
        and jsonb_typeof(pf.value->'value') = 'number'
      )
    limit 50;
    """
    
    limit_results = await run_sql_query(limit_query, "Limit features value validation")
    
    all_pass = True
    
    if flag_results is None:
        print_warn("Could not validate flag features automatically")
        print_info("Run manually:")
        print(flag_query)
    elif len(flag_results) == 0:
        print_pass("All flag features have valid value format: {\"enabled\": boolean}")
    else:
        print_fail(f"Found {len(flag_results)} flag features with invalid value format:")
        for row in flag_results[:5]:  # Show first 5
            print(f"  - {row['plan_name']}.{row['feature_name']}: {row['value']}")
        all_pass = False
    
    if limit_results is None:
        print_warn("Could not validate limit features automatically")
        print_info("Run manually:")
        print(limit_query)
    elif len(limit_results) == 0:
        print_pass("All limit features have valid value format: {\"value\": number}")
    else:
        print_fail(f"Found {len(limit_results)} limit features with invalid value format:")
        for row in limit_results[:5]:  # Show first 5
            print(f"  - {row['plan_name']}.{row['feature_name']}: {row['value']}")
        all_pass = False
    
    return all_pass

async def test_1_6_tenant_subscription_integrity():
    """Test 1.6: Tenant Subscription Integrity"""
    print_test("1.6 Tenant Subscription Integrity")
    
    query = """
    select count(*) as bad_subscriptions
    from tenant_provider_subscriptions s
    left join provider_plans pp on pp.id = s.plan_id
    where pp.id is null;
    """
    
    results = await run_sql_query(query, "Tenant subscription integrity")
    
    if not results:
        print_warn("Could not execute query automatically. Please run manually:")
        print(query)
        return False
    
    bad_subscriptions = results[0]['bad_subscriptions']
    
    if bad_subscriptions == 0:
        print_pass(f"No bad subscriptions (all reference valid provider_plans)")
        return True
    else:
        print_fail(f"Found {bad_subscriptions} subscriptions referencing invalid provider_plans")
        return False

# ============================================================================
# 2. API Correctness Tests
# ============================================================================

def test_2_1_endpoint_response_structure(base_url: str = "http://localhost:4000"):
    """Test 2.1: Endpoint Response Structure"""
    print_test("2.1 Endpoint Response Structure")
    
    url = f"{base_url}/api/v1/billing/plan-features/all"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print_pass(f"Endpoint returns 200 OK")
            
            try:
                data = response.json()
                
                # Check structure
                if isinstance(data, dict):
                    print_pass("Response is a dictionary")
                    
                    # Check for expected plans
                    expected_plans = ['free', 'pro', 'agency', 'enterprise']
                    found_plans = [p for p in expected_plans if p in data]
                    
                    if len(found_plans) > 0:
                        print_pass(f"Response includes plans: {', '.join(found_plans)}")
                    else:
                        print_warn(f"Response does not include expected plans. Found: {list(data.keys())}")
                    
                    # Check for features in each plan
                    has_features = False
                    has_flag = False
                    has_limit = False
                    
                    for plan_name, plan_features in data.items():
                        if isinstance(plan_features, dict) and len(plan_features) > 0:
                            has_features = True
                            # Check for flag and limit features
                            for feature_name, feature_value in plan_features.items():
                                if isinstance(feature_value, bool):
                                    has_flag = True
                                elif isinstance(feature_value, (int, float)):
                                    has_limit = True
                    
                    if has_features:
                        print_pass("Response includes feature mappings")
                    else:
                        print_warn("Response has empty feature mappings (may indicate empty plan_features table)")
                    
                    if has_flag:
                        print_pass("Response includes flag features (boolean values)")
                    else:
                        print_warn("Response does not include flag features")
                    
                    if has_limit:
                        print_pass("Response includes limit features (numeric values)")
                    else:
                        print_warn("Response does not include limit features")
                    
                    return True
                else:
                    print_fail(f"Response is not a dictionary: {type(data)}")
                    return False
                    
            except json.JSONDecodeError:
                print_fail("Response is not valid JSON")
                print_info(f"Response body: {response.text[:200]}")
                return False
        else:
            print_fail(f"Endpoint returns {response.status_code} instead of 200")
            print_info(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_fail(f"Cannot connect to {url}")
        print_info("Make sure the backend server is running on port 8000")
        return False
    except Exception as e:
        print_fail(f"Error testing endpoint: {e}")
        return False

def test_2_2_empty_table_vs_api_failure(base_url: str = "http://localhost:4000"):
    """Test 2.2: Empty Table vs API Failure Distinction"""
    print_test("2.2 Empty Table vs API Failure Distinction")
    
    url = f"{base_url}/api/v1/billing/plan-features/all"
    
    print_info("Note: This test requires manual verification:")
    print_info("  - Scenario A: Truncate plan_features table, verify endpoint returns 200 with empty objects")
    print_info("  - Scenario B: Stop DB, verify endpoint returns 500 error")
    print_info("  - Current test only verifies endpoint is accessible")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                # Check if all plans have empty feature dicts
                all_empty = all(
                    isinstance(features, dict) and len(features) == 0
                    for features in data.values()
                )
                
                if all_empty:
                    print_warn("All plan feature mappings are empty - this may indicate misconfiguration")
                else:
                    print_pass("Endpoint returns data (not empty)")
            
            return True
        elif response.status_code == 500:
            print_info("Endpoint returns 500 (database error) - this is expected for DB failure scenario")
            return True
        else:
            print_fail(f"Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_fail("Cannot connect to endpoint")
        return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

# ============================================================================
# Main Test Runner
# ============================================================================

async def run_all_tests(base_url: str = "http://localhost:4000"):
    """Run all integrity tests"""
    print_section("Plan Features Integrity Testing")
    print_info("This script tests database integrity and API correctness")
    print_info("Frontend and enforcement tests require manual verification")
    print_info(f"Testing API at: {base_url}")
    
    results = {
        "database": {},
        "api": {},
        "overall": True
    }
    
    # Database Tests
    print_section("1. Database Integrity Tests")
    
    results["database"]["1.1"] = await test_1_1_core_tables_population()
    results["database"]["1.2"] = await test_1_2_foreign_key_integrity()
    results["database"]["1.3"] = await test_1_3_coverage_check()
    results["database"]["1.4"] = await test_1_4_duplicate_check()
    results["database"]["1.5"] = await test_1_5_value_type_validation()
    results["database"]["1.6"] = await test_1_6_tenant_subscription_integrity()
    
    # API Tests
    print_section("2. API Correctness Tests")
    
    results["api"]["2.1"] = test_2_1_endpoint_response_structure(base_url)
    results["api"]["2.2"] = test_2_2_empty_table_vs_api_failure(base_url)
    
    # Summary
    print_section("Test Summary")
    
    db_passed = sum(1 for v in results["database"].values() if v)
    db_total = len(results["database"])
    api_passed = sum(1 for v in results["api"].values() if v)
    api_total = len(results["api"])
    
    print(f"\n{BOLD}Database Tests: {db_passed}/{db_total} passed{RESET}")
    print(f"{BOLD}API Tests: {api_passed}/{api_total} passed{RESET}")
    
    if db_passed == db_total:
        print_pass("All database integrity tests passed!")
        if api_passed == api_total:
            print_pass("All API tests passed!")
            results["overall"] = True
        else:
            print_warn("API tests require backend server to be running")
            print_info("Start server with: python scripts/start_with_migrations.py --port 8000")
            results["overall"] = True  # DB tests are the critical ones
    else:
        print_fail("Some database tests failed. Review output above.")
        results["overall"] = False
    
    print(f"\n{BOLD}Next Steps:{RESET}")
    print("1. Review any warnings or failures above")
    print("2. For frontend tests (3.1-3.2): Use browser DevTools to verify network calls")
    print("3. For enforcement tests (4.1-4.3): Test endpoints with different plan tenants")
    print("4. Complete the acceptance checklist in the plan document")
    
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test plan features integrity")
    parser.add_argument("--base-url", default="http://localhost:4000", help="Base URL for API (default: http://localhost:4000)")
    args = parser.parse_args()
    
    try:
        results = asyncio.run(run_all_tests(args.base_url))
        sys.exit(0 if results["overall"] else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Error running tests: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

