"""
Supabase Auth user creation.

Creates test users in Supabase Auth via the Admin API.
These users can then log in to the staging environment.
"""
import os
import httpx
from typing import Dict, Any, List

from .tenants import TEST_USERS, get_seed_tenant_ids


# Test user passwords (same for all test users in staging)
TEST_PASSWORD = "TestPassword123!"


async def seed_auth_users(
    supabase_url: str,
    service_role_key: str,
    db_client = None,
    clean: bool = False,
) -> Dict[str, Any]:
    """
    Create test users in Supabase Auth.

    Uses the Supabase Admin API to create users that can actually log in.
    These are linked to the app's users table via the supabase_auth_id field.

    Args:
        supabase_url: Supabase project URL
        service_role_key: Supabase service role key (has admin privileges)
        db_client: Optional Supabase database client for linking users
        clean: If True, delete existing test users first

    Returns:
        Dict with counts and user info
    """
    results = {
        "users_created": 0,
        "users_skipped": 0,
        "users_failed": 0,
        "users": [],
    }

    # Admin API endpoint
    admin_url = f"{supabase_url}/auth/v1/admin/users"

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get existing users if cleaning
        if clean:
            try:
                response = await client.get(admin_url, headers=headers)
                if response.status_code == 200:
                    existing_users = response.json().get("users", [])
                    for user in existing_users:
                        email = user.get("email", "")
                        # Only delete test users (ending in -test.local or test.local)
                        if email.endswith("-test.local") or email.endswith("@test.local"):
                            user_id = user.get("id")
                            try:
                                await client.delete(
                                    f"{admin_url}/{user_id}",
                                    headers=headers,
                                )
                                print(f"    Deleted auth user: {email}")
                            except Exception as e:
                                print(f"    Failed to delete {email}: {e}")
            except Exception as e:
                print(f"    Failed to list existing users: {e}")

        # Create each test user
        for user_data in TEST_USERS:
            email = user_data["email"]

            try:
                # Check if user already exists by fetching all and filtering
                response = await client.get(
                    admin_url,
                    headers=headers,
                )

                existing_auth_user = None
                if response.status_code == 200:
                    all_users = response.json().get("users", [])
                    # Find exact email match
                    for u in all_users:
                        if u.get("email") == email:
                            existing_auth_user = u
                            break

                if existing_auth_user:
                    auth_user_id = existing_auth_user.get("id")
                    results["users_skipped"] += 1
                    results["users"].append({
                        "email": email,
                        "status": "exists",
                        "id": auth_user_id,
                    })

                    # Ensure the link exists in app's users table
                    if db_client and auth_user_id:
                        try:
                            db_client.table("users").update({
                                "supabase_auth_id": auth_user_id
                            }).eq("id", user_data["id"]).execute()
                            print(f"    Ensured supabase_auth_id link for: {email}")
                        except Exception as link_error:
                            print(f"    Failed to link supabase_auth_id for {email}: {link_error}")
                    continue

                # Create user via Admin API
                create_data = {
                    "email": email,
                    "password": TEST_PASSWORD,
                    "email_confirm": True,  # Auto-confirm email
                    "user_metadata": {
                        "name": user_data["name"],
                        "role": user_data["role"],
                        "tenant_id": user_data["tenant_id"],
                    },
                    "app_metadata": {
                        "seed_user": True,
                        "app_user_id": user_data["id"],
                    },
                }

                response = await client.post(
                    admin_url,
                    headers=headers,
                    json=create_data,
                )

                if response.status_code in (200, 201):
                    auth_user = response.json()
                    auth_user_id = auth_user.get("id")
                    results["users_created"] += 1
                    results["users"].append({
                        "email": email,
                        "status": "created",
                        "id": auth_user_id,
                    })
                    print(f"    Created auth user: {email}")

                    # Link to app's users table
                    if db_client and auth_user_id:
                        try:
                            db_client.table("users").update({
                                "supabase_auth_id": auth_user_id
                            }).eq("id", user_data["id"]).execute()
                            print(f"    Linked supabase_auth_id for: {email}")
                        except Exception as link_error:
                            print(f"    Failed to link supabase_auth_id for {email}: {link_error}")
                else:
                    error = response.json().get("message", response.text)
                    results["users_failed"] += 1
                    results["users"].append({
                        "email": email,
                        "status": "failed",
                        "error": error,
                    })
                    print(f"    Failed to create {email}: {error}")

            except Exception as e:
                results["users_failed"] += 1
                results["users"].append({
                    "email": email,
                    "status": "error",
                    "error": str(e),
                })
                print(f"    Error creating {email}: {e}")

    return results


def get_test_credentials() -> List[Dict[str, str]]:
    """
    Get test user credentials for documentation/testing.

    Returns list of email/password pairs for test users.
    """
    return [
        {
            "email": user["email"],
            "password": TEST_PASSWORD,
            "role": user["role"],
            "tenant": user["tenant_id"],
        }
        for user in TEST_USERS
    ]


def print_test_credentials():
    """Print test credentials for manual testing."""
    print("\n" + "=" * 60)
    print("TEST USER CREDENTIALS")
    print("=" * 60)
    print(f"\nPassword for all test users: {TEST_PASSWORD}\n")

    tenant_ids = get_seed_tenant_ids()
    tenant_names = {v: k for k, v in tenant_ids.items()}

    for user in TEST_USERS:
        tenant_name = tenant_names.get(user["tenant_id"], "unknown")
        print(f"  {user['email']:<35} | {user['role']:<10} | {tenant_name}")

    print("\n" + "=" * 60)
