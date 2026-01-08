"""
Fix stuck sync jobs and trigger a fresh sync
"""
import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import db_service
from app.services.background_job_service import background_job_service, BackgroundJobType, BackgroundJobStatus
from app.services.canonical_env_sync_service import CanonicalEnvSyncService

# Configuration
ENVIRONMENT_ID = "d509a3d2-ce7d-40ae-aced-a1c40859cc6d"

async def fix_stuck_jobs(tenant_id):
    """Fix jobs that are stuck in running status"""
    print("=" * 80)
    print("FIXING STUCK JOBS")
    print("=" * 80)

    # Find all running jobs for this environment
    running_jobs = db_service.client.table("background_jobs").select(
        "id, created_at, started_at"
    ).eq("tenant_id", tenant_id).eq("resource_id", ENVIRONMENT_ID).eq(
        "status", "running"
    ).execute()

    if not running_jobs.data:
        print("No stuck jobs found")
        return

    print(f"Found {len(running_jobs.data)} stuck job(s) in running status:")

    for job in running_jobs.data:
        print(f"  - {job['id'][:12]}... created: {job['created_at'][:19]}")

        # Mark as failed with a note
        db_service.client.table("background_jobs").update({
            "status": "failed",
            "error_message": "Job was stuck in running status - reset by sync test script",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job["id"]).execute()

        print(f"    -> Marked as failed")

    print(f"\n[OK] Fixed {len(running_jobs.data)} stuck job(s)")

async def trigger_new_sync(tenant_id, environment):
    """Trigger a fresh sync"""
    print("\n" + "=" * 80)
    print("TRIGGERING FRESH SYNC")
    print("=" * 80)

    # Create Phase 1 job
    job = await background_job_service.create_job(
        tenant_id=tenant_id,
        job_type=BackgroundJobType.CANONICAL_ENV_SYNC,
        resource_id=ENVIRONMENT_ID,
        resource_type="environment",
        created_by=None
    )

    job_id = job["id"]
    print(f"Created Phase 1 job: {job_id}")

    # Start the job
    await background_job_service.update_job_status(
        job_id=job_id,
        status=BackgroundJobStatus.RUNNING
    )

    print("Running Phase 1 sync...")

    try:
        # Call the service method directly
        results = await CanonicalEnvSyncService.sync_environment(
            tenant_id=tenant_id,
            environment_id=ENVIRONMENT_ID,
            environment=environment,
            job_id=job_id,
            checkpoint=None,
            tenant_id_for_sse=tenant_id
        )

        # Update job as completed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=results
        )

        print(f"[SUCCESS] Phase 1 completed")
        print(f"  Observed workflows: {len(results.get('observed_workflow_ids', []))}")
        print(f"  Created workflows: {len(results.get('created_workflow_ids', []))}")
        print(f"  Updated workflows: {len(results.get('updated_workflow_ids', []))}")

        return job_id, results

    except Exception as e:
        print(f"[ERROR] Phase 1 failed: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark job as failed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

        return None, None

async def trigger_phase2(tenant_id, environment, phase1_job_id):
    """Trigger Phase 2 Git sync"""
    print("\n" + "=" * 80)
    print("TRIGGERING PHASE 2 GIT SYNC")
    print("=" * 80)

    # Import the Phase 2 function
    from app.api.endpoints.canonical_workflows import _run_dev_git_sync_background

    # Create Phase 2 job
    job = await background_job_service.create_job(
        tenant_id=tenant_id,
        job_type=BackgroundJobType.DEV_GIT_SYNC,
        resource_id=ENVIRONMENT_ID,
        resource_type="environment",
        created_by=None,
        metadata={
            "phase1_job_id": phase1_job_id,
            "environment_id": ENVIRONMENT_ID
        }
    )

    phase2_job_id = job["id"]
    print(f"Created Phase 2 job: {phase2_job_id}")

    print("Running Phase 2 sync...")

    try:
        # Run Phase 2 directly
        await _run_dev_git_sync_background(
            phase2_job_id,
            tenant_id,
            ENVIRONMENT_ID,
            environment,
            phase1_job_id
        )

        # Get the final job status
        final_job = await background_job_service.get_job(phase2_job_id)

        if final_job.get("status") == "completed":
            result = final_job.get("result", {})
            print(f"[SUCCESS] Phase 2 completed")
            print(f"  Workflows persisted to Git: {result.get('workflows_persisted', 0)}")
            if result.get('commit_sha'):
                print(f"  Commit SHA: {result['commit_sha']}")
            return phase2_job_id, result
        else:
            print(f"[ERROR] Phase 2 failed: {final_job.get('error_message', 'Unknown error')}")
            return None, None

    except Exception as e:
        print(f"[ERROR] Phase 2 failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

async def verify_sync(tenant_id):
    """Verify the sync results"""
    print("\n" + "=" * 80)
    print("VERIFYING SYNC RESULTS")
    print("=" * 80)

    # Check Git state
    git_state = db_service.client.table("canonical_workflow_git_state").select(
        "canonical_id, git_content_hash, last_repo_sync_at"
    ).eq("tenant_id", tenant_id).eq("environment_id", ENVIRONMENT_ID).order(
        "last_repo_sync_at", desc=True
    ).limit(10).execute()

    if git_state.data:
        print(f"\n[OK] Found {len(git_state.data)} workflow(s) in Git state:")
        for idx, state in enumerate(git_state.data[:5], 1):
            canonical_id = state["canonical_id"]
            synced_at = state.get("last_repo_sync_at", "N/A")
            if synced_at != "N/A":
                synced_at = synced_at[:19]
            print(f"  {idx}. Canonical ID: {canonical_id[:16]}..., Last sync: {synced_at}")
    else:
        print("\n[WARNING] No workflows in Git state")

    # Check recent jobs
    print("\n" + "-" * 80)
    print("Recent Phase 2 jobs:")
    print("-" * 80)

    phase2_jobs = db_service.client.table("background_jobs").select(
        "id, status, created_at, result"
    ).eq("tenant_id", tenant_id).eq("resource_id", ENVIRONMENT_ID).eq(
        "job_type", "dev_git_sync"
    ).order("created_at", desc=True).limit(3).execute()

    if phase2_jobs.data:
        for job in phase2_jobs.data:
            result = job.get("result", {})
            print(f"  - {job['id'][:12]}... | {job['status']} | {job['created_at'][:19]}")
            if result:
                print(f"    Workflows persisted: {result.get('workflows_persisted', 0)}")
    else:
        print("  No Phase 2 jobs found")

async def main():
    """Main function"""
    print("=" * 80)
    print("FIX STUCK JOBS AND TEST SYNC")
    print(f"Environment: {ENVIRONMENT_ID}")
    print("=" * 80)

    # Get environment info (select all fields with *)
    env_result = db_service.client.table("environments").select("*").eq("id", ENVIRONMENT_ID).execute()

    if not env_result.data:
        print(f"[ERROR] Environment {ENVIRONMENT_ID} not found")
        return False

    env = env_result.data[0]
    tenant_id = env["tenant_id"]

    print(f"\nEnvironment: {env.get('n8n_name', 'N/A')}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Class: {env.get('environment_class', 'N/A')}")
    print(f"Git Repo: {env.get('git_repo_url', 'N/A')}")

    # Step 1: Fix stuck jobs
    await fix_stuck_jobs(tenant_id)

    # Step 2: Trigger new sync
    phase1_job_id, phase1_result = await trigger_new_sync(tenant_id, env)
    if not phase1_job_id:
        print("\n[FAILED] Could not complete Phase 1 sync")
        return False

    # Step 3: Trigger Phase 2 (for DEV environments)
    if env.get('environment_class', '').lower() == 'dev':
        if env.get('git_repo_url') and env.get('git_pat'):
            phase2_job_id, phase2_result = await trigger_phase2(tenant_id, env, phase1_job_id)
            if not phase2_job_id:
                print("\n[FAILED] Could not complete Phase 2 sync")
                return False
        else:
            print("\n[SKIPPED] Phase 2 - Git not configured")
            phase2_result = None
    else:
        print("\n[SKIPPED] Phase 2 - Not a DEV environment")
        phase2_result = None

    # Step 4: Verify results
    await verify_sync(tenant_id)

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print(f"\n[SUCCESS] Phase 1 (n8n -> DB): COMPLETED")
    print(f"  Observed workflows: {len(phase1_result.get('observed_workflow_ids', []))}")

    if phase2_result:
        print(f"\n[SUCCESS] Phase 2 (DB -> Git): COMPLETED")
        print(f"  Workflows persisted: {phase2_result.get('workflows_persisted', 0)}")
        print(f"  Commit SHA: {phase2_result.get('commit_sha', 'N/A')}")
        print(f"\n[SUCCESS] Full sync completed successfully, including GitHub push!")
        return True
    else:
        print(f"\n[PARTIAL] Phase 1 completed, but Phase 2 was not run")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[EXCEPTION] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
