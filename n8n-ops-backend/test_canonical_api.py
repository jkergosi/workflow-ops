#!/usr/bin/env python3
"""
Test script for canonical workflow API endpoints
Usage: python test_canonical_api.py <bearer_token>
"""
import sys
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
BEARER_TOKEN = sys.argv[1] if len(sys.argv) > 1 else None

if not BEARER_TOKEN:
    print("Usage: python test_canonical_api.py <bearer_token>")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

def test_endpoint(method, path, data=None):
    """Test an API endpoint"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            print(f"Unsupported method: {method}")
            return None
        
        print(f"\n{method} {path}")
        print(f"Status: {response.status_code}")
        if response.status_code < 400:
            try:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return result
            except:
                print(f"Response: {response.text}")
                return response.text
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

print("=" * 60)
print("Testing Canonical Workflow API Endpoints")
print("=" * 60)

# Test 1: Onboarding Preflight
print("\n1. Testing Onboarding Preflight")
preflight = test_endpoint("GET", "/canonical/onboarding/preflight")

# Test 2: Check Onboarding Complete
print("\n2. Testing Onboarding Complete Check")
complete_check = test_endpoint("GET", "/canonical/onboarding/complete")

# Test 3: List Canonical Workflows
print("\n3. Testing List Canonical Workflows")
workflows = test_endpoint("GET", "/canonical/canonical-workflows")

# Test 4: List Workflow Mappings
print("\n4. Testing List Workflow Mappings")
mappings = test_endpoint("GET", "/canonical/workflow-mappings")

# Test 5: List Diff States
print("\n5. Testing List Diff States")
diff_states = test_endpoint("GET", "/canonical/diff-states")

# Test 6: List Link Suggestions
print("\n6. Testing List Link Suggestions")
suggestions = test_endpoint("GET", "/canonical/link-suggestions")

print("\n" + "=" * 60)
print("Testing Complete")
print("=" * 60)

