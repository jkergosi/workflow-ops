# Supabase RLS Policy Documentation

**Last Updated:** 2026-01-08  
**Total Tables:** 76  
**Tables with RLS:** 12 (15.8%)  
**Tables without RLS:** 64 (84.2%)

## Executive Summary

This document provides a comprehensive inventory of Row-Level Security (RLS) policies in the Supabase database. It documents both existing policies and recommendations for closing security gaps.

### Current State

**✅ Strengths:**
- Application-layer tenant isolation: 100% coverage (all 330 endpoints verified)
- Backend uses SERVICE_KEY which bypasses RLS
- Comprehensive audit logging with impersonation tracking

**⚠️ Gaps:**
- Only 12 of 76 tables have RLS enabled
- Core tables (`tenants`, `users`, `environments`) lack RLS
- Some enabled tables have overly permissive policies

**Risk Assessment:**
- **Current Risk:** LOW (backend bypasses RLS via SERVICE_KEY)
- **Future Risk:** HIGH if frontend switches to ANON_KEY or direct Supabase access is enabled
- **Compliance Risk:** MEDIUM (RLS considered best practice for SaaS multi-tenancy)

### Architecture Context

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│                    (React + Supabase)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses ANON_KEY (enforces RLS)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Supabase Database                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ RLS Enabled  │  │ RLS Disabled │  │  RLS Bypass  │    │
│  │  (12 tables) │  │  (64 tables) │  │(SERVICE_KEY) │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses SERVICE_KEY (bypasses RLS)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                      │
│         Application-layer tenant isolation (100%)           │
└─────────────────────────────────────────────────────────────┘
```

**Key Point:** Backend uses SERVICE_KEY, so RLS is currently a secondary defense layer, not the primary enforcement mechanism.

---

## Table of Contents

- [Tables WITH RLS Enabled](#tables-with-rls-enabled)
- [Tables WITHOUT RLS - By Category](#tables-without-rls---by-category)
  - [Core Tables](#core-tables-without-rls)
  - [Workflow Tables](#workflow-tables-without-rls)
  - [Operations Tables](#operations-tables-without-rls)
  - [Credential Tables](#credential-tables-without-rls)
  - [Drift Management Tables](#drift-management-tables-without-rls)
  - [Observability Tables](#observability-tables-without-rls)
  - [Billing & Entitlements](#billing--entitlements-tables-without-rls)
  - [Platform Admin Tables](#platform-admin-tables-without-rls)
  - [Other Tables](#other-tables-without-rls)
- [RLS Policy Patterns](#rls-policy-patterns)
- [Recommendations](#recommendations)
- [Migration Plan](#migration-plan)

---

## Tables WITH RLS Enabled

### 1. canonical_workflow_git_state

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Strong

#### Policies

**Policy: `canonical_git_state_tenant_isolation`**
- **Operations:** ALL (SELECT, INSERT, UPDATE, DELETE)
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```
- **WITH CHECK Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```

**Assessment:** ✅ **SECURE** - Proper tenant isolation with both USING and WITH CHECK clauses

**Migration Reference:** `dcd2f2c8774d_create_canonical_workflow_tables.py`

---

### 2. canonical_workflows

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Strong

#### Policies

**Policy: `canonical_workflows_tenant_isolation`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```
- **WITH CHECK Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```

**Assessment:** ✅ **SECURE** - Proper tenant isolation

**Migration Reference:** `dcd2f2c8774d_create_canonical_workflow_tables.py`

---

### 3. workflow_env_map

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Strong

#### Policies

**Policy: `workflow_env_map_tenant_isolation`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```
- **WITH CHECK Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```

**Assessment:** ✅ **SECURE** - Proper tenant isolation

---

### 4. workflow_diff_state

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Strong

#### Policies

**Policy: `workflow_diff_state_tenant_isolation`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```
- **WITH CHECK Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```

**Assessment:** ✅ **SECURE** - Proper tenant isolation

---

### 5. workflow_link_suggestions

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Strong

#### Policies

**Policy: `workflow_link_suggestions_tenant_isolation`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```
- **WITH CHECK Clause:**
  ```sql
  tenant_id = (current_setting('app.tenant_id', true))::uuid
  ```

