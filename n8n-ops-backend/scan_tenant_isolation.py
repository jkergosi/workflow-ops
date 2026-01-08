#!/usr/bin/env python3
"""
Tenant Isolation Scanner - CLI Tool

This script scans all API endpoints for tenant isolation patterns and generates
a security report.

Usage:
    python scan_tenant_isolation.py                 # Quick summary
    python scan_tenant_isolation.py --full           # Full report
    python scan_tenant_isolation.py --json report.json   # Export to JSON
    python scan_tenant_isolation.py --issues-only    # Show only issues
"""
import sys
import argparse
import json
import asyncio
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.tenant_isolation import (
    TenantIsolationScanner,
    verify_all_endpoints,
    print_summary
)


def main():
    parser = argparse.ArgumentParser(
        description='Scan API endpoints for tenant isolation issues'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Show full report with all endpoints'
    )
    parser.add_argument(
        '--json',
        metavar='FILE',
        help='Export results to JSON file'
    )
    parser.add_argument(
        '--issues-only',
        action='store_true',
        help='Show only endpoints with issues'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Run the scanner
    scanner = TenantIsolationScanner()
    result = scanner.scan_all_endpoints()

    # Always show summary
    print_summary(result)

    # Export to JSON if requested
    if args.json:
        json_data = scanner.export_json(result)
        with open(args.json, 'w') as f:
            json.dump(json_data, f, indent=2)
        print(f"\nJSON report saved to: {args.json}")

    # Show full report if requested
    if args.full or args.issues_only:
        report = scanner.generate_report(result, verbose=args.full and not args.issues_only)
        print(report)

    # Exit with error code if issues found
    sys.exit(1 if result.has_issues else 0)


if __name__ == '__main__':
    main()
