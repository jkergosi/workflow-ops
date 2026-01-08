"""
Direct test of sync functionality for specific environment
Bypasses API and calls services directly
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import db_service
from app.services.background_job_service import background_job_service, BackgroundJobType, BackgroundJobStatus
from app.services.canonical_env_sync_service import CanonicalEnvSyncService
from app.services.github_service import GitHubService

# Configuration
ENVIRONMENT_ID = "d509a3d2-ce7d-40ae-aced-a1c40859cc6d"

async def get_environment_info():
    """Get environment information from database"""
    print("=" * 80)
    print("ENVIRONMENT INFORMATION")
    print("=" * 80)

    # Get environment
    env_result = db_service.client.table("environments").select(
        "id, tenant_id, n8n_name, environment_class, git_repo_url, git_pat, git_folder, n8n_base_url"
    ).eq("id", ENVIRONMENT_ID).execute()

    if not env_result.data:
        print(f"[ERROR] Environment {ENVIRONMENT_ID} not found")
        return None, None

    env = env_result.data[0]
    tenant_id = env["tenant_id"]

    print(f"Environment ID: {env['id']}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Name: {env.get('n8n_name', 'N/A')}")
    print(f"Class: {env.get('environment_class', 'N/A')}")
    print(f"n8n URL: {env.get('n8n_base_url', 'N/A')}")
    print(f"Git Repo: {env.get('git_repo_url', 'N/A')}")
    print(f"Git Folder: {env.get('git_folder', 'N/A')}")
    print(f"Git PAT: {'[CONFIGURED]' if env.get('git_pat') else '[NOT CONFIGURED]'}")

    if env.get('environment_class', '').lower() != 'dev':
        print(f"\n[WARNING] This is not a DEV environment (class: {env.get('environment_class')})")
        print("Phase 2 Git sync only works for DEV environments")

    if not env.get('git_repo_url') or not env.get('git_pat'):
        print("\n[ERROR] Git is not configured for this environment")
        return tenant_id, env

    print("\n[OK] Environment is properly configured for sync")
    return tenant_id, env

async def trigger_phase1_sync(tenant_id, environment):
    """Trigger Phase 1 sync (n8n -> DB) directly"""
    print("\n" + "=" * 80)
    print("TRIGGERING PHASE 1 SYNC (n8n -> DB)")
    print("=" * 80)

    try:
        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.CANONICAL_ENV_SYNC,
            resource_id=ENVIRONMENT_ID,
            resource_type="environment",
            created_by=None
        )

        job_id = job["id"]
        print(f"Created job: {job_id}")

        # Start the job
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )

        # Initialize the sync service
        sync_service = CanonicalEnvSyncService(
            tenant_id=tenant_id,
            environment_id=ENVIRONMENT_ID,
            environment=environment,
            job_id=job_id
        )

        print("Starting Phase 1 sync...")

        # Run the sync
        result = await sync_service.run_sync()

        # Update job with result
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=result
        )

        print(f"[SUCCESS] Phase 1 completed")
        print(f"  Observed workflows: {len(result.get('observed_workflow_ids', []))}")
        print(f"  Created workflows: {len(result.get('created_workflow_ids', []))}")
        print(f"  Updated workflows: {len(result.get('updated_workflow_ids', []))}")

        return job_id, result

    except Exception as e:
        print(f"[ERROR] Phase 1 failed: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update job as failed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )
        return None, None

async def trigger_phase2_sync(tenant_id, environment, phase1_job_id):
    """Trigger Phase 2 sync (DB -> Git) directly"""
    print("\n" + "=" * 80)
    print("TRIGGERING PHASE 2 SYNC (DB -> Git)")
    print("=" * 80)

    try:
        # Import the Phase 2 function
        from app.api.endpoints.canonical_workflows import _commit_dev_workflows_to_git

        # Create background job for Phase 2
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.DEV_GIT_SYNC,
            resource_id=ENVIRONMENT_ID,
            resource_type="environment",
            created_by=None,
            metadata={"phase1_job_id": phase1_job_id}
        )

        job_id = job["id"]
        print(f"Created Phase 2 job: {job_id}")

        # Start the job
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )

        print("Starting Phase 2 sync...")

        # Run Phase 2 sync
        result = await _commit_dev_workflows_to_git(
            tenant_id=tenant_id,
            environment_id=ENVIRONMENT_ID,
            environment=environment,
            phase2_job_id=job_id,
            phase1_job_id=phase1_job_id
        )

        print(f"[SUCCESS] Phase 2 completed")
        print(f"  Workflows persisted: {result.get('workflows_persisted', 0)}")
        if result.get('commit_sha'):
            print(f"  Commit SHA: {result['commit_sha']}")

        return job_id, result

    except Exception as e:
        print(f"[ERROR] Phase 2 failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

async def verify_git_state(tenant_id):
    """Verify that workflows were persisted to Git"""
    print(f"\n" + "=" * 80)
    print("VERIFYING GIT STATE")
    print("=" * 80)

    # Check canonical_workflow_git_state table
    git_state_result = db_service.client.table("canonical_workflow_git_state").select(
        "canonical_id, git_content_hash, last_git_sync_at"
    ).eq("tenant_id", tenant_id).eq("environment_id", ENVIRONMENT_ID).order(
        "last_git_sync_at", desc=True
    ).limit(10).execute()

    if git_state_result.data:
        print(f"\n[OK] Found {len(git_state_result.data)} workflow(s) in Git state:")
        for idx, state in enumerate(git_state_result.data[:5], 1):
            canonical_id = state["canonical_id"]
            last_sync = state.get("last_git_sync_at", "N/A")
            if last_sync != "N/A":
                last_sync = last_sync[:19]
            print(f"  {idx}. Canonical ID: {canonical_id[:16]}..., Last sync: {last_sync}")
        return True
    else:
        print("\n[WARNING] No workflows found in Git state table")
        print("This may indicate that Phase 2 did not persist any workflows")
        return False

async def check_recent_syncs(tenant_id):
    """Check for recent sync jobs"""
    print(f"\n" + "=" * 80)
    print("RECENT SYNC JOBS (Last 24 hours)")
    print("=" * 80)

    twenty_four_hours_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    # Get Phase 1 jobs
    phase1_result = db_service.client.table("background_jobs").select(
        "id, status, created_at, completed_at"
    ).eq("tenant_id", tenant_id).eq("resource_id", ENVIRONMENT_ID).eq(
        "job_type", "canonical_env_sync"
    ).gte("created_at", twenty_four_hours_ago).order("created_at", desc=True).limit(5).execute()

    print(f"\nPhase 1 jobs: {len(phase1_result.data)}")
    for job in phase1_result.data:
        print(f"  - {job['id'][:12]}... | {job['status']} | {job['created_at'][:19]}")

    # Get Phase 2 jobs
    phase2_result = db_service.client.table("background_jobs").select(
        "id, status, created_at, completed_at"
    ).eq("tenant_id", tenant_id).eq("resource_id", ENVIRONMENT_ID).eq(
        "job_type", "dev_git_sync"
    ).gte("created_at", twenty_four_hours_ago).order("created_at", desc=True).limit(5).execute()

    print(f"\nPhase 2 jobs: {len(phase2_result.data)}")
    for job in phase2_result.data:
        print(f"  - {job['id'][:12]}... | {job['status']} | {job['created_at'][:19]}")

async def run_full_test():
    """Run the full sync test"""
    print("\n" + "=" * 80)
    print("FULL BACKEND SYNC TEST (DIRECT)")
    print(f"Environment: {ENVIRONMENT_ID}")
    print("=" * 80)

    # Step 1: Get environment info
    tenant_id, env = await get_environment_info()
    if not tenant_id:
        return False

    # Step 2: Check recent syncs
    await check_recent_syncs(tenant_id)

    # Step 3: Run Phase 1
    phase1_job_id, phase1_result = await trigger_phase1_sync(tenant_id, env)
    if not phase1_job_id:
        print("\n[FAILED] Phase 1 did not complete successfully")
        return False

    # Step 4: Run Phase 2 (only for DEV environments)
    if env.get('environment_class', '').lower() == 'dev':
        phase2_job_id, phase2_result = await trigger_phase2_sync(tenant_id, env, phase1_job_id)
        if not phase2_job_id:
            print("\n[FAILED] Phase 2 did not complete successfully")
            return False
    else:
        print("\n[SKIPPED] Phase 2 - Not a DEV environment")
        phase2_result = None

    # Step 5: Verify Git state
    git_verified = await verify_git_state(tenant_id)

    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    print(f"\n[SUCCESS] Phase 1 (n8n -> DB): COMPLETED")
    print(f"   - Observed workflows: {len(phase1_result.get('observed_workflow_ids', []))}")
    print(f"   - Job ID: {phase1_job_id}")

    if phase2_result:
        print(f"\n[SUCCESS] Phase 2 (DB -> Git): COMPLETED")
        print(f"   - Workflows persisted: {phase2_result.get('workflows_persisted', 0)}")
        print(f"   - Commit SHA: {phase2_result.get('commit_sha', 'N/A')}")
        print(f"\n[SUCCESS] Full sync completed successfully, including GitHub push!")
    else:
        print(f"\n[INFO] Phase 2 skipped (non-DEV environment)")

    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(run_full_test())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[EXCEPTION] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