**Assessment:** ✅ **SECURE** - Proper tenant isolation

---

### 6. features

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** None (public read)

#### Policies

**Policy: `features_select_policy`**
- **Operations:** SELECT only
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  true
  ```
- **WITH CHECK Clause:** null

**Assessment:** ✅ **ACCEPTABLE** - Public read for reference table. Features are global configuration, not tenant-specific.

**Migration Reference:** `84876189e260_create_features_and_plan_features_tables.py`

---

### 7. plan_features

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** None (public read)

#### Policies

**Policy: `plan_features_select_policy`**
- **Operations:** SELECT only
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  true
  ```
- **WITH CHECK Clause:** null

**Assessment:** ✅ **ACCEPTABLE** - Public read for reference table

**Migration Reference:** `84876189e260_create_features_and_plan_features_tables.py`

---

### 8. providers

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** None (public read)

#### Policies

**Policy: `providers_select_policy`**
- **Operations:** SELECT only
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  true
  ```
- **WITH CHECK Clause:** null

**Assessment:** ✅ **ACCEPTABLE** - Public read for provider catalog

**Migration Reference:** `migrations/create_providers_tables.sql`

---

### 9. provider_plans

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** None (public read)

#### Policies

**Policy: `provider_plans_select_policy`**
- **Operations:** SELECT only
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  true
  ```
- **WITH CHECK Clause:** null

**Assessment:** ✅ **ACCEPTABLE** - Public read for plan catalog

**Migration Reference:** `migrations/create_providers_tables.sql`

---

### 10. tenant_provider_subscriptions

**RLS Status:** ✅ Enabled  
**Policy Count:** 4  
**Tenant Isolation:** ⚠️ **NONE** - All policies allow ALL access

#### Policies

**Policy: `tenant_provider_subs_select_policy`**
- **Operations:** SELECT
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** `true` ⚠️
- **WITH CHECK Clause:** null

**Policy: `tenant_provider_subs_insert_policy`**
- **Operations:** INSERT
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** null
- **WITH CHECK Clause:** `true` ⚠️

**Policy: `tenant_provider_subs_update_policy`**
- **Operations:** UPDATE
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** `true` ⚠️
- **WITH CHECK Clause:** null

**Policy: `tenant_provider_subs_delete_policy`**
- **Operations:** DELETE
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** `true` ⚠️
- **WITH CHECK Clause:** null

**Assessment:** ⚠️ **INSECURE** - RLS is enabled but all policies use `USING (true)`, providing NO actual protection. Any user can access/modify any tenant's subscriptions.

**Recommendation:** **HIGH PRIORITY** - Replace with proper tenant isolation:
```sql
DROP POLICY IF EXISTS "tenant_provider_subs_select_policy" ON tenant_provider_subscriptions;
DROP POLICY IF EXISTS "tenant_provider_subs_insert_policy" ON tenant_provider_subscriptions;
DROP POLICY IF EXISTS "tenant_provider_subs_update_policy" ON tenant_provider_subscriptions;
DROP POLICY IF EXISTS "tenant_provider_subs_delete_policy" ON tenant_provider_subscriptions;

CREATE POLICY "tenant_provider_subs_tenant_isolation" ON tenant_provider_subscriptions
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

**Migration Reference:** `migrations/create_providers_tables.sql` (needs update)

---

### 11. audit_logs

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** ⚠️ **NONE** - Superuser policy

#### Policies

**Policy: `audit_logs_superuser_policy`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** `true` ⚠️
- **WITH CHECK Clause:** null

**Assessment:** ⚠️ **INSECURE** - Allows unrestricted access to all audit logs. Any user can read/modify any tenant's audit logs.

**Recommendation:** **HIGH PRIORITY** - Replace with tenant isolation policy:
```sql
DROP POLICY IF EXISTS "audit_logs_superuser_policy" ON audit_logs;

CREATE POLICY "audit_logs_tenant_isolation" ON audit_logs
    FOR ALL
    USING (
        -- Users can see their tenant's logs
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        -- OR Platform admins can see all logs
        OR current_setting('app.user_role', true) = 'platform_admin'
    )
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

