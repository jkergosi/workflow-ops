"""
Test to verify deletion restrictions work correctly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from app.services.database import db_service
from app.schemas.deployment import DeploymentStatus

def test_deletion_logic():
    """Test the deletion logic for different deployment statuses"""
    print("=" * 70)
    print("Testing Deployment Deletion Logic")
    print("=" * 70)
    
    # Get deployments with different statuses
    result = db_service.client.table("deployments").select("*").eq("tenant_id", "00000000-0000-0000-0000-000000000000").limit(10).execute()
    
    deployments = result.data or []
    
    print(f"\nFound {len(deployments)} deployment(s):\n")
    
    for dep in deployments:
        dep_id = dep.get('id', 'unknown')[:8]
        status = dep.get('status')
        created_at_str = dep.get('created_at')
        
        print(f"Deployment: {dep_id}...")
        print(f"  Status: {status}")
        print(f"  Created at: {created_at_str}")
        
        # Simulate the deletion logic
        if status == DeploymentStatus.RUNNING.value:
            print(f"  [BLOCKED] Cannot delete running deployments")
        elif status == DeploymentStatus.SUCCESS.value:
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
                if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
                    created_at_naive = created_at.replace(tzinfo=None)
                else:
                    created_at_naive = created_at
                age_days = (datetime.utcnow() - created_at_naive).days
                min_age_days = 1
                if age_days < min_age_days:
                    print(f"  [BLOCKED] Successful deployment must be at least {min_age_days} day old (currently {age_days} days)")
                else:
                    print(f"  [ALLOWED] Successful deployment is {age_days} days old (>= {min_age_days} day)")
            else:
                print(f"  [ALLOWED] Missing created_at, allowing deletion")
        elif status in [DeploymentStatus.FAILED.value, DeploymentStatus.CANCELED.value]:
            print(f"  [ALLOWED] Failed/canceled deployments can be deleted immediately")
        else:
            print(f"  [ALLOWED] Other status ({status}) - no restriction")
        
        print()

if __name__ == "__main__":
    test_deletion_logic()
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)

