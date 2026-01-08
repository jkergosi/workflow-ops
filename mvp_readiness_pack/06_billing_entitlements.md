# 06 - Billing, Entitlements & Downgrade Enforcement

## Entitlements Resolution Algorithm

### Architecture

**3-Tier Hierarchy**:
1. **Base Plan Features**: `plan_features` table
2. **Tenant Feature Overrides**: `tenant_feature_overrides` table (admin overrides)
3. **Runtime Checks**: Real-time validation

### Resolution Flow

**File**: `services/entitlements_service.py:get_tenant_entitlements()`

```python
def resolve_entitlements(tenant_id, provider="n8n"):
    # 1. Get active plan
    plan = get_tenant_plan(tenant_id, provider)
    
    # 2. Get plan features
    features = get_plan_features(plan.id)
    
    # 3. Apply overrides
    overrides = get_tenant_overrides(tenant_id)
    for override in overrides:
        if not override.expired:
            features[override.feature_name] = override.value
    
    # 4. Return merged entitlements
    return features
```

### Feature Types

**File**: `schemas/entitlements.py`

**Flags** (boolean):
- `snapshots_enabled`
- `promotions_enabled`
- `drift_detection_enabled`
- `canonical_workflows_enabled`
- `audit_logs_enabled`

**Limits** (numeric):
- `environment_limits`: Max environments
- `team_member_limits`: Max users
- `workflow_limits`: Max workflows (rarely enforced)

### Feature Matrix

| Feature | Free | Pro | Agency | Enterprise |
|---------|------|-----|--------|------------|
| environment_limits | 2 | 10 | -1 (unlimited) | -1 |
| team_member_limits | 3 | 10 | -1 | -1 |
| snapshots_enabled | false | true | true | true |
| promotions_enabled | false | true | true | true |
| drift_full_diff | false | false | true | true |
| drift_ttl_sla | false | false | true | true |
| audit_log_retention_days | 0 | 90 | 180 | -1 (unlimited) |

**Source**: `PRD_cursor.md` lines 735-756

---

## Server-Side Enforcement Points

### RBAC (tenant admin)
- Billing actions are now enforced server-side with `require_tenant_admin()`:
  - `/billing/subscription`
  - `/billing/checkout`
  - `/billing/portal`
  - `/billing/cancel`
  - `/billing/reactivate`
  - `/billing/invoices`
  - `/billing/upcoming-invoice`
  - `/billing/payment-history`
- Non-admin tenants receive `403 Admin role required`.

### Flag Enforcement

**Decorator**: `core/entitlements_gate.py:require_entitlement(feature_name)`

**Usage**:
```python
@router.post("/snapshots")
async def create_snapshot(
    user_info: dict = Depends(require_entitlement("snapshots_enabled"))
):
    # Endpoint logic
```

**Logic**:
1. Extract tenant_id from user_info
2. Call `entitlements_service.enforce_flag(tenant_id, feature_name)`
3. If not enabled → Raise `HTTPException(403, "Feature not available. Upgrade required.")`
4. If enabled → Pass through

**Test**: `tests/test_feature_gate.py`

**Risk**: Decorator easy to forget on new endpoints. No automated validation.

### Limit Enforcement

**Function**: `entitlements_service.py:enforce_limit()`

**Usage**:
```python
# Before creating environment
current_count = count_environments(tenant_id)
await entitlements_service.enforce_limit(
    tenant_id=tenant_id,
    feature_name="environment_limits",
    current_count=current_count
)
```

**Logic**:
1. Get limit from entitlements
2. If `current_count >= limit` and `limit != -1` → Raise `HTTPException(403, "Limit reached")`
3. Else → Pass through

**Test**: `tests/test_entitlements.py`

**Risk**: Limit checks rely on accurate current_count (sync dependency). Stale data could cause false positives/negatives.

---

## Stripe Webhook Handling

### Webhook Endpoint

**API**: `POST /api/v1/billing/stripe-webhook`

