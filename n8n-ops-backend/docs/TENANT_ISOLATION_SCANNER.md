# Tenant Isolation Scanner

## Overview

The Tenant Isolation Scanner is a security verification utility that scans all API endpoints to ensure proper tenant isolation and prevent cross-tenant data leakage. It automatically detects endpoints that may have security issues related to tenant_id enforcement.

## Features

- **Automatic Endpoint Discovery**: Scans all Python files in `app/api/endpoints/` to find FastAPI route handlers
- **Authentication Verification**: Checks that endpoints use `get_current_user` dependency
- **Tenant Extraction Detection**: Verifies that `tenant_id` is extracted from authenticated user context (not request parameters)
- **Unsafe Pattern Detection**: Identifies endpoints that extract `tenant_id` from request params/body (security risk)
- **Comprehensive Reporting**: Generates detailed reports with issues, warnings, and statistics
- **JSON Export**: Export scan results for integration with CI/CD pipelines

## Quick Start

### Run a Quick Scan

```bash
cd n8n-ops-backend
python scan_tenant_isolation.py
```

Output:
```
============================================================
TENANT ISOLATION SCAN SUMMARY
============================================================
Total Endpoints: 330
Authenticated: 190
Properly Isolated: 159
Issues: 120
Warnings: 24
Coverage: 83.7%

[!] SECURITY ISSUES FOUND - Run full report for details
============================================================
```

### View Full Report

```bash
python scan_tenant_isolation.py --full
```

### Export to JSON

```bash
python scan_tenant_isolation.py --json report.json
```

### Show Only Issues

```bash
python scan_tenant_isolation.py --issues-only
```

## Using in Python Code

### Basic Scan

```python
from app.core.tenant_isolation import TenantIsolationScanner, print_summary

# Create scanner
scanner = TenantIsolationScanner()

# Scan all endpoints
result = scanner.scan_all_endpoints()

# Print summary
print_summary(result)
```

### Generate Report

```python
# Generate human-readable report
report = scanner.generate_report(result, verbose=True)
print(report)
```

### Export to JSON

```python
import json

# Export to JSON
json_data = scanner.export_json(result)

with open('scan_results.json', 'w') as f:
    json.dump(json_data, f, indent=2)
```

### Quick Verification

```python
from app.core.tenant_isolation import verify_all_endpoints

# Get list of all issues
issues = await verify_all_endpoints()

if issues:
    print(f"Found {len(issues)} tenant isolation issues")
    for issue in issues:
        print(f"  - {issue['endpoint']}: {issue['issue']}")
```

## Security Patterns

### ✅ Safe Pattern (Recommended)

Extract `tenant_id` from authenticated user context:

```python
@router.get("/workflows")
async def get_workflows(
    user_info: dict = Depends(get_current_user)
):
    tenant_id = get_tenant_id(user_info)  # ✅ Safe: from auth context
    workflows = await db_service.get_workflows(tenant_id)
    return workflows
```

### ❌ Unsafe Pattern (Security Risk)

Extract `tenant_id` from request parameters:

```python
@router.get("/workflows")
async def get_workflows(
    tenant_id: str,  # ❌ UNSAFE: tenant_id from request param
    user_info: dict = Depends(get_current_user)
):
    # Security risk: caller can specify any tenant_id
    workflows = await db_service.get_workflows(tenant_id)
    return workflows
```

### ⚠️ No Authentication

Endpoint without authentication dependency:

```python
@router.get("/public-data")
async def get_public_data():  # ⚠️ No authentication
    # Missing: user_info: dict = Depends(get_current_user)
    return {"data": "public"}
```

## Understanding Scan Results

### Endpoint Status Indicators

- **[+] Authenticated**: Endpoint has `get_current_user` dependency
- **[-] Not authenticated**: Missing authentication dependency
- **[+] Safe tenant extraction**: Uses `get_tenant_id(user_info)` or similar safe pattern
- **[-] Unsafe tenant extraction**: Extracts `tenant_id` from request params/body

### Issue Types

1. **No authentication dependency**: Endpoint doesn't use `get_current_user`
2. **Unsafe tenant extraction**: `tenant_id` extracted from request instead of user context
3. **Write operation without tenant extraction**: POST/PUT/PATCH/DELETE on tenant-scoped resource without visible `tenant_id` extraction

### Warnings

- **Exempt endpoint**: Public/auth/platform admin endpoints that don't require tenant isolation
- **Tenant-scoped resource without visible extraction**: Authenticated endpoint on tenant-scoped resource that doesn't show explicit `get_tenant_id()` call (may still be safe)

## Exempt Endpoints

The following endpoint patterns are exempt from tenant isolation requirements:

- `/health` - Health check endpoints
- `/auth` - Authentication endpoints
- `/login` - Login endpoints
- `/register` - Registration endpoints
- `/onboard` - Onboarding endpoints
- `/platform/admin` - Platform admin endpoints (cross-tenant by design)
- `/platform/impersonation` - Impersonation management
- `/platform/console` - Platform console
- `/test` - Test endpoints

## Detection Patterns

### Safe Tenant Extraction Patterns

The scanner detects these safe patterns:

```python
# Pattern 1: Using helper function
tenant_id = get_tenant_id(user_info)

# Pattern 2: Direct access
tenant_id = user_info["tenant"]["id"]

# Pattern 3: Using .get()
tenant = user_info.get("tenant")
tenant_id = tenant.get("id")
```

### Unsafe Tenant Extraction Patterns

