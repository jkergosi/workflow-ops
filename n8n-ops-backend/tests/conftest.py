"""
Pytest fixtures for N8N Ops Backend tests.
"""
import pytest
from typing import AsyncGenerator, Generator, Any, Dict
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Import the app
import sys
import os

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.services.auth_service import get_current_user
from app.core.platform_admin import require_platform_admin


# ============ Fixtures ============

# Default test data
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def mock_tenant() -> Dict[str, Any]:
    """Default mock tenant for tests."""
    return {
        "id": MOCK_TENANT_ID,
        "name": "Test Organization",
        "email": "test@example.com",
        "subscription_tier": "pro",
        "status": "active",
        "created_at": datetime(2024, 1, 1).isoformat(),
        "updated_at": datetime(2024, 1, 1).isoformat(),
    }


@pytest.fixture
def mock_admin_user(mock_tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Default mock admin user for tests."""
    return {
        "id": MOCK_USER_ID,
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "admin",
        "status": "active",
        "tenant_id": mock_tenant["id"],
        "created_at": datetime(2024, 1, 1).isoformat(),
        "updated_at": datetime(2024, 1, 1).isoformat(),
    }


@pytest.fixture
def mock_developer_user(mock_tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Mock developer user for permission testing."""
    return {
        "id": "00000000-0000-0000-0000-000000000003",
        "email": "dev@example.com",
        "name": "Developer User",
        "role": "developer",
        "status": "active",
        "tenant_id": mock_tenant["id"],
        "created_at": datetime(2024, 1, 1).isoformat(),
        "updated_at": datetime(2024, 1, 1).isoformat(),
    }


@pytest.fixture
def mock_viewer_user(mock_tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Mock viewer user for permission testing."""
    return {
        "id": "00000000-0000-0000-0000-000000000004",
        "email": "viewer@example.com",
        "name": "Viewer User",
        "role": "viewer",
        "status": "active",
        "tenant_id": mock_tenant["id"],
        "created_at": datetime(2024, 1, 1).isoformat(),
        "updated_at": datetime(2024, 1, 1).isoformat(),
    }


@pytest.fixture
def mock_auth_user(mock_admin_user: Dict[str, Any], mock_tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Mock authenticated user response from get_current_user."""
    return {
        "user": {
            "id": mock_admin_user["id"],
            "email": mock_admin_user["email"],
            "name": mock_admin_user["name"],
            "role": mock_admin_user["role"],
        },
        "tenant": {
            "id": mock_tenant["id"],
            "name": mock_tenant["name"],
            "subscription_tier": mock_tenant["subscription_tier"],
        }
    }


@pytest.fixture
def mock_environments() -> list[Dict[str, Any]]:
    """Mock environments for testing."""
    return [
        {
            "id": "env-1",
            "tenant_id": MOCK_TENANT_ID,
            "n8n_name": "Development",
            "n8n_type": "development",
            "n8n_base_url": "https://dev.n8n.example.com",
            "is_active": True,
            "workflow_count": 5,
            "created_at": datetime(2024, 1, 1).isoformat(),
            "updated_at": datetime(2024, 1, 1).isoformat(),
        },
        {
            "id": "env-2",
            "tenant_id": MOCK_TENANT_ID,
            "n8n_name": "Production",
            "n8n_type": "production",
            "n8n_base_url": "https://prod.n8n.example.com",
            "is_active": True,
            "workflow_count": 10,
            "created_at": datetime(2024, 1, 1).isoformat(),
            "updated_at": datetime(2024, 1, 1).isoformat(),
        },
    ]


@pytest.fixture
def mock_workflows() -> list[Dict[str, Any]]:
    """Mock workflows for testing."""
    return [
        {
            "id": "wf-1",
            "n8n_workflow_id": "n8n-1",
            "environment_id": "env-1",
            "tenant_id": MOCK_TENANT_ID,
            "name": "Test Workflow 1",
            "active": True,
            "workflow_data": {
                "name": "Test Workflow 1",
                "active": True,
                "nodes": [
                    {"id": "node-1", "type": "n8n-nodes-base.start", "name": "Start"},
                ],
                "connections": {},
            },
            "created_at": datetime(2024, 1, 1).isoformat(),
            "updated_at": datetime(2024, 1, 1).isoformat(),
        },
        {
            "id": "wf-2",
            "n8n_workflow_id": "n8n-2",
            "environment_id": "env-1",
            "tenant_id": MOCK_TENANT_ID,
            "name": "Test Workflow 2",
            "active": False,
            "workflow_data": {
                "name": "Test Workflow 2",
                "active": False,
                "nodes": [],
                "connections": {},
            },
            "created_at": datetime(2024, 1, 2).isoformat(),
            "updated_at": datetime(2024, 1, 2).isoformat(),
        },
    ]


@pytest.fixture
def mock_pipelines() -> list[Dict[str, Any]]:
    """Mock pipelines for testing."""
    return [
        {
            "id": "pipeline-1",
            "tenant_id": MOCK_TENANT_ID,
            "name": "Dev to Prod Pipeline",
            "description": "Promote workflows from development to production",
            "is_active": True,
            "environment_ids": ["env-1", "env-2"],
            "stages": [
                {
                    "source_environment_id": "env-1",
                    "target_environment_id": "env-2",
                    "gates": {
                        "require_clean_drift": True,
                        "run_pre_flight_validation": False,
                        "credentials_exist_in_target": False,
                        "nodes_supported_in_target": False,
                        "webhooks_available": False,
                        "target_environment_healthy": False,
                        "max_allowed_risk_level": "High",
                    },
                    "approvals": {
                        "require_approval": True,
                        "approver_role": "admin",
                        "approver_group": None,
                        "required_approvals": None,
                    },
                    "policy_flags": {
                        "allow_placeholder_credentials": False,
                        "allow_overwriting_hotfixes": False,
                        "allow_force_promotion_on_conflicts": False,
                    },
                },
            ],
            "last_modified_by": None,
            "last_modified_at": datetime(2024, 1, 1).isoformat(),
            "created_at": datetime(2024, 1, 1).isoformat(),
            "updated_at": datetime(2024, 1, 1).isoformat(),
        },
    ]


@pytest.fixture
def mock_db_service():
    """Create a mock database service."""
    mock = MagicMock()

    # Set up async method mocks
    mock.get_environments = AsyncMock(return_value=[])
    mock.get_environment = AsyncMock(return_value=None)
    mock.create_environment = AsyncMock()
    mock.update_environment = AsyncMock()
    mock.delete_environment = AsyncMock()

    mock.get_workflows = AsyncMock(return_value=[])
    mock.get_workflow = AsyncMock(return_value=None)
    mock.create_workflow = AsyncMock()
    mock.update_workflow = AsyncMock()
    mock.delete_workflow = AsyncMock()

    mock.get_pipelines = AsyncMock(return_value=[])
    mock.get_pipeline = AsyncMock(return_value=None)
    mock.create_pipeline = AsyncMock()
    mock.update_pipeline = AsyncMock()
    mock.delete_pipeline = AsyncMock()

    return mock


@pytest.fixture
def mock_n8n_client():
    """Create a mock N8N API client."""
    mock = MagicMock()

    mock.get_workflows = AsyncMock(return_value=[])
    mock.get_workflow = AsyncMock(return_value=None)
    mock.create_workflow = AsyncMock()
    mock.update_workflow = AsyncMock()
    mock.activate_workflow = AsyncMock()
    mock.deactivate_workflow = AsyncMock()
    mock.delete_workflow = AsyncMock()

    mock.get_executions = AsyncMock(return_value=[])
    mock.get_credentials = AsyncMock(return_value=[])
    mock.get_users = AsyncMock(return_value=[])
    mock.get_tags = AsyncMock(return_value=[])

    return mock


# ============ App and Client Fixtures ============


def create_auth_override(user_data: Dict[str, Any]):
    """Create an auth override function for testing."""
    async def mock_get_current_user(credentials=None):
        return user_data
    return mock_get_current_user


def create_platform_admin_override(user_info: Dict[str, Any]):
    """Create a platform admin override function for testing."""
    async def mock_require_platform_admin(allow_when_impersonating: bool = False):
        return {**user_info, "is_platform_admin": True, "actor_user_id": user_info.get("user", {}).get("id")}
    return mock_require_platform_admin


@pytest.fixture
def test_app(mock_auth_user: Dict[str, Any]) -> FastAPI:
    """Create a test FastAPI app with dependency overrides."""
    # Override authentication
    app.dependency_overrides[get_current_user] = create_auth_override(mock_auth_user)
    
    # Override require_platform_admin for all admin endpoints
    # Since require_platform_admin() is a factory, we need to patch is_platform_admin instead
    from unittest.mock import patch
    import app.core.platform_admin as platform_admin_module
    original_is_platform_admin = platform_admin_module.is_platform_admin
    
    def mock_is_platform_admin(user_id: str) -> bool:
        # Return True for test users
        if user_id == mock_auth_user.get("user", {}).get("id"):
            return True
        return original_is_platform_admin(user_id)
    
    platform_admin_module.is_platform_admin = mock_is_platform_admin

    yield app

    # Clean up overrides after test
    app.dependency_overrides.clear()
    platform_admin_module.is_platform_admin = original_is_platform_admin


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    with TestClient(test_app) as c:
        yield c


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for async tests."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Default auth headers for API tests."""
    return {
        "Authorization": f"Bearer dev-token-{MOCK_USER_ID}",
        "Content-Type": "application/json",
    }


# ============ Time Control Fixtures ============


@pytest.fixture
def frozen_time():
    """
    Fixture for time-based tests using freezegun.
    Usage:
        def test_something(frozen_time):
            with freezegun.freeze_time("2024-01-15 10:00:00"):
                # Test time-dependent code
    """
    import freezegun
    return freezegun


@pytest.fixture
def fixed_datetime():
    """Return a fixed datetime for deterministic tests."""
    return datetime(2024, 1, 15, 10, 0, 0)


# ============ Testkit Fixtures ============


@pytest.fixture
def n8n_factory():
    """N8N response factory for generating test data."""
    from tests.testkit import N8nResponseFactory
    return N8nResponseFactory


@pytest.fixture
def github_factory():
    """GitHub response factory for generating test data."""
    from tests.testkit import GitHubResponseFactory
    return GitHubResponseFactory


@pytest.fixture
def stripe_factory():
    """Stripe event factory for generating test data."""
    from tests.testkit import StripeEventFactory
    return StripeEventFactory


@pytest.fixture
def database_seeder():
    """Database seeder factory for creating test records."""
    from tests.testkit import DatabaseSeeder
    return DatabaseSeeder


@pytest.fixture
def testkit(n8n_factory, github_factory, stripe_factory, database_seeder):
    """
    Combined testkit fixture providing access to all factories.
    
    Usage:
        def test_something(testkit):
            workflow = testkit.n8n.workflow({"id": "123"})
            setup = testkit.db.create_full_tenant_setup()
    """
    class Testkit:
        n8n = n8n_factory
        github = github_factory
        stripe = stripe_factory
        db = database_seeder
    
    return Testkit


@pytest.fixture
def n8n_http_mock():
    """
    N8N HTTP mock fixture for mocking n8n API calls.
    
    Usage:
        def test_something(n8n_http_mock):
            mock = n8n_http_mock("https://dev.n8n.example.com")
            with mock:
                mock.mock_get_workflows([...])
                # Make API calls - they will be mocked
    """
    from tests.testkit import N8nHttpMock
    return N8nHttpMock


@pytest.fixture
def github_http_mock():
    """
    GitHub HTTP mock fixture for mocking GitHub API calls.
    
    Usage:
        def test_something(github_http_mock):
            mock = github_http_mock()
            with mock:
                mock.mock_get_repo("owner", "repo")
                # Make API calls - they will be mocked
    """
    from tests.testkit import GitHubHttpMock
    return GitHubHttpMock


@pytest.fixture
def stripe_webhook_mock():
    """
    Stripe webhook mock fixture for generating webhook signatures.
    
    Usage:
        def test_something(stripe_webhook_mock):
            mock = stripe_webhook_mock("whsec_test_secret")
            headers = mock.create_webhook_headers(payload)
    """
    from tests.testkit import StripeWebhookMock
    return StripeWebhookMock