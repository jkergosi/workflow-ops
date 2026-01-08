# Security Documentation

This directory contains security-related documentation for the n8n-ops platform.

## Documents

### Row-Level Security (RLS)
- **[RLS_POLICIES.md](RLS_POLICIES.md)** - Comprehensive documentation of all Supabase RLS policies (76 tables)
- **[RLS_VERIFICATION.md](RLS_VERIFICATION.md)** - SQL queries and procedures to verify RLS policies
- **[RLS_CHANGE_CHECKLIST.md](RLS_CHANGE_CHECKLIST.md)** - Checklist for adding/modifying RLS policies
- **[RLS_SUMMARY.md](RLS_SUMMARY.md)** - Executive summary and quick reference
- **[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)** - Documentation implementation report (2026-01-08)

### Security Audits & Tools
- **[SECURITY_AUDIT_RESULTS.md](SECURITY_AUDIT_RESULTS.md)** - Comprehensive tenant isolation audit results
- **[TENANT_ISOLATION_SCANNER.md](TENANT_ISOLATION_SCANNER.md)** - Documentation for the endpoint scanner tool

## Quick Links

### ⚡ New to RLS Documentation?
→ Start with **[QUICK_START.md](QUICK_START.md)** (5-minute overview)

### For Developers
- Adding a new table? → [RLS_CHANGE_CHECKLIST.md](RLS_CHANGE_CHECKLIST.md)
- Verifying RLS policies? → [RLS_VERIFICATION.md](RLS_VERIFICATION.md)
- Understanding current policies? → [RLS_POLICIES.md](RLS_POLICIES.md)

### For Security Review
- Tenant isolation verification → [SECURITY_AUDIT_RESULTS.md](SECURITY_AUDIT_RESULTS.md)
- RLS policy inventory → [RLS_POLICIES.md](RLS_POLICIES.md)
- Endpoint security patterns → [TENANT_ISOLATION_SCANNER.md](TENANT_ISOLATION_SCANNER.md)

## Security Context

### Backend Architecture
- **Backend**: Uses Supabase `SERVICE_KEY` which **bypasses RLS**
- **Frontend**: Uses Supabase `ANON_KEY` which **enforces RLS** (when implemented)
- **Direct Supabase Access**: Any direct database access via ANON_KEY will be subject to RLS

### Tenant Isolation Strategy
The platform enforces tenant isolation at multiple layers:

1. **Application Layer** (Primary): Backend extracts `tenant_id` from JWT and filters all queries
2. **RLS Layer** (Secondary): Supabase RLS protects against direct database access
3. **Audit Layer**: All write operations logged with tenant context

### Current Status
As of 2026-01-08:
- ✅ Application-layer tenant isolation: **100% coverage** (330 endpoints verified)
- ⚠️ RLS coverage: **12 of 76 tables** have RLS enabled
- ✅ Audit logging: **Comprehensive with impersonation tracking**

See [RLS_POLICIES.md](RLS_POLICIES.md) for detailed gap analysis and recommendations.

## Related Documentation

### Project Root
- [`/mvp_readiness_pack/05_multitenancy_security_impersonation.md`](../../../mvp_readiness_pack/05_multitenancy_security_impersonation.md) - Security architecture overview
- [`/mvp_readiness_pack/08_database_schema_relevant.md`](../../../mvp_readiness_pack/08_database_schema_relevant.md) - Database schema documentation

### Backend Docs
- [`/n8n-ops-backend/CLAUDE.md`](../../CLAUDE.md) - Technical architecture reference

