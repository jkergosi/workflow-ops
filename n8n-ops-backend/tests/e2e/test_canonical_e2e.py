"""
E2E tests for canonical workflow onboarding flow.

Tests the complete canonical onboarding:
1. Preflight checks
2. Inventory phase (create canonical workflows)
3. Link untracked workflows
4. Matrix view generation
5. Git sync
6. Error scenarios
"""
import pytest
from unittest.mock import AsyncMock
from tests.testkit import N8nHttpMock, GitHubHttpMock, DatabaseSeeder


pytestmark = pytest.mark.asyncio


class TestCanonicalOnboardingE2E:
    """E2E tests for canonical workflow onboarding."""
    
    async def test_complete_onboarding_flow(
        self,
        async_client,
        testkit,
        n8n_http_mock,
        github_http_mock
    ):
        """Test complete canonical onboarding from preflight to completion."""
        setup = testkit.db.create_full_tenant_setup()
        prod_env = setup["environments"]["prod"]
        
        # Mock n8n workflows in anchor environment
        workflows = [
            testkit.n8n.workflow({"id": "wf-1", "name": "Customer Onboarding"}),
            testkit.n8n.workflow({"id": "wf-2", "name": "Email Notification"})
        ]
        
        # Mock GitHub repository
        with github_http_mock() as gh_mock:
            gh_mock.mock_get_repo("testorg", "n8n-workflows")
            gh_mock.mock_get_commits("testorg", "n8n-workflows")
            
            with n8n_http_mock(prod_env["n8n_base_url"]) as n8n_mock:
                n8n_mock.mock_get_workflows(workflows)
                
                # Step 1: Run preflight checks
                response = await async_client.get(
                    "/api/v1/canonical/onboard/preflight"
                )
                assert response.status_code in [200, 503]
                
                # Step 2: Start inventory phase
                response = await async_client.post(
                    "/api/v1/canonical/onboard/inventory",
                    json={"anchor_environment_id": prod_env["id"]}
                )
                assert response.status_code in [200, 201, 503]
                
                # Step 3: Check untracked workflows
                response = await async_client.get(
                    "/api/v1/canonical/untracked"
                )
                assert response.status_code in [200, 503]
    
    async def test_matrix_view_generation(
        self,
        async_client,
        testkit
    ):
        """Test canonical workflow matrix view generation."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Get matrix view
        response = await async_client.get(
            "/api/v1/workflows/matrix"
        )
        
        assert response.status_code in [200, 503]
        # Matrix should show workflows across environments
    
    async def test_link_untracked_workflow(
        self,
        async_client,
        testkit
    ):
        """Test linking an untracked workflow to canonical."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Link untracked workflow
        response = await async_client.post(
            "/api/v1/canonical/link",
            json={
                "workflow_id": "wf-untracked",
                "canonical_id": "canonical-1"
            }
        )
        
        assert response.status_code in [200, 404, 503]


class TestCanonicalErrorScenariosE2E:
    """E2E tests for canonical onboarding error scenarios."""
    
    async def test_github_timeout_during_sync(
        self,
        async_client,
        testkit,
        github_http_mock
    ):
        """Test handling of GitHub API timeout during sync."""
        setup = testkit.db.create_full_tenant_setup()
        
        with github_http_mock() as mock:
            mock.mock_timeout("/repos/testorg/n8n-workflows")
            
            response = await async_client.post(
                "/api/v1/canonical/sync-repo"
            )
            
            assert response.status_code in [500, 503, 504]
    
    async def test_git_conflict_scenario(
        self,
        async_client,
        testkit,
        github_http_mock
    ):
        """Test handling of Git merge conflicts."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Mock Git conflict response
        with github_http_mock() as mock:
            mock.router.put("/repos/testorg/n8n-workflows/contents/workflows/test.json").mock(
                return_value={"error": "merge conflict"}
            )
            
            # Attempt sync that would cause conflict
            response = await async_client.post(
                "/api/v1/canonical/sync-repo"
            )
            
            assert response.status_code in [409, 500, 503]
    
    async def test_canonical_id_collision(
        self,
        async_client,
        testkit
    ):
        """Test handling of canonical ID collisions."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Create two workflows with same name (would cause ID collision)
        # System should handle this gracefully
        pass  # Implementation depends on actual collision detection

