import requests
import time

dep_id = '878b8e13-d7dd-42aa-a619-b47fab43c2aa'

print("Waiting for backend to start...")
time.sleep(8)

print("=" * 60)
print("TESTING DELETION ENDPOINT")
print("=" * 60)

try:
    url = f'http://localhost:4000/api/v1/deployments/{dep_id}'
    response = requests.delete(
        url,
        headers={'Authorization': 'Bearer test'},
        timeout=5
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if "7 days" in response.text or "7 day" in response.text:
        print("\n*** ERROR: Backend is returning OLD CODE (7 days) ***")
        print("The backend process needs to be completely restarted.")
    elif "1 day" in response.text:
        print("\n*** SUCCESS: Backend is returning NEW CODE (1 day) ***")
    else:
        print("\n*** Unexpected response format ***")
        
except Exception as e:
    print(f"Error: {e}")

