"""Test stale deployment detection logic"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app.services.database import db_service

# Simulate the stale detection logic
result = db_service.client.table("deployments").select("*").eq("status", "running").eq("tenant_id", "00000000-0000-0000-0000-000000000000").execute()

deps = result.data or []
print(f"Found {len(deps)} running deployment(s)\n")

for dep in deps:
    dep_id = dep.get('id', 'unknown')[:8]
    started_at_str = dep.get('started_at')
    
    if started_at_str:
        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        if hasattr(started_at, 'tzinfo') and started_at.tzinfo is not None:
            started_at_naive = started_at.replace(tzinfo=None)
        else:
            started_at_naive = started_at
        hours_running = (datetime.utcnow() - started_at_naive).total_seconds() / 3600
        
        print(f"Deployment: {dep_id}...")
        print(f"  Hours running: {hours_running:.2f}")
        print(f"  Should be marked as failed: {hours_running > 1}")
        print(f"  Will be caught by: {'get_deployments (polling)' if hours_running > 1 else 'N/A'}")
        print()

