"""Tenant isolation verification utility with endpoint scanner.

This module provides utilities to scan and verify tenant isolation patterns
across all API endpoints to ensure proper tenant_id enforcement and prevent
cross-tenant data leakage.

Key Features:
- Scans all API endpoint files for route handlers
- Verifies tenant_id is extracted from authenticated user context
- Detects unsafe patterns (tenant_id from request params/body)
- Checks for proper authentication dependencies
- Generates comprehensive security verification reports

Usage:
    from app.core.tenant_isolation import TenantIsolationScanner, verify_all_endpoints

    # Scan all endpoints
    scanner = TenantIsolationScanner()
    results = await scanner.scan_all_endpoints()

    # Generate report
    report = scanner.generate_report(results)
    print(report)

    # Quick verification
    issues = await verify_all_endpoints()
    if issues:
        print(f"Found {len(issues)} tenant isolation issues")
"""
import ast
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    """Information about an API endpoint."""
    file_path: str
    function_name: str
    http_method: str
    route_path: str
    line_number: int
    has_authentication: bool = False
    extracts_tenant_from_user: bool = False
    unsafe_tenant_extraction: bool = False
    tenant_extraction_method: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Results from scanning all endpoints."""
    total_endpoints: int = 0
    authenticated_endpoints: int = 0
    properly_isolated_endpoints: int = 0
    endpoints_with_issues: int = 0
    endpoints_with_warnings: int = 0
    endpoints: List[EndpointInfo] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return self.endpoints_with_issues > 0

    @property
    def isolation_coverage(self) -> float:
        """Calculate percentage of authenticated endpoints with proper isolation."""
        if self.authenticated_endpoints == 0:
            return 0.0
        return (self.properly_isolated_endpoints / self.authenticated_endpoints) * 100


class TenantIsolationScanner:
    """Scanner to verify tenant isolation patterns across API endpoints."""

    # Safe patterns for extracting tenant_id from user context
    SAFE_TENANT_PATTERNS = [
        r'get_tenant_id\s*\(\s*user_info\s*\)',
        r'user_info\s*\.\s*get\s*\(\s*["\']tenant["\']\s*\)',
        r'user_context\s*\.\s*get\s*\(\s*["\']tenant["\']\s*\)',
        r'tenant\s*=\s*user_info\s*\.\s*get\s*\(\s*["\']tenant["\']\s*\)',
        r'tenant_id\s*=\s*get_tenant_id\s*\(',
        r'tenant_id\s*=\s*user_info\[["\'"]tenant["\'"]]\[["\'"]id["\'"]',
        r'tenant_id\s*=\s*user_context\[["\'"]tenant["\'"]]\[["\'"]id["\'"]',
    ]

    # Unsafe patterns that extract tenant_id from request params/body
    UNSAFE_TENANT_PATTERNS = [
        r'tenant_id\s*:\s*str\s*=',  # tenant_id as path/query parameter
        r'tenant_id\s*=\s*request\.',  # tenant_id from request object
        r'tenant_id\s*=\s*body\.',  # tenant_id from request body
        r'tenant_id\s*in\s*\[.*\]',  # tenant_id in parameter list (path/query)
    ]

    # Authentication dependency patterns
    AUTH_DEPENDENCY_PATTERNS = [
        r'Depends\s*\(\s*get_current_user\s*\)',
        r'Depends\s*\(\s*get_current_user_optional\s*\)',
        r'user_info\s*:\s*dict\s*=\s*Depends\s*\(\s*get_current_user',
        r'user_context\s*:\s*dict\s*=\s*Depends\s*\(\s*get_current_user',
        r'Depends\s*\(\s*require_platform_admin\s*\(',  # Platform admin authentication
        r'Depends\s*\(\s*require_entitlement\s*\(',     # Entitlement gates include auth
    ]

    # HTTP methods that indicate route handlers
    HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    # Endpoints that don't require tenant isolation (public/auth endpoints)
    EXEMPT_PATTERNS = [
        r'/health',
        r'/auth',
        r'/login',
        r'/register',
        r'/onboard',
        r'/platform/admin',  # Platform admin endpoints operate cross-tenant
        r'/platform/impersonation',  # Impersonation management
        r'/platform/console',  # Platform console
        r'/test',  # Test endpoints
    ]

    def __init__(self, endpoints_dir: Optional[str] = None):
        """
        Initialize the scanner.

        Args:
            endpoints_dir: Directory containing endpoint files.
                          Defaults to app/api/endpoints relative to project root.
        """
        if endpoints_dir is None:
            # Find project root and construct default path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent  # Go up to project root
            endpoints_dir = project_root / "app" / "api" / "endpoints"

        self.endpoints_dir = Path(endpoints_dir)
        if not self.endpoints_dir.exists():
            raise ValueError(f"Endpoints directory not found: {self.endpoints_dir}")

    def _is_exempt_endpoint(self, route_path: str) -> bool:
        """Check if an endpoint is exempt from tenant isolation requirements."""
        return any(re.search(pattern, route_path) for pattern in self.EXEMPT_PATTERNS)

    def _extract_route_info(self, decorator_line: str) -> Optional[Tuple[str, str]]:
        """
        Extract HTTP method and route path from a decorator line.

        Args:
            decorator_line: The decorator line (e.g., @router.get("/workflows"))

        Returns:
            Tuple of (http_method, route_path) or None if not a route decorator
        """
        for method in self.HTTP_METHODS:
            # Match both quoted strings and empty decorators like @router.get()
            pattern = rf'@router\.{method}\s*\(\s*(?:["\']([^"\']*)["\']|)'
            match = re.search(pattern, decorator_line)
            if match:
                route = match.group(1) if match.group(1) is not None else ""
                return method.upper(), route
        return None

    def _check_authentication(self, function_def: str) -> bool:
        """Check if function has authentication dependency."""
        return any(
            re.search(pattern, function_def)
            for pattern in self.AUTH_DEPENDENCY_PATTERNS
        )

    def _check_safe_tenant_extraction(self, function_body: str) -> Tuple[bool, Optional[str]]:
        """
        Check if function safely extracts tenant_id from user context.

        Returns:
            Tuple of (has_safe_extraction, extraction_method)
        """
        for pattern in self.SAFE_TENANT_PATTERNS:
            match = re.search(pattern, function_body)
            if match:
                return True, match.group(0)
        return False, None

    def _check_unsafe_tenant_extraction(self, function_def: str) -> bool:
        """Check if function has unsafe tenant_id extraction patterns."""
        return any(
            re.search(pattern, function_def)
            for pattern in self.UNSAFE_TENANT_PATTERNS
        )

    def _analyze_function(
        self,
        file_path: str,
        function_node,  # Union[ast.FunctionDef, ast.AsyncFunctionDef]
        source_lines: List[str]
    ) -> Optional[EndpointInfo]:
        """
        Analyze a function to determine if it's an endpoint and verify tenant isolation.

        Args:
            file_path: Path to the source file
            function_node: AST node for the function
            source_lines: Source code lines

        Returns:
            EndpointInfo if function is an endpoint, None otherwise
        """
        # Check if function has a router decorator
        route_info = None
        for decorator in function_node.decorator_list:
            # Use ast.unparse if available (Python 3.9+), otherwise reconstruct
            if hasattr(ast, 'unparse'):
                decorator_line = f"@{ast.unparse(decorator)}"
            else:
                # Fallback: get source segment
                decorator_line = ast.get_source_segment(
                    '\n'.join(source_lines), decorator
                ) or ''
                if not decorator_line.startswith('@'):
                    decorator_line = f"@{decorator_line}"

            route_info = self._extract_route_info(decorator_line)
            if route_info:
                break

        if not route_info:
            return None

        http_method, route_path = route_info

        # Get function source code
        try:
            function_start = function_node.lineno - 1
            function_end = function_node.end_lineno
            function_lines = source_lines[function_start:function_end]
            function_source = '\n'.join(function_lines)
        except Exception as e:
            logger.warning(f"Could not extract function source: {e}")
            function_source = ""

        # Extract function parameters
        params = [arg.arg for arg in function_node.args.args]

        # Create endpoint info
        endpoint = EndpointInfo(
            file_path=file_path,
            function_name=function_node.name,
            http_method=http_method,
            route_path=route_path,
            line_number=function_node.lineno,
            parameters=params,
        )

        # Check if endpoint is exempt
        if self._is_exempt_endpoint(route_path):
            endpoint.warnings.append("Exempt endpoint (public/auth/platform admin)")
            return endpoint

        # Check authentication
        endpoint.has_authentication = self._check_authentication(function_source)
        if not endpoint.has_authentication:
            endpoint.issues.append(
                "No authentication dependency found (get_current_user)"
            )

        # Check for unsafe tenant extraction patterns
        endpoint.unsafe_tenant_extraction = self._check_unsafe_tenant_extraction(
            function_source
        )
        if endpoint.unsafe_tenant_extraction:
            endpoint.issues.append(
                "Unsafe: tenant_id extracted from request params/body instead of user context"
            )

        # Check for safe tenant extraction
        has_safe_extraction, method = self._check_safe_tenant_extraction(function_source)
        endpoint.extracts_tenant_from_user = has_safe_extraction
        endpoint.tenant_extraction_method = method

        # Validate tenant isolation for authenticated endpoints
        if endpoint.has_authentication and not endpoint.extracts_tenant_from_user:
            # Check if this is a write operation (POST, PUT, PATCH, DELETE)
            is_write_operation = http_method in ['POST', 'PUT', 'PATCH', 'DELETE']
            # Check if this endpoint likely deals with tenant-scoped data
            tenant_scoped_patterns = [
                r'workflow', r'environment', r'deployment', r'credential',
                r'execution', r'team', r'snapshot', r'promotion',
                r'pipeline', r'drift', r'canonical', r'tenant'
            ]
            likely_tenant_scoped = any(
                re.search(pattern, route_path, re.IGNORECASE) or
                re.search(pattern, function_node.name, re.IGNORECASE)
                for pattern in tenant_scoped_patterns
            )

            if is_write_operation and likely_tenant_scoped:
                endpoint.issues.append(
                    "Write operation on tenant-scoped resource without visible tenant_id extraction"
                )
            elif likely_tenant_scoped:
                endpoint.warnings.append(
                    "Tenant-scoped resource without visible tenant_id extraction from user context"
                )

        return endpoint

    def scan_file(self, file_path: Path) -> List[EndpointInfo]:
        """
        Scan a single Python file for API endpoints.

        Args:
            file_path: Path to the Python file

        Returns:
            List of EndpointInfo for all endpoints found in the file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
                source_lines = source.splitlines()
        except Exception as e:
            logger.error(f"Could not read file {file_path}: {e}")
            return []

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return []

        endpoints = []
        for node in ast.walk(tree):
            # Check both sync and async function definitions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                endpoint = self._analyze_function(str(file_path), node, source_lines)
                if endpoint:
                    endpoints.append(endpoint)

        return endpoints

    def scan_all_endpoints(self) -> ScanResult:
        """
        Scan all endpoint files in the endpoints directory.

        Returns:
            ScanResult containing all scanned endpoints and statistics
        """
        result = ScanResult()

        # Find all Python files in endpoints directory
        python_files = list(self.endpoints_dir.glob("*.py"))
        python_files = [f for f in python_files if f.name != "__init__.py"]

        logger.info(f"Scanning {len(python_files)} endpoint files...")

        for file_path in python_files:
            endpoints = self.scan_file(file_path)
            result.endpoints.extend(endpoints)

        # Calculate statistics
        result.total_endpoints = len(result.endpoints)
        result.authenticated_endpoints = sum(
            1 for e in result.endpoints if e.has_authentication
        )
        result.properly_isolated_endpoints = sum(
            1 for e in result.endpoints
            if e.has_authentication and e.extracts_tenant_from_user and not e.unsafe_tenant_extraction
        )
        result.endpoints_with_issues = sum(
            1 for e in result.endpoints if e.issues
        )
        result.endpoints_with_warnings = sum(
            1 for e in result.endpoints if e.warnings
        )

        return result

    def generate_report(self, result: ScanResult, verbose: bool = False) -> str:
        """
        Generate a human-readable report from scan results.

        Args:
            result: ScanResult from scan_all_endpoints()
            verbose: Include all endpoints in report (default: only issues/warnings)

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 80,
            "TENANT ISOLATION SECURITY SCAN REPORT",
            "=" * 80,
            "",
            f"Total Endpoints Scanned: {result.total_endpoints}",
            f"Authenticated Endpoints: {result.authenticated_endpoints}",
            f"Properly Isolated Endpoints: {result.properly_isolated_endpoints}",
            f"Endpoints with Issues: {result.endpoints_with_issues}",
            f"Endpoints with Warnings: {result.endpoints_with_warnings}",
            f"Isolation Coverage: {result.isolation_coverage:.1f}%",
            "",
        ]

        if result.has_issues:
            lines.extend([
                "[!] SECURITY ISSUES FOUND",
                "=" * 80,
                "",
            ])
        else:
            lines.extend([
                "[OK] NO SECURITY ISSUES FOUND",
                "=" * 80,
                "",
            ])

        # Group endpoints by file
        endpoints_by_file = {}
        for endpoint in result.endpoints:
            file_name = Path(endpoint.file_path).name
            if file_name not in endpoints_by_file:
                endpoints_by_file[file_name] = []
            endpoints_by_file[file_name].append(endpoint)

        # Report endpoints with issues first
        if result.endpoints_with_issues > 0:
            lines.extend([
                "ENDPOINTS WITH ISSUES:",
                "-" * 80,
                "",
            ])
            for file_name in sorted(endpoints_by_file.keys()):
                endpoints = [e for e in endpoints_by_file[file_name] if e.issues]
                if endpoints:
                    lines.append(f"File: {file_name}")
                    lines.append("")
                    for endpoint in endpoints:
                        lines.extend(self._format_endpoint(endpoint, show_details=True))
                        lines.append("")

        # Report endpoints with warnings
        if result.endpoints_with_warnings > 0:
            lines.extend([
                "",
                "ENDPOINTS WITH WARNINGS:",
                "-" * 80,
                "",
            ])
            for file_name in sorted(endpoints_by_file.keys()):
                endpoints = [e for e in endpoints_by_file[file_name] if e.warnings and not e.issues]
                if endpoints:
                    lines.append(f"File: {file_name}")
                    lines.append("")
                    for endpoint in endpoints:
                        lines.extend(self._format_endpoint(endpoint, show_details=True))
                        lines.append("")

        # Optionally include all endpoints
        if verbose:
            lines.extend([
                "",
                "ALL ENDPOINTS:",
                "-" * 80,
                "",
            ])
            for file_name in sorted(endpoints_by_file.keys()):
                lines.append(f"File: {file_name}")
                lines.append("")
                for endpoint in endpoints_by_file[file_name]:
                    lines.extend(self._format_endpoint(endpoint))
                    lines.append("")

        return '\n'.join(lines)

    def _format_endpoint(self, endpoint: EndpointInfo, show_details: bool = False) -> List[str]:
        """Format an endpoint for display in the report."""
        lines = [
            f"  {endpoint.http_method} {endpoint.route_path}",
            f"    Function: {endpoint.function_name} (line {endpoint.line_number})",
        ]

        status_parts = []
        if endpoint.has_authentication:
            status_parts.append("[+] Authenticated")
        else:
            status_parts.append("[-] Not authenticated")

        if endpoint.extracts_tenant_from_user:
            status_parts.append("[+] Safe tenant extraction")

        if endpoint.unsafe_tenant_extraction:
            status_parts.append("[-] Unsafe tenant extraction")

        lines.append(f"    Status: {', '.join(status_parts)}")

        if endpoint.tenant_extraction_method:
            lines.append(f"    Method: {endpoint.tenant_extraction_method}")

        if endpoint.issues:
            for issue in endpoint.issues:
                lines.append(f"    [!] ISSUE: {issue}")

        if endpoint.warnings:
            for warning in endpoint.warnings:
                lines.append(f"    [*] WARNING: {warning}")

        return lines

    def export_json(self, result: ScanResult) -> Dict[str, Any]:
        """
        Export scan results as JSON-serializable dictionary.

        Args:
            result: ScanResult from scan_all_endpoints()

        Returns:
            Dictionary with all scan results
        """
        return {
            "summary": {
                "total_endpoints": result.total_endpoints,
                "authenticated_endpoints": result.authenticated_endpoints,
                "properly_isolated_endpoints": result.properly_isolated_endpoints,
                "endpoints_with_issues": result.endpoints_with_issues,
                "endpoints_with_warnings": result.endpoints_with_warnings,
                "isolation_coverage": result.isolation_coverage,
                "has_issues": result.has_issues,
            },
            "endpoints": [
                {
                    "file_path": e.file_path,
                    "function_name": e.function_name,
                    "http_method": e.http_method,
                    "route_path": e.route_path,
                    "line_number": e.line_number,
                    "has_authentication": e.has_authentication,
                    "extracts_tenant_from_user": e.extracts_tenant_from_user,
                    "unsafe_tenant_extraction": e.unsafe_tenant_extraction,
                    "tenant_extraction_method": e.tenant_extraction_method,
                    "parameters": e.parameters,
                    "issues": e.issues,
                    "warnings": e.warnings,
                }
                for e in result.endpoints
            ]
        }


async def verify_all_endpoints() -> List[Dict[str, Any]]:
    """
    Quick verification function to check all endpoints for tenant isolation issues.

    This is a convenience function for use in tests or scripts.

    Returns:
        List of issues found (empty list if no issues)

    Example:
        issues = await verify_all_endpoints()
        if issues:
            print(f"Found {len(issues)} tenant isolation issues")
            for issue in issues:
                print(f"  - {issue['endpoint']}: {issue['issue']}")
    """
    scanner = TenantIsolationScanner()
    result = scanner.scan_all_endpoints()

    issues = []
    for endpoint in result.endpoints:
        for issue in endpoint.issues:
            issues.append({
                "endpoint": f"{endpoint.http_method} {endpoint.route_path}",
                "function": endpoint.function_name,
                "file": Path(endpoint.file_path).name,
                "line": endpoint.line_number,
                "issue": issue,
            })

    return issues


def print_summary(result: ScanResult) -> None:
    """
    Print a quick summary of scan results to console.

    Args:
        result: ScanResult from scan_all_endpoints()
    """
    print("\n" + "=" * 60)
    print("TENANT ISOLATION SCAN SUMMARY")
    print("=" * 60)
    print(f"Total Endpoints: {result.total_endpoints}")
    print(f"Authenticated: {result.authenticated_endpoints}")
    print(f"Properly Isolated: {result.properly_isolated_endpoints}")
    print(f"Issues: {result.endpoints_with_issues}")
    print(f"Warnings: {result.endpoints_with_warnings}")
    print(f"Coverage: {result.isolation_coverage:.1f}%")

    if result.has_issues:
        print("\n[!] SECURITY ISSUES FOUND - Run full report for details")
    else:
        print("\n[OK] NO SECURITY ISSUES FOUND")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Allow running as a standalone script
    import asyncio

    async def main():
        """Run the scanner and print report."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Print summary
        print_summary(result)

        # Print full report (only issues and warnings by default)
        report = scanner.generate_report(result, verbose=False)
        print(report)

        # Optionally export JSON
        # import json
        # with open('tenant_isolation_report.json', 'w') as f:
        #     json.dump(scanner.export_json(result), f, indent=2)

    asyncio.run(main())