**File**: `api/endpoints/billing.py:stripe_webhook()`

**Security**: Stripe signature verification

```python
sig_header = request.headers.get("stripe-signature")
event = stripe.Webhook.construct_event(
    payload=await request.body(),
    sig_header=sig_header,
    secret=settings.STRIPE_WEBHOOK_SECRET
)
```

### Event Handlers

| Event Type | Handler | Action |
|-----------|---------|--------|
| `customer.subscription.created` | `handle_subscription_created()` | Create `tenant_provider_subscriptions` record |
| `customer.subscription.updated` | `handle_subscription_updated()` | Update subscription, detect downgrades |
| `customer.subscription.deleted` | `handle_subscription_deleted()` | Mark subscription inactive, trigger downgrade |
| `invoice.paid` | `handle_invoice_paid()` | Record payment in `payment_history` |
| `invoice.payment_failed` | `handle_invoice_payment_failed()` | Send notification, potentially suspend |

**Test**: `tests/test_billing_webhooks.py`

### Downgrade Detection

**File**: `billing.py:handle_subscription_updated()` (lines 911-1038)

**Logic**:
```python
old_plan = subscription.items[0].price.metadata.get("plan_name")
new_plan = subscription.items[0].price.metadata.get("plan_name")

old_precedence = get_plan_precedence(old_plan)  # free=0, pro=1, agency=2, enterprise=3
new_precedence = get_plan_precedence(new_plan)

if new_precedence < old_precedence:
    # Downgrade detected
    await downgrade_service.handle_plan_downgrade(
        tenant_id=tenant_id,
        old_plan=old_plan,
        new_plan=new_plan
    )
```

**Plan Precedence** (hardcoded):
- free: 0
- pro: 1
- agency: 2
- enterprise: 3

**Risk**: Precedence hardcoded. If new plans added, precedence must be manually updated.

---

## Downgrade / Over-Limit Behavior

### Downgrade Service

**File**: `services/downgrade_service.py`

**Flow**:
1. Detect over-limit resources
2. Apply downgrade policy
3. Create grace period records
4. Notify tenant

### Over-Limit Detection

**Functions**:
- `detect_environment_overlimit(tenant_id)` → Returns (is_over, current_count, limit, over_limit_ids)
- `detect_team_member_overlimit(tenant_id)` → Similar

**Trigger**: Webhook handler calls detection after plan change

**Selection Strategy**: `core/downgrade_policy.py:ResourceSelectionStrategy`
- `OLDEST_FIRST`: Delete oldest resources first
- `NEWEST_FIRST`: Delete newest resources first
- `USER_CHOICE`: User selects which to delete (NOT IMPLEMENTED)

**Risk**: Detection only runs on webhook (not periodic). Tenants could stay over-limit indefinitely if webhook missed.

### Downgrade Policy

**File**: `core/downgrade_policy.py:DowngradePolicy`

**Policy Config**:
```python
POLICIES = {
    ResourceType.ENVIRONMENT: DowngradePolicy(
        resource_type=ResourceType.ENVIRONMENT,
        grace_period_days=14,
        action=DowngradeAction.READ_ONLY,
        selection_strategy=ResourceSelectionStrategy.OLDEST_FIRST
    ),
    ResourceType.TEAM_MEMBER: DowngradePolicy(
        resource_type=ResourceType.TEAM_MEMBER,
        grace_period_days=7,
        action=DowngradeAction.DISABLE,
        selection_strategy=ResourceSelectionStrategy.NEWEST_FIRST
    )
}
```

**Actions**:
- `READ_ONLY`: Resource accessible but not editable
- `SCHEDULE_DELETION`: Mark for deletion after grace period
- `DISABLE`: Immediately disable
- `IMMEDIATE_DELETE`: Delete immediately (no grace)
- `WARN_ONLY`: Log warning only
- `ARCHIVE`: Soft delete

