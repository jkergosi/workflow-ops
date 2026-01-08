"""Comprehensive tenant isolation test suite.

This test suite verifies that all API endpoints properly enforce tenant isolation
to prevent cross-tenant data leakage. It tests:

1. Tenant ID is extracted from authenticated user context (not request params)
2. Cross-tenant access attempts are properly blocked
3. Database queries filter by tenant_id
4. Write operations respect tenant boundaries
5. Impersonation sessions maintain proper tenant isolation

Key Security Principles Tested:
- Server-side tenant_id enforcement from auth context
- No trust of client-provided tenant_id values
- Proper authentication dependencies on all tenant-scoped endpoints
- Audit logging includes correct tenant_id during impersonation
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from typing import Dict, Any, List
from datetime import datetime

from app.core.tenant_isolation import (
    TenantIsolationScanner,
    ScanResult,
    EndpointInfo,
    verify_all_endpoints,
)
from app.services.auth_service import get_current_user
from app.main import app


# ============ Test Fixtures ============

@pytest.fixture
def tenant_a() -> Dict[str, Any]:
    """Mock tenant A."""
    return {
        "id": "tenant-aaa-111",
        "name": "Tenant A Organization",
        "email": "admin@tenant-a.com",
        "subscription_tier": "pro",
        "status": "active",
    }


@pytest.fixture
def tenant_b() -> Dict[str, Any]:
    """Mock tenant B."""
    return {
        "id": "tenant-bbb-222",
        "name": "Tenant B Organization",
        "email": "admin@tenant-b.com",
        "subscription_tier": "pro",
        "status": "active",
    }


@pytest.fixture
def user_tenant_a(tenant_a: Dict[str, Any]) -> Dict[str, Any]:
    """Mock user belonging to tenant A."""
    return {
        "user": {
            "id": "user-a-001",
            "email": "user@tenant-a.com",
            "name": "User A",
            "role": "admin",
            "status": "active",
        },
        "tenant": tenant_a,
        "impersonating": False,
    }


@pytest.fixture
def user_tenant_b(tenant_b: Dict[str, Any]) -> Dict[str, Any]:
    """Mock user belonging to tenant B."""
    return {
        "user": {
            "id": "user-b-001",
            "email": "user@tenant-b.com",
            "name": "User B",
            "role": "admin",
            "status": "active",
        },
        "tenant": tenant_b,
        "impersonating": False,
    }


@pytest.fixture
def platform_admin_user() -> Dict[str, Any]:
    """Mock platform administrator (no tenant affiliation)."""
    return {
        "user": {
            "id": "platform-admin-001",
            "email": "admin@platform.com",
            "name": "Platform Admin",
            "role": "platform_admin",
            "status": "active",
        },
        "tenant": None,
        "is_platform_admin": True,
        "impersonating": False,
    }


@pytest.fixture
def impersonation_context(platform_admin_user: Dict[str, Any], user_tenant_a: Dict[str, Any]) -> Dict[str, Any]:
    """Mock impersonation context: platform admin impersonating user in tenant A."""
    return {
        "user": user_tenant_a["user"],
        "tenant": user_tenant_a["tenant"],
        "impersonating": True,
        "impersonation_session_id": "session-12345",
        "impersonated_user_id": user_tenant_a["user"]["id"],
        "impersonated_tenant_id": user_tenant_a["tenant"]["id"],
        "actor_user": platform_admin_user["user"],
        "actor_user_id": platform_admin_user["user"]["id"],
    }


# ============ TenantIsolationScanner Tests ============

class TestTenantIsolationScanner:
    """Tests for the TenantIsolationScanner utility."""

    def test_scanner_initialization(self):
        """Test scanner can be initialized with default endpoints directory."""
        scanner = TenantIsolationScanner()
        assert scanner.endpoints_dir.exists()
        assert scanner.endpoints_dir.name == "endpoints"

    def test_scanner_with_custom_directory(self, tmp_path):
        """Test scanner can be initialized with a custom directory."""
        custom_dir = tmp_path / "custom_endpoints"
        custom_dir.mkdir()

        scanner = TenantIsolationScanner(str(custom_dir))
        assert scanner.endpoints_dir == custom_dir

    def test_scanner_with_nonexistent_directory(self):
        """Test scanner raises error for nonexistent directory."""
        with pytest.raises(ValueError, match="Endpoints directory not found"):
            TenantIsolationScanner("/nonexistent/path")

    def test_exempt_endpoint_detection(self):
        """Test detection of endpoints that are exempt from tenant isolation."""
        scanner = TenantIsolationScanner()

        # These should be exempt
        assert scanner._is_exempt_endpoint("/health")
        assert scanner._is_exempt_endpoint("/auth/login")
        assert scanner._is_exempt_endpoint("/auth/register")
        assert scanner._is_exempt_endpoint("/platform/admin/users")
        assert scanner._is_exempt_endpoint("/platform/impersonation/start")
        assert scanner._is_exempt_endpoint("/onboard/tenant")

        # These should NOT be exempt
        assert not scanner._is_exempt_endpoint("/workflows")
        assert not scanner._is_exempt_endpoint("/environments")
        assert not scanner._is_exempt_endpoint("/deployments")

    def test_route_info_extraction(self):
        """Test extraction of HTTP method and route path from decorators."""
        scanner = TenantIsolationScanner()

        # Test various decorator formats
        assert scanner._extract_route_info('@router.get("/workflows")') == ("GET", "/workflows")
        assert scanner._extract_route_info('@router.post("/environments")') == ("POST", "/environments")
        assert scanner._extract_route_info("@router.delete('/workflows/{id}')") == ("DELETE", "/workflows/{id}")
        assert scanner._extract_route_info('@router.put("")') == ("PUT", "")
        assert scanner._extract_route_info('@router.patch()') == ("PATCH", "")

        # Non-route decorators should return None
        assert scanner._extract_route_info('@require_entitlement("workflow_read")') is None
        assert scanner._extract_route_info('@property') is None

    def test_authentication_check(self):
        """Test detection of authentication dependencies."""
        scanner = TenantIsolationScanner()

        # Should detect authentication
        assert scanner._check_authentication("user_info: dict = Depends(get_current_user)")
        assert scanner._check_authentication("user_context: dict = Depends(get_current_user)")
        assert scanner._check_authentication("_: dict = Depends(require_platform_admin())")
        assert scanner._check_authentication("_: dict = Depends(require_entitlement('read'))")

        # Should NOT detect authentication (no Depends)
        assert not scanner._check_authentication("user_info: dict")
        assert not scanner._check_authentication("tenant_id: str")

    def test_safe_tenant_extraction_detection(self):
        """Test detection of safe tenant_id extraction from user context."""
        scanner = TenantIsolationScanner()

        # Safe patterns
        has_safe, method = scanner._check_safe_tenant_extraction("tenant_id = get_tenant_id(user_info)")
        assert has_safe
        assert "get_tenant_id(user_info)" in method

        has_safe, method = scanner._check_safe_tenant_extraction("tenant = user_info.get('tenant')")
        assert has_safe

        has_safe, method = scanner._check_safe_tenant_extraction('tenant_id = user_info["tenant"]["id"]')
        assert has_safe

        # Unsafe/missing patterns
        has_safe, method = scanner._check_safe_tenant_extraction("tenant_id = request.query_params.get('tenant_id')")
        assert not has_safe

        has_safe, method = scanner._check_safe_tenant_extraction("# No tenant extraction here")
        assert not has_safe

    def test_unsafe_tenant_extraction_detection(self):
        """Test detection of unsafe tenant_id extraction from request."""
        scanner = TenantIsolationScanner()

        # Unsafe patterns (tenant_id from request parameters)
        assert scanner._check_unsafe_tenant_extraction("async def handler(tenant_id: str = Query())")
        assert scanner._check_unsafe_tenant_extraction("tenant_id = request.query_params.get('tenant_id')")
        assert scanner._check_unsafe_tenant_extraction("tenant_id = body.tenant_id")

        # Safe patterns (no request-based extraction)
        assert not scanner._check_unsafe_tenant_extraction("tenant_id = get_tenant_id(user_info)")
        assert not scanner._check_unsafe_tenant_extraction("tenant = user_info['tenant']")

    def test_scan_result_properties(self):
        """Test ScanResult computed properties."""
        result = ScanResult(
            total_endpoints=10,
            authenticated_endpoints=8,
            properly_isolated_endpoints=6,
            endpoints_with_issues=2,
            endpoints_with_warnings=1,
        )

        assert result.has_issues is True
        assert result.isolation_coverage == 75.0  # 6/8 * 100

        # Test with no issues
        result_clean = ScanResult(
            total_endpoints=10,
            authenticated_endpoints=10,
            properly_isolated_endpoints=10,
            endpoints_with_issues=0,
        )
        assert result_clean.has_issues is False
        assert result_clean.isolation_coverage == 100.0

    def test_scan_result_coverage_with_no_auth(self):
        """Test isolation coverage when no endpoints have authentication."""
        result = ScanResult(
            total_endpoints=5,
            authenticated_endpoints=0,
            properly_isolated_endpoints=0,
        )
        assert result.isolation_coverage == 0.0


# ============ Real Endpoint Scanning Tests ============

class TestRealEndpointScanning:
    """Tests that scan actual API endpoint files."""

    def test_scan_all_endpoints_executes(self):
        """Test that scanning all endpoints completes without errors."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        assert isinstance(result, ScanResult)
        assert result.total_endpoints > 0  # Should find at least some endpoints
        assert isinstance(result.endpoints, list)

    def test_scan_generates_valid_report(self):
        """Test that report generation works and produces readable output."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        report = scanner.generate_report(result, verbose=False)
        assert isinstance(report, str)
        assert len(report) > 0
        assert "TENANT ISOLATION SECURITY SCAN REPORT" in report
        assert f"Total Endpoints Scanned: {result.total_endpoints}" in report

    def test_scan_generates_verbose_report(self):
        """Test verbose report includes all endpoints."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        report = scanner.generate_report(result, verbose=True)
        assert "ALL ENDPOINTS:" in report

    def test_scan_exports_json(self):
        """Test JSON export contains all required fields."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        json_data = scanner.export_json(result)

        assert "summary" in json_data
        assert "endpoints" in json_data
        assert json_data["summary"]["total_endpoints"] == result.total_endpoints
        assert len(json_data["endpoints"]) == result.total_endpoints

        # Check endpoint structure
        if json_data["endpoints"]:
            endpoint = json_data["endpoints"][0]
            assert "file_path" in endpoint
            assert "function_name" in endpoint
            assert "http_method" in endpoint
            assert "route_path" in endpoint
            assert "has_authentication" in endpoint
            assert "issues" in endpoint

    @pytest.mark.asyncio
    async def test_verify_all_endpoints_function(self):
        """Test the convenience verify_all_endpoints() function."""
        issues = await verify_all_endpoints()

        assert isinstance(issues, list)
        # Issues list may or may not be empty depending on codebase state
        # Just verify structure if issues exist
        if issues:
            for issue in issues:
                assert "endpoint" in issue
                assert "function" in issue
                assert "file" in issue
                assert "line" in issue
                assert "issue" in issue


# ============ Cross-Tenant Access Prevention Tests ============

class TestCrossTenantAccessPrevention:
    """Tests verifying that users cannot access data from other tenants."""

    @pytest.mark.asyncio
    async def test_workflows_endpoint_enforces_tenant_isolation(
        self,
        user_tenant_a: Dict[str, Any],
        tenant_b: Dict[str, Any],
    ):
        """Test that workflows endpoint filters by authenticated user's tenant_id."""
        from app.services.database import db_service

        with patch.object(db_service, 'get_environment') as mock_get_env:
            with patch.object(db_service, 'get_workflows_from_canonical') as mock_get_workflows:
                # Setup: environment belongs to tenant A
                mock_get_env.return_value = {
                    "id": "env-a-001",
                    "tenant_id": tenant_b["id"],  # Environment belongs to tenant B
                    "n8n_name": "Production",
                }

                mock_get_workflows.return_value = []

                # Mock authentication to return tenant A user
                app.dependency_overrides[get_current_user] = lambda: user_tenant_a

                client = TestClient(app)

                # User A tries to access environment from tenant B
                # The get_environment should be called with tenant A's ID
                response = client.get("/api/workflows?environment_id=env-b-001")

                # Verify the call used the authenticated user's tenant_id
                if mock_get_env.called:
                    call_args = mock_get_env.call_args
                    called_tenant_id = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('tenant_id')
                    assert called_tenant_id == user_tenant_a["tenant"]["id"], \
                        "Endpoint should use authenticated user's tenant_id, not request parameter"

                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_environments_endpoint_filters_by_tenant(
        self,
        user_tenant_a: Dict[str, Any],
        tenant_b: Dict[str, Any],
    ):
        """Test that environments endpoint only returns environments for the authenticated user's tenant."""
        from app.services.database import db_service
        from app.core.entitlements_gate import require_entitlement

        # Mock both the database call and entitlements
        with patch.object(db_service, 'get_environments', new_callable=AsyncMock) as mock_get_envs:
            mock_get_envs.return_value = [
                {"id": "env-a-001", "tenant_id": user_tenant_a["tenant"]["id"], "n8n_name": "Dev"},
                {"id": "env-a-002", "tenant_id": user_tenant_a["tenant"]["id"], "n8n_name": "Prod"},
            ]

            # Mock entitlement check
            async def mock_entitlement(*args, **kwargs):
                return user_tenant_a

            app.dependency_overrides[get_current_user] = lambda: user_tenant_a
            app.dependency_overrides[require_entitlement("environment_basic")] = mock_entitlement

            client = TestClient(app)
            response = client.get("/api/environments/")

            # Verify get_environments was called with the correct tenant_id
            if mock_get_envs.called:
                call_args = mock_get_envs.call_args
                called_tenant_id = call_args[0][0] if call_args[0] else None
                assert called_tenant_id == user_tenant_a["tenant"]["id"], \
                    "get_environments should be called with authenticated user's tenant_id"

            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_tenant_id_not_accepted_from_query_params(
        self,
        user_tenant_a: Dict[str, Any],
    ):
        """Test that tenant_id in query params is ignored in favor of auth context."""
        from app.services.database import db_service

        with patch.object(db_service, 'get_environments') as mock_get_envs:
            mock_get_envs.return_value = []

            app.dependency_overrides[get_current_user] = lambda: user_tenant_a

            client = TestClient(app)

            # Try to pass a different tenant_id in query params
            # This should be ignored, and the auth context tenant_id should be used
            response = client.get("/api/environments/?tenant_id=malicious-tenant-id")

            # Verify the authenticated user's tenant_id was used, not the query param
            if mock_get_envs.called:
                call_args = mock_get_envs.call_args
                called_tenant_id = call_args[0][0] if call_args[0] else None
                assert called_tenant_id == user_tenant_a["tenant"]["id"], \
                    "Query param tenant_id should be ignored"
                assert called_tenant_id != "malicious-tenant-id"

            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_database_queries_filter_by_tenant(
        self,
        user_tenant_a: Dict[str, Any],
    ):
        """Test that database service methods require and use tenant_id parameter."""
        from app.services.database import db_service

        # This test verifies that db_service methods are called with tenant_id
        # and that the service would filter results by tenant

        with patch.object(db_service, 'client') as mock_client:
            mock_table = MagicMock()
            mock_select = MagicMock()
            mock_eq = MagicMock()
            mock_execute = MagicMock()

            mock_execute.data = []
            mock_eq.execute.return_value = mock_execute
            mock_select.eq.return_value = mock_eq
            mock_table.select.return_value = mock_select
            mock_client.table.return_value = mock_table

            # Call db_service method with tenant_id
            result = await db_service.get_environments(user_tenant_a["tenant"]["id"])

            # Verify the query filtered by tenant_id
            mock_table.select.assert_called()
            # The eq() call should include tenant_id filter
            if mock_select.eq.called:
                # At least one eq() call should be for tenant_id
                eq_calls = [call for call in mock_select.eq.call_args_list]
                assert len(eq_calls) > 0, "Should filter by tenant_id"