### 12. tenant_notes

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** ⚠️ **NONE** - Superuser policy

#### Policies

**Policy: `tenant_notes_superuser_policy`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:** `true` ⚠️
- **WITH CHECK Clause:** null

**Assessment:** ⚠️ **INSECURE** - No tenant isolation. Any user can access any tenant's notes.

**Recommendation:** **MEDIUM PRIORITY** - Add tenant isolation:
```sql
DROP POLICY IF EXISTS "tenant_notes_superuser_policy" ON tenant_notes;

CREATE POLICY "tenant_notes_tenant_isolation" ON tenant_notes
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

### 13. n8n_users

**RLS Status:** ✅ Enabled  
**Policy Count:** 1  
**Tenant Isolation:** Partial

#### Policies

**Policy: `Tenant isolation for n8n_users`**
- **Operations:** ALL
- **Type:** PERMISSIVE
- **Roles:** public
- **USING Clause:**
  ```sql
  tenant_id IN (
      SELECT tenants.id
      FROM tenants
      WHERE (tenants.id = n8n_users.tenant_id)
  )
  ```
- **WITH CHECK Clause:** null

**Assessment:** ⚠️ **OVERLY COMPLEX** - The USING clause is redundant (WHERE clause is always true). Should be simplified.

**Recommendation:** **LOW PRIORITY** - Simplify to standard pattern:
```sql
DROP POLICY IF EXISTS "Tenant isolation for n8n_users" ON n8n_users;

CREATE POLICY "n8n_users_tenant_isolation" ON n8n_users
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

### 14-16. ai_prompt, command, tool

**RLS Status:** ✅ Enabled  
**Policy Count:** 0 ⚠️  
**Tenant Isolation:** Unknown

**Assessment:** ⚠️ **BLOCKS ALL ACCESS** - RLS is enabled but no policies defined. This will block ALL operations.

**Action Required:** Either:
1. Add appropriate policies, or
2. Disable RLS if not needed

**Status:** Requires investigation - These tables not documented in schema files

---

## Tables WITHOUT RLS - By Category

### Core Tables (WITHOUT RLS)

#### tenants

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id` (PK)  
**Sensitive Data:** Tenant names, slugs, subscription info  

**Current Exposure:** Any user with ANON_KEY can read/modify all tenants

**Recommendation:** **CRITICAL PRIORITY** - Enable RLS with special policy:
```sql
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

-- Users can only see their own tenant
CREATE POLICY "tenants_self_access" ON tenants
    FOR SELECT
    USING (id = (current_setting('app.tenant_id', true))::uuid);

-- Platform admins can see all
CREATE POLICY "tenants_platform_admin" ON tenants
    FOR ALL
    USING (current_setting('app.user_role', true) = 'platform_admin');
```

**Migration Reference:** Base schema (needs RLS migration)

---

#### users

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, `email`, `role`, `supabase_auth_id`  
**Sensitive Data:** User emails, roles, authentication IDs

**Current Exposure:** Any user can see all users across all tenants

**Recommendation:** **CRITICAL PRIORITY** - Enable RLS:
```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_tenant_isolation" ON users
    FOR ALL
    USING (
        -- Users can access users in their tenant
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        -- OR Platform admins can access all
        OR current_setting('app.user_role', true) = 'platform_admin'
    )
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### environments

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, `url`, `api_key` (encrypted)  
**Sensitive Data:** n8n instance URLs, API keys

**Current Exposure:** Any user can access any tenant's environment credentials

**Recommendation:** **CRITICAL PRIORITY** - Enable RLS:
```sql
ALTER TABLE environments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "environments_tenant_isolation" ON environments
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

### Workflow Tables (WITHOUT RLS)

#### workflows

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, `workflow_data` (JSONB)  
**Status:** Being phased out in favor of workflow_env_map

**Recommendation:** **MEDIUM PRIORITY** - Enable RLS or deprecate:
```sql
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workflows_tenant_isolation" ON workflows
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

### Operations Tables (WITHOUT RLS)