**Grace Period Tracking**:
- **Table**: `downgrade_grace_periods`
- **Columns**:
  - `id`, `tenant_id`, `resource_type`, `resource_id`
  - `grace_period_days`: Length of grace period
  - `expires_at`: Grace period end
  - `status`: active/completed/cancelled
  - `action`: What happens on expiry
  - `notified_at`: When tenant was notified

**Migration**: `alembic/versions/380513d302f0_add_downgrade_grace_periods_table.py`

**Gap**: Grace period expiry not automated. No job to enforce action on expiry.

### Downgrade Error Handling

**File**: `billing.py:handle_subscription_updated()`

```python
try:
    downgrade_summary = await downgrade_service.handle_plan_downgrade(...)
    logger.info(f"Downgrade completed: {downgrade_summary}")
except Exception as e:
    logger.error(f"Downgrade failed: {e}")
    # Don't fail webhook - just log error
```

**Behavior**: Downgrade errors logged but don't fail webhook. Tenant subscription updated even if downgrade handling fails.

**Risk**: Webhook succeeds but tenant still over-limit with no grace period created.

---

## Retention Enforcement

### Retention Job

**File**: `services/background_jobs/retention_job.py`

**Schedule**: Daily at 2 AM UTC (`RETENTION_JOB_SCHEDULE_CRON = "0 2 * * *"`)

**Startup**: `main.py:startup_event()` calls `start_retention_scheduler()`

**Target Resources**:
- **Executions**: Delete based on plan retention days
- **Audit Logs**: Delete based on plan retention days

### Retention Logic

```python
async def trigger_retention_enforcement(dry_run=False):
    for tenant in get_all_tenants():
        entitlements = get_tenant_entitlements(tenant.id)
        exec_retention = entitlements.get("execution_retention_days", 7)
        audit_retention = entitlements.get("audit_log_retention_days", 0)
        
        cutoff_exec = now() - timedelta(days=exec_retention)
        cutoff_audit = now() - timedelta(days=audit_retention)
        
        if not dry_run:
            delete_executions_before(tenant.id, cutoff_exec, min_preserve=100)
            delete_audit_logs_before(tenant.id, cutoff_audit, min_preserve=100)
```

**Safety**: Preserves minimum 100 records per tenant even if retention policy would delete more.

**Batch Size**: 1000 records per batch (from config: `RETENTION_JOB_BATCH_SIZE`)

**Test**: `tests/test_retention.py`

