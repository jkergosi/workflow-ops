# Entitlement Enforcement Verification Tests

This directory contains verification tests for the server-side entitlement enforcement feature implementation.

## Purpose

These tests verify that the following features are working correctly:

1. **Environment Limit Enforcement**
   - Free plan: 1 environment maximum
   - Pro plan: 3 environments maximum
   - Prevents creation via direct API calls

2. **Team Member Limit Enforcement**
   - Server-side validation of team member limits
   - Prevents bypassing through API

3. **Downgrade Handling**
   - Grace period creation when downgrading
   - Proper tracking in `downgrade_grace_periods` table
   - Grace period actions (read-only, disable, delete)

4. **Webhook Locking**
   - Prevents race conditions from concurrent Stripe webhooks
   - Uses PostgreSQL advisory locks
   - Ensures idempotent webhook processing

5. **Retention Policy Enforcement**
   - Execution retention based on plan (7 days Free, 30 days Pro)
   - Audit log retention based on plan
   - Automated cleanup via scheduled jobs

## Prerequisites

### Backend Requirements

- Backend server running at `http://localhost:8000`
- Test tenant created with known credentials
- Database with entitlement tables populated

### Environment Variables

Create a `.env.test` file in the project root with:

```env
# API Configuration
API_BASE_URL=http://localhost:8000
BASE_URL=http://localhost:3000

# Test Credentials
TEST_TENANT_EMAIL=test-enforcement@example.com
TEST_AUTH_TOKEN=your_test_auth_token_here

# Optional: Override for specific tests
TEST_TENANT_ID=tenant_id_here
```

### Test Tenant Setup

1. Create a test tenant in your database
2. Obtain an authentication token for the tenant
3. Ensure the tenant has a subscription (Free or Pro)
4. Set up test data (optional environments, team members)

## Running the Tests

### Run All Verification Tests

```bash
# Using Playwright Test Runner
npx playwright test tests/verification

# With UI mode for debugging
npx playwright test tests/verification --ui

# With headed browser (see what's happening)
npx playwright test tests/verification --headed
```

### Run Specific Test Suites

```bash
# Environment limit tests only
npx playwright test tests/verification -g "Environment Limit"

# Team member tests only
npx playwright test tests/verification -g "Team Member"

# Downgrade tests only
npx playwright test tests/verification -g "Downgrade"

# Webhook tests only
npx playwright test tests/verification -g "Webhook"

# Retention tests only
npx playwright test tests/verification -g "Retention"
```

### Run with Detailed Output

```bash
# Show console logs and detailed output
npx playwright test tests/verification --reporter=list

# Generate HTML report
npx playwright test tests/verification --reporter=html
```

## Test Scenarios

### 1. Environment Limit Enforcement

**Free Plan (1 environment):**
- ✅ Can create 1st environment
- ❌ Cannot create 2nd environment (403 Forbidden)
- ✅ Error message includes current count and limit

**Pro Plan (3 environments):**
- ✅ Can create up to 3 environments
- ❌ Cannot create 4th environment (403 Forbidden)
- ✅ Concurrent requests all properly rejected

### 2. Team Member Limit Enforcement

**Free Plan (1 user):**
- ❌ Cannot invite additional team members
- ✅ Error message explains limit

**Pro Plan (10 users):**
- ✅ Can invite up to 10 team members
- ❌ Cannot invite 11th member

### 3. Downgrade Grace Period Handling

**Scenario: Pro → Free Downgrade with 3 environments:**
- ✅ 2 environments enter grace period (30 days)
- ✅ Grace period records created in database
- ✅ Grace period status visible to user
- ✅ After expiry, appropriate action taken (read-only/delete)

### 4. Webhook Race Condition Prevention

**Scenario: Concurrent Stripe webhooks:**
- ✅ Only one webhook processes at a time
- ✅ No duplicate subscription updates
- ✅ Locks are automatically released
- ✅ Subscription state remains consistent

### 5. Retention Policy Enforcement

**Execution Retention:**
- ✅ Free plan: No executions older than 7 days
- ✅ Pro plan: No executions older than 30 days
- ✅ Cleanup happens automatically via scheduled job

**Audit Log Retention:**
- ✅ Logs cleaned up per plan retention policy
- ✅ Critical logs preserved

## Interpreting Results

### Success Criteria

All tests should pass with green checkmarks (✓). Key validations:

1. **403 Forbidden** responses when limits are exceeded
2. **Error details** include limit information
3. **Grace periods** created with correct expiry dates
4. **No race conditions** in concurrent webhook processing
5. **Retention policies** enforced (no old data beyond retention period)

### Expected Warnings

Some tests may show warnings (⚠) which are acceptable:

- `⚠ No active grace periods found` - Normal if no recent downgrades
- `⚠ Audit logs endpoint not accessible` - Normal for non-admin users
- `⚠ Webhook lock status endpoint not available` - May be admin-only

### Debugging Failed Tests

If tests fail:

1. **Check Backend Logs**: Look for enforcement-related errors
2. **Verify Database State**: Check `downgrade_grace_periods`, `environments`, `users` tables
3. **Review API Responses**: Check error messages and status codes
4. **Run Tests in UI Mode**: `npx playwright test --ui` for step-by-step debugging
5. **Check Test Data**: Ensure test tenant exists and has correct plan

## After Verification

Once all tests pass and the feature is confirmed working:

1. **Document Results**: Save test report for records
2. **Delete Verification Tests**: As specified in T016
3. **Keep Core E2E Tests**: Regular environment/team tests should remain

## Cleanup

To remove verification tests after successful verification:

```bash
# Delete the verification test file
rm tests/verification/test_entitlement_enforcement.spec.ts

# Delete this README
rm tests/verification/README.md

# Remove verification directory if empty
rmdir tests/verification
```

## Troubleshooting

### "API health check failed"

- Ensure backend is running: `cd ../n8n-ops-backend && python -m app.main`
- Check API URL in `.env.test`

### "Authentication required"

- Generate a valid test token
- Update `TEST_AUTH_TOKEN` in `.env.test`
- Verify token hasn't expired

### "Tenant not found"

- Create test tenant in database
- Update `TEST_TENANT_EMAIL` in `.env.test`

### "Webhook lock timeout"

- Check PostgreSQL advisory lock functions exist
- Verify database connection is healthy
- Look for stuck locks: `SELECT * FROM pg_locks WHERE locktype = 'advisory';`

## Related Files

- `app/services/downgrade_service.py` - Downgrade handling logic
- `app/services/webhook_lock_service.py` - Webhook locking implementation
- `app/api/endpoints/environments.py` - Environment limit enforcement
- `app/api/endpoints/teams.py` - Team member limit enforcement
- `app/api/endpoints/billing.py` - Webhook handlers with locking
- `app/core/entitlements_gate.py` - Entitlement decorators
- `app/services/retention_enforcement_service.py` - Retention policy enforcement

## Support

For issues or questions about these tests, refer to:
- Implementation Plan: `T014` specification
- Feature Documentation: Server-Side Entitlement Enforcement spec
