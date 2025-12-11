"""Tests for the entitlements system (Phase 1 and Phase 2)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.services.entitlements_service import EntitlementsService, entitlements_service


class TestEntitlementsService:
    """Tests for EntitlementsService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        service = EntitlementsService()
        service.clear_cache()
        return service

    @pytest.fixture
    def mock_tenant_plan(self):
        """Mock tenant plan data."""
        return {
            "plan_id": "plan-pro",
            "plan_name": "pro",
            "plan_display_name": "Pro Plan",
            "entitlements_version": 1
        }

    @pytest.fixture
    def mock_plan_features_pro(self):
        """Mock plan features for pro plan."""
        return [
            {
                "feature_name": "snapshots_enabled",
                "feature_type": "flag",
                "value": {"enabled": True}
            },
            {
                "feature_name": "workflow_ci_cd",
                "feature_type": "flag",
                "value": {"enabled": True}
            },
            {
                "feature_name": "workflow_limits",
                "feature_type": "limit",
                "value": {"value": 200}
            },
        ]

    @pytest.fixture
    def mock_plan_features_free(self):
        """Mock plan features for free plan."""
        return [
            {
                "feature_name": "snapshots_enabled",
                "feature_type": "flag",
                "value": {"enabled": True}
            },
            {
                "feature_name": "workflow_ci_cd",
                "feature_type": "flag",
                "value": {"enabled": False}
            },
            {
                "feature_name": "workflow_limits",
                "feature_type": "limit",
                "value": {"value": 10}
            },
        ]

    # ==================== get_tenant_entitlements ====================

    @pytest.mark.asyncio
    async def test_get_tenant_entitlements_returns_free_defaults_when_no_plan(
        self, service
    ):
        """Test that free plan defaults are returned when tenant has no plan."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan:
            mock_get_plan.return_value = None

            result = await service.get_tenant_entitlements("tenant-123")

            assert result["plan_name"] == "free"
            assert result["features"]["snapshots_enabled"] is True
            assert result["features"]["workflow_ci_cd"] is False
            assert result["features"]["workflow_limits"] == 10

    @pytest.mark.asyncio
    async def test_get_tenant_entitlements_returns_plan_features(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test that correct features are returned for tenant's plan."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            result = await service.get_tenant_entitlements("tenant-123")

            assert result["plan_id"] == "plan-pro"
            assert result["plan_name"] == "pro"
            assert result["features"]["snapshots_enabled"] is True
            assert result["features"]["workflow_ci_cd"] is True
            assert result["features"]["workflow_limits"] == 200

    @pytest.mark.asyncio
    async def test_get_tenant_entitlements_uses_cache(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test that entitlements are cached and reused."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            # First call populates cache
            await service.get_tenant_entitlements("tenant-123")
            # Second call should use cache
            await service.get_tenant_entitlements("tenant-123")

            # _get_tenant_plan called twice, _get_plan_features only once
            assert mock_get_plan.call_count == 2
            assert mock_get_features.call_count == 1

    # ==================== has_flag ====================

    @pytest.mark.asyncio
    async def test_has_flag_returns_true_when_enabled(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test that has_flag returns True when feature is enabled."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            result = await service.has_flag("tenant-123", "workflow_ci_cd")
            assert result is True

    @pytest.mark.asyncio
    async def test_has_flag_returns_false_when_disabled(
        self, service, mock_tenant_plan, mock_plan_features_free
    ):
        """Test that has_flag returns False when feature is disabled."""
        mock_tenant_plan["plan_name"] = "free"
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_free

            result = await service.has_flag("tenant-123", "workflow_ci_cd")
            assert result is False

    # ==================== get_limit ====================

    @pytest.mark.asyncio
    async def test_get_limit_returns_correct_value(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test that get_limit returns the correct limit value."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            result = await service.get_limit("tenant-123", "workflow_limits")
            assert result == 200

    # ==================== check_flag ====================

    @pytest.mark.asyncio
    async def test_check_flag_returns_allowed_when_enabled(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test check_flag returns (True, '') when feature is enabled."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            allowed, message = await service.check_flag("tenant-123", "workflow_ci_cd")
            assert allowed is True
            assert message == ""

    @pytest.mark.asyncio
    async def test_check_flag_returns_denied_with_message_when_disabled(
        self, service, mock_tenant_plan, mock_plan_features_free
    ):
        """Test check_flag returns (False, message) when feature is disabled."""
        mock_tenant_plan["plan_name"] = "free"
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_free

            allowed, message = await service.check_flag("tenant-123", "workflow_ci_cd")
            assert allowed is False
            assert "Workflow CI/CD" in message
            assert "Pro" in message

    # ==================== check_limit ====================

    @pytest.mark.asyncio
    async def test_check_limit_returns_allowed_when_under_limit(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test check_limit returns allowed when under limit."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            allowed, message, current, limit = await service.check_limit(
                "tenant-123", "workflow_limits", 50
            )
            assert allowed is True
            assert message == ""
            assert current == 50
            assert limit == 200

    @pytest.mark.asyncio
    async def test_check_limit_returns_denied_when_at_limit(
        self, service, mock_tenant_plan, mock_plan_features_free
    ):
        """Test check_limit returns denied when at limit."""
        mock_tenant_plan["plan_name"] = "free"
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_free

            allowed, message, current, limit = await service.check_limit(
                "tenant-123", "workflow_limits", 10
            )
            assert allowed is False
            assert "limit reached" in message
            assert current == 10
            assert limit == 10

    # ==================== enforce_flag ====================

    @pytest.mark.asyncio
    async def test_enforce_flag_does_not_raise_when_enabled(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test enforce_flag doesn't raise when feature is enabled."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            # Should not raise
            await service.enforce_flag("tenant-123", "workflow_ci_cd")

    @pytest.mark.asyncio
    async def test_enforce_flag_raises_403_when_disabled(
        self, service, mock_tenant_plan, mock_plan_features_free
    ):
        """Test enforce_flag raises 403 HTTPException when feature is disabled."""
        mock_tenant_plan["plan_name"] = "free"
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_free

            with pytest.raises(HTTPException) as exc_info:
                await service.enforce_flag("tenant-123", "workflow_ci_cd")

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail["error"] == "feature_not_available"
            assert exc_info.value.detail["feature"] == "workflow_ci_cd"

    # ==================== enforce_limit ====================

    @pytest.mark.asyncio
    async def test_enforce_limit_does_not_raise_when_under_limit(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test enforce_limit doesn't raise when under limit."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            # Should not raise
            await service.enforce_limit("tenant-123", "workflow_limits", 50)

    @pytest.mark.asyncio
    async def test_enforce_limit_raises_403_when_at_limit(
        self, service, mock_tenant_plan, mock_plan_features_free
    ):
        """Test enforce_limit raises 403 HTTPException when at limit."""
        mock_tenant_plan["plan_name"] = "free"
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_free

            with pytest.raises(HTTPException) as exc_info:
                await service.enforce_limit("tenant-123", "workflow_limits", 10)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail["error"] == "limit_reached"
            assert exc_info.value.detail["feature"] == "workflow_limits"
            assert exc_info.value.detail["current_count"] == 10
            assert exc_info.value.detail["limit"] == 10

    # ==================== clear_cache ====================

    @pytest.mark.asyncio
    async def test_clear_cache_clears_all_entries(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test clear_cache clears all cache entries."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            # Populate cache
            await service.get_tenant_entitlements("tenant-123")
            await service.get_tenant_entitlements("tenant-456")

            # Clear all
            service.clear_cache()

            # Cache should be empty, so _get_plan_features should be called again
            await service.get_tenant_entitlements("tenant-123")

            # Should be called 3 times (2 initial + 1 after clear)
            assert mock_get_features.call_count == 3

    @pytest.mark.asyncio
    async def test_clear_cache_clears_specific_tenant(
        self, service, mock_tenant_plan, mock_plan_features_pro
    ):
        """Test clear_cache clears only specific tenant entries."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan
            mock_get_features.return_value = mock_plan_features_pro

            # Populate cache for two tenants
            await service.get_tenant_entitlements("tenant-123")
            await service.get_tenant_entitlements("tenant-456")

            # Clear only tenant-123
            service.clear_cache("tenant-123")

            # Call again - tenant-123 should need fresh fetch
            await service.get_tenant_entitlements("tenant-123")
            # But tenant-456 should still use cache
            await service.get_tenant_entitlements("tenant-456")

            # Should be called 3 times (tenant-123 twice, tenant-456 once)
            assert mock_get_features.call_count == 3

    # ==================== Free plan defaults ====================

    @pytest.mark.asyncio
    async def test_free_plan_defaults_values(self, service):
        """Test that free plan defaults have correct values."""
        defaults = await service._get_free_plan_defaults()

        assert defaults["plan_name"] == "free"
        assert defaults["plan_id"] is None
        assert defaults["entitlements_version"] == 0
        assert defaults["features"]["snapshots_enabled"] is True
        assert defaults["features"]["workflow_ci_cd"] is False
        assert defaults["features"]["workflow_limits"] == 10


