import pytest

from app.services.auth_service import get_current_user


def _override_user(user_info: dict):
    async def _dependency(credentials=None):
        return user_info

    return _dependency


@pytest.fixture
def non_admin_user(mock_developer_user, mock_tenant):
    return {
        "user": {
            "id": mock_developer_user["id"],
            "email": mock_developer_user["email"],
            "name": mock_developer_user["name"],
            "role": mock_developer_user["role"],
        },
        "tenant": {
            "id": mock_tenant["id"],
            "name": mock_tenant["name"],
            "subscription_tier": mock_tenant["subscription_tier"],
        },
    }


def test_promotions_execute_requires_admin(client, auth_headers, non_admin_user):
    client.app.dependency_overrides[get_current_user] = _override_user(non_admin_user)

    response = client.post(
        "/api/v1/promotions/execute/promo-1",
        json={"scheduled_at": None},
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_pipeline_write_requires_admin(client, auth_headers, non_admin_user):
    client.app.dependency_overrides[get_current_user] = _override_user(non_admin_user)

    body = {
        "name": "CI/CD",
        "description": "Test pipeline",
        "is_active": True,
        "environment_ids": [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ],
        "stages": [
            {
                "source_environment_id": "00000000-0000-0000-0000-000000000001",
                "target_environment_id": "00000000-0000-0000-0000-000000000002",
                "gates": {},
                "approvals": {"require_approval": False},
                "policy_flags": {},
            }
        ],
    }

    response = client.post("/api/v1/pipelines", json=body, headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_billing_checkout_requires_admin(client, auth_headers, non_admin_user):
    client.app.dependency_overrides[get_current_user] = _override_user(non_admin_user)

    body = {
        "price_id": "price_test_123",
        "success_url": "https://app.example.com/billing/success",
        "cancel_url": "https://app.example.com/billing/cancel",
        "billing_cycle": "monthly",
    }

    response = client.post("/api/v1/billing/checkout", json=body, headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_impersonation_requires_admin_role(client, auth_headers, non_admin_user):
    client.app.dependency_overrides[get_current_user] = _override_user(non_admin_user)

    response = client.post(
        "/api/v1/auth/impersonate/target-user-id", headers=auth_headers
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only administrators can impersonate other users"

