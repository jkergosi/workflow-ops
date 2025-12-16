"""Test entitlements API endpoints."""
import requests
import json

TENANT_ID = "00000000-0000-0000-0000-000000000000"
BASE_URL = "http://localhost:3000/api/v1"
TOKEN = f"dev-token-{TENANT_ID}"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

print("Testing /auth/status endpoint...")
try:
    response = requests.get(f"{BASE_URL}/auth/status", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response text (first 500 chars): {response.text[:500]}")
    if response.status_code == 200:
        try:
            data = response.json()
            print("\nEntitlements:")
            if data.get("entitlements"):
                ents = data["entitlements"]
                print(f"  Plan: {ents.get('plan_name')}")
                print(f"  Features:")
                features = ents.get("features", {})
                print(f"    environment_limits: {features.get('environment_limits')}")
                print(f"    workflow_ci_cd: {features.get('workflow_ci_cd')}")
                print(f"    All features: {json.dumps(features, indent=4)}")
            else:
                print("  No entitlements in response!")
                print(f"  Full response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            print("Raw response:")
            print(response.text)
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50)
print("Testing /admin/entitlements/debug endpoint...")
try:
    response = requests.get(f"{BASE_URL}/admin/entitlements/debug/{TENANT_ID}", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response text (first 500 chars): {response.text[:500]}")
    if response.status_code == 200:
        try:
            data = response.json()
            print("\nDebug Info:")
            print(f"  Tenant Plan: {data.get('tenant_plan', {}).get('plan_name')}")
            print(f"  Computed Entitlements:")
            comp = data.get("computed_entitlements", {})
            print(f"    Plan: {comp.get('plan_name')}")
            print(f"    workflow_ci_cd_enabled: {comp.get('workflow_ci_cd_enabled')}")
            features = comp.get('all_features', {})
            print(f"    environment_limits: {features.get('environment_limits')}")
            print(f"    All features: {json.dumps(features, indent=4)}")
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            print("Raw response:")
            print(response.text)
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")
