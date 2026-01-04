# Cursor Instructions — Platform Admin Tenants Page (Provider-Scoped Plans)
Applies to: **Platform Admin UI only** (no tenant-facing changes)

## Goal
Refactor the Platform Admin **Tenants** page so it no longer assumes a single tenant-level plan (Pro/Enterprise), and instead reflects **provider-scoped subscriptions** (Option A + B+explicit provisioning model already chosen).

---

## Scope / Stop Conditions
### In scope
- Update **Platform Admin → Tenants** page UI + API usage to:
  - remove tenant-level plan assumptions
  - display provider subscriptions per tenant (provider + plan)
  - add provider-aware filtering
  - improve empty state + CSV export fields
  - add row-level quick actions (incl. impersonate if available)

### Out of scope (DO NOT implement)
- Bundles / global tenant plan
- Auto-provisioning subscriptions on tenant creation
- Tenant-facing UI changes
- Billing portal redesign
- New providers beyond N8N (support UI pattern, but don’t require Make to exist)

---

## 1) Replace Top Summary Cards (Remove Plan Counts)
### Current problem
Top cards show counts for **Enterprise / Pro** which implies a single tenant plan, incompatible with provider-scoped subscriptions.

### Implement
Replace the top cards with:
- **Total Tenants**
- **Active Tenants** (derive from tenant.status, NOT plan)
- **With Providers** (tenants having ≥1 tenant_provider_subscription row)
- **No Providers** (tenants having 0 provider subscriptions)

If you already have tenant status types:
- Optionally add **Suspended** / **Trial** instead of “Active Tenants”.

Implementation detail:
- Compute counts from the tenants list response if it’s small; otherwise add/extend an admin stats endpoint.
- Avoid showing “Pro/Enterprise” anywhere on this page.

---

## 2) Tenants Table: Add Provider Subscriptions Column
Add columns (minimum):
- Tenant (name + email / owner)
- Status
- **Providers** (chips)
- **Billing State** (derived)
- Updated / Created
- Actions

### Providers column (chips)
For each tenant, show chips like:
- `N8N · Pro`
- `N8N · Free`

Rules:
- If no subscriptions → show a muted label: `No providers`
- If plan unknown → `N8N · —`

Design:
- Chips should be compact; show max ~2 and a “+N” overflow indicator with tooltip/popover.

Data requirement:
- Tenants list response must include provider subscriptions joined with:
  - provider key + display_name
  - plan key + plan name (or display label)
  - subscription status

---

## 3) Replace Filters: Remove “All Plans”; Add Provider-Aware Filters
### Remove
- `All Plans` dropdown (tenant-level plans)

### Add
- **Provider** dropdown: All / N8N / (future providers)
- **Provider Plan** dropdown: All / Free / Pro / Agency (scoped to provider selection)
- **Subscription State** dropdown: All / None / Active / Past Due / Canceled
- Keep search + tenant status filter if already present.

Rules:
- If Provider = All, Provider Plan dropdown should be disabled or show “Select a provider”.
- Subscription State = None filters tenants with 0 provider subscriptions.

---

## 4) Row-Level Quick Actions (Platform Admin Only)
Add an actions menu per tenant row:
- **View Tenant** (existing detail page)
- **Manage Subscriptions** (navigate to tenant detail → subscriptions section, or open modal)
- **Impersonate** (if feature exists)
- (Optional) Copy tenant ID

Impersonate behavior:
- Use existing impersonation mechanism if present.
- If not implemented, keep the menu item hidden (feature flag); do not build it here.

---

## 5) Empty State Improvements
Update copy to:
- Title: `No tenants yet`
- Body: `Create your first tenant to start managing subscriptions and providers.`
- Primary CTA: `Add Tenant`
- Secondary (optional): `Configure Provider Catalog` (link to platform providers page) — only if that page exists.

---

## 6) Export CSV: Make it Provider-Scoped
Update export to include provider subscription data:
- provider_count
- providers (string list, e.g. `n8n,make`)
- provider_plans (string list, e.g. `n8n:pro; make:free`)
- billing_state (derived)
- subscription_states (e.g. `n8n:active`)

Implementation:
- If export mirrors visible columns, extend it to include the above fields.
- If export uses a backend endpoint, add these fields server-side.

---

## Derived Field Definitions (Keep Simple)
### provider_count
Count of tenant_provider_subscriptions rows for that tenant.

### billing_state (platform admin diagnostic)
- `Free-only` if all subscriptions are free OR no paid stripe subscription present.
- `Has paid` if any subscription is on a paid plan.
- `Past due` if any subscription status is past_due (takes precedence).

If you have canonical billing status already, use it.

---

## Backend/API Requirements
Ensure the Platform Admin Tenants list endpoint returns enough data to render the table and filters.

### Preferred: Extend existing admin tenants list endpoint
Add:
- `provider_subscriptions: Array<{ provider: {key, display_name}, plan: {key, name, is_free}, status, stripe_subscription_id? }>`
And optionally:
- `provider_count`
- `billing_state` (or compute client-side)

### Filters support
Endpoint should accept query params:
- providerKey
- planKey
- subscriptionState (none/active/past_due/canceled)
- tenantStatus
- search

If backend changes are heavy, client-side filtering is acceptable only if tenant counts are small.

---

## Frontend Implementation Notes (Minimal refactor)
- Keep existing layout, styling system, and component patterns.
- Prefer adding a small `ProvidersChips` component over rewriting the table.
- Keep state management local to the page; do not store provider names in Zustand/localStorage.
- Use existing admin API clients/hooks where possible.

Suggested components:
- `ProvidersChips.tsx` — renders chip list + overflow.
- `TenantsFilters.tsx` — provider-aware filter controls.

---

## Acceptance Criteria
- No “Pro/Enterprise” tenant-level plan counts/labels remain on this page.
- Tenants table shows provider+plan chips per tenant.
- Filters include Provider + Provider Plan + Subscription State (None supported).
- Empty state copy updated and CTA works.
- CSV export includes provider subscription fields.
- Page remains Platform Admin only (platform nav).

---

## Quick Manual Test Plan
1. Tenant with no provider subscriptions → shows `No providers`; filter Subscription State=None matches.
2. Tenant with N8N Free → shows `N8N · Free`; billing_state=Free-only.
3. Tenant with N8N Pro → shows `N8N · Pro`; billing_state=Has paid.
4. past_due subscription → billing_state=Past due; filter works.
5. Export CSV includes provider_plans like `n8n:free` / `n8n:pro`.
