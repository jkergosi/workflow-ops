# N8N Ops – Admin / Superuser Functional Spec

This document defines the **Admin → Superuser** functionality for the N8N Ops platform. It assumes:

- Auth0 for authentication and tenant-scoped authorization
- Stripe for billing (Free / Pro / Agency / Enterprise plans)
- Supabase (or equivalent) for Postgres
- Feature flags and plan-based entitlements are already implemented
- Observability (metrics, logs, alerts) is already baked in

The goal: give the platform superuser a single place to manage **tenants, users, plans, billing, usage, and system settings**.

**Note:** Feature Matrix (`/admin/entitlements/matrix`) and Tenant Overrides (`/admin/entitlements/overrides`) are already implemented and functional. This document focuses on remaining requirements.

---

## 1. Roles and Scope

### 1.1 Roles

- **End User** – normal user within a tenant; no access to Admin menu.
- **Tenant Admin** – manages users and settings within their own tenant.
- **Superuser (Platform Admin)** – global admin with access to the Admin menu.

### 1.2 Superuser Capabilities

Superuser can:

- View and manage **all tenants**
- View and adjust **plans, billing, and usage**
- Configure **global system settings** (Auth0, Stripe, email)
- View **audit logs** and perform sensitive operations (suspend tenant, etc.)

Superuser actions must be fully audited.

---

## 2. Admin Navigation Structure

Under the main **Admin** menu in N8N Ops, add the following sections (visible only to superusers):

1. **Tenants**
2. **Plans & Billing**
3. **Usage & Limits**
4. **System Settings**
5. **Audit Logs**

Each section is outlined below.

---

## 3. Tenants

### 3.1 Tenants List

**Route:** `/admin/tenants`

**Purpose:** Global overview of all tenants with enhanced filtering and navigation to tenant details.

**Columns:**

- Tenant Name (clickable, links to tenant detail page)
- Tenant ID (slug/identifier)
- Plan (Free / Pro / Agency / Enterprise) with badge styling
- Status (Active / Trial / Suspended / Cancelled / Archived) with color coding
- Primary Contact (Name + Email in single column)
- Created At (formatted date)
- MRR (Monthly Recurring Revenue, abbreviated e.g. `$99/mo`, only for paid plans)
- Quick Stats (Workflows count, Environments count, Users count as icons/numbers)

**Capabilities:**

- **Search:** Search by tenant name, Tenant ID, primary contact email
- **Filters:**
  - Plan dropdown (All / Free / Pro / Agency / Enterprise)
  - Status dropdown (All / Active / Trial / Suspended / Cancelled / Archived)
  - Created date range picker (from date / to date)
- **Actions:**
  - Click tenant name or row to navigate to tenant detail page
  - Create new tenant button (opens dialog)

**Display Requirements:**

- Table should be paginated (e.g., 25/50/100 per page)
- Sortable columns (default: Created At descending)
- Show total count above table
- Export to CSV button (optional but useful)

### 3.2 Tenant Detail Page

**Route:** `/admin/tenants/:tenantId`

**Purpose:** Comprehensive tenant management with all relevant information and actions in tabbed interface.

**Layout:** Tabs at top, content area below. Each tab contains relevant sections and actions.

#### 3.2.1 Overview Tab

**Purpose:** Basic tenant information and lifecycle management actions.

**Display Sections:**

- **Tenant Information Card:**
  - Tenant name (editable text field with save button)
  - Tenant ID / slug (read-only, displayed as monospace code)
  - Status badge (dropdown to change status: Active / Trial / Suspended / Cancelled / Archived)
  - Created at (read-only, formatted)
  - Last active timestamp (read-only, formatted, with "Never" if no activity)

- **Contact Information Card:**
  - Primary contact name (editable)
  - Primary contact email (editable)
  - Contact email validation required

**Action Buttons (in prominent action area):**

- **Suspend Tenant:** 
  - Opens confirmation dialog explaining what suspension means (soft lock access, preserve data)
  - Changes status to "Suspended"
  - Logged in audit log
  
- **Reactivate Tenant:** 
  - Only visible when status is Suspended
  - Changes status back to "Active"
  - Logged in audit log

- **Cancel Tenant:** 
  - Opens confirmation dialog with warning about subscription cancellation
  - Cancels Stripe subscription (via API)
  - Changes tenant status to "Cancelled"
  - Logged in audit log