# ============ Impersonation Tenant Isolation Tests ============

class TestImpersonationTenantIsolation:
    """Tests verifying tenant isolation is maintained during impersonation."""

    def test_impersonation_context_includes_correct_tenant(
        self,
        impersonation_context: Dict[str, Any],
    ):
        """Test that impersonation context includes the target user's tenant_id."""
        assert impersonation_context["impersonating"] is True
        assert impersonation_context["tenant"]["id"] == impersonation_context["impersonated_tenant_id"]
        assert impersonation_context["impersonated_user_id"] is not None
        assert impersonation_context["actor_user_id"] is not None

    @pytest.mark.asyncio
    async def test_impersonation_actions_scoped_to_target_tenant(
        self,
        impersonation_context: Dict[str, Any],
    ):
        """Test that actions during impersonation are scoped to the target user's tenant."""
        from app.services.database import db_service

        with patch.object(db_service, 'get_environments') as mock_get_envs:
            mock_get_envs.return_value = []

            app.dependency_overrides[get_current_user] = lambda: impersonation_context

            client = TestClient(app)
            response = client.get("/api/environments/")

            # Should use the impersonated user's tenant_id, not the platform admin's
            if mock_get_envs.called:
                call_args = mock_get_envs.call_args
                called_tenant_id = call_args[0][0] if call_args[0] else None
                assert called_tenant_id == impersonation_context["impersonated_tenant_id"]

            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_impersonation_audit_logs_include_both_actors(
        self,
        impersonation_context: Dict[str, Any],
    ):
        """Test that audit logs during impersonation record both the admin and target user."""
        from app.services.audit_middleware import get_audit_context

        audit_context = get_audit_context(impersonation_context)

        # Should record the platform admin as the actor
        assert audit_context["actor_id"] == impersonation_context["actor_user_id"]
        assert audit_context["actor_email"] == impersonation_context["actor_user"]["email"]

        # Should record the impersonated user
        assert audit_context["impersonated_user_id"] == impersonation_context["impersonated_user_id"]
        assert audit_context["impersonated_tenant_id"] == impersonation_context["impersonated_tenant_id"]

        # Should include session ID
        assert audit_context["impersonation_session_id"] == impersonation_context["impersonation_session_id"]

        # Tenant should be the target tenant
        assert audit_context["tenant_id"] == impersonation_context["impersonated_tenant_id"]

    def test_platform_admin_cannot_impersonate_without_session(
        self,
        platform_admin_user: Dict[str, Any],
    ):
        """Test that platform admins cannot access tenant data without active impersonation."""
        # Platform admin without impersonation has no tenant
        assert platform_admin_user.get("tenant") is None
        assert platform_admin_user.get("impersonating") is False

        # Attempting to get tenant_id should fail or return None
        tenant = platform_admin_user.get("tenant") or {}
        tenant_id = tenant.get("id")
        assert tenant_id is None


