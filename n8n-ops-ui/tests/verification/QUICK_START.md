# Quick Start Guide - Entitlement Enforcement Verification

**⏱️ Estimated Time:** 10-15 minutes

## Prerequisites (5 minutes)

### 1. Start Backend Server
```bash
cd F:\web\AllThings\_projects\n8n-ops-trees\main\n8n-ops-backend
python -m app.main
```

### 2. Start Frontend (Optional)
```bash
cd F:\web\AllThings\_projects\n8n-ops-trees\main\n8n-ops-ui
npm run dev
```

### 3. Configure Test Environment
Create `.env.test` in the UI project root:

```env
API_BASE_URL=http://localhost:8000
BASE_URL=http://localhost:3000
TEST_TENANT_EMAIL=your-test-tenant@example.com
TEST_AUTH_TOKEN=your_auth_token_here
```

**Getting TEST_AUTH_TOKEN:**
1. Log in to your app at http://localhost:3000
2. Open browser DevTools → Application/Storage → Local Storage
3. Find `auth_token` or similar key
4. Copy the value

## Running Tests (5 minutes)

### Option 1: Automated Script (Recommended)
```bash
# Windows
cd F:\web\AllThings\_projects\n8n-ops-trees\main\n8n-ops-ui
tests\verification\run-verification.bat

# Linux/Mac
./tests/verification/run-verification.sh
```

### Option 2: Manual Execution
```bash
# All tests
npx playwright test tests/verification

# With visual UI
npx playwright test tests/verification --ui

# Specific suite only
npx playwright test tests/verification -g "Environment"
```

## Interpreting Results (2 minutes)

### Success ✅
```
✓ should enforce Free plan environment limit (1 environment)
✓ should allow Pro plan to create up to 3 environments
✓ should enforce team member limits based on plan
✓ should handle plan downgrade with grace periods
...
All tests passed!
```

### Partial Success with Warnings ⚠️
```
✓ Tests passing...
⚠ No active grace periods found (tenant may not have downgraded recently)
⚠ Audit logs endpoint not accessible (may require admin role)
```
**→ This is OK!** Warnings are expected and documented.

### Failure ❌
```
✗ should enforce Free plan environment limit (1 environment)
   Expected status: 403
   Received status: 201
```
**→ Fix needed!** See troubleshooting below.

## Common Issues & Quick Fixes

| Issue | Fix |
|-------|-----|
| "Backend not responding" | Start backend: `python -m app.main` |
| "Authentication required" | Update `TEST_AUTH_TOKEN` in `.env.test` |
| "Tenant at limit already" | Delete test environments or use fresh tenant |
| Tests timing out | Increase timeout in `playwright.config.ts` |

## Quick Validation Checklist

Before running tests, verify:

- [ ] Backend server running (check http://localhost:8000/health)
- [ ] `.env.test` file created with valid credentials
- [ ] Test tenant exists in database
- [ ] Playwright installed (`npm install`)

## After Testing

### If All Tests Pass ✅
1. Save test report: `npx playwright test tests/verification --reporter=html`
2. Document results in VERIFICATION_SUMMARY.md
3. Proceed to Task T016 (delete verification tests)

### If Tests Fail ❌
1. Check backend logs for errors
2. Verify database state (grace periods, limits)
3. Run with UI mode: `npx playwright test tests/verification --ui`
4. Review error details in test output
5. Fix implementation issues
6. Re-run tests

## Need Help?

- **Detailed docs**: Read `README.md` in this directory
- **Full summary**: See `VERIFICATION_SUMMARY.md`
- **Test code**: Review `test_entitlement_enforcement.spec.ts`

## Test Coverage Summary

| Feature | Test Suite | Status |
|---------|------------|--------|
| Environment Limits | "Environment Limit Enforcement" | ✅ Ready |
| Team Member Limits | "Team Member Limit Enforcement" | ✅ Ready |
| Downgrade & Grace | "Downgrade Behavior & Grace Periods" | ✅ Ready |
| Webhook Locking | "Webhook Locking & Idempotency" | ✅ Ready |
| Retention Policy | "Retention Policy Enforcement" | ✅ Ready |
| API Bypass Prevention | "API Direct Access Prevention" | ✅ Ready |
| Integration | "Comprehensive Integration Test" | ✅ Ready |

---

**Ready to test?** Run: `tests\verification\run-verification.bat`
