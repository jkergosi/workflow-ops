"""
Script to run database migration for credential health tracking
"""

def run_migration():
    """Run the credential health tracking migration"""

    print("=" * 60)
    print("MIGRATION: add_credential_health_tracking")
    print("=" * 60)

    # Read the migration file
    with open("migrations/add_credential_health_tracking.sql", "r") as f:
        migration_sql = f.read()

    print("\nMigration SQL:")
    print("-" * 60)
    print(migration_sql)
    print("-" * 60)

    print("\n" + "=" * 60)
    print("INSTRUCTIONS TO RUN THE MIGRATION:")
    print("=" * 60)
    print("\nOption 1: Supabase Dashboard (RECOMMENDED)")
    print("  1. Go to: https://supabase.com/dashboard")
    print("  2. Select your project")
    print("  3. Click 'SQL Editor' in the left sidebar")
    print("  4. Click 'New Query'")
    print("  5. Copy and paste the SQL from above")
    print("  6. Click 'Run' (or press Ctrl+Enter)")
    print("\nOption 2: Command Line (if you have psql installed)")
    print("  Get the connection string from Supabase Dashboard:")
    print("  Settings > Database > Connection String > Direct Connection")
    print("  Then run:")
    print("  psql '<connection-string>' -f migrations/add_credential_health_tracking.sql")

    print("\n" + "=" * 60)
    print("AFTER RUNNING THE MIGRATION:")
    print("=" * 60)
    print("\nVerify the migration worked by running this SQL query:")
    print("  SELECT column_name, data_type")
    print("  FROM information_schema.columns")
    print("  WHERE table_name = 'credential_mappings'")
    print("  AND column_name IN ('last_test_at', 'last_test_status', 'last_test_error');")
    print("\nYou should see three new columns listed.")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    run_migration()
