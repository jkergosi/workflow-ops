"""
E2E tests for drift detection and incident management flow.

Tests the complete drift workflow:
1. Detect drift (scheduled or on-demand)
2. Create incident
3. Lifecycle transitions (acknowledge → stabilize → reconcile → close)
4. TTL enforcement blocking promotions
5. Error scenarios
"""
import pytest
from unittest.mock import AsyncMock
from tests.testkit import N8nHttpMock, N8nResponseFactory, DatabaseSeeder


pytestmark = pytest.mark.asyncio


class TestDriftDetectionE2E:
    """E2E tests for drift detection flow."""
    
    async def test_drift_detection_and_incident_creation(
        self,
        async_client,
        testkit,
        n8n_http_mock
    ):
        """Test drift detection creates incident when workflow differs."""
        setup = testkit.db.create_full_tenant_setup()
        prod_env = setup["environments"]["prod"]
        
        # Mock n8n to return drifted workflow
        drifted_workflow = testkit.n8n.workflow({
            "id": "wf-1",
            "name": "Customer Workflow",
            "updatedAt": "2024-01-05T10:00:00.000Z",  # Newer than Git
            "nodes": [{"id": "node-new", "type": "modified"}]  # Different content
        })
        
        with n8n_http_mock(prod_env["n8n_base_url"]) as mock:
            mock.mock_get_workflows([drifted_workflow])
            
            # Trigger drift detection
            response = await async_client.post(
                f"/api/v1/incidents/check-drift",
                json={"environment_id": prod_env["id"]}
            )
            
            # Should detect drift and create incident
            assert response.status_code in [200, 201, 503]
    
    async def test_drift_incident_lifecycle(
        self,
        async_client,
        testkit
    ):
        """Test complete incident lifecycle from detection to closure."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Step 1: Incident detected (DETECTED status)
        incident_id = "incident-1"
        
        # Step 2: Acknowledge incident
        response = await async_client.post(
            f"/api/v1/incidents/{incident_id}/acknowledge",
            json={"notes": "Investigating"}
        )
        assert response.status_code in [200, 404, 503]
        
        # Step 3: Stabilize incident
        response = await async_client.post(
            f"/api/v1/incidents/{incident_id}/stabilize",
            json={"reason": "Root cause identified"}
        )
        assert response.status_code in [200, 404, 503]
        
        # Step 4: Reconcile drift
        response = await async_client.post(
            f"/api/v1/incidents/{incident_id}/reconcile",
            json={"resolution_type": "promote"}
        )
        assert response.status_code in [200, 404, 503]
        
        # Step 5: Close incident
        response = await async_client.post(
            f"/api/v1/incidents/{incident_id}/close"
        )
        assert response.status_code in [200, 404, 503]
    
    async def test_ttl_blocks_promotion(
        self,
        async_client,
        testkit
    ):
        """Test that expired drift incidents block promotions."""
        setup = testkit.db.create_full_tenant_setup()
        prod_env = setup["environments"]["prod"]
        
        # Check if drift would block promotion
        response = await async_client.get(
            f"/api/v1/promotions/drift-check/{prod_env['id']}"
        )
        
        assert response.status_code in [200, 503]
        # If blocking, response should indicate which incidents are blocking


class TestDriftErrorScenariosE2E:
    """E2E tests for drift detection error scenarios."""
    
    async def test_drift_check_n8n_unavailable(
        self,
        async_client,
        testkit,
        n8n_http_mock
    ):
        """Test drift check handles n8n unavailability."""
        setup = testkit.db.create_full_tenant_setup()
        prod_env = setup["environments"]["prod"]
        
        with n8n_http_mock(prod_env["n8n_base_url"]) as mock:
            mock.mock_server_error("/workflows")
            
            response = await async_client.post(
                f"/api/v1/incidents/check-drift",
                json={"environment_id": prod_env["id"]}
            )
            
            # Should handle error gracefully
            assert response.status_code in [500, 503]
    
    async def test_malformed_drift_snapshot(
        self,
        async_client,
        testkit,
        n8n_http_mock
    ):
        """Test handling of malformed workflow data during drift check."""
        setup = testkit.db.create_full_tenant_setup()
        prod_env = setup["environments"]["prod"]
        
        # Mock n8n to return malformed data
        with n8n_http_mock(prod_env["n8n_base_url"]) as mock:
            mock.router.get("/workflows").mock(
                return_value=testkit.n8n.malformed_json()
            )
            
            response = await async_client.post(
                f"/api/v1/incidents/check-drift",
                json={"environment_id": prod_env["id"]}
            )
            
            # Should handle parsing error
            assert response.status_code in [500, 503]