- **Schedule Deletion:** 
  - Opens dialog with:
    - Retention period selector (30 / 60 / 90 days)
    - Planned deletion date display (calculated from selected period)
    - Warning message about data loss
  - Creates scheduled deletion record
  - Status changes to "Archived" (or similar)
  - Logged in audit log

- **Export Tenant Data:** 
  - Button that initiates export job
  - Shows progress indicator
  - When complete, provides download link or S3 link
  - Export should include all tenant data (workflows, users, environments, execution history, etc.)

**Implementation Notes:**

- All status changes should update the tenant record and trigger appropriate side effects (e.g., suspend should disable login access)
- Deletion scheduling should create a background job/task for actual deletion
- Data export should be async and notify admin when ready

#### 3.2.2 Users & Roles Tab

**Purpose:** Manage users within the tenant, including roles and access control.

**Data Source:** Combined data from Auth0 and local user table (users table in database).

**Display Table Columns:**

- Name (full name from Auth0/local)
- Email (primary identifier)
- Role (Tenant Admin / Member / Read-only, etc.) - editable dropdown per row
- Status (Active / Invited / Disabled) - badge with color coding
- Last login (formatted timestamp, "Never" if no login)
- Actions (dropdown menu per row)

**Per-Row Actions Menu:**

- **Promote to Admin / Demote from Admin:** 
  - Changes role in both Auth0 and local database
  - Confirmation required for demotion
  - Logged in audit log

- **Disable User / Re-enable User:** 
  - Disables in Auth0 (blocks login)
  - Updates status in local database
  - Confirmation required for disable action
  - Logged in audit log

- **Resend Invite:** 
  - Sends invitation email to user
  - Only available if status is "Invited"
  - Shows success/error notification

- **Force Logout / Revoke Sessions:** 
  - Revokes all Auth0 sessions for user
  - User must re-authenticate
  - Confirmation required
  - Logged in audit log

- **Open in Auth0:** 
  - Opens new tab to Auth0 dashboard with user pre-selected
  - Deep link format: `https://[domain].auth0.com/users/[user_id]`

**Implementation Notes:**

