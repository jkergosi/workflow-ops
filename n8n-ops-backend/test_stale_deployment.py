"""Test to check stale deployment detection"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app.services.database import db_service

result = db_service.client.table("deployments").select("*").eq("status", "running").eq("tenant_id", "00000000-0000-0000-0000-000000000000").execute()

deps = result.data or []
print(f"Found {len(deps)} running deployment(s):\n")

for dep in deps:
    dep_id = dep.get('id', 'unknown')[:8]
    started_at = dep.get('started_at')
    
    if started_at:
        started = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        if hasattr(started, 'tzinfo') and started.tzinfo is not None:
            started_naive = started.replace(tzinfo=None)
        else:
            started_naive = started
        minutes_running = (datetime.utcnow() - started_naive).total_seconds() / 60
        
        print(f"Deployment: {dep_id}...")
        print(f"  Started: {started_at}")
        print(f"  Minutes running: {minutes_running:.1f}")
        print(f"  Hours running: {minutes_running / 60:.2f}")
        print(f"  Should be cleaned up: {minutes_running > 60} (>1 hour)")
        print()