**Risk**: Deletion timing (2 AM UTC) may cause load spike. No staggering across tenants.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/billing/checkout` | Create Stripe checkout session |
| POST | `/billing/stripe-webhook` | Handle Stripe events |
| GET | `/billing/subscriptions` | List tenant subscriptions |
| POST | `/billing/cancel` | Cancel subscription |
| GET | `/billing/customer-portal` | Redirect to Stripe portal |
| GET | `/providers/{id}/entitlements` | Get tenant entitlements |
| GET | `/providers/{id}/plans` | List available plans |
| POST | `/admin/entitlements/overrides` | Create feature override |
| GET | `/admin/entitlements/overrides` | List overrides |
| DELETE | `/admin/entitlements/overrides/{id}` | Remove override |
| GET | `/admin/usage/over-limits` | List tenants over limits |
| GET | `/retention/policies` | Get retention policies |
| POST | `/retention/enforce` | Trigger retention (manual) |

---

## Database Tables

### tenant_provider_subscriptions

**Purpose**: Track active subscriptions per provider

**Key Columns**:
- `id`, `tenant_id`, `provider_id`
- `plan_id`: FK to provider_plans
- `stripe_subscription_id`: Stripe sub ID
- `status`: active/cancelled/past_due
- `current_period_start`, `current_period_end`
- `cancel_at_period_end` (bool)
- `created_at`, `updated_at`

### provider_plans

**Purpose**: Define plans per provider

**Key Columns**:
- `id`, `provider_id`
- `name`: free/pro/agency/enterprise
- `display_name`: "Free Plan"
- `stripe_price_id_monthly`, `stripe_price_id_yearly`
- `monthly_price`, `yearly_price`
- `features` (JSONB): Feature definitions
- `is_active` (bool)

### plan_features

**Purpose**: Map features to plans

**Key Columns**:
- `plan_id`, `feature_name`
- `feature_value` (JSONB): Flag (bool) or limit (number)

### tenant_feature_overrides

**Purpose**: Admin overrides for specific tenants

**Key Columns**:
- `id`, `tenant_id`, `feature_name`
- `override_value` (JSONB)
- `expires_at`: Optional expiration
- `reason`: Admin notes
- `created_by`, `created_at`

### downgrade_grace_periods

**Purpose**: Track grace periods for over-limit resources

**Key Columns**: See "Downgrade Policy" section

---

## Tests

| Test File | Coverage |
|-----------|----------|
| `test_billing_api.py` | Checkout, subscription CRUD |
| `test_billing_webhooks.py` | Webhook handling, downgrade detection |
| `test_entitlements.py` | Entitlement resolution, flag/limit enforcement |
| `test_feature_gate.py` | Feature gate decorator |
| `test_retention.py` | Retention enforcement, batch deletion |
| `test_tenant_plan_service.py` | Plan resolution |

**Gaps**: No E2E checkout flow test, grace period expiry enforcement untested

---

## Risk Areas

### High Risk

1. **Downgrade Errors Don't Fail Webhook**: Tenant subscription updated even if downgrade handling fails. Could leave tenant over-limit with no grace period.

2. **Grace Period Expiry Not Enforced**: Grace periods tracked but no automated job to enforce action on expiry.

3. **Over-Limit Detection Only on Webhook**: If webhook missed, tenant could stay over-limit indefinitely.

4. **USER_CHOICE Strategy Not Implemented**: Policy exists but not usable. Always falls back to OLDEST_FIRST/NEWEST_FIRST.

### Medium Risk

1. **Feature Gate Decorator Forgettable**: Easy to forget on new endpoints. No CI/CD validation.

2. **Limit Check Sync Dependency**: Relies on accurate current_count. Stale data could cause issues.

3. **Plan Precedence Hardcoded**: New plans require manual precedence update.

4. **Retention Load Spike**: All tenants processed at 2 AM UTC. No staggering.

### Low Risk

1. **Override Expiration**: Tracked but not automatically enforced. Admin must manually remove expired overrides.

2. **Webhook Idempotency**: Relies on Stripe event ID. Could process duplicate events if ID check fails.

---

## Gaps & Missing Features

### Not Implemented

1. **Grace Period Expiry Enforcement**: No automated job to enforce actions on expiry.

2. **USER_CHOICE Downgrade Strategy**: User selection UI not implemented.

3. **Periodic Over-Limit Detection**: Only runs on webhook.

4. **Checkout E2E Testing**: No comprehensive E2E test for full checkout flow.

5. **Override Auto-Removal**: Expired overrides not automatically removed.

### Unclear Behavior

1. **Downgrade Rollback**: If downgrade handling fails, is there a rollback mechanism?

2. **Concurrent Plan Changes**: Can multiple plan changes happen simultaneously?

3. **Resource Reactivation**: If user upgrades during grace period, how are resources reactivated?

---

## Recommendations

### Must Fix Before MVP Launch

1. Implement grace period expiry enforcement (daily job)
2. Add periodic over-limit detection (not just webhook)
3. Fail webhook if downgrade handling fails (or retry)
4. Document plan precedence and update mechanism

### Should Fix Post-MVP

1. Implement USER_CHOICE downgrade strategy UI
2. Add automatic override expiry removal
3. Add checkout E2E tests
4. Stagger retention enforcement across tenants

### Nice to Have

1. Downgrade preview (show what will be affected)
2. Grace period extension requests
3. Resource usage forecasting
4. Self-service plan comparison UI

