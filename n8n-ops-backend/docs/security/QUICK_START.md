# RLS Documentation Quick Start

**Want to understand RLS in your n8n-ops platform? Start here!**

## 30-Second Overview

- **76 tables** in your database
- **12 tables** (16%) have RLS enabled
- **64 tables** (84%) don't have RLS (security gap)
- **Backend uses SERVICE_KEY** → bypasses RLS (application-layer isolation is primary)
- **Frontend uses ANON_KEY** → enforces RLS (limited protection currently)

## 5-Minute Deep Dive

### What is RLS?

Row-Level Security (RLS) is a PostgreSQL/Supabase feature that filters database rows based on who's accessing them. Think of it as database-level multi-tenancy protection.

### Current State

**✅ Good News:**
- Application layer has 100% tenant isolation (all 330 endpoints verified)
- Backend safely uses SERVICE_KEY (bypasses RLS by design)
- Some workflow tables have proper RLS

**⚠️ Concerns:**
- Only 12 of 76 tables protected by RLS
- Some enabled policies are overly permissive
- Critical tables like `tenants`, `users`, `environments` lack RLS

**Risk Level:** Currently LOW (backend bypasses RLS), but HIGH if frontend ever uses ANON_KEY directly

### Critical Security Gaps

**Must fix before production:**
1. `tenant_provider_subscriptions` - Has RLS but policies allow ALL access
2. `audit_logs` - Has RLS but superuser policy allows ALL access  
3. `tenant_api_keys` - No RLS (contains API keys!)
4. `tenants`, `users`, `environments` - No RLS (core tables)
5. Credential tables - Migration exists but not applied

## Common Tasks

### I'm adding a new table

→ Follow [RLS_CHANGE_CHECKLIST.md](RLS_CHANGE_CHECKLIST.md)

**TL;DR:**
```sql
ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY "my_table_tenant_isolation" ON my_table
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

### I need to verify RLS policies

→ Use queries from [RLS_VERIFICATION.md](RLS_VERIFICATION.md)

**Quick check:**
```sql
-- See which tables have RLS
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' AND rowsecurity = true;

-- See policies for a specific table
SELECT * FROM pg_policies WHERE tablename = 'your_table_name';
```

### I want to understand all current policies

→ Read [RLS_POLICIES.md](RLS_POLICIES.md)

All 76 tables documented with:
- Current RLS status
- Existing policies
- Recommended policies
- Priority level

### I need the executive summary

→ See [RLS_SUMMARY.md](RLS_SUMMARY.md)

Quick overview of findings, gaps, and recommendations.

### I'm doing a security audit

→ Start with [RLS_VERIFICATION.md](RLS_VERIFICATION.md), then compare to [RLS_POLICIES.md](RLS_POLICIES.md)

**Key queries:**
```sql
-- RLS coverage
SELECT 
    rowsecurity AS rls_enabled,
    COUNT(*) AS table_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS percentage
FROM pg_tables
WHERE schemaname = 'public'
GROUP BY rowsecurity;

-- Tables with tenant_id but no RLS
SELECT 
    t.tablename,
    '⚠️ NEEDS RLS' AS recommendation
FROM pg_tables t
INNER JOIN information_schema.columns c 
    ON c.table_name = t.tablename 
    AND c.column_name = 'tenant_id'
WHERE t.schemaname = 'public' 
  AND t.rowsecurity = false;
```

## Priority Action Items

### This Week
1. Review [RLS_POLICIES.md](RLS_POLICIES.md) gap analysis
2. Fix `tenant_provider_subscriptions` policies
3. Fix `audit_logs` policy
4. Investigate why credential table migrations didn't apply

### Next 2 Weeks
5. Enable RLS on critical tables: `tenant_api_keys`, `tenants`, `users`, `environments`
6. Test with ANON_KEY to ensure policies work
7. Add RLS verification to CI/CD

### Next Month
8. Enable RLS on operations tables: `deployments`, `promotions`, `pipelines`
9. Enable RLS on observability tables: `executions` (test performance)
10. Enable RLS on billing tables: `subscriptions`, `payment_history`

## Policy Patterns Cheat Sheet

### Standard tenant isolation
```sql
CREATE POLICY "table_tenant_isolation" ON table_name
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

### Public read, restricted write
```sql
CREATE POLICY "table_public_read" ON table_name
    FOR SELECT USING (true);
```

### Platform admin override
```sql
CREATE POLICY "table_with_admin" ON table_name
    FOR ALL
    USING (
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        OR current_setting('app.user_role', true) = 'platform_admin'
    );
```