The scanner flags these unsafe patterns:

```python
# Pattern 1: Path/query parameter
async def endpoint(tenant_id: str = ...):

# Pattern 2: From request object
tenant_id = request.query_params.get("tenant_id")

# Pattern 3: From request body
tenant_id = body.tenant_id
```

## CI/CD Integration

### Exit Codes

- **0**: No issues found
- **1**: Security issues found

### Example GitHub Action

```yaml
name: Tenant Isolation Check

on: [push, pull_request]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd n8n-ops-backend
          pip install -r requirements.txt
      - name: Run tenant isolation scan
        run: |
          cd n8n-ops-backend
          python scan_tenant_isolation.py --json scan_results.json
      - name: Upload scan results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: tenant-isolation-report
          path: n8n-ops-backend/scan_results.json
```

## Advanced Usage

### Custom Endpoints Directory

```python
scanner = TenantIsolationScanner(endpoints_dir="/custom/path/to/endpoints")
result = scanner.scan_all_endpoints()
```

### Filter Results

```python
# Get only endpoints with issues
endpoints_with_issues = [
    e for e in result.endpoints if e.issues
]

# Get only write operations with issues
write_ops_with_issues = [
    e for e in result.endpoints
    if e.http_method in ['POST', 'PUT', 'PATCH', 'DELETE'] and e.issues
]

# Get endpoints by file
from pathlib import Path
workflows_endpoints = [
    e for e in result.endpoints
    if Path(e.file_path).name == 'workflows.py'
]
```

### Access Individual Endpoint Details

```python
for endpoint in result.endpoints:
    print(f"Endpoint: {endpoint.http_method} {endpoint.route_path}")
    print(f"  File: {endpoint.file_path}")
    print(f"  Function: {endpoint.function_name} (line {endpoint.line_number})")
    print(f"  Authenticated: {endpoint.has_authentication}")
    print(f"  Safe Extraction: {endpoint.extracts_tenant_from_user}")
    print(f"  Unsafe Extraction: {endpoint.unsafe_tenant_extraction}")

    if endpoint.tenant_extraction_method:
        print(f"  Method: {endpoint.tenant_extraction_method}")

    if endpoint.issues:
        print(f"  Issues: {endpoint.issues}")

    if endpoint.warnings:
        print(f"  Warnings: {endpoint.warnings}")
```

## Architecture

### Components

1. **TenantIsolationScanner**: Main scanner class that orchestrates the scan
2. **EndpointInfo**: Data class holding information about each endpoint
3. **ScanResult**: Data class with scan statistics and results
4. **Pattern Matchers**: Regex patterns to detect safe/unsafe tenant extraction

### Scanning Process

1. **Discovery**: Find all `.py` files in `app/api/endpoints/`
2. **Parsing**: Use Python AST to parse each file
3. **Detection**: Find functions with `@router.{method}` decorators
4. **Analysis**: Check each endpoint for:
   - Authentication dependency
   - Tenant extraction patterns
   - Unsafe patterns
   - Tenant-scoped resource indicators
5. **Reporting**: Generate statistics and detailed reports

### AST-Based Analysis

The scanner uses Python's Abstract Syntax Tree (AST) module to:
- Parse Python source files without executing them
- Find async and sync function definitions
- Analyze decorators to detect route handlers
- Extract function signatures and parameters
- Search function bodies for tenant extraction patterns

## Limitations

1. **Static Analysis**: Cannot detect tenant isolation in dynamically called functions
2. **Pattern Matching**: May miss tenant extraction if using non-standard patterns
3. **False Positives**: May flag platform admin endpoints that intentionally operate cross-tenant
4. **No Runtime Analysis**: Cannot verify actual database queries or API calls

## Best Practices

1. **Always extract tenant_id from user context**: Never accept it as a request parameter
2. **Use the helper function**: Prefer `get_tenant_id(user_info)` for consistency
3. **Require authentication**: All tenant-scoped endpoints should use `Depends(get_current_user)`
4. **Document exemptions**: Add comments for legitimate platform admin endpoints
5. **Run regularly**: Include the scanner in your CI/CD pipeline
6. **Review warnings**: Investigate endpoints with warnings to ensure they're safe

## Troubleshooting

### Scanner finds 0 endpoints

- Check that the endpoints directory path is correct
- Verify that endpoint files use `@router.{method}` decorators
- Ensure Python files are valid syntax (scanner skips files with syntax errors)

### False positives on platform admin endpoints

- Platform admin endpoints (`/platform/admin/*`) are automatically exempted
- Add custom exempt patterns if needed by modifying `EXEMPT_PATTERNS` in the scanner

### Missing tenant extraction detection

- Ensure you're using one of the standard patterns (see Detection Patterns section)
- If using a custom pattern, add it to `SAFE_TENANT_PATTERNS` in the scanner

## Contributing

To improve the scanner:

1. Add new safe patterns to `SAFE_TENANT_PATTERNS`
2. Add new unsafe patterns to `UNSAFE_TENANT_PATTERNS`
3. Update exempt patterns in `EXEMPT_PATTERNS`
4. Improve AST analysis in `_analyze_function()`

## Related Documentation

- [Impersonation Audit Trail](./IMPERSONATION_AUDIT.md) (if exists)
- [Security Best Practices](./SECURITY.md) (if exists)
- [Authentication Service](../app/services/auth_service.py)
- [Audit Middleware](../app/services/audit_middleware.py)

## License

Part of the n8n-ops platform. See main project LICENSE file.
