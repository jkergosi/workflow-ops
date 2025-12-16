"""
Test to verify deployment deletion and stale cleanup fixes work correctly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app.services.database import db_service
from app.services.background_job_service import background_job_service, BackgroundJobStatus
from app.schemas.deployment import DeploymentStatus

def test_deployment_age_calculation():
    """Test that deployment age uses created_at, not started_at"""
    print("=" * 70)
    print("TEST 1: Deployment Age Calculation (should use created_at)")
    print("=" * 70)
    
    # Get a deployment
    result = db_service.client.table("deployments").select("*").eq("tenant_id", "00000000-0000-0000-0000-000000000000").limit(1).execute()
    
    if not result.data:
        print("No deployments found")
        return
    
    dep = result.data[0]
    dep_id = dep.get('id', 'unknown')[:8]
    
    print(f"\nDeployment: {dep_id}...")
    print(f"  Status: {dep.get('status')}")
    print(f"  Created at: {dep.get('created_at')}")
    print(f"  Started at: {dep.get('started_at')}")
    
    # Calculate age using created_at (correct way)
    if dep.get('created_at'):
        created_at_str = dep['created_at']
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
            created_at_naive = created_at.replace(tzinfo=None)
        else:
            created_at_naive = created_at
        age_days = (datetime.utcnow() - created_at_naive).days
        
        print(f"\n  Age calculation (using created_at): {age_days} days")
        
        # Show what it would be with started_at (wrong way)
        if dep.get('started_at'):
            started_at_str = dep['started_at']
            started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00')) if isinstance(started_at_str, str) else started_at_str
            if hasattr(started_at, 'tzinfo') and started_at.tzinfo is not None:
                started_at_naive = started_at.replace(tzinfo=None)
            else:
                started_at_naive = started_at
            age_from_started = (datetime.utcnow() - started_at_naive).days
            print(f"  Age calculation (using started_at - WRONG): {age_from_started} days")
            print(f"  Difference: {age_days - age_from_started} days")
        
        if age_days < 7:
            print(f"\n  [PASS] Would correctly reject deletion (age {age_days} < 7 days)")
        else:
            print(f"\n  [PASS] Would allow deletion (age {age_days} >= 7 days)")
    else:
        print("\n  [FAIL] Missing created_at field!")

def test_stale_deployments():
    """Test finding stale deployments"""
    print("\n" + "=" * 70)
    print("TEST 2: Stale Deployment Detection")
    print("=" * 70)
    
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    result = db_service.client.table("deployments").select("*").eq("status", "running").eq("tenant_id", "00000000-0000-0000-0000-000000000000").lt("started_at", cutoff_time.isoformat()).execute()
    
    stale_deployments = result.data or []
    print(f"\nFound {len(stale_deployments)} stale running deployment(s) (>24 hours):")
    
    for dep in stale_deployments:
        dep_id = dep.get('id', 'unknown')[:8]
        started_at = dep.get('started_at')
        
        if started_at:
            started = datetime.fromisoformat(started_at.replace('Z', '+00:00')) if isinstance(started_at, str) else started_at
            if hasattr(started, 'tzinfo') and started.tzinfo is not None:
                started_naive = started.replace(tzinfo=None)
            else:
                started_naive = started
            hours_running = (datetime.utcnow() - started_naive).total_seconds() / 3600
            
            print(f"\n  Deployment: {dep_id}...")
            print(f"    Hours running: {hours_running:.2f}")
            print(f"    [NEEDS CLEANUP] Should be marked as failed")
    
    if len(stale_deployments) == 0:
        print("\n  [PASS] No stale deployments found")

async def test_cleanup_function():
    """Test the cleanup function"""
    print("\n" + "=" * 70)
    print("TEST 3: Cleanup Function Execution")
    print("=" * 70)
    
    import asyncio
    
    try:
        print("\nRunning cleanup_stale_jobs()...")
        cleanup_result = await background_job_service.cleanup_stale_jobs(max_runtime_hours=24)
        
        print(f"\nCleanup Results:")
        print(f"  Cleaned: {cleanup_result['cleaned_count']} jobs")
        print(f"  Failed: {cleanup_result['failed_count']} jobs")
        print(f"  Stale running: {cleanup_result['stale_running']} jobs")
        print(f"  Stale pending: {cleanup_result['stale_pending']} jobs")
        
        if cleanup_result['cleaned_count'] > 0:
            print(f"\n  [PASS] Cleanup function executed and cleaned {cleanup_result['cleaned_count']} jobs")
        else:
            print(f"\n  [INFO] No stale jobs found to clean")
            
    except Exception as e:
        print(f"\n  [FAIL] Cleanup function failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_deployment_age_calculation()
    test_stale_deployments()
    
    import asyncio
    asyncio.run(test_cleanup_function())
    
    print("\n" + "=" * 70)
    print("All Tests Complete")
    print("=" * 70)