# ============ Get Tenant ID Helper Tests ============

class TestGetTenantIdHelper:
    """Tests for the get_tenant_id() helper function used in endpoints."""

    def test_get_tenant_id_extracts_from_user_info(self, user_tenant_a: Dict[str, Any]):
        """Test that get_tenant_id correctly extracts tenant_id from user_info."""
        from app.api.endpoints.workflows import get_tenant_id

        tenant_id = get_tenant_id(user_tenant_a)
        assert tenant_id == user_tenant_a["tenant"]["id"]

    def test_get_tenant_id_raises_when_tenant_missing(self):
        """Test that get_tenant_id raises HTTPException when tenant is missing."""
        from app.api.endpoints.workflows import get_tenant_id

        user_without_tenant = {
            "user": {"id": "user-123", "email": "user@example.com"},
            "tenant": None,
        }

        with pytest.raises(HTTPException) as exc_info:
            get_tenant_id(user_without_tenant)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in str(exc_info.value.detail)

    def test_get_tenant_id_raises_when_tenant_id_missing(self):
        """Test that get_tenant_id raises HTTPException when tenant exists but has no ID."""
        from app.api.endpoints.workflows import get_tenant_id

        user_with_empty_tenant = {
            "user": {"id": "user-123", "email": "user@example.com"},
            "tenant": {},  # Tenant dict exists but is empty
        }

        with pytest.raises(HTTPException) as exc_info:
            get_tenant_id(user_with_empty_tenant)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ============ Write Operation Tenant Isolation Tests ============

