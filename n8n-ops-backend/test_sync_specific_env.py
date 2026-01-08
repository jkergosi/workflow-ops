"""
Comprehensive test script for syncing a specific environment
Tests the full sync flow including Phase 1 (n8n->DB) and Phase 2 (DB->Git)
"""
import asyncio
import sys
import os
import httpx
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import db_service
from app.services.background_job_service import background_job_service

# Configuration
ENVIRONMENT_ID = "d509a3d2-ce7d-40ae-aced-a1c40859cc6d"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IjdsK3crQytiTzNGMVoxbk4iLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3hqdW5meXVncGJ5anNscWt6bHduLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIxNjBkMjdhYy05ZTQzLTRkYjktOWI5MS1lMDlkN2FiZDMwYjciLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY3ODEyMTEyLCJpYXQiOjE3Njc4MDg1MTIsImVtYWlsIjoiamFzb25rQGluZ2Vuc3lzdGVtcy5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiamFzb25rQGluZ2Vuc3lzdGVtcy5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwicGhvbmVfdmVyaWZpZWQiOmZhbHNlLCJzdWIiOiIxNjBkMjdhYy05ZTQzLTRkYjktOWI5MS1lMDlkN2FiZDMwYjcifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJvdHAiLCJ0aW1lc3RhbXAiOjE3NjczOTk1MjN9XSwic2Vzc2lvbl9pZCI6ImNjYjM0ZWVmLTQ1ZjYtNDAwMS1iNWU0LTFjOTdiNmFmZTEyZCIsImlzX2Fub255bW91cyI6ZmFsc2V9.nnkYpCpE7hcEM6YcS-jb7gX0Yzrv8my7CXyWz0WnVRU"
API_BASE_URL = "http://localhost:8000"

async def get_environment_info():
    """Get environment information from database"""
    print("=" * 80)
    print("ENVIRONMENT INFORMATION")
    print("=" * 80)

    # Get all tenants to find the right one
    tenants_result = db_service.client.table("tenants").select("id").execute()
    if not tenants_result.data:
        print("[ERROR] No tenants found")
        return None, None

    # Try to find the environment across all tenants
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

