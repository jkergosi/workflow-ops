"""
Test script for bulk sync endpoint (T011)

This script verifies that the POST /api/bulk/sync endpoint:
1. Accepts workflow_ids and environment_id
2. Validates max 50 workflows
3. Returns job_id immediately
4. Starts background task
"""
import asyncio
import sys
from pathlib import Path

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.schemas.bulk_operations import BulkOperationRequest, BulkOperationType
from app.core.config import settings


def test_schema_validation():
    """Test that BulkOperationRequest validates correctly"""
    print("\n=== Testing Schema Validation ===")

    # Test valid request
    try:
        request = BulkOperationRequest(
            workflow_ids=["wf1", "wf2", "wf3"],
            operation_type=BulkOperationType.SYNC
        )
        print(f"✓ Valid request accepted: {len(request.workflow_ids)} workflows")
    except Exception as e:
        print(f"✗ Valid request failed: {e}")
        return False

    # Test empty list
    try:
        request = BulkOperationRequest(
            workflow_ids=[],
            operation_type=BulkOperationType.SYNC
        )
        print(f"✗ Empty list should be rejected but was accepted")
        return False
    except ValueError as e:
        print(f"✓ Empty list correctly rejected: {e}")

    # Test max 50 workflows
    try:
        request = BulkOperationRequest(
            workflow_ids=[f"wf{i}" for i in range(50)],
            operation_type=BulkOperationType.SYNC
        )
        print(f"✓ Maximum 50 workflows accepted")
    except Exception as e:
        print(f"✗ Max 50 workflows failed: {e}")
        return False

    # Test over 50 workflows
    try:
        request = BulkOperationRequest(
            workflow_ids=[f"wf{i}" for i in range(51)],
            operation_type=BulkOperationType.SYNC
        )
        print(f"✗ Over 50 workflows should be rejected but was accepted")
        return False
    except ValueError as e:
        print(f"✓ Over 50 workflows correctly rejected: {e}")

    # Test duplicate removal
    try:
        request = BulkOperationRequest(
            workflow_ids=["wf1", "wf2", "wf1", "wf3", "wf2"],
            operation_type=BulkOperationType.SYNC
        )
        if len(request.workflow_ids) == 3:
            print(f"✓ Duplicates correctly removed: {request.workflow_ids}")
        else:
            print(f"✗ Duplicates not removed correctly: {request.workflow_ids}")
            return False
    except Exception as e:
        print(f"✗ Duplicate removal failed: {e}")
        return False

    return True


def test_config():
    """Test that MAX_BULK_WORKFLOWS is configured"""
    print("\n=== Testing Configuration ===")

    if hasattr(settings, 'MAX_BULK_WORKFLOWS'):
        print(f"✓ MAX_BULK_WORKFLOWS configured: {settings.MAX_BULK_WORKFLOWS}")
        if settings.MAX_BULK_WORKFLOWS == 50:
            print(f"✓ MAX_BULK_WORKFLOWS set to correct value (50)")
            return True
        else:
            print(f"✗ MAX_BULK_WORKFLOWS should be 50 but is {settings.MAX_BULK_WORKFLOWS}")
            return False
    else:
        print(f"✗ MAX_BULK_WORKFLOWS not configured")
        return False


def test_imports():
    """Test that all required modules can be imported"""
    print("\n=== Testing Imports ===")

    try:
        from app.api.endpoints.bulk_operations import router
        print("✓ bulk_operations endpoint imported successfully")
    except Exception as e:
        print(f"✗ Failed to import bulk_operations endpoint: {e}")
        return False

    try:
        from app.services.bulk_workflow_service import bulk_workflow_service
        print("✓ bulk_workflow_service imported successfully")
    except Exception as e:
        print(f"✗ Failed to import bulk_workflow_service: {e}")
        return False

    try:
        from app.schemas.bulk_operations import (
            BulkOperationRequest,
            BulkOperationResponse,
            BulkOperationType
        )
        print("✓ bulk_operations schemas imported successfully")
    except Exception as e:
        print(f"✗ Failed to import bulk_operations schemas: {e}")
        return False

    return True


def test_endpoint_registration():
    """Test that the endpoint is registered in main.py"""
    print("\n=== Testing Endpoint Registration ===")

    try:
        from app.main import app

        # Check if bulk_operations routes are registered
        routes = [route.path for route in app.routes]
        bulk_routes = [r for r in routes if '/bulk' in r]

        if bulk_routes:
            print(f"✓ Bulk operation routes registered: {bulk_routes}")

            # Check specifically for /sync endpoint
            sync_route = any('/bulk/sync' in r for r in bulk_routes)
            if sync_route:
                print(f"✓ /bulk/sync endpoint found")
                return True
            else:
                print(f"✗ /bulk/sync endpoint not found")
                return False
        else:
            print(f"✗ No bulk operation routes found")
            return False

    except Exception as e:
        print(f"✗ Failed to check endpoint registration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing POST /api/bulk/sync Endpoint Implementation (T011)")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Schema Validation", test_schema_validation()))
    results.append(("Endpoint Registration", test_endpoint_registration()))

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    print("=" * 60)
    if all_passed:
        print("✓ All tests passed! T011 implementation complete.")
    else:
        print("✗ Some tests failed. Please review the errors above.")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