#### deployments

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, deployment status, workflow selections

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "deployments_tenant_isolation" ON deployments
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### promotions

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, source/target environments, execution results

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE promotions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "promotions_tenant_isolation" ON promotions
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### pipelines

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, pipeline stages, gates

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE pipelines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pipelines_tenant_isolation" ON pipelines
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### snapshots

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, git commits, workflow snapshots

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "snapshots_tenant_isolation" ON snapshots
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### deployment_workflows

**RLS Status:** ❌ Disabled  
**Contains:** Per-workflow deployment results

**Recommendation:** **MEDIUM PRIORITY** - Indirect tenant isolation via deployments FK

---

### Credential Tables (WITHOUT RLS)

#### logical_credentials

**RLS Status:** ❌ Disabled  
**Migration Shows:** RLS SHOULD be enabled (see `migrations/create_credential_tables.sql`)

**Gap Analysis:** Migration file defines RLS policy but it's not enabled in Supabase

**Policy from Migration:**
```sql
ALTER TABLE logical_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY logical_credentials_tenant_isolation ON logical_credentials
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

**Recommendation:** **CRITICAL PRIORITY** - Run the migration that's already defined

---

#### credential_mappings

**RLS Status:** ❌ Disabled  
**Migration Shows:** RLS SHOULD be enabled

**Policy from Migration:**
```sql
ALTER TABLE credential_mappings ENABLE ROW LEVEL SECURITY;

CREATE POLICY credential_mappings_tenant_isolation ON credential_mappings
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

**Recommendation:** **CRITICAL PRIORITY** - Run the migration that's already defined

---

#### workflow_credential_dependencies

**RLS Status:** ❌ Disabled  
**Migration Shows:** RLS SHOULD be enabled

**Policy from Migration:**
```sql
ALTER TABLE workflow_credential_dependencies ENABLE ROW LEVEL SECURITY;

CREATE POLICY workflow_deps_tenant_isolation ON workflow_credential_dependencies
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

**Recommendation:** **CRITICAL PRIORITY** - Run the migration that's already defined

---

#### credentials

**RLS Status:** ❌ Disabled  
**Contains:** Credential metadata from n8n

**Recommendation:** **HIGH PRIORITY**

---

### Drift Management Tables (WITHOUT RLS)

#### drift_incidents

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, drift detection results

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE drift_incidents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "drift_incidents_tenant_isolation" ON drift_incidents
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### drift_policies

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, TTL policies, SLA configurations

**Recommendation:** **HIGH PRIORITY**

---

#### drift_approvals

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, approval requests

**Recommendation:** **MEDIUM PRIORITY**

---

#### drift_check_history

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, historical drift checks

**Recommendation:** **MEDIUM PRIORITY**

---

#### drift_check_workflow_flags

**RLS Status:** ❌ Disabled  
**Contains:** Per-workflow drift flags

**Recommendation:** **MEDIUM PRIORITY**

---

#### drift_policy_templates

**RLS Status:** ❌ Disabled  
**Contains:** Global templates (no tenant_id?)

**Recommendation:** **LOW PRIORITY** - Review if needs tenant_id

---

#### drift_reconciliation_artifacts

**RLS Status:** ❌ Disabled  
**Contains:** Reconciliation results

**Recommendation:** **MEDIUM PRIORITY**

---

### Observability Tables (WITHOUT RLS)

#### executions

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, execution data, results  
**Volume:** Potentially millions of records

**Recommendation:** **HIGH PRIORITY** (but consider performance impact)
```sql
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "executions_tenant_isolation" ON executions
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);

