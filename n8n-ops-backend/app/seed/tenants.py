"""
Tenant and organization seeding.

Creates test tenants with various subscription tiers and statuses.
Uses deterministic UUIDs for stable references across seeds.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from supabase import Client

# Deterministic UUIDs for stable test data
# Generated from namespace UUID + name for reproducibility
NAMESPACE_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def deterministic_uuid(name: str) -> str:
    """Generate a deterministic UUID from a name."""
    return str(uuid.uuid5(NAMESPACE_UUID, name))


# Test tenant definitions
TEST_TENANTS = [
    {
        "id": deterministic_uuid("acme-corp"),
        "name": "Acme Corporation",
        "email": "admin@acme-test.local",
        "subscription_tier": "pro",
        "status": "active",
        "primary_contact_name": "Alice Admin",
    },
    {
        "id": deterministic_uuid("startup-inc"),
        "name": "Startup Inc",
        "email": "team@startup-test.local",
        "subscription_tier": "free",
        "status": "active",
        "primary_contact_name": "Bob Builder",
    },
    {
        "id": deterministic_uuid("enterprise-co"),
        "name": "Enterprise Co",
        "email": "ops@enterprise-test.local",
        "subscription_tier": "enterprise",
        "status": "active",
        "primary_contact_name": "Carol CTO",
    },
    {
        "id": deterministic_uuid("agency-partners"),
        "name": "Agency Partners",
        "email": "hello@agency-test.local",
        "subscription_tier": "agency",
        "status": "active",
        "primary_contact_name": "David Director",
    },
    {
        "id": deterministic_uuid("trial-user"),
        "name": "Trial User Org",
        "email": "trial@test.local",
        "subscription_tier": "free",
        "status": "trial",
        "primary_contact_name": "Eve Explorer",
    },
]

# Test users for each tenant
TEST_USERS = [
    # Acme Corp users
    {
        "id": deterministic_uuid("alice-admin"),
        "tenant_id": deterministic_uuid("acme-corp"),
        "email": "alice@acme-test.local",
        "name": "Alice Admin",
        "role": "admin",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    {
        "id": deterministic_uuid("alice-dev"),
        "tenant_id": deterministic_uuid("acme-corp"),
        "email": "dev@acme-test.local",
        "name": "Alex Developer",
        "role": "developer",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    {
        "id": deterministic_uuid("alice-viewer"),
        "tenant_id": deterministic_uuid("acme-corp"),
        "email": "viewer@acme-test.local",
        "name": "Victor Viewer",
        "role": "viewer",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    # Startup Inc users
    {
        "id": deterministic_uuid("bob-admin"),
        "tenant_id": deterministic_uuid("startup-inc"),
        "email": "bob@startup-test.local",
        "name": "Bob Builder",
        "role": "admin",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    # Enterprise Co users
    {
        "id": deterministic_uuid("carol-admin"),
        "tenant_id": deterministic_uuid("enterprise-co"),
        "email": "carol@enterprise-test.local",
        "name": "Carol CTO",
        "role": "admin",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    {
        "id": deterministic_uuid("carol-dev1"),
        "tenant_id": deterministic_uuid("enterprise-co"),
        "email": "dev1@enterprise-test.local",
        "name": "Dan Developer",
        "role": "developer",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    {
        "id": deterministic_uuid("carol-dev2"),
        "tenant_id": deterministic_uuid("enterprise-co"),
        "email": "dev2@enterprise-test.local",
        "name": "Diana Developer",
        "role": "developer",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    # Agency Partners users
    {
        "id": deterministic_uuid("david-admin"),
        "tenant_id": deterministic_uuid("agency-partners"),
        "email": "david@agency-test.local",
        "name": "David Director",
        "role": "admin",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
    # Trial user
    {
        "id": deterministic_uuid("eve-admin"),
        "tenant_id": deterministic_uuid("trial-user"),
        "email": "eve@test.local",
        "name": "Eve Explorer",
        "role": "admin",
        "status": "active",
        "supabase_auth_id": None,  # Will be linked when user signs up
    },
]


async def seed_tenants(client: Client, clean: bool = False) -> Dict[str, Any]:
    """
    Seed test tenants and users.

    Args:
        client: Supabase client
        clean: If True, delete existing seed data first

    Returns:
        Dict with counts and created IDs
    """
    results = {
        "tenants_created": 0,
        "tenants_skipped": 0,
        "users_created": 0,
        "users_skipped": 0,
        "tenant_ids": [],
        "user_ids": [],
    }

    # Get seed tenant IDs for cleanup
    seed_tenant_ids = [t["id"] for t in TEST_TENANTS]
    seed_user_ids = [u["id"] for u in TEST_USERS]

    if clean:
        # Delete seed users first (foreign key constraint)
        for user_id in seed_user_ids:
            try:
                client.table("users").delete().eq("id", user_id).execute()
            except Exception:
                pass

        # Delete seed tenants
        for tenant_id in seed_tenant_ids:
            try:
                client.table("tenants").delete().eq("id", tenant_id).execute()
            except Exception:
                pass

        print(f"  Cleaned {len(seed_tenant_ids)} seed tenants and {len(seed_user_ids)} users")

    # Create tenants
    now = datetime.utcnow().isoformat()

    for tenant_data in TEST_TENANTS:
        try:
            # Check if exists
            existing = client.table("tenants").select("id").eq("id", tenant_data["id"]).execute()

            if existing.data:
                results["tenants_skipped"] += 1
                results["tenant_ids"].append(tenant_data["id"])
                continue

            # Create tenant
            full_tenant = {
                **tenant_data,
                "created_at": now,
                "updated_at": now,
            }

            client.table("tenants").insert(full_tenant).execute()
            results["tenants_created"] += 1
            results["tenant_ids"].append(tenant_data["id"])
            print(f"    Created tenant: {tenant_data['name']}")

        except Exception as e:
            print(f"    Failed to create tenant {tenant_data['name']}: {e}")

    # Create users
    for user_data in TEST_USERS:
        try:
            # Check if exists
            existing = client.table("users").select("id").eq("id", user_data["id"]).execute()

            if existing.data:
                results["users_skipped"] += 1
                results["user_ids"].append(user_data["id"])
                continue

            # Create user
            full_user = {
                **user_data,
                "created_at": now,
                "updated_at": now,
            }

            client.table("users").insert(full_user).execute()
            results["users_created"] += 1
            results["user_ids"].append(user_data["id"])
            print(f"    Created user: {user_data['email']}")

        except Exception as e:
            print(f"    Failed to create user {user_data['email']}: {e}")

    return results


# Export tenant IDs for use in other seed modules
def get_seed_tenant_ids() -> Dict[str, str]:
    """Get mapping of tenant names to their deterministic IDs."""
    return {
        "acme": deterministic_uuid("acme-corp"),
        "startup": deterministic_uuid("startup-inc"),
        "enterprise": deterministic_uuid("enterprise-co"),
        "agency": deterministic_uuid("agency-partners"),
        "trial": deterministic_uuid("trial-user"),
    }


def get_seed_user_ids() -> Dict[str, str]:
    """Get mapping of user names to their deterministic IDs."""
    return {
        "alice": deterministic_uuid("alice-admin"),
        "bob": deterministic_uuid("bob-admin"),
        "carol": deterministic_uuid("carol-admin"),
        "david": deterministic_uuid("david-admin"),
        "eve": deterministic_uuid("eve-admin"),
    }
