# RLS Change Checklist

This checklist ensures proper Row-Level Security implementation when adding or modifying database tables.

## When to Use RLS

**✅ Tables that NEED RLS:**
- Contains `tenant_id` column (tenant-scoped data)
- Stores user-generated data (workflows, environments, deployments, etc.)
- Contains sensitive information (credentials, API keys, billing data)
- Accessed directly by frontend via Supabase client

**❌ Tables that DON'T need RLS:**
- Migration tracking tables (`alembic_version`)
- Global configuration tables with no tenant context
- Tables only accessed via backend SERVICE_KEY
- Public reference data (if truly public and non-sensitive)

**⚠️ Consider RLS for:**
- Audit logs (may contain sensitive data)
- Background job tracking (if contains tenant-specific data)
- Platform admin tables (use role-based policies)

---

## Checklist for Adding a New Table

### 1. Design Phase
- [ ] Determine if table needs `tenant_id` column
- [ ] Identify who should have access (all users, admins only, platform admins, etc.)
- [ ] Determine access patterns (read-only, read-write, delete allowed, etc.)
- [ ] Review existing similar tables for policy patterns

### 2. Migration Creation
- [ ] Add table creation SQL to Alembic migration
- [ ] Include `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE` if tenant-scoped
- [ ] Add `ENABLE ROW LEVEL SECURITY` statement
- [ ] Create appropriate RLS policies (see patterns below)
- [ ] Add indexes including `tenant_id` for performance
- [ ] Test migration in development environment

### 3. RLS Policy Implementation

**Standard Tenant Isolation Pattern:**
```sql
-- Enable RLS
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

-- Create policy
CREATE POLICY "{table_name}_tenant_isolation" ON {table_name}
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

**For Different Operations:**
```sql
-- Separate policies for different operations
CREATE POLICY "{table_name}_select" ON {table_name}
    FOR SELECT
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid);

CREATE POLICY "{table_name}_insert" ON {table_name}
    FOR INSERT
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);

CREATE POLICY "{table_name}_update" ON {table_name}
    FOR UPDATE
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);

CREATE POLICY "{table_name}_delete" ON {table_name}
    FOR DELETE
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

**Public Read Pattern:**
```sql
-- For reference tables that all users can read
CREATE POLICY "{table_name}_select_policy" ON {table_name}
    FOR SELECT
    USING (true);
```

**Platform Admin Pattern:**
```sql
-- Platform admins can access all tenants
CREATE POLICY "{table_name}_platform_admin" ON {table_name}
    FOR ALL
    USING (
        current_setting('app.user_role', true) = 'platform_admin'
        OR tenant_id = (current_setting('app.tenant_id', true))::uuid
    );
```

### 4. Documentation
- [ ] Add table entry to [`RLS_POLICIES.md`](RLS_POLICIES.md) with:
  - RLS status (enabled/disabled)
  - Policy definitions
  - Tenant isolation method
  - Exceptions or special cases
- [ ] Add verification query to [`RLS_VERIFICATION.md`](RLS_VERIFICATION.md)
- [ ] Update table count in documentation

### 5. Testing
- [ ] Run migration on development database
- [ ] Verify RLS is enabled: `SELECT tablename, rowsecurity FROM pg_tables WHERE tablename = '{table_name}';`
- [ ] Verify policies exist: `SELECT * FROM pg_policies WHERE tablename = '{table_name}';`
- [ ] Test with ANON_KEY (should enforce isolation):
  ```sql
  SET app.tenant_id = '{tenant_id}';
  SELECT * FROM {table_name};  -- Should only return records for this tenant
  ```
- [ ] Test with SERVICE_KEY (should bypass RLS):
  ```sql
  SELECT * FROM {table_name};  -- Should return all records
  ```
- [ ] Test INSERT with wrong tenant_id (should fail with WITH CHECK)
- [ ] Test cross-tenant access (should be denied)

### 6. Code Changes
- [ ] Update backend service methods to set `app.tenant_id` if using ANON_KEY
- [ ] Add tests for tenant isolation on this table
- [ ] Update API endpoints to handle RLS errors gracefully
- [ ] Review frontend code if it accesses this table directly

### 7. Review & Deploy
- [ ] Code review with focus on RLS policies
- [ ] Security review if handling sensitive data
- [ ] Stage deployment and verification
- [ ] Production deployment
- [ ] Post-deployment verification using queries from [`RLS_VERIFICATION.md`](RLS_VERIFICATION.md)

---

## Checklist for Modifying Existing RLS Policies

### Pre-Change
- [ ] Document current policy definition (screenshot or SQL export)
- [ ] Identify why change is needed
- [ ] Review impact on existing data access patterns
- [ ] Create rollback plan
- [ ] Test change in development first