-- Critical: Ensure index exists
CREATE INDEX IF NOT EXISTS idx_executions_tenant_id ON executions(tenant_id);
```

---

#### execution_rollups_daily

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, aggregated metrics

**Recommendation:** **HIGH PRIORITY**

---

#### execution_retention_policies

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, retention configurations

**Recommendation:** **HIGH PRIORITY**

---

### Billing & Entitlements Tables (WITHOUT RLS)

#### plans

**RLS Status:** ❌ Disabled  
**Contains:** Global plan definitions (no tenant_id)

**Recommendation:** **LOW PRIORITY** - Consider enabling SELECT-only policy for transparency

---

#### plan_limits

**RLS Status:** ❌ Disabled  
**Contains:** Global limit definitions

**Recommendation:** **LOW PRIORITY**

---

#### plan_feature_requirements

**RLS Status:** ❌ Disabled  
**Contains:** Global feature requirements

**Recommendation:** **LOW PRIORITY**

---

#### plan_policy_overrides

**RLS Status:** ❌ Disabled  
**Contains:** Per-plan policy overrides

**Recommendation:** **MEDIUM PRIORITY** - Review schema

---

#### plan_retention_defaults

**RLS Status:** ❌ Disabled  
**Contains:** Default retention per plan

**Recommendation:** **LOW PRIORITY**

---

#### tenant_plans

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, active plan assignments

**Recommendation:** **HIGH PRIORITY**
```sql
ALTER TABLE tenant_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_plans_tenant_isolation" ON tenant_plans
    FOR ALL
    USING (
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        OR current_setting('app.user_role', true) = 'platform_admin'
    )
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

---

#### tenant_feature_overrides

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, admin feature overrides

**Recommendation:** **HIGH PRIORITY**

---

#### subscriptions

**RLS Status:** ❌ Disabled  
**Contains:** Stripe subscription data

**Recommendation:** **HIGH PRIORITY** - Contains billing data

---

#### subscription_items

**RLS Status:** ❌ Disabled  

**Recommendation:** **MEDIUM PRIORITY**

---

#### subscription_plans

**RLS Status:** ❌ Disabled  

**Recommendation:** **MEDIUM PRIORITY**

---

#### subscription_plan_price_items

**RLS Status:** ❌ Disabled  

**Recommendation:** **LOW PRIORITY**

---

#### payment_history

**RLS Status:** ❌ Disabled  
**Contains:** Payment records

**Recommendation:** **HIGH PRIORITY** - Sensitive financial data

---

### Platform Admin Tables (WITHOUT RLS)

#### platform_admins

**RLS Status:** ❌ Disabled  
**Contains:** Platform admin user IDs

**Recommendation:** **MEDIUM PRIORITY** - Consider read-only policy for admins
```sql
ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;

-- Only platform admins can manage platform admins
CREATE POLICY "platform_admins_admin_only" ON platform_admins
    FOR ALL
    USING (current_setting('app.user_role', true) = 'platform_admin');
```

---

#### platform_impersonation_sessions

**RLS Status:** ❌ Disabled  
**Contains:** Active impersonation sessions

**Recommendation:** **HIGH PRIORITY** - Security audit table
```sql
ALTER TABLE platform_impersonation_sessions ENABLE ROW LEVEL SECURITY;

-- Only platform admins can see impersonation sessions
CREATE POLICY "impersonation_sessions_admin_only" ON platform_impersonation_sessions
    FOR ALL
    USING (current_setting('app.user_role', true) = 'platform_admin');
```

---

### Other Tables (WITHOUT RLS)

#### background_jobs

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, job status, metadata

**Recommendation:** **MEDIUM PRIORITY**

---

#### events

**RLS Status:** ❌ Disabled  
**Contains:** Event tracking

**Recommendation:** **MEDIUM PRIORITY** - Review if needs tenant isolation

---

#### tags

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, workflow tags

**Recommendation:** **LOW PRIORITY**

---

#### notification_channels

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, channel configs

**Recommendation:** **MEDIUM PRIORITY**

---

#### notification_rules

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, notification routing

**Recommendation:** **MEDIUM PRIORITY**

---

#### health_checks

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, environment health status

**Recommendation:** **MEDIUM PRIORITY**

---

#### environment_types

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, custom environment types

**Recommendation:** **LOW PRIORITY**

---

#### workflow_policy_matrix

**RLS Status:** ❌ Disabled  
**Contains:** Policy definitions per environment class

**Recommendation:** **LOW PRIORITY** - May be global config

---

#### workflow_snapshots

**RLS Status:** ❌ Disabled  
**Contains:** Workflow version history

**Recommendation:** **MEDIUM PRIORITY**

---

#### tenant_api_keys

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, API keys

**Recommendation:** **CRITICAL PRIORITY** - Highly sensitive

