# Tenant Provider Subscriptions — B + Explicit Provisioning
Version: MVP (N8N only), multi-provider ready

## 1. Decision Summary (Locked)
- Model: Independent plans per provider
- Storage: B — explicit subscription row with a plan
- Provisioning: Explicit only (onboarding or tenant admin action)
- No automatic subscriptions on tenant creation
- Free is a real plan with entitlements
- Paid plans do NOT imply access to other providers

## 2. Data Model

### Table: tenant_provider_subscriptions
Purpose: Represents a tenant’s explicit relationship to a provider with an always-present plan.

Columns:
- id (uuid, pk)
- tenant_id (uuid, fk → tenants.id)
- provider_id (uuid, fk → providers.id)
- plan_id (uuid, fk → provider_plans.id, NOT NULL)
- status (enum: active | trialing | past_due | canceled), default active for Free
- stripe_subscription_id (text, nullable)
- stripe_item_id (text, nullable)
- created_at (timestamptz)
- updated_at (timestamptz)

Constraints:
- UNIQUE (tenant_id, provider_id)
- plan_id NOT NULL
- Application-level validation:
  provider_plans.provider_id MUST equal tenant_provider_subscriptions.provider_id

Policy:
- Row exists ONLY after explicit selection
- Once row exists, it ALWAYS has a plan (Free or Paid)

## 3. Provisioning Rules

Create or update a row when:
1. Onboarding
   - User selects provider (MVP: N8N)
   - User selects plan (Free or Pro)
   - Create row with selected plan

2. Tenant Admin → Providers
   - “Add provider” (future)
   - Create row with provider’s Free plan or chosen plan

Do NOT create rows on:
- Tenant creation
- Login / first visit
- Platform catalog changes

## 4. Cancellation / Downgrade Behavior
- Cancel Paid → downgrade to Free
- Keep the row
- Set plan_id = provider’s Free plan
- status = active

## 5. Entitlement & Gating Rules

For any provider-scoped feature:
1. Fetch tenant_provider_subscriptions for (tenant_id, provider_id)
2. If missing → provider not selected → block + CTA “Add provider”
3. If present → gate by plan.entitlements

No global tenant plan checks. Always provider-scoped.

## 6. API Contracts (Minimum)

GET /api/tenant/providers
Returns selected providers with plan + entitlements.

POST /api/tenant/providers/:providerKey/subscribe
Body:
{ "planKey": "free" | "pro" }

Behavior:
- If row exists → update plan_id
- If not → create row
- Handle Stripe create/update if paid

## 7. UI — Onboarding (MVP)

Step: Providers & Plans
- Show provider cards (N8N only)
- Plan selector: Free / Pro
- Continue → persist subscription row

## 8. UI — Tenant Admin

Page: Providers & Plans
Table columns:
- Provider
- Current Plan
- Status
- Actions: Upgrade/Downgrade, Manage Billing, Cancel (downgrades to Free)

## 9. Platform Admin (Out of Scope)
- Platform manages provider + plan catalog only
- No tenant subscriptions in platform settings

## 10. MVP Checklist
- Create table + constraints
- Ensure Free plan for N8N exists
- Write onboarding provisioning
- Replace global plan checks with provider-scoped checks
- Add Tenant Admin Providers & Plans page

## 11. Invariants
- No implicit provider subscriptions
- Subscription row always has a plan
- Provider access is independent
- Free is explicit, not inferred