### Change Implementation
- [ ] Create Alembic migration to modify policy
- [ ] Use `DROP POLICY` and `CREATE POLICY` (or `ALTER POLICY` if available)
- [ ] Update [`RLS_POLICIES.md`](RLS_POLICIES.md) with new policy definition
- [ ] Add migration note with revision ID and date

### Post-Change
- [ ] Verify policy in Supabase dashboard
- [ ] Test with various user roles
- [ ] Monitor for access errors in production
- [ ] Update verification queries if needed

---

## Common Patterns Reference

### 1. Standard Tenant Isolation
Most common pattern for tenant-scoped tables:
```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_tenant_isolation" ON {table_name}
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

### 2. Public Read, Restricted Write
For reference tables:
```sql
CREATE POLICY "{table_name}_public_read" ON {table_name}
    FOR SELECT USING (true);

CREATE POLICY "{table_name}_admin_write" ON {table_name}
    FOR INSERT WITH CHECK (current_setting('app.user_role', true) = 'admin');
```

### 3. User-Owned Resources
For tables with `user_id`:
```sql
CREATE POLICY "{table_name}_owner_access" ON {table_name}
    FOR ALL
    USING (
        user_id = (current_setting('app.user_id', true))::uuid
        AND tenant_id = (current_setting('app.tenant_id', true))::uuid
    );
```

### 4. Environment-Scoped Resources
For tables that belong to specific environments:
```sql
CREATE POLICY "{table_name}_env_tenant_isolation" ON {table_name}
    FOR ALL
    USING (
        environment_id IN (
            SELECT id FROM environments 
            WHERE tenant_id = (current_setting('app.tenant_id', true))::uuid
        )
    );
```

### 5. Superuser Override (⚠️ Use with caution)
Only for specific admin/platform tables:
```sql
CREATE POLICY "{table_name}_superuser_policy" ON {table_name}
    FOR ALL
    USING (true);  -- Allows all access (no real protection)
```

---

## Migration Template

```python
"""add_rls_to_{table_name}

Revision ID: {revision_id}
Revises: {previous_revision}
Create Date: {date}
"""
from alembic import op
import sqlalchemy as sa

revision = '{revision_id}'
down_revision = '{previous_revision}'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Enable RLS
    op.execute('''
        ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
    ''')
    
    # Create tenant isolation policy
    op.execute('''
        CREATE POLICY "{table_name}_tenant_isolation" ON {table_name}
            FOR ALL
            USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
            WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
    ''')
    
    # Add documentation comment
    op.execute('''
        COMMENT ON TABLE {table_name} IS 'RLS enabled - tenant isolated via app.tenant_id';
    ''')

def downgrade() -> None:
    # Drop policy
    op.execute('''
        DROP POLICY IF EXISTS "{table_name}_tenant_isolation" ON {table_name};
    ''')
    
    # Disable RLS
    op.execute('''
        ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;
    ''')
```

---

## Troubleshooting

### "new row violates row-level security policy"
- Check that `WITH CHECK` clause allows the operation
- Verify `app.tenant_id` is set correctly
- Ensure `tenant_id` in INSERT matches authenticated tenant

### "permission denied for table"
- RLS enabled but no policy grants access
- Add appropriate policy or disable RLS if not needed

### Policy not taking effect
- Verify policy is created: `SELECT * FROM pg_policies WHERE tablename = '{table_name}';`
- Check if using SERVICE_KEY (bypasses RLS)
- Ensure `app.tenant_id` setting is configured

### Performance issues
- Add index on `tenant_id`: `CREATE INDEX idx_{table_name}_tenant_id ON {table_name}(tenant_id);`
- Consider partial indexes for common query patterns
- Review EXPLAIN plans for queries

---

## Best Practices

1. **Default to RLS enabled** for all tenant-scoped tables
2. **Test policies thoroughly** before deploying to production
3. **Document exceptions** when bypassing standard patterns
4. **Use descriptive policy names** that indicate purpose
5. **Prefer stricter policies** - easier to loosen than tighten later
6. **Monitor RLS errors** in production for policy misconfigurations
7. **Keep policies simple** - complex logic belongs in application code
8. **Version control policies** via Alembic migrations, not manual SQL
9. **Review regularly** as part of security audits
10. **Avoid superuser policies** (`USING (true)`) unless absolutely necessary

---

## References

- [RLS_POLICIES.md](RLS_POLICIES.md) - Current policy inventory
- [RLS_VERIFICATION.md](RLS_VERIFICATION.md) - Verification procedures
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)

