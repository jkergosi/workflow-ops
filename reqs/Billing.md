# WorkflowOps — Agency & Billing Master Specification
Multi-Tenant Governance, Entitlements, and Billing (Authoritative)

---

## 0. Scope & Authority

This document is the **single source of truth** for:
- Agency (multi-client) functionality
- Tenant hierarchy and isolation
- Billing and entitlements (Free / Pro / Agency / Enterprise)
- Stripe integration and reconciliation
- Enforcement boundaries

This file supersedes all partial or previous specifications.

---

## 1. Core Invariants (Hard Rules)

1. **Entitlements are the only feature gate**
   - Source of truth: `tenant_plans → plans → plan_features`
   - Billing mirrors Stripe state only

2. **Exactly one active plan per tenant**
   - Enforced via partial unique index

3. **Agency is a parent tenant**
   - Clients are child tenants
   - Clients may not have child tenants

4. **Client isolation is absolute**
   - No cross-client data access at DB or API layer

5. **Billing never directly gates features**
   - Loss of billing downgrades entitlements only

---

## 2. Tenant Model

### 2.1 Tenant Types

**Agency Tenant**
- Parent tenant
- Has active `plans.agency` or `plans.enterprise`
- Owns zero or more client tenants
- Sole Stripe customer

**Client Tenant**
- Child tenant
- `parent_tenant_id` set
- Fully isolated execution domain
- No Stripe identifiers
- No independent plan assignment

---

## 3. Tenant Hierarchy Schema

```sql
ALTER TABLE tenants
ADD COLUMN parent_tenant_id uuid REFERENCES tenants(id);

CREATE INDEX ix_tenants_parent ON tenants(parent_tenant_id);
```

Rules:
- Agency tenants have `parent_tenant_id = NULL`
- Client tenants must have `parent_tenant_id` set
- Deleting an agency requires resolving all clients

---

## 4. Client Isolation Guarantees

Each client tenant has:
- Dedicated environments (Dev / Staging / Prod, max 3)
- Client-scoped workflows, executions, deployments
- Client-scoped credentials and providers
- Client-scoped snapshots, restores, drift incidents
- Client-scoped audit logs and tags

**Enforcement**
- All queries must scope by `tenant_id`
- Cross-client joins forbidden except via agency aggregate views

---

## 5. Roles & Access Model

### 5.1 Agency Roles

- **Agency Owner**
- **Agency Admin**
- **Agency Operator (optional / future)**

Capabilities:
- View all client tenants
- Switch tenant context
- Manage client users
- View aggregated health and reporting

### 5.2 Client Roles

- Client Admin
- Client User

Capabilities:
- Full access within own tenant only
- No agency or sibling visibility

---

## 6. Environment Model

Per client:
- Up to 3 environments
- Environment type detection (prod vs non-prod)
- Environment-scoped credentials
- Independent deployment lifecycle

---

## 7. Promotion Pipelines

Per client:
- Dev → Staging → Prod pipeline
- Snapshot before promotion
- Drift check before promotion
- Optional approval gate

Agency-level:
- Default pipeline templates
- Policy enforcement (lockable at Agency+ / Enterprise)

---

## 8. Drift & Incident Management

Per client:
- Drift detection per environment
- Drift incidents tied to snapshots
- Restore and resolution audit trail

Agency view:
- Clients with active drift
- Compliance posture overview

---

## 9. Billing & Entitlements Overview

### 9.1 Canonical Plans

`plans` table must include:
- free
- pro
- agency
- enterprise

### 9.2 One Active Plan Enforcement

```sql
CREATE UNIQUE INDEX ux_tenant_plans_one_active
ON tenant_plans (tenant_id)
WHERE is_active = true;
```

---

## 10. Stripe Pricing Model

### 10.1 Pro
- Single subscription item

### 10.2 Agency
Subscription contains **two items**:
1. **Agency Base**
   - Quantity = 1
2. **Per-Client**
   - Quantity = number of active client tenants

Only the agency tenant:
- Has `stripe_customer_id`
- Has `stripe_subscription_id`

---

## 11. Subscription Items Schema

```sql
CREATE TABLE subscription_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  stripe_subscription_id text NOT NULL,
  stripe_subscription_item_id text NOT NULL,
  stripe_price_id text NOT NULL,
  usage_type text NOT NULL CHECK (usage_type IN ('base','per_client')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

---

## 12. Client Count (Authoritative)

Client count =
- tenants where `parent_tenant_id = agency_tenant_id`
- and `status = active`

Triggers:
- Client created
- Client activated/deactivated
- Client deleted
- Reconciliation job

Stripe per-client quantity must be updated accordingly.

---

## 13. Checkout Requirements

Stripe Checkout Session must include:
- `metadata.tenant_id`
- `subscription.metadata.tenant_id`

Required for webhook resolution.

---

## 14. Webhook Handling Rules

### Status → Entitlements
- `trialing`, `active` → paid plan
- `cancel_at_period_end` → keep until end
- `canceled`, `unpaid`, `incomplete_expired` → free

### Required Webhooks
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

All handlers must be idempotent.

---

## 15. Client Lifecycle Rules

### Create Client
- Requires active agency plan
- Creates child tenant
- Increments Stripe per-client quantity

### Disable Client
- Status → inactive
- Decrements Stripe quantity

### Delete Client
- Soft delete recommended
- Treated as inactive for billing

---

## 16. Enforcement on Billing Loss

If agency subscription becomes unpaid or canceled:
- Agency plan downgraded to free
- Client creation blocked
- Agency views read-only
- Client tenants inaccessible until restored

---

## 17. Enterprise Plan

- No Stripe checkout
- Assigned manually by admin
- Full agency capabilities + overrides
- `set_tenant_plan(tenant_id, plans.enterprise)`

---

## 18. Reconciliation Job (Required)

Admin-only command:
- Recompute client counts
- Verify Stripe quantities
- Verify tenant_plans correctness
- Repair drift safely

Must be safe to re-run.

---

## 19. Explicit Non-Goals

Do NOT implement:
- Cross-client workflows
- Shared credentials across clients
- Client-to-client data movement
- Usage-based metering (for now)

---

## 20. Summary

Agency functionality in WorkflowOps provides **true multi-tenant governance**:
- Hard client isolation
- Centralized billing
- Delegated operations
- Policy-enforced promotion
- Scalable MSP and platform use cases

This file is authoritative.
