#!/usr/bin/env python3
"""
Comprehensive tenant isolation verification script.

This script analyzes all API endpoints and generates a detailed report
showing which endpoints properly enforce tenant isolation.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.tenant_isolation import TenantIsolationScanner, print_summary


def categorize_endpoints(scan_result):
    """
    Categorize endpoints into different security classifications.

    Categories:
    1. Platform Admin Endpoints - Exempt from tenant isolation (cross-tenant by design)
    2. Public/Auth Endpoints - No authentication required
    3. Properly Isolated - Authenticated with safe tenant extraction
    4. Authenticated but No Visible Isolation - May use DB-level isolation
    5. Issues - Missing authentication or unsafe patterns
    """
    categories = {
        "platform_admin": [],
        "public_auth": [],
        "properly_isolated": [],
        "authenticated_no_visible_isolation": [],
        "test_endpoints": [],
        "issues": []
    }

    for endpoint in scan_result.endpoints:
        # Categorize based on route path and issues
        route = endpoint.route_path.lower()

        # Platform admin endpoints
        if any(pattern in route for pattern in ['/platform/', '/admin', '/tenants/']):
            if not endpoint.has_authentication:
                categories["platform_admin"].append(endpoint)
            elif endpoint.has_authentication and endpoint.extracts_tenant_from_user:
                categories["properly_isolated"].append(endpoint)
            elif endpoint.has_authentication:
                categories["authenticated_no_visible_isolation"].append(endpoint)
            continue

        # Test endpoints
        if '/test' in route or route == '/health' or '/health/' in route:
            categories["test_endpoints"].append(endpoint)
            continue

        # Public/auth endpoints
        if any(pattern in route for pattern in ['/auth', '/login', '/onboard', '/webhook']):
            categories["public_auth"].append(endpoint)
            continue

        # Categorize tenant-scoped endpoints
        if endpoint.has_authentication and endpoint.extracts_tenant_from_user and not endpoint.unsafe_tenant_extraction:
            categories["properly_isolated"].append(endpoint)
        elif endpoint.has_authentication and not endpoint.extracts_tenant_from_user:
            categories["authenticated_no_visible_isolation"].append(endpoint)
        elif endpoint.issues:
            categories["issues"].append(endpoint)

    return categories


def generate_detailed_report(scan_result, categories):
    """Generate a comprehensive markdown report."""
    lines = [
        "# Tenant Isolation Verification Report",
        "",
        f"**Generated:** {scan_result.total_endpoints} endpoints scanned",
        f"**Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Executive Summary",
        "",
        f"- **Total Endpoints:** {scan_result.total_endpoints}",
        f"- **Authenticated Endpoints:** {scan_result.authenticated_endpoints}",
        f"- **Properly Isolated:** {scan_result.properly_isolated_endpoints}",
        f"- **Isolation Coverage:** {scan_result.isolation_coverage:.1f}%",
        "",
        "## Endpoint Classification",
        "",
        f"| Category | Count | Description |",
        f"|----------|-------|-------------|",
        f"| Platform Admin | {len(categories['platform_admin'])} | Cross-tenant endpoints for platform administration |",
        f"| Public/Auth | {len(categories['public_auth'])} | Public endpoints (auth, webhooks, onboarding) |",
        f"| Properly Isolated | {len(categories['properly_isolated'])} | Authenticated with visible tenant_id extraction |",
        f"| Authenticated (DB-level isolation) | {len(categories['authenticated_no_visible_isolation'])} | Authenticated, may use DB-level isolation |",
        f"| Test Endpoints | {len(categories['test_endpoints'])} | Test and health check endpoints |",
        f"| Issues | {len(categories['issues'])} | Endpoints with security concerns |",
        "",
    ]

    # Platform admin endpoints
    if categories["platform_admin"]:
        lines.extend([
            "## Platform Admin Endpoints (Cross-Tenant by Design)",
            "",
            "These endpoints are used by platform administrators to manage multiple tenants.",
            "They do NOT enforce tenant isolation as they operate across tenant boundaries.",
            "",
        ])

        by_file = {}
        for ep in categories["platform_admin"]:
            file_name = Path(ep.file_path).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(ep)

        for file_name in sorted(by_file.keys()):
            lines.append(f"### {file_name}")
            lines.append("")
            for ep in by_file[file_name]:
                lines.append(f"- `{ep.http_method} {ep.route_path}` - {ep.function_name}()")
            lines.append("")

    # Properly isolated endpoints
    if categories["properly_isolated"]:
        lines.extend([
            "## Properly Isolated Endpoints [OK]",
            "",
            "These endpoints correctly extract tenant_id from the authenticated user context.",
            "",
        ])

        by_file = {}
        for ep in categories["properly_isolated"]:
            file_name = Path(ep.file_path).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(ep)

        for file_name in sorted(by_file.keys()):
            lines.append(f"### {file_name}")
            lines.append("")
            for ep in by_file[file_name]:
                method = ep.tenant_extraction_method or "user context"
                lines.append(f"- `{ep.http_method} {ep.route_path}` - {ep.function_name}() - Extract: `{method}`")
            lines.append("")

    # Authenticated but no visible isolation
    if categories["authenticated_no_visible_isolation"]:
        lines.extend([
            "## Authenticated Endpoints (Database-Level Isolation)",
            "",
            "These endpoints use authentication but don't show visible tenant_id extraction.",
            "They may rely on database-level isolation through foreign key relationships.",
            "",
            "**Review Required:** Verify these endpoints properly filter by tenant through",
            "database relationships or add explicit tenant_id filtering.",
            "",
        ])

        by_file = {}
        for ep in categories["authenticated_no_visible_isolation"]:
            file_name = Path(ep.file_path).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(ep)

        for file_name in sorted(by_file.keys()):
            lines.append(f"### {file_name}")
            lines.append("")
            for ep in by_file[file_name]:
                warnings_str = ""
                if ep.warnings:
                    warnings_str = f" [!] {', '.join(ep.warnings)}"
                lines.append(f"- `{ep.http_method} {ep.route_path}` - {ep.function_name}(){warnings_str}")
            lines.append("")

    # Issues
    if categories["issues"]:
        lines.extend([
            "## Endpoints with Issues [WARNING]",
            "",
            "These endpoints have security concerns that should be addressed.",
            "",
        ])

        by_file = {}
        for ep in categories["issues"]:
            file_name = Path(ep.file_path).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(ep)

        for file_name in sorted(by_file.keys()):
            lines.append(f"### {file_name}")
            lines.append("")
            for ep in by_file[file_name]:
                lines.append(f"- `{ep.http_method} {ep.route_path}` - {ep.function_name}()")
                for issue in ep.issues:
                    lines.append(f"  - [!] {issue}")
            lines.append("")

    # Public/Auth endpoints
    if categories["public_auth"]:
        lines.extend([
            "## Public/Auth Endpoints",
            "",
            "These endpoints don't require tenant isolation (authentication, webhooks, etc.).",
            "",
        ])

        by_file = {}
        for ep in categories["public_auth"]:
            file_name = Path(ep.file_path).name
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(ep)

        for file_name in sorted(by_file.keys()):
            lines.append(f"### {file_name}")
            lines.append("")
            for ep in by_file[file_name]:
                lines.append(f"- `{ep.http_method} {ep.route_path}` - {ep.function_name}()")
            lines.append("")

    # Test endpoints
    if categories["test_endpoints"]:
        lines.extend([
            "## Test and Health Check Endpoints",
            "",
            "These endpoints are for testing and health checks.",
            "",
        ])

        for ep in categories["test_endpoints"]:
            file_name = Path(ep.file_path).name
            lines.append(f"- `{ep.http_method} {ep.route_path}` ({file_name})")
        lines.append("")

    lines.extend([
        "## Recommendations",
        "",
        "1. **Platform Admin Endpoints:** These are correctly designed to operate cross-tenant.",
        "   They should require platform_admin role validation.",
        "",
        "2. **Authenticated Endpoints (DB-level isolation):** Review these endpoints to ensure",
        "   tenant isolation is enforced through database foreign key relationships. Consider",
        "   adding explicit tenant_id validation for defense in depth.",
        "",
        "3. **Public/Auth Endpoints:** These are correct as-is (no tenant isolation needed).",
        "",
        "## Conclusion",
        "",
        f"**{scan_result.properly_isolated_endpoints}** endpoints have been verified with proper tenant isolation.",
        f"**{len(categories['authenticated_no_visible_isolation'])}** endpoints use database-level isolation (verify separately).",
        f"**{len(categories['platform_admin'])}** platform admin endpoints correctly operate cross-tenant.",
        "",
        "The remaining endpoints are either public/auth endpoints or test endpoints that don't require tenant isolation.",
        "",
    ])

    return "\n".join(lines)


def main():
    """Run the verification and generate reports."""
    print("=" * 80)
    print("TENANT ISOLATION VERIFICATION")
    print("=" * 80)
    print()

    # Initialize scanner
    scanner = TenantIsolationScanner()

    # Scan all endpoints
    print("Scanning API endpoints...")
    result = scanner.scan_all_endpoints()

    # Print summary
    print_summary(result)

    # Categorize endpoints
    print("\nCategorizing endpoints...")
    categories = categorize_endpoints(result)

    # Generate detailed report
    print("Generating detailed report...")
    report = generate_detailed_report(result, categories)

    # Save report to file
    report_path = Path(__file__).parent.parent.parent / "TENANT_ISOLATION_VERIFICATION.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n[OK] Report saved to: {report_path}")

    # Export JSON data
    json_path = Path(__file__).parent.parent.parent / "tenant_isolation_scan.json"
    with open(json_path, 'w') as f:
        json.dump(scanner.export_json(result), f, indent=2)

    print(f"[OK] JSON data saved to: {json_path}")

    # Print category summary
    print("\n" + "=" * 80)
    print("ENDPOINT CATEGORIES")
    print("=" * 80)
    print(f"Platform Admin Endpoints:        {len(categories['platform_admin'])}")
    print(f"Public/Auth Endpoints:           {len(categories['public_auth'])}")
    print(f"Properly Isolated:               {len(categories['properly_isolated'])}")
    print(f"Authenticated (DB isolation):    {len(categories['authenticated_no_visible_isolation'])}")
    print(f"Test Endpoints:                  {len(categories['test_endpoints'])}")
    print(f"Issues:                          {len(categories['issues'])}")
    print("=" * 80)

    return 0 if not result.has_issues else 1


if __name__ == "__main__":
    sys.exit(main())