class TestEntitlementsServiceSingleton:
    """Tests for the singleton instance."""

    def test_singleton_instance_exists(self):
        """Test that singleton instance is created."""
        assert entitlements_service is not None
        assert isinstance(entitlements_service, EntitlementsService)


class TestPhase2Features:
    """Tests for Phase 2 feature catalog."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        service = EntitlementsService()
        service.clear_cache()
        return service

    @pytest.fixture
    def mock_pro_plan_phase2(self):
        """Mock plan features for pro plan with Phase 2 features."""
        return [
            {"feature_name": "environment_basic", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "environment_health", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "environment_diff", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "environment_limits", "feature_type": "limit", "value": {"value": 10}},
            {"feature_name": "workflow_read", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "workflow_push", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "workflow_dirty_check", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "workflow_ci_cd", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "workflow_ci_cd_approval", "feature_type": "flag", "value": {"enabled": False}},
            {"feature_name": "workflow_limits", "feature_type": "limit", "value": {"value": 200}},
            {"feature_name": "snapshots_enabled", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "snapshots_auto", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "snapshots_history", "feature_type": "limit", "value": {"value": 30}},
            {"feature_name": "snapshots_export", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "observability_basic", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "observability_alerts", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "observability_alerts_advanced", "feature_type": "flag", "value": {"enabled": False}},
            {"feature_name": "observability_logs", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "observability_limits", "feature_type": "limit", "value": {"value": 30}},
            {"feature_name": "rbac_basic", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "rbac_advanced", "feature_type": "flag", "value": {"enabled": False}},
            {"feature_name": "audit_logs", "feature_type": "flag", "value": {"enabled": True}},
            {"feature_name": "audit_export", "feature_type": "flag", "value": {"enabled": False}},
            {"feature_name": "sso_saml", "feature_type": "flag", "value": {"enabled": False}},
            {"feature_name": "support_priority", "feature_type": "flag", "value": {"enabled": True}},
        ]

    @pytest.fixture
    def mock_tenant_plan_pro(self):
        """Mock tenant plan data for pro."""
        return {
            "plan_id": "plan-pro",
            "plan_name": "pro",
            "plan_display_name": "Pro Plan",
            "entitlements_version": 2
        }

    # ==================== Phase 2 Feature Tests ====================

    @pytest.mark.asyncio
    async def test_free_plan_defaults_has_all_phase2_features(self, service):
        """Test that free plan defaults include all 25 Phase 2 features."""
        defaults = await service._get_free_plan_defaults()
        features = defaults["features"]

        # Environment features
        assert "environment_basic" in features
        assert features["environment_basic"] is True
        assert "environment_health" in features
        assert features["environment_health"] is False
        assert "environment_diff" in features
        assert features["environment_diff"] is False
        assert "environment_limits" in features
        assert features["environment_limits"] == 2

        # Workflow features
        assert "workflow_read" in features
        assert features["workflow_read"] is True
        assert "workflow_push" in features
        assert features["workflow_push"] is True
        assert "workflow_dirty_check" in features
        assert features["workflow_dirty_check"] is False
        assert "workflow_ci_cd" in features
        assert features["workflow_ci_cd"] is False
        assert "workflow_ci_cd_approval" in features
        assert features["workflow_ci_cd_approval"] is False
        assert "workflow_limits" in features
        assert features["workflow_limits"] == 10

        # Snapshot features
        assert "snapshots_enabled" in features
        assert features["snapshots_enabled"] is True
        assert "snapshots_auto" in features
        assert features["snapshots_auto"] is False
        assert "snapshots_history" in features
        assert features["snapshots_history"] == 5
        assert "snapshots_export" in features
        assert features["snapshots_export"] is False

        # Observability features
        assert "observability_basic" in features
        assert features["observability_basic"] is True
        assert "observability_alerts" in features
        assert features["observability_alerts"] is False
        assert "observability_alerts_advanced" in features
        assert features["observability_alerts_advanced"] is False
        assert "observability_logs" in features
        assert features["observability_logs"] is False
        assert "observability_limits" in features
        assert features["observability_limits"] == 7

        # RBAC features
        assert "rbac_basic" in features
        assert features["rbac_basic"] is True
        assert "rbac_advanced" in features
        assert features["rbac_advanced"] is False
        assert "audit_logs" in features
        assert features["audit_logs"] is False
        assert "audit_export" in features
        assert features["audit_export"] is False

        # Agency features
        assert "agency_enabled" in features
        assert features["agency_enabled"] is False
        assert "agency_client_management" in features
        assert features["agency_client_management"] is False
        assert "agency_whitelabel" in features
        assert features["agency_whitelabel"] is False
        assert "agency_client_limits" in features
        assert features["agency_client_limits"] == 0

        # Enterprise features
        assert "sso_saml" in features
        assert features["sso_saml"] is False
        assert "support_priority" in features
        assert features["support_priority"] is False
        assert "data_residency" in features
        assert features["data_residency"] is False

    def test_feature_display_names_has_all_features(self, service):
        """Test that FEATURE_DISPLAY_NAMES contains all Phase 2 features."""
        from app.services.entitlements_service import FEATURE_DISPLAY_NAMES

        expected_features = [
            # Phase 1
            "snapshots_enabled", "workflow_ci_cd", "workflow_limits",
            # Phase 2 - Environment
            "environment_basic", "environment_health", "environment_diff", "environment_limits",
            # Phase 2 - Workflows
            "workflow_read", "workflow_push", "workflow_dirty_check", "workflow_ci_cd_approval",
            # Phase 2 - Snapshots
            "snapshots_auto", "snapshots_history", "snapshots_export",
            # Phase 2 - Observability
            "observability_basic", "observability_alerts", "observability_alerts_advanced",
            "observability_logs", "observability_limits",
            # Phase 2 - RBAC
            "rbac_basic", "rbac_advanced", "audit_logs", "audit_export",
            # Phase 2 - Agency
            "agency_enabled", "agency_client_management", "agency_whitelabel", "agency_client_limits",
            # Phase 2 - Enterprise
            "sso_saml", "support_priority", "data_residency",
        ]

        for feature in expected_features:
            assert feature in FEATURE_DISPLAY_NAMES, f"Missing display name for {feature}"
            assert isinstance(FEATURE_DISPLAY_NAMES[feature], str)
            assert len(FEATURE_DISPLAY_NAMES[feature]) > 0

    def test_feature_required_plans_has_all_features(self, service):
        """Test that FEATURE_REQUIRED_PLANS contains all Phase 2 features."""
        from app.services.entitlements_service import FEATURE_REQUIRED_PLANS

        expected_features = [
            "snapshots_enabled", "workflow_ci_cd", "workflow_limits",
            "environment_basic", "environment_health", "environment_diff",
            "workflow_read", "workflow_push", "workflow_dirty_check", "workflow_ci_cd_approval",
            "snapshots_auto", "snapshots_export",
            "observability_basic", "observability_alerts", "observability_alerts_advanced", "observability_logs",
            "rbac_basic", "rbac_advanced", "audit_logs", "audit_export",
            "agency_enabled", "agency_client_management", "agency_whitelabel",
            "sso_saml", "support_priority", "data_residency",
        ]

        for feature in expected_features:
            assert feature in FEATURE_REQUIRED_PLANS, f"Missing required plan for {feature}"
            assert FEATURE_REQUIRED_PLANS[feature] in ["free", "pro", "agency", "enterprise"]

    @pytest.mark.asyncio
    async def test_has_flag_works_for_phase2_features(
        self, service, mock_tenant_plan_pro, mock_pro_plan_phase2
    ):
        """Test has_flag works correctly for Phase 2 features."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan_pro
            mock_get_features.return_value = mock_pro_plan_phase2

            # Pro plan should have these enabled
            assert await service.has_flag("tenant-123", "environment_health") is True
            assert await service.has_flag("tenant-123", "observability_alerts") is True
            assert await service.has_flag("tenant-123", "rbac_basic") is True

            # Pro plan should NOT have these enabled
            assert await service.has_flag("tenant-123", "workflow_ci_cd_approval") is False
            assert await service.has_flag("tenant-123", "observability_alerts_advanced") is False
            assert await service.has_flag("tenant-123", "sso_saml") is False

    @pytest.mark.asyncio
    async def test_get_limit_works_for_phase2_features(
        self, service, mock_tenant_plan_pro, mock_pro_plan_phase2
    ):
        """Test get_limit works correctly for Phase 2 limit features."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan_pro
            mock_get_features.return_value = mock_pro_plan_phase2

            assert await service.get_limit("tenant-123", "environment_limits") == 10
            assert await service.get_limit("tenant-123", "snapshots_history") == 30
            assert await service.get_limit("tenant-123", "observability_limits") == 30

    @pytest.mark.asyncio
    async def test_enforce_flag_phase2_feature(
        self, service, mock_tenant_plan_pro, mock_pro_plan_phase2
    ):
        """Test enforce_flag works for Phase 2 features."""
        with patch.object(
            service, "_get_tenant_plan", new_callable=AsyncMock
        ) as mock_get_plan, patch.object(
            service, "_get_plan_features", new_callable=AsyncMock
        ) as mock_get_features:
            mock_get_plan.return_value = mock_tenant_plan_pro
            mock_get_features.return_value = mock_pro_plan_phase2

            # Should not raise for enabled feature
            await service.enforce_flag("tenant-123", "observability_alerts")

            # Should raise 403 for disabled feature
            with pytest.raises(HTTPException) as exc_info:
                await service.enforce_flag("tenant-123", "sso_saml")

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail["feature"] == "sso_saml"