---

#### support_requests

**RLS Status:** ❌ Disabled  
**Contains:** `tenant_id`, support tickets

**Recommendation:** **HIGH PRIORITY**

---

#### support_attachments

**RLS Status:** ❌ Disabled  
**Contains:** Support ticket attachments

**Recommendation:** **MEDIUM PRIORITY**

---

#### support_config

**RLS Status:** ❌ Disabled  
**Contains:** Support configuration

**Recommendation:** **LOW PRIORITY**

---

#### feature_access_log

**RLS Status:** ❌ Disabled  
**Contains:** Feature access tracking

**Recommendation:** **LOW PRIORITY**

---

#### feature_config_audit

**RLS Status:** ❌ Disabled  
**Contains:** Feature config change audit

**Recommendation:** **LOW PRIORITY**

---

#### provider_users

**RLS Status:** ❌ Disabled  
**Contains:** Provider-specific user data

**Recommendation:** **MEDIUM PRIORITY** - Review schema

---

#### incident_payloads

**RLS Status:** ❌ Disabled  
**Contains:** Incident data

**Recommendation:** **MEDIUM PRIORITY**

---

#### alembic_version

**RLS Status:** ❌ Disabled  
**Contains:** Migration tracking

**Recommendation:** **NONE** - System table, no RLS needed

---

#### sessions

**RLS Status:** ❌ Disabled  
**Contains:** Session data

**Recommendation:** **MEDIUM PRIORITY** - Review if needs isolation

---

#### memory_short / memory_long

**RLS Status:** ❌ Disabled  
**Contains:** Unknown (possibly AI/LLM context?)

**Recommendation:** **REVIEW REQUIRED** - Investigate purpose and data

---

#### playbook

**RLS Status:** ❌ Disabled  

**Recommendation:** **REVIEW REQUIRED**

---

---

## RLS Policy Patterns

### Pattern 1: Standard Tenant Isolation (Most Common)

Use for any table with `tenant_id`:

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_tenant_isolation" ON {table_name}
    FOR ALL
    USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
```

**Applied to:** Most tenant-scoped tables

---

### Pattern 2: Public Read, No Write

For reference/catalog tables:

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_public_read" ON {table_name}
    FOR SELECT
    USING (true);
```

**Applied to:** `features`, `plan_features`, `providers`, `provider_plans`

---

### Pattern 3: Platform Admin Override

For admin-managed tables:

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_with_admin" ON {table_name}
    FOR ALL
    USING (
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        OR current_setting('app.user_role', true) = 'platform_admin'
    )
    WITH CHECK (
        tenant_id = (current_setting('app.tenant_id', true))::uuid
        OR current_setting('app.user_role', true) = 'platform_admin'
    );
```

**Applied to:** `tenants`, `users`, `audit_logs`

---

### Pattern 4: Platform Admin Only

For platform-scoped tables:

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_platform_only" ON {table_name}
    FOR ALL
    USING (current_setting('app.user_role', true) = 'platform_admin');
```

**Applied to:** `platform_admins`, `platform_impersonation_sessions`

---

### Pattern 5: Environment-Scoped

For tables that belong to environments (indirect tenant isolation):

```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "{table_name}_env_isolation" ON {table_name}
    FOR ALL
    USING (
        environment_id IN (
            SELECT id FROM environments 
            WHERE tenant_id = (current_setting('app.tenant_id', true))::uuid
        )
    );
```

**Applied to:** `executions` (via environment), `health_checks`, etc.

---

## Recommendations

### Critical Priority (Security Risk)

1. **tenant_api_keys** - API keys must be tenant-isolated
2. **tenants** - Core table needs protection
3. **users** - User data needs isolation
4. **environments** - Contains encrypted API keys
5. **logical_credentials**, **credential_mappings**, **workflow_credential_dependencies** - Migration exists but not applied
6. **tenant_provider_subscriptions** - Fix overly permissive policies
7. **audit_logs** - Replace superuser policy

### High Priority (Data Leakage Risk)