- User list should refresh after role/status changes
- Auth0 API integration required for session revocation and user management
- Role changes should be validated (e.g., can't remove last admin)

#### 3.2.3 Plan & Features Tab

**Purpose:** View and manage tenant's plan, billing cycle, trial status, and feature overrides.

**Display Sections:**

- **Plan Summary Card:**
  - Current plan name (large, prominent)
  - Billing interval (Monthly / Annual) - badge
  - Trial status indicator (if applicable):
    - "Trial active until [date]"
    - "Trial expired on [date]"
    - "No trial"
  - Plan change dropdown (select new plan with confirmation)

- **Plan-Based Features Section:**
  - Table or card layout showing features from plan
  - Feature name, type (flag/limit), current value
  - Derived from plan's feature profile (use existing feature matrix system)
  - Read-only display (plan features come from plan definition)

- **Tenant Overrides Section:**
  - List of per-tenant feature overrides
  - Display format: Feature name → Override value → Reason → Actions
  - Example rows:
    - `feature.n8n_backups` → Enabled (override) → "Beta program" → [Edit] [Remove]
    - `limit.max_workflows` → 200 (override) → "Enterprise agreement" → [Edit] [Remove]
  - "Add Override" button opens dialog
  - Link to full Tenant Overrides page (already exists at `/admin/entitlements/overrides`)

**Action Buttons:**

- **Change Plan:** 
  - Dropdown with available plans
  - Confirmation dialog showing:
    - Current plan → New plan
    - Proration information
    - Impact on features
  - Updates Stripe subscription (via API)
  - Updates tenant plan assignment
  - Logged in audit log

- **Manage Trial:** 
  - Button opens trial management dialog
  - Options:
    - Start trial (if no active trial)
    - Extend trial (add days)
    - Cancel trial (end immediately)
  - Updates Stripe subscription trial dates
  - Logged in audit log

**Implementation Notes:**

- Plan changes should integrate with Stripe API to update subscription
- Feature overrides should link to existing override management system
- All plan/trial changes must update Stripe and local database atomically

#### 3.2.4 Billing Tab

**Purpose:** Complete billing and subscription management for the tenant.

See Section 4.2 for detailed requirements. This tab should display all billing information and actions.

**Key Elements:**
- Subscription summary with Stripe links
- Invoice history with download links
- Payment method display
- Subscription management actions (cancel, change interval, etc.)

#### 3.2.5 Usage Tab

**Purpose:** View tenant's current usage versus plan limits.

See Section 5.1 for detailed requirements. This tab should show metrics and usage percentages.

**Key Elements:**
- Metrics cards (workflows, executions, API calls, seats, storage)
- Current value vs plan limit for each metric
- Percentage usage indicators with color coding (green/yellow/red)
- Override management links

#### 3.2.6 Notes Tab

**Purpose:** Internal notes and history about the tenant (never visible to tenant users).

**Display:**

- **Timeline View:** Chronological list of notes (newest first)
  - Each note shows:
    - Date and time
    - Author (superuser name/email)
    - Note content (freeform text, supports multi-line)
    - Delete button (only for note author or superuser)

- **Add Note Section:**
  - Text area for note input
  - "Add Note" button
  - Character limit (e.g., 2000 characters)
  - Auto-save draft (optional)

**Use Cases:**

- Record custom pricing agreements
- Note support escalations and resolutions
- Track sales conversations and beta program participation
- General internal notes for context

**Implementation Notes:**

- Notes should be stored with tenant ID, author ID, timestamp
- Notes are never exposed to tenant users via any API
- Consider markdown support for formatting (optional)

---

## 4. Plans & Billing

### 4.1 Plans Management

**Route:** `/admin/plans`

**Purpose:** Create, edit, and manage subscription plans and their Stripe mappings.

**Current State Note:** Plans exist in database but there's no admin UI for managing them.

**List View Table:**

**Columns:**
- Plan name (Free / Pro / Agency / Enterprise)
- Display name (user-facing name)
- Internal plan ID (UUID)
- Stripe Product ID (with copy button)
- Stripe Price IDs (Monthly / Annual as separate columns, with copy buttons)
- Status badge (Active / Deprecated)
- Base price display (Monthly price, Annual price)
- Key limits summary (e.g., "200 workflows, 25 users" as tooltip or expandable)
- Actions column (Edit, Deprecate/Reactivate)

**Actions:**

- **Create New Plan:**
  - Opens multi-step dialog/form:
    - Step 1: Basic Info
      - Plan name (slug, e.g., "pro")
      - Display name (e.g., "Pro Plan")
      - Description
    - Step 2: Stripe Mapping
      - Stripe Product ID (with lookup/search if possible)
      - Stripe Price ID (Monthly) - with lookup
      - Stripe Price ID (Annual) - with lookup
      - Validate that price IDs exist in Stripe
    - Step 3: Feature Profile
      - Link to feature matrix (select existing plan to copy features from)
      - Or configure features inline
      - Key limits input (workflows, users, environments, etc.)
    - Step 4: Pricing Display
      - Monthly base price (read from Stripe)
      - Annual base price (read from Stripe)
      - Confirm before saving
  - Saves to database plan table
  - Logged in audit log

- **Edit Plan:**
  - Opens similar form pre-filled with current values
  - Can update:
    - Display name, description
    - Feature flags and limits
    - Add new Stripe price IDs (but keep historical ones for existing subscriptions)
  - Cannot change plan name (slug) once created
  - Warning if changing limits that affect existing tenants
  - Logged in audit log

- **Deprecate Plan:**
  - Marks plan as "Deprecated" (not available for new signups)
  - Existing tenants keep the plan until manually changed
  - Can reactivate deprecated plans
  - Confirmation required
  - Logged in audit log

**Implementation Notes:**

- Stripe integration required to validate and fetch price information
- Historical Stripe price IDs should be preserved to avoid breaking existing subscriptions
- Plan deprecation should prevent selection during tenant creation/plan changes
- Consider read-only mode for plans with active subscriptions (to prevent breaking changes)

### 4.2 Tenant Billing (Per-Tenant Subscription)

**Route:** `/admin/tenants/:tenantId/billing` (also accessible as tab in tenant detail)

**Purpose:** Complete view of tenant's subscription, invoices, and payment information with management actions.

**Display Sections:**

- **Subscription Summary Card:**
  - Current plan name and billing interval (Monthly/Annual)
  - Subscription status badge with color:
    - Active (green)
    - Trialing (blue)
    - Past Due (yellow)
    - Cancelled (red)
    - Incomplete (orange)
  - Trial information (if applicable):
    - "Trial ends on [date]"
    - Days remaining display
  - Stripe Customer ID (with copy button and deep link)
  - Stripe Subscription ID (with copy button and deep link)
  - Deep links format: `https://dashboard.stripe.com/customers/[customer_id]`

- **Invoices Table:**
  - Columns: Date, Invoice #, Amount, Status, Actions
  - Status badges: Paid, Open, Void, Uncollectible
  - Amount displayed with currency symbol
  - "View" action opens Stripe-hosted invoice in new tab
  - "Download PDF" action (if available from Stripe)
  - Paginated table
  - Sort by date (newest first)

- **Payment Method Card:**
  - Card brand icon (Visa, Mastercard, etc.)
  - Last 4 digits of card
  - Expiry date (MM/YY format)
  - Read-only display (cannot edit in admin UI)
  - Note: "Update payment method in Stripe customer portal"
  - Link to open Stripe customer portal

- **Tax/Billing Details Card:**
  - Company name (if business customer)
  - Tax ID / VAT number (if provided)
  - Billing address (formatted)
  - Read-only display (managed via Stripe)

**Action Buttons:**

- **Change Plan:**
  - Dropdown with available plans
  - Billing interval toggle (Monthly ↔ Annual)
  - Proration checkbox ("Prorate charges")
  - Confirmation dialog showing:
    - Current plan and price
    - New plan and price
    - Prorated amount (if applicable)
    - Effective date
  - Updates Stripe subscription
  - Updates local tenant plan
  - Logged in audit log

- **Change Billing Interval:**
  - Switch between Monthly and Annual
  - Confirmation with price change details
  - Updates Stripe subscription
  - Logged in audit log

- **Manage Trial:**
  - Dialog with options:
    - Start trial (if no active trial) - input days
    - Extend trial - input additional days
    - End trial immediately
  - Updates Stripe subscription trial dates
  - Logged in audit log

- **Apply Coupon or Credit:**
  - Input field for coupon code
  - Or input field for credit amount (with currency)
  - Applies to Stripe customer/subscription
  - Shows confirmation with applied amount
  - Logged in audit log

- **Cancel Subscription:**
  - Opens cancellation dialog:
    - Radio options:
      - "Cancel at period end" (keeps access until billing period ends)
      - "Cancel immediately" (requires confirmation)
    - Reason input (optional, for internal notes)
  - Updates Stripe subscription
  - Updates tenant status to "Cancelled" (if immediate)
  - Logged in audit log

- **Re-send Invoice Email:**
  - Button next to each invoice in table
  - Sends invoice email via Stripe API
  - Shows success notification

- **Open Stripe Customer Portal:**
  - Button opens Stripe-hosted customer portal in new tab
  - Portal URL generated via Stripe API (portal session)

**Business Logic:**

- When subscription status becomes `past_due`:
  - Show warning banner in tenant detail
  - Optionally change tenant status to "Suspended" (configurable policy)
- When subscription is cancelled:
  - If "at period end": tenant remains active until period ends, then status changes to "Cancelled"
  - If immediate: tenant status changes to "Cancelled" immediately
  - Consider feature locking based on status (e.g., disable certain features for cancelled tenants)

**Implementation Notes:**

- All Stripe actions must use Stripe API (never expose raw API keys to frontend)
- Deep links to Stripe should open in new tabs
- Subscription status should sync from Stripe webhooks (real-time updates)
- Payment method and billing details are read-only in admin UI (managed in Stripe)

### 4.3 Global Billing Dashboard

**Route:** `/admin/billing`

**Purpose:** System-wide view of revenue, subscriptions, and billing health.

**Current State Note:** UI exists but uses mock data. Needs real Stripe integration.

**Display Sections:**

- **Revenue Metrics Cards (Top Row):**
  - Monthly Recurring Revenue (MRR) - large number with trend indicator
  - Annual Recurring Revenue (ARR) - large number with trend indicator
  - New subscriptions (last 30 days) - count with comparison to previous period
  - Churned subscriptions (last 30 days) - count with churn rate percentage
  - Active paying tenants - count (excludes free tier)
  - Active trials - count

- **Plan Distribution Chart:**
  - Visual chart (pie or bar) showing tenant count by plan
  - Breakdown: Free, Pro, Agency, Enterprise
  - Numbers and percentages

- **Recent Successful Charges Table:**
  - Columns: Date, Tenant, Amount, Plan, Invoice #
  - Last 50 charges
  - Sortable and filterable
  - Click tenant name to go to tenant detail
  - Click invoice # to open Stripe invoice

- **Recent Failed Payments Table:**
  - Columns: Date, Tenant, Amount, Plan, Failure reason, Retry date
  - Last 50 failed payments
  - Color-coded rows (red tint for urgency)
  - Failure reason from Stripe (e.g., "insufficient_funds", "card_declined")
  - Actions: "View in Stripe", "Contact tenant" (opens email)

- **Tenants in Dunning Section:**
  - Table of tenants with problematic subscriptions
  - Includes subscriptions with:
    - Status: `past_due`
    - Status: `incomplete`
    - Multiple failed payment attempts (3+)
  - Columns: Tenant, Plan, Status, Last payment attempt, Amount, Actions
  - Actions: "View billing", "Contact tenant", "Open in Stripe"
  - Priority sorting (most urgent first)

**Actions:**

- Click any tenant name → Navigate to tenant detail page
- Click any Stripe ID → Open in Stripe dashboard (deep link)
- Export data buttons (CSV export for tables)

**Implementation Notes:**

- All data should come from Stripe API and local database
- Metrics should be calculated in real-time or cached with reasonable refresh interval
- Failed payments and dunning status should update via Stripe webhooks
- Consider date range filters for metrics (e.g., last 7/30/90 days)

---

## 5. Usage & Limits

### 5.1 Tenant Usage View

**Route:** `/admin/tenants/:tenantId/usage` (also accessible as tab in tenant detail)

**Purpose:** View tenant's current usage metrics compared to plan limits.

**Display Format:**

**Metrics Cards Grid (2-3 columns):**

Each metric displayed as a card with:
- Metric name (e.g., "Workflows", "Executions", "API Calls")
- Icon or visual indicator
- Large current value number
- Plan limit (with "Unlimited" if -1 or very high)
- Progress bar showing % usage
- Color coding:
  - Green: 0-75% usage
  - Yellow: 75-90% usage
  - Red: 90%+ usage or over limit
- Warning indicator if over limit

**Metrics to Display:**

1. **Workflows:**
   - Current: Count of active workflows (not deleted)
   - Limit: From plan (e.g., 200 for Pro)
   - % Usage: Current / Limit

2. **Executions:**
   - Current: Executions in current period (day/month, configurable)
   - Limit: From plan (if applicable)
   - Period selector: "Today", "This Month", "Last Month"

3. **API Calls:**
   - Current: API calls in current period
   - Limit: From plan (if applicable)
   - Period selector: Same as executions

4. **Seats (Users):**
   - Current: Active user count
   - Limit: From plan (e.g., 25 for Pro)
   - % Usage: Current / Limit

5. **Storage:**
   - Current: Storage used (GB or MB, human-readable)
   - Limit: From plan (if applicable)
   - % Usage: Current / Limit
   - Note: Only if storage tracking is implemented

6. **Environments:**
   - Current: Environment count
   - Limit: From plan
   - % Usage: Current / Limit

**Actions:**

- **Override Limits:** 
  - Button/link to tenant overrides page (already exists)
  - Or inline override creation for quick adjustments

- **Recommend Upgrade:** 
  - Show upgrade suggestion if usage consistently exceeds 80%+
  - Link to change plan action

**Implementation Notes:**

- Usage data should be aggregated from existing database tables
- Real-time or near-real-time updates (refresh button available)
- Consider caching with TTL for performance
- Historical usage charts/graphs (optional but useful)

### 5.2 Global Usage Overview

**Route:** `/admin/usage`

**Purpose:** Identify heavy users, usage trends, and upsell opportunities.

**Display Sections:**

- **Top Tenants Tables (Tabs or Accordion):**

  - **By Executions:**
    - Table: Rank, Tenant, Plan, Executions (period), % of total, Trend
    - Default period: Last 30 days
    - Period selector: Today, 7 days, 30 days, 90 days
  
  - **By Workflows:**
    - Table: Rank, Tenant, Plan, Workflow count, Trend
  
  - **By Seats:**
    - Table: Rank, Tenant, Plan, User count, Limit, % usage
  
  - **By Storage:** (if applicable)
    - Table: Rank, Tenant, Plan, Storage used, Limit

- **Tenants Near or Over Limits Section:**
  - Table of tenants approaching or exceeding limits
  - Columns: Tenant, Plan, Metric, Current, Limit, % Usage, Status
  - Status badges: "At Limit", "Over Limit", "Near Limit" (90%+)
  - Filterable by metric type
  - Sortable by % usage
  - Actions: "View tenant", "Recommend upgrade"

- **Filters:**
  - Plan filter (All / Free / Pro / Agency / Enterprise)
  - Timeframe filter (Today / 7 days / 30 days / 90 days)
  - Metric type filter (All / Executions / Workflows / Seats / Storage)

**Actions:**

- Click tenant name → Navigate to tenant detail
- Export data (CSV)

**Implementation Notes:**

- Data should be aggregated efficiently (consider background jobs for heavy calculations)
- Top tenants lists should be paginated
- Consider date range caching for performance
- Trend indicators can show up/down arrows with percentage change

---

## 6. System Settings

**Route:** `/admin/settings`

**Purpose:** Configure global system settings and integrations.

**Current State Note:** Basic settings page exists. Needs enhancement with Auth0 and Stripe-specific sections.

**Layout:** Tabbed interface with sections for different setting categories.

### 6.1 General Settings Tab

**Current Implementation:** Already exists with system configuration, database connection, email settings, environment variables.

**Keep As Is:** No changes needed unless specific enhancements requested.

### 6.2 Auth Settings Tab

**Route:** `/admin/settings/auth` (new tab)

**Purpose:** View and manage Auth0 configuration.

**Display Sections:**

- **Auth0 Connection Information:**
  - Auth0 domain (read-only, displayed)
  - Auth0 client ID (masked, e.g., `abc123...xyz789`, with show/hide toggle)
  - Auth0 client name (read-only, from Auth0)
  - Connection status indicator (Connected / Disconnected)
  - Last synced timestamp

- **Auth0 URLs Configuration:**
  - Allowed callback URLs (read-only list, with copy buttons)
  - Allowed logout URLs (read-only list, with copy buttons)
  - Note: "To modify URLs, update in Auth0 dashboard"

- **Connection Types:**
  - List of enabled connection types (e.g., "Username-Password", "Google", "GitHub")
  - Read-only display
  - Status indicators (Enabled / Disabled)

**Actions:**

- **Open Auth0 Dashboard:** 
  - Button opens Auth0 Management Dashboard in new tab
  - Deep link to application configuration page

- **Test Connection:** 
  - Button to test Auth0 API connectivity
  - Shows success/error message

- **Refresh Configuration:** 
  - Button to fetch latest Auth0 configuration
  - Updates displayed values

**Implementation Notes:**

- Auth0 configuration is primarily read-only in admin UI (managed in Auth0)
- Mask sensitive values (API keys, secrets)
- Deep links should navigate to relevant Auth0 sections

### 6.3 Stripe Settings Tab

**Route:** `/admin/settings/payments` (new tab)

**Purpose:** View and manage Stripe configuration and test webhook connectivity.

**Display Sections:**

- **Stripe Mode:**
  - Large badge showing "Test Mode" or "Live Mode"
  - Toggle to switch modes (with confirmation for switching to live)
  - Warning banner when in test mode

- **Stripe Keys:**
  - Stripe Publishable Key (masked, e.g., `pk_test_...`, with copy button)
  - Stripe Secret Key (masked, e.g., `sk_test_...`, with show/hide toggle)
  - Note: "Keys are stored securely. Contact system administrator to change."

- **Webhook Configuration:**
  - Webhook endpoint URL (read-only, displayed with copy button)
  - Webhook signing secret (masked, with show/hide toggle)
  - Last webhook received timestamp
  - Webhook status indicator (Active / Inactive / Error)

- **Stripe Settings:**
  - Default currency (read-only, e.g., "USD")
  - Tax configuration flags:
    - "Collect VAT" (checkbox, if applicable)
    - "Reverse charge enabled" (checkbox, if applicable)
  - Other tax settings as needed

**Actions:**

- **Test Webhook:**
  - Button sends test webhook event from Stripe
  - Shows success/error message
  - Displays received webhook payload (for debugging)

- **Open Stripe Dashboard:**
  - Button opens Stripe Dashboard in new tab
  - Deep link to webhooks or settings page

- **Refresh Webhook Status:**
  - Button checks webhook endpoint health
  - Updates status indicator

**Implementation Notes:**

- All sensitive keys should be masked by default
- Webhook testing should use Stripe API to send test events
- Mode switching should update configuration and may require restart (note this)
- Deep links should navigate to relevant Stripe sections

### 6.4 Email / Notifications Tab

**Route:** `/admin/settings/notifications` (new tab, or enhance existing email section)

**Purpose:** Configure email provider and notification settings.

**Current State Note:** Email configuration exists in general settings. Consider moving to dedicated tab or enhancing existing.

**Display Sections:**

- **Email Provider Configuration:**
  - Provider selection (SendGrid / AWS SES / Other)
  - API key (masked, with show/hide toggle)
  - API key validation status

- **Email Settings:**
  - Default from address (email input)
  - From name (text input)
  - Reply-to address (email input)
  - Test email recipient (for testing)

**Actions:**

- **Send Test Email:**
  - Input recipient email
  - Button sends test email
  - Shows success/error message

- **Save Changes:**
  - Validates email addresses
  - Saves configuration
  - Shows success notification

**Implementation Notes:**

- Mask API keys and secrets
- Validate email format before saving
- Test email should be sent to verify configuration

---

## 7. Audit Logs

**Route:** `/admin/audit-logs`

**Purpose:** Comprehensive audit trail of all admin and system actions.

**Current State Note:** UI exists but uses mock data. Needs real backend integration.

**Display:**

- **Filters Section (Top):**
  - Time range picker (from date / to date, with presets: Today, Last 7 days, Last 30 days, Last 90 days)
  - Actor filter (dropdown with superuser list, "All" option)
  - Action type filter (dropdown with action types, "All" option):
    - TENANT_CREATED
    - TENANT_UPDATED
    - TENANT_SUSPENDED
    - TENANT_REACTIVATED
    - TENANT_CANCELLED
    - TENANT_DELETION_SCHEDULED
    - TENANT_PLAN_CHANGED
    - USER_ROLE_CHANGED
    - USER_DISABLED
    - USER_ENABLED
    - FEATURE_OVERRIDE_ADDED
    - FEATURE_OVERRIDE_REMOVED
    - PLAN_CREATED
    - PLAN_UPDATED
    - SUBSCRIPTION_CANCELLED
    - TRIAL_STARTED
    - TRIAL_EXTENDED
    - SETTINGS_UPDATED
    - And others as needed
  - Tenant filter (searchable dropdown with tenant list, "All" option)
  - "Clear Filters" button
  - "Export Logs" button (CSV export of filtered results)

- **Audit Log Table:**
  - Columns:
    - Timestamp (formatted date and time, sortable)
    - Actor (Superuser name and email, with avatar if available)
    - Action (action type badge with color coding)
    - Target Entity:
      - Tenant name (if applicable, clickable → tenant detail)
      - User name/email (if applicable)
      - Plan name (if applicable)
      - Feature key (if applicable)
    - Details (summary text, expandable for full details)
    - Metadata (expandable section showing old/new values, notes)
  - Pagination (25/50/100 per page)
  - Sortable columns (default: Timestamp descending)

**Log Entry Details:**

Each log entry should include:

- **Actor:**
  - Superuser ID
  - Superuser email
  - Superuser name

- **Timestamp:**
  - ISO 8601 format
  - Displayed in user's timezone

- **Action Type:**
  - Standardized action codes (e.g., `TENANT_PLAN_CHANGED`)
  - Human-readable labels

- **Target Entity:**
  - Tenant ID and name (if applicable)
  - User ID and email (if applicable)
  - Plan ID and name (if applicable)
  - Feature key (if applicable)
  - Resource ID (generic, for other entities)

- **Metadata:**
  - Old value / New value (for update actions)
  - Notes (freeform text from admin, e.g., "Customer requested downgrade via support ticket #123")
  - IP address (if available)
  - User agent (if available)

**Implementation Notes:**

- All admin actions must write to audit log table
- Logs should be immutable (no deletion, only archival)
- Consider log retention policy (e.g., keep for 1-2 years)
- Export functionality should respect filters
- Consider search functionality within log details
- Performance: Index on timestamp, actor, action_type, tenant_id for fast filtering

---

## 8. Non-Functional Requirements

### 8.1 Authorization

- Admin menu and all routes under `/admin` are restricted to superuser role.
- Tenant admins never see global admin sections.
- Role checks should be enforced at both frontend (menu visibility) and backend (API endpoints).

### 8.2 Auditability

- Any change to tenants, plans, billing adjustments, feature overrides, or system settings must be written to audit logs.
- Audit logs should capture:
  - Who performed the action (superuser)
  - When it was performed (timestamp)
  - What action was performed (action type)
  - What entity was affected (tenant, user, plan, etc.)
  - What changed (old value, new value)
  - Why it changed (notes/reason, if provided)

### 8.3 Safety

- Destructive actions must require confirmation:
  - Cancel subscription
  - Suspend tenant
  - Schedule deletion
  - Delete user
  - Force logout
- Confirmation dialogs should clearly explain consequences.
- Consider requiring re-authentication for highly destructive actions (optional but recommended):
  - Schedule tenant deletion
  - Hard delete tenant
  - Change critical system settings

### 8.4 Observability

- Admin actions should emit events to existing observability pipeline.
- Failed admin actions should trigger alerts.
- Monitor audit log volume and errors.

### 8.5 Data Security

- Never expose sensitive data in UI:
  - Full API keys or secrets (always mask)
  - Credit card numbers (never stored or displayed)
  - Passwords (never displayed)
- Use deep links to external providers (Auth0, Stripe) rather than embedding sensitive data.

### 8.6 Performance

- Large lists (tenants, audit logs, invoices) should be paginated.
- Consider caching for frequently accessed data (plan details, feature matrix).
- Background jobs for heavy operations (data export, usage aggregation).

---

## 9. Phased Delivery Plan

### Phase 1 — Core (Ship first)
Scope:
- Tenant Detail Page with all tabs (Overview, Users & Roles, Plan & Features, Billing, Usage, Notes)
- Plans Management UI
- Stripe integration (per-tenant billing + global billing) replacing all mock data
- Real Audit Logs backend + UI filters

Success criteria:
- All admin routes gated to superuser; data loads from real APIs/DB
- Plan changes and trials flow through Stripe; audit logs written for every admin action
- Tenant detail tabs fully navigable and functional (CRUD where defined)

### Phase 2 — Visibility & Control
Scope:
- Usage & Limits views (tenant + global) with percent-of-limit visuals and upgrade prompts
- Enhanced System Settings tabs (Auth0, Stripe, Email/Notifications) with deep links and masking
- Enhanced Tenants List (filters for plan/status/date, MRR column, clickable to detail)

Success criteria:
- Usage data sourced from real metrics; limits shown vs plan
- Settings surfaces live config readouts with test actions (Auth0 connectivity, Stripe webhook test, email test)
- Tenant list filtering and navigation improve admin workflow

### Phase 3 — Polish & Analytics
Scope:
- CSV exports (tenants, audit logs, billing tables, usage tables)
- Advanced filtering/search across tables (e.g., action-type presets, dunning filters)
- Historical usage charts/graphs (optional if data available)

Success criteria:
- Exports respect active filters
- Tables support richer search without regressions to perf
- Charts accurately reflect stored history where present

---

## 10. Integration Points

### Existing Systems to Leverage

- **Feature Matrix System:** Already implemented at `/admin/entitlements/matrix` - use for plan features display
- **Tenant Overrides System:** Already implemented at `/admin/entitlements/overrides` - link from tenant detail Plan & Features tab
- **Entitlements Service:** Backend service for calculating effective entitlements - use for usage limits
- **Stripe Service:** Backend service for Stripe API calls - extend for admin billing actions
- **Auth0 Service:** Backend service for Auth0 API calls - extend for user management actions

### External Services

- **Stripe API:** For subscription management, invoices, payment methods, webhooks
- **Auth0 API:** For user management, session revocation, user lookups
- **Database:** Supabase/Postgres for tenant, user, plan, audit log storage

---

This spec should be implemented as the **Admin / Superuser** area within N8N Ops, leveraging the existing routing, layout, and RBAC patterns already in the app.
