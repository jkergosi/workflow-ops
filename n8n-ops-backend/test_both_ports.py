"""Test deletion endpoint on both ports 3000 and 4000"""
import requests
import sys

dep_id = '878b8e13-d7dd-42aa-a619-b47fab43c2aa'

print("=" * 60)
print("TESTING DELETION ON BOTH PORTS")
print("=" * 60)

for port in [3000, 4000]:
    print(f"\n--- Testing Port {port} ---")
    try:
        url = f'http://localhost:{port}/api/v1/deployments/{dep_id}'
        response = requests.delete(
            url,
            headers={'Authorization': 'Bearer test'},
            timeout=3
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        
        if "7 days" in response.text or "7 day" in response.text:
            print(f"❌ PORT {port} HAS OLD CODE (7 days)")
        elif "1 day" in response.text:
            print(f"✅ PORT {port} HAS NEW CODE (1 day)")
        else:
            print(f"⚠️  PORT {port} - Unexpected response")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Port {port} - Connection refused (not running)")
    except Exception as e:
        print(f"❌ Port {port} - Error: {e}")

print("\n" + "=" * 60)

