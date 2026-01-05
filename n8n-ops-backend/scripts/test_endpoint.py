import requests
import json

base = "http://localhost:4000"
endpoints = [
    "/api/v1/billing/plan-features/all",
    "/api/v1/billing/feature-display-names",
    "/api/v1/billing/plan-configurations",
    "/api/v1/platform/entitlements/plan-features/all",
    "/api/v1/admin/entitlements/plan-features/all"
]

for ep in endpoints:
    url = base + ep
    try:
        r = requests.get(url, timeout=5)
        print(f"{ep}: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:5]}")
    except Exception as e:
        print(f"{ep}: ERROR - {e}")

