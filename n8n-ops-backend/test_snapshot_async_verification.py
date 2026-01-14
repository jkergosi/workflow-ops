"""
Test script to verify snapshot creation is async with real-time progress updates.
Verifies T007: Real-time progress updates appear on activity detail page.

Run this after triggering a snapshot creation from the UI.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.database import db_service
from app.services.background_job_service import background_job_service, BackgroundJobType, BackgroundJobStatus

async def test_snapshot_async_verification():
    """Verify snapshot creation is async with real-time progress"""
    print("=" * 70)
    print("T007: Snapshot Async Creation with Real-time Progress Verification")
    print("=" * 70)

    tenant_id = input("\nEnter tenant_id: ").strip()
    environment_id = input("Enter environment_id: ").strip()

    # Get environment
    environment = await db_service.get_environment(environment_id, tenant_id)
    if not environment:
        print(f"❌ ERROR: Environment {environment_id} not found")
        return

    print(f"\n✓ Environment found: {environment.get('name', environment_id)}")

    print("\n" + "=" * 70)
    print("Checking Recent Snapshot Creation Jobs")
    print("=" * 70)

    # Get recent snapshot creation jobs (last 10 minutes)
    ten_minutes_ago = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

    snapshot_jobs_result = await db_service.client.table("background_jobs").select(
        "id, status, result, progress, created_at, started_at, completed_at, error_message"
    ).eq("tenant_id", tenant_id).eq("resource_id", environment_id).eq(
        "job_type", BackgroundJobType.SNAPSHOT_CREATE
    ).gte("created_at", ten_minutes_ago).order("created_at", desc=True).limit(5).execute()

    if not snapshot_jobs_result.data:
        print("⚠️  No recent snapshot creation jobs found (last 10 minutes)")
        print("   Please trigger a snapshot creation from the UI first")
        print("   (Go to Snapshots page → Click 'Create Snapshot')")
        return

    print(f"\nFound {len(snapshot_jobs_result.data)} recent snapshot job(s):")

    # Track if we found any jobs with progress data
    jobs_with_progress = []

    for idx, job in enumerate(snapshot_jobs_result.data, 1):
        job_id = job['id']
        job_id_short = job_id[:8] + "..."

        print(f"\n{idx}. Snapshot Job: {job_id_short}")
        print(f"   Status: {job.get('status')}")
        print(f"   Created: {job.get('created_at')}")

        if job.get('started_at'):
            print(f"   Started: {job.get('started_at')}")

        if job.get('completed_at'):
            print(f"   Completed: {job.get('completed_at')}")
            duration = (datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00')) -
                       datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))).total_seconds()
            print(f"   Duration: {duration:.2f}s")

        # Check progress data
        progress = job.get('progress') or {}

        print(f"\n   Progress Data:")
        if progress:
            current_step = progress.get('current_step') or progress.get('currentStep')
            current = progress.get('current')
            total = progress.get('total')
            message = progress.get('message')

            if current_step:
                print(f"     ✓ Current step: {current_step}")
            else:
                print(f"     ✗ No current_step found")

            if current is not None and total is not None:
                print(f"     ✓ Progress: {current}/{total} items")
                percentage = (current / total * 100) if total > 0 else 0
                print(f"     ✓ Percentage: {percentage:.1f}%")
            else:
                print(f"     ✗ No progress counts found")

            if message:
                print(f"     ✓ Message: {message}")

            # Track jobs with substantial progress data
            if current_step or (current is not None and total is not None):
                jobs_with_progress.append({
                    'job_id': job_id,
                    'job_id_short': job_id_short,
                    'status': job.get('status'),
                    'progress': progress,
                    'result': job.get('result')
                })
        else:
            print(f"     ✗ No progress data found")

        # Check result data
        result = job.get('result') or {}
        if result and job.get('status') == 'completed':
            print(f"\n   Result Data:")
            snapshot_id = result.get('snapshot_id')
            workflows_count = result.get('workflows_count')
            commit_sha = result.get('commit_sha')

            if snapshot_id:
                print(f"     ✓ Snapshot ID: {snapshot_id[:8]}...")
            if workflows_count is not None:
                print(f"     ✓ Workflows: {workflows_count}")
            if commit_sha:
                print(f"     ✓ Commit SHA: {commit_sha[:8]}...")

        if job.get('error_message'):
            print(f"\n   ❌ Error: {job.get('error_message')}")

    print("\n" + "=" * 70)
    print("T007 Verification Summary")
    print("=" * 70)

    # Analyze results
    success_criteria = {
        'jobs_found': len(snapshot_jobs_result.data) > 0,
        'async_execution': False,
        'progress_tracking': False,
        'completion_data': False
    }

    # Check for async execution (job should complete quickly in terms of API response)
    for job in snapshot_jobs_result.data:
        if job.get('created_at') and job.get('started_at'):
            created = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
            started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
            response_time = (started - created).total_seconds()

            # If job started within 5 seconds of creation, it's async
            if response_time < 5:
                success_criteria['async_execution'] = True
                break

    # Check for progress tracking
    if jobs_with_progress:
        success_criteria['progress_tracking'] = True

        # Check for completion data
        for job_info in jobs_with_progress:
            if job_info['status'] == 'completed' and job_info.get('result'):
                result = job_info['result']
                if result.get('snapshot_id'):
                    success_criteria['completion_data'] = True
                    break

    print("\n✅ Acceptance Criteria:")
    print(f"  [{'✓' if success_criteria['jobs_found'] else '✗'}] Snapshot creation jobs found")
    print(f"  [{'✓' if success_criteria['async_execution'] else '✗'}] Async execution (non-blocking)")
    print(f"  [{'✓' if success_criteria['progress_tracking'] else '✗'}] Real-time progress tracking")
    print(f"  [{'✓' if success_criteria['completion_data'] else '✗'}] Completion data available")

    if all(success_criteria.values()):
        print("\n🎉 T007 PASSED: Real-time progress updates are working!")
        print("\nWhat this means:")
        print("  • Snapshot creation is async (non-blocking)")
        print("  • Progress data is tracked during execution")
        print("  • UI can display real-time updates on activity detail page")
        print("  • Completion summary is available when done")
    else:
        print("\n⚠️  T007 INCOMPLETE: Some criteria not met")

        if not success_criteria['jobs_found']:
            print("\n  → No snapshot jobs found. Please:")
            print("    1. Go to the Snapshots page in the UI")
            print("    2. Click 'Create Snapshot' button")
            print("    3. Verify you're redirected to /activity/{job_id}")
            print("    4. Run this verification script again")

        if not success_criteria['progress_tracking']:
            print("\n  → Progress tracking not detected. Check:")
            print("    1. snapshot_service.py emits progress updates")
            print("    2. background_job_service.update_progress() is called")
            print("    3. Progress data is persisted to database")

        if not success_criteria['completion_data']:
            print("\n  → Completion data not found. Ensure:")
            print("    1. Result includes snapshot_id, workflows_count")
            print("    2. Job completes successfully")

    # Additional check: Verify activity detail page would show progress
    print("\n" + "=" * 70)
    print("Activity Detail Page Progress Display Check")
    print("=" * 70)

    if jobs_with_progress:
        print("\nThe activity detail page will show:")

        for job_info in jobs_with_progress[:1]:  # Just show first job as example
            progress = job_info['progress']

            print(f"\nFor job: {job_info['job_id_short']}")
            print(f"  Status Badge: {job_info['status'].upper()}")

            current_step = progress.get('current_step') or progress.get('currentStep')
            if current_step:
                print(f"  Current Phase: '{current_step}'")

            current = progress.get('current')
            total = progress.get('total')
            if current is not None and total is not None and total > 0:
                percentage = (current / total * 100)
                print(f"  Progress Bar: {percentage:.1f}% ({current}/{total} workflows)")

            if job_info['status'] == 'completed':
                result = job_info.get('result') or {}
                print(f"\n  Completion Summary:")
                if result.get('snapshot_id'):
                    print(f"    • Snapshot ID: {result['snapshot_id'][:8]}...")
                if result.get('workflows_count') is not None:
                    print(f"    • Workflows: {result['workflows_count']}")
                if result.get('commit_sha'):
                    print(f"    • Commit: {result['commit_sha'][:8]}...")
    else:
        print("\n⚠️  No progress data to display")
        print("   Activity detail page will show limited information")

    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)

    print("\n1. Manual UI Verification:")
    print("   a. Open Snapshots page")
    print("   b. Click 'Create Snapshot'")
    print("   c. Verify immediate redirect to /activity/{job_id}")
    print("   d. Watch for:")
    print("      - Live progress bar updating")
    print("      - Current step/phase displayed")
    print("      - Real-time log messages (if SSE is working)")
    print("      - Completion summary when done")

    print("\n2. SSE Connection Verification:")
    print("   a. Open browser DevTools → Network tab")
    print("   b. Filter for 'eventsource' or '/stream'")
    print("   c. Verify SSE connection is established")
    print("   d. Check messages contain progress updates")

    print("\n3. If issues found:")
    print("   a. Check backend logs for SSE events")
    print("   b. Verify snapshot_service.py emits progress")
    print("   c. Ensure ActivityDetailPage.tsx handles updates")

async def test_live_snapshot_monitoring():
    """Create a snapshot and monitor it in real-time (optional interactive test)"""
    print("\n" + "=" * 70)
    print("OPTIONAL: Live Snapshot Creation Monitoring")
    print("=" * 70)

    proceed = input("\nDo you want to create a snapshot and monitor it live? (y/n): ").strip().lower()

    if proceed != 'y':
        print("Skipping live monitoring test.")
        return

    tenant_id = input("Enter tenant_id: ").strip()
    environment_id = input("Enter environment_id: ").strip()

    # Note: This would require importing snapshot_service and creating a job
    # For now, just provide instructions
    print("\nTo monitor a live snapshot creation:")
    print("1. Open the UI in your browser")
    print("2. Navigate to Snapshots page")
    print("3. Click 'Create Snapshot'")
    print("4. Watch the activity detail page for real-time updates")
    print("\nThis verification script will detect that job when you run the main test again.")

if __name__ == "__main__":
    try:
        asyncio.run(test_snapshot_async_verification())

        # Optional: Run live monitoring test
        # asyncio.run(test_live_snapshot_monitoring())

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
