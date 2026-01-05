"""Direct API endpoint testing"""
import requests
import json

base_url = "http://localhost:4000"
endpoint = f"{base_url}/api/v1/billing/plan-features/all"

print(f"Testing: {endpoint}")
print("=" * 60)

try:
    response = requests.get(endpoint, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ SUCCESS - Endpoint is accessible!")
        print(f"\nResponse structure:")
        print(f"  Plans: {list(data.keys())}")
        
        for plan_name in data.keys():
            features = data[plan_name]
            print(f"  {plan_name}: {len(features)} features")
            
            # Show sample features
            sample = list(features.items())[:3]
            for feat_name, feat_value in sample:
                print(f"    - {feat_name}: {feat_value} ({type(feat_value).__name__})")
        
        # Check for flag and limit features
        has_flag = any(isinstance(v, bool) for plan in data.values() for v in plan.values())
        has_limit = any(isinstance(v, (int, float)) for plan in data.values() for v in plan.values())
        
        print(f"\nFeature types:")
        print(f"  Flag features (boolean): {'✅' if has_flag else '❌'}")
        print(f"  Limit features (numeric): {'✅' if has_limit else '❌'}")
        
    else:
        print(f"\n❌ FAILED - Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to server")
    print("Make sure the backend server is running on port 4000")
except Exception as e:
    print(f"❌ Error: {e}")

