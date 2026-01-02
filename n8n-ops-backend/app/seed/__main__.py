"""
Seed CLI entrypoint.

Usage:
    python -m app.seed --env staging
    python -m app.seed --env staging --clean
    python -m app.seed --env staging --only tenants,plans
    python -m app.seed --print-credentials
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv


async def run_seed(args):
    """Run the seeding process."""
    # Load environment-specific .env file
    env_file = f".env.{args.env}" if args.env != "local" else ".env"
    env_path = Path(__file__).parent.parent.parent / env_file

    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_file}")
    else:
        load_dotenv()
        print(f"Using default .env (no {env_file} found)")

    # Import after loading env
    from supabase import create_client
    from app.core.config import settings

    # Validate required env vars
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"SEEDING DATABASE: {args.env}")
    print("=" * 60)
    print(f"  Supabase URL: {settings.SUPABASE_URL}")
    print(f"  Clean mode: {args.clean}")
    print(f"  Modules: {args.only or 'all'}")

    # Create Supabase client with service key (admin access)
    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY,
    )

    # Determine which modules to run
    modules = args.only.split(",") if args.only else ["tenants", "plans", "workflows", "config", "auth"]

    results = {}

    # Import seed functions
    from app.seed.tenants import seed_tenants
    from app.seed.plans import seed_plans
    from app.seed.workflows import seed_workflows
    from app.seed.config import seed_config
    from app.seed.users import seed_auth_users, print_test_credentials

    # Run tenants first (other modules depend on it)
    if "tenants" in modules:
        print("\n[1] Seeding tenants and users...")
        results["tenants"] = await seed_tenants(client, clean=args.clean)
        print(f"    Created: {results['tenants']['tenants_created']} tenants, {results['tenants']['users_created']} users")
        print(f"    Skipped: {results['tenants']['tenants_skipped']} tenants, {results['tenants']['users_skipped']} users")

    # Run plans
    if "plans" in modules:
        print("\n[2] Seeding subscription plans...")
        results["plans"] = await seed_plans(client, clean=args.clean)
        print(f"    Created: {results['plans']['plans_created']} plans")
        print(f"    Updated: {results['plans']['plans_updated']} plans")
        print(f"    Tenant plans: {results['plans']['tenant_plans_created']}")

    # Run workflows
    if "workflows" in modules:
        print("\n[3] Seeding workflows and environments...")
        results["workflows"] = await seed_workflows(client, clean=args.clean)
        print(f"    Environments: {results['workflows']['environments_created']} created, {results['workflows']['environments_skipped']} skipped")
        print(f"    Workflows: {results['workflows']['workflows_created']} created, {results['workflows']['workflows_skipped']} skipped")
        print(f"    Executions: {results['workflows']['executions_created']}")
        print(f"    Tags: {results['workflows']['tags_created']}")

    # Run config
    if "config" in modules:
        print("\n[4] Seeding configuration...")
        results["config"] = await seed_config(client, clean=args.clean)
        print(f"    Environment types: {results['config']['environment_types_created']} created")
        print(f"    Drift policies: {results['config']['drift_policies_created']} created")

    # Run auth users (Supabase Auth)
    if "auth" in modules:
        print("\n[5] Seeding Supabase Auth users...")
        results["auth"] = await seed_auth_users(
            supabase_url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_KEY,
            db_client=client,
            clean=args.clean,
        )
        print(f"    Created: {results['auth']['users_created']}")
        print(f"    Skipped: {results['auth']['users_skipped']}")
        print(f"    Failed: {results['auth']['users_failed']}")

    # Print summary
    print("\n" + "=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)

    # Print credentials if requested or if auth was seeded
    if args.print_credentials or "auth" in modules:
        print_test_credentials()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Seed staging/test database with synthetic data"
    )
    parser.add_argument(
        "--env",
        default="staging",
        choices=["staging", "local", "test"],
        help="Environment to seed (default: staging)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing seed data before seeding"
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Comma-separated list of modules to run (tenants,plans,workflows,config,auth)"
    )
    parser.add_argument(
        "--print-credentials",
        action="store_true",
        help="Print test user credentials after seeding"
    )

    args = parser.parse_args()

    # Handle print-credentials only
    if args.print_credentials and not args.only:
        from app.seed.users import print_test_credentials
        print_test_credentials()
        return

    # Run async seeding
    asyncio.run(run_seed(args))


if __name__ == "__main__":
    main()