8. **deployments**, **promotions**, **pipelines**, **snapshots** - Operations data
9. **drift_incidents**, **drift_policies** - Governance data
10. **executions** - Observability data (high volume, test performance)
11. **tenant_plans**, **tenant_feature_overrides** - Entitlement data
12. **subscriptions**, **payment_history** - Billing data
13. **support_requests** - Support data
14. **platform_impersonation_sessions** - Audit data

### Medium Priority (Best Practice)

15. **workflows** (if not deprecated), **workflow_snapshots**
16. **drift_approvals**, **drift_check_history**
17. **execution_rollups_daily**, **execution_retention_policies**
18. **notification_channels**, **notification_rules**
19. **background_jobs**, **events**
20. **plan_policy_overrides**

### Low Priority (Less Critical)

21. **tags**, **environment_types**
22. **plan_limits**, **plan_feature_requirements**, **plan_retention_defaults**
23. **feature_access_log**, **feature_config_audit**
24. Simplify **n8n_users** policy

### Fix Existing Policies

- **tenant_provider_subscriptions** - Replace `USING (true)` with proper isolation
- **audit_logs** - Replace superuser policy with tenant isolation + admin override
- **tenant_notes** - Replace superuser policy
- **n8n_users** - Simplify redundant subquery

### Tables Needing Investigation

- **ai_prompt**, **command**, **tool** - RLS enabled but no policies
- **memory_short**, **memory_long**, **playbook** - Unknown purpose

---

## Migration Plan

### Phase 1: Critical Security (Week 1)

Create single migration to enable RLS on critical tables:

```python
"""enable_rls_critical_tables

Revision ID: rls_critical_001
Revises: current_head
Create Date: 2026-01-XX
"""

def upgrade() -> None:
    # Apply credential table policies (already defined)
    op.execute(open('migrations/create_credential_tables.sql').read())
    
    # Fix tenant_provider_subscriptions
    op.execute('''
        DROP POLICY IF EXISTS "tenant_provider_subs_select_policy" ON tenant_provider_subscriptions;
        DROP POLICY IF EXISTS "tenant_provider_subs_insert_policy" ON tenant_provider_subscriptions;
        DROP POLICY IF EXISTS "tenant_provider_subs_update_policy" ON tenant_provider_subscriptions;
        DROP POLICY IF EXISTS "tenant_provider_subs_delete_policy" ON tenant_provider_subscriptions;
        
        CREATE POLICY "tenant_provider_subs_tenant_isolation" ON tenant_provider_subscriptions
            FOR ALL
            USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
            WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
    ''')
    
    # tenant_api_keys
    op.execute('''
        ALTER TABLE tenant_api_keys ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "tenant_api_keys_tenant_isolation" ON tenant_api_keys
            FOR ALL
            USING (tenant_id = (current_setting('app.tenant_id', true))::uuid)
            WITH CHECK (tenant_id = (current_setting('app.tenant_id', true))::uuid);
    ''')
    
    # Add remaining critical tables...
```

### Phase 2: High Priority (Week 2)

Operations, drift, observability tables

### Phase 3: Medium Priority (Week 3)

Remaining tenant-scoped tables

### Phase 4: Cleanup (Week 4)

- Fix overly permissive policies
- Test all policies
- Update documentation

---

## Verification

After enabling RLS, verify using queries from [RLS_VERIFICATION.md](RLS_VERIFICATION.md):

```sql
-- Verify RLS status
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' AND rowsecurity = true
ORDER BY tablename;

-- Export all policies
SELECT * FROM pg_policies WHERE schemaname = 'public';
```

---

## Related Documentation

- [RLS_VERIFICATION.md](RLS_VERIFICATION.md) - Verification procedures
- [RLS_CHANGE_CHECKLIST.md](RLS_CHANGE_CHECKLIST.md) - Adding/modifying policies
- [SECURITY_AUDIT_RESULTS.md](SECURITY_AUDIT_RESULTS.md) - Tenant isolation audit
- [TENANT_ISOLATION_SCANNER.md](TENANT_ISOLATION_SCANNER.md) - Endpoint scanner

---

**Document Maintainer:** Update this document after any RLS policy changes  
**Review Schedule:** Monthly, or before major releases  
**Last Reviewed:** 2026-01-08