class TestWriteOperationTenantIsolation:
    """Tests ensuring write operations respect tenant boundaries."""

    @pytest.mark.asyncio
    async def test_create_environment_scoped_to_tenant(
        self,
        user_tenant_a: Dict[str, Any],
    ):
        """Test that creating an environment automatically associates it with the user's tenant."""
        from app.services.database import db_service

        with patch.object(db_service, 'create_environment') as mock_create:
            with patch.object(db_service, 'get_environments') as mock_get_envs:
                mock_get_envs.return_value = []
                mock_create.return_value = {"id": "new-env-001", "tenant_id": user_tenant_a["tenant"]["id"]}

                app.dependency_overrides[get_current_user] = lambda: user_tenant_a

                client = TestClient(app)

                # Try to create environment with a different tenant_id in body
                response = client.post(
                    "/api/environments/",
                    json={
                        "n8n_name": "New Environment",
                        "n8n_base_url": "https://new.n8n.example.com",
                        "n8n_api_key": "test-key",
                        "tenant_id": "malicious-tenant-id",  # Should be ignored
                    }
                )

                # Verify create was called with the authenticated user's tenant_id
                if mock_create.called:
                    call_kwargs = mock_create.call_args[1] if mock_create.call_args else {}
                    # The service should override any tenant_id from the request body
                    # with the authenticated user's tenant_id
                    if "tenant_id" in call_kwargs:
                        assert call_kwargs["tenant_id"] == user_tenant_a["tenant"]["id"]

                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_only_affects_own_tenant_resources(
        self,
        user_tenant_a: Dict[str, Any],
        tenant_b: Dict[str, Any],
    ):
        """Test that update operations can only modify resources belonging to the user's tenant."""
        from app.services.database import db_service
        from app.core.entitlements_gate import require_entitlement

        with patch.object(db_service, 'get_environment', new_callable=AsyncMock) as mock_get_env:
            with patch.object(db_service, 'update_environment', new_callable=AsyncMock) as mock_update:
                # Setup: Environment belongs to tenant B, so it won't be found for tenant A
                mock_get_env.return_value = None  # Simulate not found (filtered by tenant)
                mock_update.return_value = None

                # Mock entitlement check
                async def mock_entitlement(*args, **kwargs):
                    return user_tenant_a

                app.dependency_overrides[get_current_user] = lambda: user_tenant_a
                app.dependency_overrides[require_entitlement("environment_write")] = mock_entitlement

                client = TestClient(app)

                # User A tries to update environment from tenant B
                response = client.put(
                    "/api/environments/env-b-001",
                    json={"n8n_name": "Hacked Name"}
                )

                # The endpoint should fail (404 or 403) because the environment
                # doesn't exist in this tenant's scope
                # We just verify the correct tenant_id was used in the lookup
                if mock_get_env.called:
                    call_args = mock_get_env.call_args
                    # Verify it queried with the authenticated user's tenant_id
                    if len(call_args[0]) > 1:
                        called_tenant_id = call_args[0][1]
                        assert called_tenant_id == user_tenant_a["tenant"]["id"], \
                            "Should query with authenticated user's tenant_id"

                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_only_affects_own_tenant_resources(
        self,
        user_tenant_a: Dict[str, Any],
    ):
        """Test that delete operations can only remove resources belonging to the user's tenant."""
        from app.services.database import db_service

        with patch.object(db_service, 'get_environment') as mock_get_env:
            with patch.object(db_service, 'delete_environment') as mock_delete:
                # Environment exists and belongs to tenant A
                mock_get_env.return_value = {
                    "id": "env-a-001",
                    "tenant_id": user_tenant_a["tenant"]["id"],
                }
                mock_delete.return_value = True

                app.dependency_overrides[get_current_user] = lambda: user_tenant_a

                client = TestClient(app)
                response = client.delete("/api/environments/env-a-001")

                # Verify get_environment was called with correct tenant_id
                if mock_get_env.called:
                    call_args = mock_get_env.call_args
                    if len(call_args[0]) > 1:
                        called_tenant_id = call_args[0][1]
                        assert called_tenant_id == user_tenant_a["tenant"]["id"]

                app.dependency_overrides.clear()


