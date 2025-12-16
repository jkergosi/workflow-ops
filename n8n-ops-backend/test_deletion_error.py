"""Test the deletion endpoint to see what error message it actually returns"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from app.main import app
from app.services.database import db_service

client = TestClient(app)

print("=" * 60)
print("TESTING DELETION ENDPOINT")
print("=" * 60)

# Get a deployment
print("\n1. Fetching deployments...")
response = client.get('/api/v1/deployments/', headers={'Authorization': 'Bearer test'})
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    deployments = data.get('deployments', [])
    
    if deployments:
        # Find a successful deployment that's less than 1 day old
        from datetime import datetime
        now = datetime.utcnow()
        
        for dep in deployments:
            dep_id = dep['id']
            dep_status = dep.get('status')
            created_at_str = dep.get('created_at')
            
            if dep_status == 'success' and created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                age_days = (now - created_at.replace(tzinfo=None)).days
                
                print(f"\n2. Found deployment:")
                print(f"   ID: {dep_id[:8]}...")
                print(f"   Status: {dep_status}")
                print(f"   Created: {created_at_str}")
                print(f"   Age: {age_days} days")
                
                if age_days < 1:
                    print(f"\n3. Attempting to delete (should fail with age restriction)...")
                    del_response = client.delete(
                        f'/api/v1/deployments/{dep_id}',
                        headers={'Authorization': 'Bearer test'}
                    )
                    print(f"   Status: {del_response.status_code}")
                    print(f"   Response: {del_response.text}")
                    
                    # Check if error message contains "7 days" or "1 day"
                    if "7 days" in del_response.text or "7 day" in del_response.text:
                        print("\n   ❌ ERROR: Response contains '7 days' - OLD CODE IS RUNNING!")
                    elif "1 day" in del_response.text or "1 days" in del_response.text:
                        print("\n   ✅ Response contains '1 day' - NEW CODE IS RUNNING!")
                    else:
                        print(f"\n   ⚠️  Unexpected error message format")
                    break
        else:
            print("\n   No suitable deployment found (all are >= 1 day old)")
    else:
        print("\n   No deployments found")
else:
    print(f"\n   Failed to fetch deployments: {response.text}")

print("\n" + "=" * 60)

