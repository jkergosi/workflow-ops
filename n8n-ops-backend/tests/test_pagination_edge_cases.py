"""
Comprehensive tests for paginated endpoints - edge cases.

Tests for T016: Test all updated paginated endpoints with edge cases:
- Empty results
- Page beyond total
- Invalid page_size

Endpoints tested:
1. GET /canonical-workflows (page, page_size, include_deleted)
2. GET /workflow-mappings (page, page_size, environment_id, canonical_id, status)
3. GET /diff-states (page, page_size, source_env_id, target_env_id, canonical_id)
4. GET /restore/snapshots/{workflow_id} (page, page_size)
5. GET /billing/invoices (page, page_size)
6. GET /billing/payment-history (page, page_size)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from fastapi import status


# Mock constants
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_ID = "00000000-0000-0000-0000-000000000002"
MOCK_ENVIRONMENT_ID = "00000000-0000-0000-0000-000000000003"
MOCK_CANONICAL_ID = "canonical-test-001"
MOCK_WORKFLOW_ID = "workflow-test-001"


class TestCanonicalWorkflowsPagination:
    """Tests for GET /api/v1/canonical-workflows pagination edge cases."""

    def test_canonical_workflows_empty_results(self, client, auth_headers):
        """Should return empty results with valid pagination metadata when no workflows exist."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            # Mock query chain for empty results
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            # Mock get_workflow_mappings for collision detection
            mock_db.get_workflow_mappings = AsyncMock(return_value=[])

            response = client.get(
                "/api/v1/canonical/canonical-workflows?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pagination envelope structure
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "pageSize" in data
            assert "totalPages" in data
            assert "hasMore" in data

            # Verify empty results
            assert data["items"] == []
            assert data["total"] == 0
            assert data["page"] == 1
            assert data["pageSize"] == 50
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_canonical_workflows_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            # Mock query chain - page 10 when only 2 pages exist
            mock_response = MagicMock()
            mock_response.data = []  # No data for page 10
            mock_response.count = 75  # Total of 75 items (2 pages with page_size=50)

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            # Mock get_workflow_mappings for collision detection
            mock_db.get_workflow_mappings = AsyncMock(return_value=[])

            response = client.get(
                "/api/v1/canonical/canonical-workflows?page=10&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should return empty items but with correct total metadata
            assert data["items"] == []
            assert data["total"] == 75
            assert data["page"] == 10
            assert data["pageSize"] == 50
            assert data["totalPages"] == 2  # ceil(75 / 50) = 2
            assert data["hasMore"] is False

    def test_canonical_workflows_invalid_page_size_too_large(self, client, auth_headers):
        """Should cap page_size to MAX_PAGE_SIZE (100) when larger value requested."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            # Mock get_workflow_mappings for collision detection
            mock_db.get_workflow_mappings = AsyncMock(return_value=[])

            # Request page_size=500 (should be capped to 100)
            response = client.get(
                "/api/v1/canonical/canonical-workflows?page=1&page_size=500",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be capped to MAX_PAGE_SIZE=100
            assert data["pageSize"] == 100

    def test_canonical_workflows_invalid_page_size_zero(self, client, auth_headers):
        """Should default to minimum page_size (1) when zero or negative value requested."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            # Mock get_workflow_mappings for collision detection
            mock_db.get_workflow_mappings = AsyncMock(return_value=[])

            # Request page_size=0 (should be normalized to 1)
            response = client.get(
                "/api/v1/canonical/canonical-workflows?page=1&page_size=0",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be normalized to MIN_PAGE_SIZE=1
            assert data["pageSize"] == 1


class TestWorkflowMappingsPagination:
    """Tests for GET /api/v1/workflow-mappings pagination edge cases."""

    def test_workflow_mappings_empty_results(self, client, auth_headers):
        """Should return empty results with valid pagination metadata when no mappings exist."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/canonical/workflow-mappings?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_workflow_mappings_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 120  # 3 pages with page_size=50

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/canonical/workflow-mappings?page=5&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 120
            assert data["page"] == 5
            assert data["totalPages"] == 3
            assert data["hasMore"] is False

    def test_workflow_mappings_with_filters(self, client, auth_headers):
        """Should handle empty results with filter parameters."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            # Build a complete mock chain with proper return values for filter queries
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            # Build the query chain properly
            mock_range = MagicMock()
            mock_range.return_value = mock_query

            mock_order2 = MagicMock()
            mock_order2.return_value.range.return_value = mock_query

            mock_order1 = MagicMock()
            mock_order1.return_value.order.return_value.range.return_value = mock_query

            # With environment_id filter, we have: .select().eq(tenant).eq(env_id).order().order().range()
            mock_eq2 = MagicMock()
            mock_eq2.return_value.order.return_value.order.return_value.range.return_value = mock_query

            mock_eq1 = MagicMock()
            mock_eq1.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query

            mock_select = MagicMock()
            mock_select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query

            mock_db.client.table.return_value = mock_table

            response = client.get(
                f"/api/v1/canonical/workflow-mappings?page=1&page_size=50&environment_id={MOCK_ENVIRONMENT_ID}",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0


class TestDiffStatesPagination:
    """Tests for GET /api/v1/diff-states pagination edge cases."""

    def test_diff_states_empty_results(self, client, auth_headers):
        """Should return empty results when no diff states exist."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/canonical/diff-states?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_diff_states_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 25  # 1 page with page_size=50

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/canonical/diff-states?page=3&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 25
            assert data["page"] == 3
            assert data["totalPages"] == 1
            assert data["hasMore"] is False

    def test_diff_states_invalid_page_size(self, client, auth_headers):
        """Should cap page_size to MAX_PAGE_SIZE."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/canonical/diff-states?page=1&page_size=999",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be capped to MAX_PAGE_SIZE=100
            assert data["pageSize"] == 100


class TestRestoreSnapshotsPagination:
    """Tests for GET /api/v1/restore/snapshots/{workflow_id} pagination edge cases."""

    def test_snapshots_empty_results(self, client, auth_headers):
        """Should return empty results when no snapshots exist for workflow."""
        with patch("app.api.endpoints.restore.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                f"/api/v1/restore/snapshots/{MOCK_WORKFLOW_ID}?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_snapshots_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.restore.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 10  # 1 page with page_size=50

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                f"/api/v1/restore/snapshots/{MOCK_WORKFLOW_ID}?page=5&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 10
            assert data["page"] == 5
            assert data["totalPages"] == 1
            assert data["hasMore"] is False

    def test_snapshots_invalid_page_size_too_large(self, client, auth_headers):
        """Should cap page_size to MAX_PAGE_SIZE."""
        with patch("app.api.endpoints.restore.db_service") as mock_db:
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
            mock_db.client.table.return_value = mock_table

            response = client.get(
                f"/api/v1/restore/snapshots/{MOCK_WORKFLOW_ID}?page=1&page_size=200",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["pageSize"] == 100


class TestBillingInvoicesPagination:
    """Tests for GET /api/v1/billing/invoices pagination edge cases."""

    def test_invoices_empty_results_no_subscription(self, client, auth_headers):
        """Should return empty results when tenant has no subscription."""
        with patch("app.api.endpoints.billing.db_service") as mock_db, \
             patch("app.api.endpoints.billing.stripe_service") as mock_stripe:
            # Mock no subscription found
            mock_response = MagicMock()
            mock_response.data = None
            mock_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response

            response = client.get(
                "/api/v1/billing/invoices?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_invoices_empty_results_no_invoices(self, client, auth_headers):
        """Should return empty results when subscription exists but has no invoices."""
        with patch("app.api.endpoints.billing.db_service") as mock_db, \
             patch("app.api.endpoints.billing.stripe_service") as mock_stripe:
            # Mock subscription found
            mock_response = MagicMock()
            mock_response.data = {"stripe_customer_id": "cus_test123"}
            mock_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response

            # Mock Stripe returns no invoices
            mock_stripe.list_invoices = AsyncMock(return_value={
                "data": [],
                "has_more": False,
                "total_count": 0
            })

            response = client.get(
                "/api/v1/billing/invoices?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["hasMore"] is False

    def test_invoices_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.billing.db_service") as mock_db, \
             patch("app.api.endpoints.billing.stripe_service") as mock_stripe:
            # Mock subscription found
            mock_response = MagicMock()
            mock_response.data = {"stripe_customer_id": "cus_test123"}
            mock_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response

            # Mock Stripe - page 5 when only 2 pages exist (75 total, 50 per page)
            # Note: Stripe list_invoices returns a dict, not total_count separately
            # The endpoint calculates total from the response
            mock_stripe.list_invoices = AsyncMock(return_value={
                "data": [],  # Empty results for page beyond total
                "has_more": False  # No more pages available
            })

            response = client.get(
                "/api/v1/billing/invoices?page=5&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # When Stripe returns no data and has_more=False on a high page number,
            # the endpoint should still return valid pagination structure
            assert data["items"] == []
            # Total will be 0 since Stripe returned no data (endpoint infers from Stripe response)
            assert data["total"] >= 0
            assert data["page"] == 5

    def test_invoices_invalid_page_size(self, client, auth_headers):
        """Should cap page_size to MAX_PAGE_SIZE."""
        with patch("app.api.endpoints.billing.db_service") as mock_db, \
             patch("app.api.endpoints.billing.stripe_service") as mock_stripe:
            # Mock subscription found
            mock_response = MagicMock()
            mock_response.data = {"stripe_customer_id": "cus_test123"}
            mock_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response

            # Mock Stripe
            mock_stripe.list_invoices = AsyncMock(return_value={
                "data": [],
                "has_more": False,
                "total_count": 0
            })

            response = client.get(
                "/api/v1/billing/invoices?page=1&page_size=1000",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be capped to MAX_PAGE_SIZE=100
            assert data["pageSize"] == 100


class TestBillingPaymentHistoryPagination:
    """Tests for GET /api/v1/billing/payment-history pagination edge cases."""

    def test_payment_history_empty_results(self, client, auth_headers):
        """Should return empty results when no payment history exists."""
        with patch("app.api.endpoints.billing.db_service") as mock_db:
            # Mock count query
            mock_count_response = MagicMock()
            mock_count_response.count = 0

            # Mock data query
            mock_data_response = MagicMock()
            mock_data_response.data = []

            mock_table = MagicMock()
            # Count query chain
            mock_table.select.return_value.eq.return_value.execute.return_value = mock_count_response
            # Data query chain (needs to be different instance)
            mock_table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_data_response

            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/billing/payment-history?page=1&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["hasMore"] is False

    def test_payment_history_page_beyond_total(self, client, auth_headers):
        """Should return empty items when requesting page beyond total pages."""
        with patch("app.api.endpoints.billing.db_service") as mock_db:
            # Mock count query
            mock_count_response = MagicMock()
            mock_count_response.count = 30  # 1 page with page_size=50

            # Mock data query
            mock_data_response = MagicMock()
            mock_data_response.data = []

            mock_table = MagicMock()
            # Count query chain
            mock_table.select.return_value.eq.return_value.execute.return_value = mock_count_response
            # Data query chain
            mock_table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_data_response

            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/billing/payment-history?page=3&page_size=50",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["items"] == []
            assert data["total"] == 30
            assert data["page"] == 3
            assert data["totalPages"] == 1
            assert data["hasMore"] is False

    def test_payment_history_invalid_page_size_too_large(self, client, auth_headers):
        """Should cap page_size to MAX_PAGE_SIZE."""
        with patch("app.api.endpoints.billing.db_service") as mock_db:
            # Mock count query
            mock_count_response = MagicMock()
            mock_count_response.count = 0

            # Mock data query
            mock_data_response = MagicMock()
            mock_data_response.data = []

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.execute.return_value = mock_count_response
            mock_table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_data_response

            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/billing/payment-history?page=1&page_size=500",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be capped to MAX_PAGE_SIZE=100
            assert data["pageSize"] == 100

    def test_payment_history_invalid_page_size_zero(self, client, auth_headers):
        """Should normalize to minimum page_size when zero or negative value requested."""
        with patch("app.api.endpoints.billing.db_service") as mock_db:
            # Mock count query
            mock_count_response = MagicMock()
            mock_count_response.count = 0

            # Mock data query
            mock_data_response = MagicMock()
            mock_data_response.data = []

            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.execute.return_value = mock_count_response
            mock_table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_data_response

            mock_db.client.table.return_value = mock_table

            response = client.get(
                "/api/v1/billing/payment-history?page=1&page_size=0",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be normalized to MIN_PAGE_SIZE=1
            assert data["pageSize"] == 1


class TestPaginationConsistency:
    """Cross-endpoint tests to verify consistent pagination behavior."""

    def test_all_endpoints_return_standard_envelope(self, client, auth_headers):
        """Verify all paginated endpoints return the standard pagination envelope structure."""
        with patch("app.api.endpoints.canonical_workflows.db_service") as mock_canonical_db, \
             patch("app.api.endpoints.restore.db_service") as mock_restore_db, \
             patch("app.api.endpoints.billing.db_service") as mock_billing_db, \
             patch("app.api.endpoints.billing.stripe_service") as mock_stripe:

            # Setup standard mock response for all endpoints
            mock_response = MagicMock()
            mock_response.data = []
            mock_response.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_response

            # Setup mock chains for each endpoint type
            for mock_db in [mock_canonical_db, mock_restore_db, mock_billing_db]:
                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
                mock_table.select.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
                mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value = mock_query
                mock_table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_response
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_response
                mock_db.client.table.return_value = mock_table

            # Mock for canonical workflows collision detection
            mock_canonical_db.get_workflow_mappings = AsyncMock(return_value=[])

            # Mock for billing invoices
            mock_billing_response = MagicMock()
            mock_billing_response.data = None
            mock_billing_db.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_billing_response

            endpoints = [
                "/api/v1/canonical/canonical-workflows",
                "/api/v1/canonical/workflow-mappings",
                "/api/v1/canonical/diff-states",
                f"/api/v1/restore/snapshots/{MOCK_WORKFLOW_ID}",
                "/api/v1/billing/invoices",
                "/api/v1/billing/payment-history",
            ]

            for endpoint in endpoints:
                response = client.get(f"{endpoint}?page=1&page_size=50", headers=auth_headers)
                assert response.status_code == status.HTTP_200_OK, f"Failed for {endpoint}"

                data = response.json()

                # Verify standard pagination envelope
                assert "items" in data, f"Missing 'items' in {endpoint}"
                assert "total" in data, f"Missing 'total' in {endpoint}"
                assert "page" in data, f"Missing 'page' in {endpoint}"
                assert "pageSize" in data, f"Missing 'pageSize' in {endpoint}"
                assert "totalPages" in data, f"Missing 'totalPages' in {endpoint}"
                assert "hasMore" in data, f"Missing 'hasMore' in {endpoint}"

                # Verify types
                assert isinstance(data["items"], list), f"Invalid 'items' type in {endpoint}"
                assert isinstance(data["total"], int), f"Invalid 'total' type in {endpoint}"
                assert isinstance(data["page"], int), f"Invalid 'page' type in {endpoint}"
                assert isinstance(data["pageSize"], int), f"Invalid 'pageSize' type in {endpoint}"
                assert isinstance(data["totalPages"], int), f"Invalid 'totalPages' type in {endpoint}"
                assert isinstance(data["hasMore"], bool), f"Invalid 'hasMore' type in {endpoint}"

    def test_pagination_metadata_calculations_consistent(self, client, auth_headers):
        """Verify pagination metadata calculations are consistent across all endpoints."""
        test_cases = [
            # (total, page_size, expected_total_pages)
            (0, 50, 0),      # No items
            (1, 50, 1),      # One item
            (50, 50, 1),     # Exactly one page
            (51, 50, 2),     # One item over
            (100, 50, 2),    # Exactly two pages
            (101, 50, 3),    # One item over two pages
            (75, 50, 2),     # Partial second page
        ]

        for total, page_size, expected_total_pages in test_cases:
            with patch("app.api.endpoints.canonical_workflows.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = []
                mock_response.count = total

                mock_query = MagicMock()
                mock_query.execute.return_value = mock_response

                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.is_.return_value.order.return_value.range.return_value = mock_query
                mock_db.client.table.return_value = mock_table

                # Mock get_workflow_mappings for collision detection
                mock_db.get_workflow_mappings = AsyncMock(return_value=[])

                response = client.get(
                    f"/api/v1/canonical/canonical-workflows?page=1&page_size={page_size}",
                    headers=auth_headers
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()

                assert data["total"] == total, f"Failed for total={total}, page_size={page_size}"
                assert data["totalPages"] == expected_total_pages, f"Expected {expected_total_pages} pages for total={total}, page_size={page_size}, got {data['totalPages']}"

                # Verify hasMore is correct
                if total == 0:
                    assert data["hasMore"] is False
                elif expected_total_pages > 1:
                    assert data["hasMore"] is True  # On page 1 with multiple pages
                else:
                    assert data["hasMore"] is False  # On page 1 of 1