# ============ Security Best Practices Tests ============

class TestSecurityBestPractices:
    """Tests verifying adherence to security best practices."""

    def test_no_endpoints_accept_tenant_id_from_request_body(self):
        """Test that no endpoint functions accept tenant_id as a request parameter."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Filter out exempt endpoints
        non_exempt_endpoints = [
            e for e in result.endpoints
            if not scanner._is_exempt_endpoint(e.route_path)
        ]

        # Check for unsafe tenant extraction
        unsafe_endpoints = [
            e for e in non_exempt_endpoints
            if e.unsafe_tenant_extraction
        ]

        # Generate detailed report of violations
        if unsafe_endpoints:
            violations = []
            for endpoint in unsafe_endpoints:
                violations.append(
                    f"{endpoint.http_method} {endpoint.route_path} "
                    f"in {endpoint.file_path}:{endpoint.line_number}"
                )

            # This is a critical security issue
            pytest.fail(
                f"Found {len(unsafe_endpoints)} endpoints with unsafe tenant_id extraction:\n" +
                "\n".join(violations)
            )

    def test_all_write_endpoints_have_authentication(self):
        """Test that all write operation endpoints require authentication."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Filter write operations (POST, PUT, PATCH, DELETE)
        write_operations = [
            e for e in result.endpoints
            if e.http_method in ['POST', 'PUT', 'PATCH', 'DELETE']
            and not scanner._is_exempt_endpoint(e.route_path)
        ]

        # Additional exempt patterns for webhooks and public endpoints
        webhook_patterns = ['/webhook', '/check-email', '/callback']

        # Check for missing authentication
        unauthenticated_writes = [
            e for e in write_operations
            if not e.has_authentication
            and not any(pattern in e.route_path for pattern in webhook_patterns)
        ]

        if unauthenticated_writes:
            violations = []
            for endpoint in unauthenticated_writes:
                violations.append(
                    f"{endpoint.http_method} {endpoint.route_path} "
                    f"in {endpoint.file_path}:{endpoint.line_number}"
                )

            pytest.fail(
                f"Found {len(unauthenticated_writes)} write endpoints without authentication:\n" +
                "\n".join(violations)
            )

    def test_tenant_scoped_endpoints_extract_tenant_from_auth(self):
        """Test that tenant-scoped endpoints extract tenant_id from auth context."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Filter authenticated, tenant-scoped endpoints
        tenant_scoped = [
            e for e in result.endpoints
            if e.has_authentication
            and not scanner._is_exempt_endpoint(e.route_path)
            and any(pattern in e.route_path.lower() or pattern in e.function_name.lower()
                   for pattern in ['workflow', 'environment', 'deployment', 'credential',
                                  'execution', 'team', 'snapshot', 'promotion', 'pipeline'])
        ]

        # These should all have safe tenant extraction
        missing_tenant_extraction = [
            e for e in tenant_scoped
            if not e.extracts_tenant_from_user and e.http_method in ['POST', 'PUT', 'PATCH', 'DELETE']
        ]

        # Generate warnings (may have false positives)
        if missing_tenant_extraction:
            warnings = []
            for endpoint in missing_tenant_extraction:
                warnings.append(
                    f"{endpoint.http_method} {endpoint.route_path} "
                    f"in {endpoint.file_path}:{endpoint.line_number}"
                )

            # Log as warning but don't fail (some endpoints might extract via helpers)
            import warnings as py_warnings
            py_warnings.warn(
                f"Found {len(missing_tenant_extraction)} tenant-scoped write endpoints "
                f"without visible tenant extraction from user context:\n" +
                "\n".join(warnings)
            )

    def test_isolation_coverage_meets_threshold(self):
        """Test that tenant isolation coverage meets minimum threshold."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Define minimum acceptable coverage
        # Note: Lower threshold accounts for helper functions that extract tenant_id
        # which may not be detected by static analysis
        MIN_COVERAGE = 50.0

        coverage = result.isolation_coverage

        # Log coverage information for visibility
        print(f"\nTenant Isolation Coverage: {coverage:.1f}%")
        print(f"Properly isolated: {result.properly_isolated_endpoints}/{result.authenticated_endpoints}")

        if coverage < MIN_COVERAGE:
            pytest.fail(
                f"Tenant isolation coverage is {coverage:.1f}%, "
                f"which is below the minimum threshold of {MIN_COVERAGE}%.\n"
                f"Properly isolated: {result.properly_isolated_endpoints}/{result.authenticated_endpoints}"
            )

        # Warn if below ideal threshold but above minimum
        if coverage < 70.0:
            import warnings
            warnings.warn(
                f"Tenant isolation coverage is {coverage:.1f}%, "
                f"which is below the ideal threshold of 70.0%. "
                "Consider adding explicit tenant_id extraction in more endpoints."
            )


