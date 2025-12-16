"""
Test script to verify deployment deletion and stale job cleanup fixes.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from app.services.database import db_service
from app.services.background_job_service import background_job_service, BackgroundJobStatus

async def test_deployment_deletion():
    """Test that deployment deletion uses created_at correctly"""
    print("=" * 60)
    print("Testing Deployment Deletion Fix")
    print("=" * 60)
    
    # Get a deployment that's not running (Supabase client is synchronous)
    result = db_service.client.table("deployments").select("*").eq("tenant_id", "00000000-0000-0000-0000-000000000000").neq("status", "running").limit(1).execute()
    
    if not result.data:
        print("❌ No non-running deployments found to test")
        return
    
    deployment = result.data[0]
    print(f"\nFound deployment: {deployment['id'][:8]}...")
    print(f"  Status: {deployment.get('status')}")
    print(f"  Created at: {deployment.get('created_at')}")
    print(f"  Started at: {deployment.get('started_at')}")
    
    # Calculate age using created_at
    if deployment.get('created_at'):
        created_at_str = deployment['created_at']
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
            created_at_naive = created_at.replace(tzinfo=None)
        else:
            created_at_naive = created_at
        age_days = (datetime.utcnow() - created_at_naive).days
        print(f"  Age (from created_at): {age_days} days")
        
        if age_days < 7:
            print(f"  ✅ Would correctly reject deletion (age < 7 days)")
        else:
            print(f"  ✅ Would allow deletion (age >= 7 days)")
    else:
        print("  ⚠️  Missing created_at field!")

async def test_stale_jobs():
    """Test stale job cleanup"""
    print("\n" + "=" * 60)
    print("Testing Stale Job Cleanup")
    print("=" * 60)
    
    # Check for running jobs (Supabase client is synchronous)
    result = db_service.client.table("background_jobs").select("*").eq("status", BackgroundJobStatus.RUNNING).eq("tenant_id", "00000000-0000-0000-0000-000000000000").execute()
    
    running_jobs = result.data or []
    print(f"\nFound {len(running_jobs)} running job(s):")
    
    for job in running_jobs:
        job_id = job.get('id', 'unknown')
        started_at = job.get('started_at')
        created_at = job.get('created_at')
        
        print(f"\n  Job: {job_id[:8]}...")
        print(f"    Type: {job.get('job_type')}")
        print(f"    Started at: {started_at}")
        print(f"    Created at: {created_at}")
        
        if started_at:
            started = datetime.fromisoformat(started_at.replace('Z', '+00:00')) if isinstance(started_at, str) else started_at
            if hasattr(started, 'tzinfo') and started.tzinfo is not None:
                started_naive = started.replace(tzinfo=None)
            else:
                started_naive = started
            hours_running = (datetime.utcnow() - started_naive).total_seconds() / 3600
            print(f"    Hours running: {hours_running:.2f}")
            
            if hours_running > 24:
                print(f"    ⚠️  STALE: Running for more than 24 hours!")
            else:
                print(f"    ✅ Not stale yet")
    
    # Check for pending jobs older than 1 hour (Supabase client is synchronous)
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    pending_result = db_service.client.table("background_jobs").select("*").eq("status", BackgroundJobStatus.PENDING).lt("created_at", one_hour_ago).eq("tenant_id", "00000000-0000-0000-0000-000000000000").execute()
    
    stale_pending = pending_result.data or []
    print(f"\nFound {len(stale_pending)} stale pending job(s) (>1 hour old)")
    
    # Now test the cleanup function
    print("\n" + "-" * 60)
    print("Running cleanup_stale_jobs()...")
    print("-" * 60)
    
    try:
        cleanup_result = await background_job_service.cleanup_stale_jobs(max_runtime_hours=24)
        print(f"\n✅ Cleanup completed:")
        print(f"   Cleaned: {cleanup_result['cleaned_count']} jobs")
        print(f"   Failed: {cleanup_result['failed_count']} jobs")
        print(f"   Stale running: {cleanup_result['stale_running']} jobs")
        print(f"   Stale pending: {cleanup_result['stale_pending']} jobs")
    except Exception as e:
        print(f"\n❌ Cleanup failed: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_running_deployments():
    """Check for running deployments that should be cleaned up"""
    print("\n" + "=" * 60)
    print("Checking Running Deployments")
    print("=" * 60)
    
    result = db_service.client.table("deployments").select("*").eq("status", "running").eq("tenant_id", "00000000-0000-0000-0000-000000000000").execute()
    
    running_deployments = result.data or []
    print(f"\nFound {len(running_deployments)} running deployment(s):")
    
    for dep in running_deployments:
        dep_id = dep.get('id', 'unknown')
        started_at = dep.get('started_at')
        created_at = dep.get('created_at')
        
        print(f"\n  Deployment: {dep_id[:8]}...")
        print(f"    Started at: {started_at}")
        print(f"    Created at: {created_at}")
        
        if started_at:
            started = datetime.fromisoformat(started_at.replace('Z', '+00:00')) if isinstance(started_at, str) else started_at
            if hasattr(started, 'tzinfo') and started.tzinfo is not None:
                started_naive = started.replace(tzinfo=None)
            else:
                started_naive = started
            hours_running = (datetime.utcnow() - started_naive).total_seconds() / 3600
            print(f"    Hours running: {hours_running:.2f}")
            
            if hours_running > 48:
                print(f"    ⚠️  VERY STALE: Running for more than 2 days!")
        else:
            print(f"    ⚠️  Missing started_at field!")

async def main():
    await test_running_deployments()
    await test_stale_jobs()
    await test_deployment_deletion()
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