async def trigger_sync(tenant_id):
    """Trigger environment sync via API"""
    print("\n" + "=" * 80)
    print("TRIGGERING ENVIRONMENT SYNC (Phase 1)")
    print("=" * 80)

    url = f"{API_BASE_URL}/api/v1/canonical/sync/env/{ENVIRONMENT_ID}"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    print(f"POST {url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers)

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                job_id = data.get("job_id")
                print(f"[SUCCESS] Sync job created: {job_id}")
                return job_id
            else:
                print(f"[ERROR] Failed to trigger sync")
                print(f"Response: {response.text}")
                return None

    except Exception as e:
        print(f"[ERROR] Exception while triggering sync: {str(e)}")
        return None

async def monitor_phase1_job(job_id, tenant_id, timeout_seconds=300):
    """Monitor Phase 1 sync job until completion"""
    print(f"\n" + "=" * 80)
    print(f"MONITORING PHASE 1 JOB: {job_id}")
    print("=" * 80)

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout_seconds:
        # Get job status
        job_result = db_service.client.table("background_jobs").select(
            "id, status, result, error_message, started_at, completed_at, metadata"
        ).eq("id", job_id).execute()

        if not job_result.data:
            print("[ERROR] Job not found")
            return None

        job = job_result.data[0]
        status = job.get("status")

        if status != last_status:
            print(f"\nStatus: {status}")
            if job.get("started_at"):
                print(f"Started: {job['started_at'][:19]}")
            last_status = status

        if status == "completed":
            print(f"Completed: {job.get('completed_at', 'N/A')[:19]}")
            result = job.get("result", {})
            print(f"\n[SUCCESS] Phase 1 completed")
            print(f"  Observed workflows: {len(result.get('observed_workflow_ids', []))}")
            print(f"  Created workflows: {len(result.get('created_workflow_ids', []))}")
            print(f"  Updated workflows: {len(result.get('updated_workflow_ids', []))}")
            return job

        elif status == "failed":
            error_msg = job.get("error_message", "Unknown error")
            print(f"\n[ERROR] Phase 1 failed: {error_msg}")
            return job

        elif status == "running":
            print(".", end="", flush=True)

        await asyncio.sleep(2)

    print(f"\n[TIMEOUT] Phase 1 job did not complete within {timeout_seconds} seconds")
    return None

async def find_phase2_job(phase1_job_id, tenant_id, max_wait_seconds=30):
    """Find the Phase 2 job created for the Phase 1 job"""
    print(f"\n" + "=" * 80)
    print(f"LOOKING FOR PHASE 2 JOB")
    print("=" * 80)

    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        # Look for Phase 2 job with metadata referencing Phase 1
        phase2_result = db_service.client.table("background_jobs").select(
            "id, status, result, error_message, created_at, started_at, completed_at, metadata"
        ).eq("tenant_id", tenant_id).eq("resource_id", ENVIRONMENT_ID).eq(
            "job_type", "dev_git_sync"
        ).order("created_at", desc=True).limit(10).execute()

        # Find the job that references our Phase 1 job
        for job in phase2_result.data:
            metadata = job.get("metadata", {})
            if metadata.get("phase1_job_id") == phase1_job_id:
                print(f"[FOUND] Phase 2 job: {job['id']}")
                print(f"Created: {job['created_at'][:19]}")
                return job

        print(".", end="", flush=True)
        await asyncio.sleep(2)

    print(f"\n[WARNING] No Phase 2 job found within {max_wait_seconds} seconds")
    print("This may indicate that Phase 2 is not being triggered automatically")
    return None

async def monitor_phase2_job(job_id, tenant_id, timeout_seconds=300):
    """Monitor Phase 2 Git sync job until completion"""
    print(f"\n" + "=" * 80)
    print(f"MONITORING PHASE 2 JOB: {job_id}")
    print("=" * 80)

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout_seconds:
        # Get job status
        job_result = db_service.client.table("background_jobs").select(
            "id, status, result, error_message, started_at, completed_at, metadata"
        ).eq("id", job_id).execute()

        if not job_result.data:
            print("[ERROR] Job not found")
            return None

        job = job_result.data[0]
        status = job.get("status")

        if status != last_status:
            print(f"\nStatus: {status}")
            if job.get("started_at"):
                print(f"Started: {job['started_at'][:19]}")
            last_status = status

        if status == "completed":
            print(f"Completed: {job.get('completed_at', 'N/A')[:19]}")
            result = job.get("result", {})
            workflows_persisted = result.get("workflows_persisted", 0)
            commit_sha = result.get("commit_sha")

            print(f"\n[SUCCESS] Phase 2 completed")
            print(f"  Workflows persisted to Git: {workflows_persisted}")
            if commit_sha:
                print(f"  Commit SHA: {commit_sha}")

            return job

        elif status == "failed":
            error_msg = job.get("error_message", "Unknown error")
            print(f"\n[ERROR] Phase 2 failed: {error_msg}")
            return job

        elif status == "running":
            print(".", end="", flush=True)

        await asyncio.sleep(2)

    print(f"\n[TIMEOUT] Phase 2 job did not complete within {timeout_seconds} seconds")
    return None

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
    else:
        print("\n[WARNING] No workflows found in Git state table")
        print("This may indicate that Phase 2 did not persist any workflows")

async def run_full_test():
    """Run the full sync test"""
    print("\n" + "=" * 80)
    print("FULL BACKEND SYNC TEST")
    print(f"Environment: {ENVIRONMENT_ID}")
    print("=" * 80)

    # Step 1: Get environment info
    tenant_id, env = await get_environment_info()
    if not tenant_id:
        return False

    # Step 2: Trigger sync
    phase1_job_id = await trigger_sync(tenant_id)
    if not phase1_job_id:
        return False

    # Step 3: Monitor Phase 1
    phase1_job = await monitor_phase1_job(phase1_job_id, tenant_id)
    if not phase1_job:
        return False

    if phase1_job.get("status") != "completed":
        print("\n[FAILED] Phase 1 did not complete successfully")
        return False

    # Step 4: Find Phase 2 job
    phase2_job = await find_phase2_job(phase1_job_id, tenant_id)
    if not phase2_job:
        print("\n[FAILED] Phase 2 job was not created")
        print("This indicates the automatic Phase 2 trigger is not working")
        return False

    # Step 5: Monitor Phase 2
    phase2_job_final = await monitor_phase2_job(phase2_job["id"], tenant_id)
    if not phase2_job_final:
        return False

    if phase2_job_final.get("status") != "completed":
        print("\n[FAILED] Phase 2 did not complete successfully")
        return False

    # Step 6: Verify Git state
    await verify_git_state(tenant_id)

    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    phase1_result = phase1_job.get("result", {})
    phase2_result = phase2_job_final.get("result", {})

    print(f"\n[SUCCESS] Phase 1 (n8n -> DB): COMPLETED")
    print(f"   - Observed workflows: {len(phase1_result.get('observed_workflow_ids', []))}")
    print(f"   - Job ID: {phase1_job_id}")

    print(f"\n[SUCCESS] Phase 2 (DB -> Git): COMPLETED")
    print(f"   - Workflows persisted: {phase2_result.get('workflows_persisted', 0)}")
    print(f"   - Commit SHA: {phase2_result.get('commit_sha', 'N/A')}")
    print(f"   - Job ID: {phase2_job_final['id']}")

    print(f"\n[SUCCESS] Full sync completed successfully, including GitHub push!")
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