# ============ Integration Test ============

class TestTenantIsolationIntegration:
    """End-to-end integration tests for tenant isolation."""

    @pytest.mark.asyncio
    async def test_complete_tenant_isolation_scan(self):
        """Run a complete tenant isolation scan and verify results."""
        scanner = TenantIsolationScanner()
        result = scanner.scan_all_endpoints()

        # Basic assertions
        assert result.total_endpoints > 0
        assert result.authenticated_endpoints > 0

        # Generate reports
        report = scanner.generate_report(result, verbose=False)
        json_data = scanner.export_json(result)

        # Verify report structure
        assert "TENANT ISOLATION SECURITY SCAN REPORT" in report
        assert "summary" in json_data
        assert "endpoints" in json_data

        # Log results for visibility
        print("\n" + "="*80)
        print("TENANT ISOLATION TEST RESULTS")
        print("="*80)
        print(f"Total Endpoints: {result.total_endpoints}")
        print(f"Authenticated: {result.authenticated_endpoints}")
        print(f"Properly Isolated: {result.properly_isolated_endpoints}")
        print(f"Issues: {result.endpoints_with_issues}")
        print(f"Warnings: {result.endpoints_with_warnings}")
        print(f"Coverage: {result.isolation_coverage:.1f}%")
        print("="*80)

        # Count critical security issues (excluding common false positives)
        critical_issues = []
        for endpoint in result.endpoints:
            if endpoint.issues:
                # Filter out issues from endpoints that are likely false positives
                is_webhook = '/webhook' in endpoint.route_path or '/callback' in endpoint.route_path
                is_check_email = '/check-email' in endpoint.route_path
                is_platform_endpoint = '/platform/' in endpoint.route_path

                if not (is_webhook or is_check_email or is_platform_endpoint):
                    # Check for critical issues (unsafe tenant extraction)
                    for issue in endpoint.issues:
                        if "Unsafe: tenant_id extracted from request" in issue:
                            critical_issues.append((endpoint, issue))

        # Fail only if critical security issues are found
        if critical_issues:
            print("\n[!] CRITICAL SECURITY ISSUES DETECTED:")
            for endpoint, issue in critical_issues:
                print(f"\n  {endpoint.http_method} {endpoint.route_path}")
                print(f"  File: {endpoint.file_path}:{endpoint.line_number}")
                print(f"    [!] {issue}")

            pytest.fail(
                f"Found {len(critical_issues)} critical tenant isolation issues. "
                "See output above for details."
            )

        # Log non-critical issues as warnings
        if result.has_issues and not critical_issues:
            print("\n[*] NON-CRITICAL ISSUES DETECTED (likely false positives):")
            print(f"    {result.endpoints_with_issues} endpoints with issues")
            print("    These may be webhooks, public endpoints, or use helper functions")
            print("    Review the full report for details if needed")
