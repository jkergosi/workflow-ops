# WorkflowOps — Billing & Subscription Page Redesign (Cursor Instructions)

## Goal
Redesign the Billing page so it is operational (status, charges, invoices, usage vs entitlements) and does NOT show the full plan cards by default. Keep plan comparison behind explicit intent (“Change plan”).

## Scope
- Page route: `/billing` (or existing billing page route)
- Keep Stripe customer portal flow (Manage Subscription) if already implemented.
- Remove “Available Plans” cards from default page rendering.
- Show resolved entitlements (numeric, Unlimited, Custom). Never show “undefined”.

---

## UX Requirements

### 1) Page Layout (Top-to-bottom)
1. **Subscription Overview** (primary card)
2. **Usage & Limits Summary** (secondary card)
3. **Payment Method** (secondary card)
4. **Invoices** (table)
5. **Links** to deeper admin pages (Usage & Limits, Entitlements Audit) if they exist

### 2) Subscription Overview Card (must be above the fold)
Display:
- Plan name (e.g., Free / Pro / Agency / Custom)
- Status badge: `Active | Trialing | Past Due | Canceled`
- Billing cadence: `Monthly | Annual`
- Next invoice date + amount (if active/trialing)
- Cancelation state (if cancel at period end, show: “Cancels on <date>”)

Actions:
- Primary: **Change Plan**
- Secondary: **Manage Subscription** (opens Stripe portal)
- Destructive (de-emphasized): **Cancel Subscription** (if not Free and not already canceled)
  - If you already use Stripe portal for cancel, route through portal.

Rules:
- If Free plan: hide “Cancel”, show “Upgrade” instead of “Manage Subscription” unless you have a free Stripe customer.
- If status is Past Due: show warning + “Update payment method” CTA.

### 3) Usage & Limits Summary Card
Purpose: show top limits that drive upgrades and risk (agency load).

Display 4–6 key metrics (choose the ones you actually enforce):
- Environments: `used / limit`
- Team members: `used / limit`
- Promotions this month: `used / limit` (if applicable)
- Backups/snapshots: `used / limit` (if applicable)
- Providers connected: `used / limit` (if applicable)
- Any other hard limit you enforce

Include:
- “View full usage & limits” → link to `/usage-limits` (or existing)
- If within 80% of any limit, show a warning state for that row.

Formatting rules:
- Limit values must render as:
  - number (e.g., 3)
  - `Unlimited`
  - `Custom`
  - `—` only if not applicable (not configured for that plan)
- Never render `undefined` or `null`.

### 4) Payment Method Card
Display:
- Default payment method brand + last4 + exp (if exists)
- Billing email (if you store it; otherwise omit)

Actions:
- **Update payment method** (route through Stripe portal or your billing update flow)

Rules:
- If no payment method on file and plan is paid: show warning + “Add payment method”.

### 5) Invoices Table
Table columns:
- Date
- Invoice #
- Amount
- Status (Paid / Open / Uncollectible / Void)
- Download (PDF link)

Behaviors:
- Show latest 10 invoices, with “View all” if more.
- Clicking Download opens the invoice PDF URL.

Empty state:
- “No invoices yet” (Free plan or newly created paid tenant)

### 6) Plans / Pricing Content Removal
- Remove “Available Plans” section from the Billing page body.
- “Change Plan” opens either:
  - A dedicated `/plans` page (recommended), OR
  - A modal with plan choices (minimal)
- Only show plan comparisons after the user clicks “Change Plan”.

---

## Data / API Requirements

### 1) Single DTO for Billing Page
Implement (or adapt) an endpoint to hydrate the page in one call:
- `GET /api/billing/overview`

Response shape (example):
```json
{
  "plan": {
    "key": "pro",
    "name": "Pro",
    "is_custom": false
  },
  "subscription": {
    "status": "active",
    "interval": "month",
    "current_period_end": "2026-02-12T00:00:00Z",
    "cancel_at_period_end": false,
    "next_amount_cents": 4900,
    "currency": "USD"
  },
  "usage": {
    "environments_used": 2,
    "team_members_used": 4
  },
  "entitlements": {
    "environments_limit": 3,
    "team_members_limit": 5,
    "promotions_monthly_limit": 50,
    "snapshots_monthly_limit": "Unlimited"
  },
  "payment_method": {
    "brand": "Visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2027
  },
  "invoices": [
    {
      "id": "in_123",
      "number": "WO-1042",
      "created": "2026-01-12T00:00:00Z",
      "status": "paid",
      "amount_paid_cents": 4900,
      "currency": "USD",
      "pdf_url": "https://..."
    }
  ],
  "links": {
    "stripe_portal_url": "https://...",
    "change_plan_url": "/plans",
    "usage_limits_url": "/usage-limits",
    "entitlements_audit_url": "/entitlements-audit"
  }
}