### Platform admin only
```sql
CREATE POLICY "table_platform_only" ON table_name
    FOR ALL
    USING (current_setting('app.user_role', true) = 'platform_admin');
```

## Red Flags 🚩

**If you see these, investigate:**

1. **RLS enabled but no policies defined** → Blocks ALL access
   ```sql
   -- Find tables in this state
   SELECT t.tablename
   FROM pg_tables t
   WHERE t.schemaname = 'public'
     AND t.rowsecurity = true
     AND NOT EXISTS (SELECT 1 FROM pg_policies p WHERE p.tablename = t.tablename);
   ```

2. **Policy uses `USING (true)`** → No protection
   ```sql
   -- Find overly permissive policies
   SELECT tablename, policyname
   FROM pg_policies
   WHERE qual = 'true' OR qual IS NULL;
   ```

3. **Table has `tenant_id` but no RLS** → Security gap
   ```sql
   -- Find unprotected tenant-scoped tables
   SELECT t.tablename
   FROM pg_tables t
   INNER JOIN information_schema.columns c 
       ON c.table_name = t.tablename AND c.column_name = 'tenant_id'
   WHERE t.schemaname = 'public' AND t.rowsecurity = false;
   ```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│              🔑 Uses: Supabase ANON_KEY                 │
│                   (enforces RLS)                        │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│           Supabase PostgreSQL Database                  │
│                                                         │
│  ✅ Protected (12 tables):                             │
│     - canonical_workflows, workflow_env_map, etc.      │
│     - features, providers (public read)                │
│                                                         │
│  ⚠️ Insecure (3 tables):                               │
│     - tenant_provider_subscriptions (USING true)       │
│     - audit_logs (superuser policy)                    │
│                                                         │
│  ❌ Unprotected (64 tables):                           │
│     - tenants, users, environments                     │
│     - executions, deployments, promotions              │
│     - and many more...                                 │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                Backend (FastAPI)                        │
│            🔑 Uses: Supabase SERVICE_KEY                │
│                 (bypasses RLS)                          │
│                                                         │
│  ✅ Application-layer tenant isolation:                │
│     - 100% endpoint coverage (330 endpoints)           │
│     - tenant_id from JWT auth context                  │
│     - All queries filtered by tenant                   │
└─────────────────────────────────────────────────────────┘
```

## Compliance Checklist

### For SOC 2 / ISO 27001
- [ ] Document multi-layered security approach (application + RLS)
- [ ] Note backend bypasses RLS by design (SERVICE_KEY)
- [ ] Application layer provides primary tenant isolation
- [ ] RLS provides defense-in-depth
- [ ] Gap closure plan with timeline

### For GDPR
- [ ] Enable RLS on `users` table (contains personal data)
- [ ] Enable RLS on `audit_logs` (contains activity data)
- [ ] Enable RLS on `executions` (may contain user data)
- [ ] Document data isolation mechanisms
- [ ] Verify tenant data cannot leak

## Links to Full Documentation

- **[README.md](README.md)** - Documentation index
- **[RLS_POLICIES.md](RLS_POLICIES.md)** - Complete policy inventory (1000 lines)
- **[RLS_VERIFICATION.md](RLS_VERIFICATION.md)** - Verification procedures (450 lines)
- **[RLS_CHANGE_CHECKLIST.md](RLS_CHANGE_CHECKLIST.md)** - Developer guide (400 lines)
- **[RLS_SUMMARY.md](RLS_SUMMARY.md)** - Executive summary
- **[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)** - Documentation project report

## Need Help?

**Common Questions:**

**Q: Should I enable RLS on my new table?**  
A: If it has `tenant_id` → YES. If it's global config → Maybe not. See checklist.

**Q: Why do we use SERVICE_KEY in the backend?**  
A: Performance and flexibility. Application-layer isolation is more powerful and allows complex cross-tenant queries for platform admins.

**Q: Is it safe that 64 tables lack RLS?**  
A: Currently yes (backend bypasses RLS), but risky long-term. Should fix before enabling direct Supabase access from frontend.

**Q: Where do I start fixing gaps?**  
A: Start with "Critical Priority" section in [RLS_POLICIES.md](RLS_POLICIES.md):
1. Fix overly permissive policies
2. Apply credential table migrations
3. Enable RLS on `tenant_api_keys`, `tenants`, `users`, `environments`

**Q: How do I test RLS policies?**  
A: See "Testing RLS Policies" section in [RLS_VERIFICATION.md](RLS_VERIFICATION.md)

---

**Created:** 2026-01-08  
**Maintainer:** Update after major RLS changes  
**Questions?** Check the full documentation or review verification procedures.

