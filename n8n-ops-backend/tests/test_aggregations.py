"""
Unit tests for execution aggregation correctness.

Tests success rate and P95 duration calculations to ensure mathematical accuracy
and proper handling of edge cases, particularly for T006 and T007 fixes.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock
from typing import List, Dict, Any

from app.services.database import DatabaseService


class TestSuccessRateCalculations:
    """Test success rate aggregation correctness."""

    @pytest.mark.asyncio
    async def test_success_rate_excludes_non_completed_executions(self, monkeypatch):
        """
        GIVEN executions with mixed statuses (success, error, running, waiting)
        WHEN calculating success rate
        THEN only completed executions (success + error) should be in the denominator
        """
        # Mock data: 5 success, 3 error, 2 running, 1 waiting
        # Expected: 5/(5+3) * 100 = 62.5%
        mock_executions = [
            {"status": "success", "execution_time": 100},
            {"status": "success", "execution_time": 150},
            {"status": "success", "execution_time": 200},
            {"status": "success", "execution_time": 120},
            {"status": "success", "execution_time": 180},
            {"status": "error", "execution_time": 90},
            {"status": "error", "execution_time": 110},
            {"status": "error", "execution_time": 130},
            {"status": "running", "execution_time": None},
            {"status": "running", "execution_time": None},
            {"status": "waiting", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # Verify success rate calculation
        assert result["total_executions"] == 11
        assert result["success_count"] == 5
        assert result["failure_count"] == 3
        assert result["success_rate"] == 62.5  # 5/(5+3) * 100

    @pytest.mark.asyncio
    async def test_success_rate_all_success(self, monkeypatch):
        """
        GIVEN all successful executions
        WHEN calculating success rate
        THEN success rate should be 100%
        """
        mock_executions = [
            {"status": "success", "execution_time": 100},
            {"status": "success", "execution_time": 150},
            {"status": "success", "execution_time": 200},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_success_rate_all_failures(self, monkeypatch):
        """
        GIVEN all failed executions
        WHEN calculating success rate
        THEN success rate should be 0%
        """
        mock_executions = [
            {"status": "error", "execution_time": 100},
            {"status": "error", "execution_time": 150},
            {"status": "error", "execution_time": 200},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_success_rate_no_completed_executions(self, monkeypatch):
        """
        GIVEN only running/waiting executions (no completed)
        WHEN calculating success rate
        THEN success rate should be 0% (avoid division by zero)
        """
        mock_executions = [
            {"status": "running", "execution_time": None},
            {"status": "waiting", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["success_rate"] == 0.0
        assert result["success_count"] == 0
        assert result["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_success_rate_empty_dataset(self, monkeypatch):
        """
        GIVEN no executions
        WHEN calculating success rate
        THEN success rate should be 0% (handle empty gracefully)
        """
        mock_executions = []

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["total_executions"] == 0
        assert result["success_rate"] == 0.0


class TestP95DurationCalculations:
    """Test P95 duration aggregation correctness using PERCENTILE_CONT."""

    @pytest.mark.asyncio
    async def test_p95_duration_linear_interpolation(self, monkeypatch):
        """
        GIVEN a known dataset
        WHEN calculating P95 duration
        THEN result should match numpy.percentile (linear interpolation method)
        """
        # Dataset with 20 values: 100, 110, 120, ..., 290
        durations = [100 + (i * 10) for i in range(20)]
        mock_executions = [
            {"status": "success", "execution_time": d} for d in durations
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # Calculate expected P95 using numpy (matches PostgreSQL PERCENTILE_CONT)
        expected_p95 = float(np.percentile(durations, 95))

        assert result["p95_duration_ms"] == expected_p95
        # For this dataset: P95 should be 280.5 (linear interpolation)
        assert result["p95_duration_ms"] == 280.5

    @pytest.mark.asyncio
    async def test_p95_duration_single_value(self, monkeypatch):
        """
        GIVEN a single execution
        WHEN calculating P95 duration
        THEN P95 should equal that single value
        """
        mock_executions = [
            {"status": "success", "execution_time": 150},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["p95_duration_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_p95_duration_filters_none_values(self, monkeypatch):
        """
        GIVEN executions with some None durations
        WHEN calculating P95 duration
        THEN None values should be excluded from calculation
        """
        mock_executions = [
            {"status": "success", "execution_time": 100},
            {"status": "success", "execution_time": 200},
            {"status": "success", "execution_time": 300},
            {"status": "running", "execution_time": None},  # Should be filtered
            {"status": "error", "execution_time": None},   # Should be filtered
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # P95 of [100, 200, 300]
        expected_p95 = float(np.percentile([100, 200, 300], 95))
        assert result["p95_duration_ms"] == expected_p95

    @pytest.mark.asyncio
    async def test_p95_duration_no_durations(self, monkeypatch):
        """
        GIVEN no executions with valid durations
        WHEN calculating P95 duration
        THEN P95 should be None
        """
        mock_executions = [
            {"status": "running", "execution_time": None},
            {"status": "waiting", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["p95_duration_ms"] is None

    @pytest.mark.asyncio
    async def test_p95_duration_large_dataset(self, monkeypatch):
        """
        GIVEN a large dataset (1000 executions)
        WHEN calculating P95 duration
        THEN result should correctly identify the 95th percentile
        """
        # Create 1000 values: 1, 2, 3, ..., 1000
        durations = list(range(1, 1001))
        mock_executions = [
            {"status": "success", "execution_time": d} for d in durations
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # P95 of [1, 2, ..., 1000] should be 950.05
        expected_p95 = float(np.percentile(durations, 95))
        assert result["p95_duration_ms"] == expected_p95
        assert 950.0 <= result["p95_duration_ms"] <= 951.0  # Sanity check


class TestWorkflowLevelAggregations:
    """Test per-workflow aggregation correctness."""

    @pytest.mark.asyncio
    async def test_workflow_success_rate_calculation(self, monkeypatch):
        """
        GIVEN multiple workflows with different success rates
        WHEN calculating per-workflow stats
        THEN each workflow should have correct success rate
        """
        mock_executions = [
            # Workflow 1: 3 success, 1 error = 75% success rate
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 100},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 110},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 120},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "error", "execution_time": 90},

            # Workflow 2: 1 success, 1 error = 50% success rate
            {"workflow_id": "wf-2", "workflow_name": "Workflow 2", "status": "success", "execution_time": 200},
            {"workflow_id": "wf-2", "workflow_name": "Workflow 2", "status": "error", "execution_time": 210},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_workflow_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z",
            limit=10
        )

        # Find workflow 1 in results
        wf1 = next(r for r in result if r["workflow_id"] == "wf-1")
        assert wf1["success_count"] == 3
        assert wf1["failure_count"] == 1
        assert wf1["success_rate"] == 75.0

        # Find workflow 2 in results
        wf2 = next(r for r in result if r["workflow_id"] == "wf-2")
        assert wf2["success_count"] == 1
        assert wf2["failure_count"] == 1
        assert wf2["success_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_workflow_p95_duration_calculation(self, monkeypatch):
        """
        GIVEN workflows with different duration distributions
        WHEN calculating per-workflow P95
        THEN each workflow should have correct P95 duration
        """
        # Workflow 1: durations [100, 110, 120, 130, 140]
        # P95 should be 138 (linear interpolation)
        mock_executions = [
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 100},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 110},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 120},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 130},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 140},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_workflow_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z",
            limit=10
        )

        wf1 = result[0]
        expected_p95 = float(np.percentile([100, 110, 120, 130, 140], 95))
        assert wf1["p95_duration_ms"] == expected_p95
        assert wf1["p95_duration_ms"] == 138.0

    @pytest.mark.asyncio
    async def test_workflow_error_rate_calculation(self, monkeypatch):
        """
        GIVEN workflows with failures
        WHEN calculating error rate
        THEN error rate should be (failures / completed) * 100
        """
        mock_executions = [
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 100},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "error", "execution_time": 110},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "error", "execution_time": 120},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "error", "execution_time": 130},
            # 1 success, 3 errors = 75% error rate
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_workflow_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z",
            limit=10
        )

        wf1 = result[0]
        assert wf1["error_rate"] == 75.0  # 3/(1+3) * 100

    @pytest.mark.asyncio
    async def test_workflow_aggregation_with_running_executions(self, monkeypatch):
        """
        GIVEN workflow with running executions
        WHEN calculating workflow stats
        THEN running executions should be counted in total but not in success/error rates
        """
        mock_executions = [
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "success", "execution_time": 100},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "error", "execution_time": 110},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "running", "execution_time": None},
            {"workflow_id": "wf-1", "workflow_name": "Workflow 1", "status": "running", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_workflow_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z",
            limit=10
        )

        wf1 = result[0]
        assert wf1["execution_count"] == 4  # All 4 executions counted
        assert wf1["success_count"] == 1
        assert wf1["failure_count"] == 1
        # Success rate: 1/(1+1) * 100 = 50% (running excluded)
        assert wf1["success_rate"] == 50.0


class TestAverageDurationCalculations:
    """Test average duration calculation correctness."""

    @pytest.mark.asyncio
    async def test_avg_duration_calculation(self, monkeypatch):
        """
        GIVEN executions with various durations
        WHEN calculating average duration
        THEN result should be arithmetic mean of non-None durations
        """
        durations = [100, 150, 200, 250, 300]
        mock_executions = [
            {"status": "success", "execution_time": d} for d in durations
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        expected_avg = sum(durations) / len(durations)
        assert result["avg_duration_ms"] == expected_avg
        assert result["avg_duration_ms"] == 200.0

    @pytest.mark.asyncio
    async def test_avg_duration_filters_none_values(self, monkeypatch):
        """
        GIVEN executions with some None durations
        WHEN calculating average duration
        THEN None values should be excluded
        """
        mock_executions = [
            {"status": "success", "execution_time": 100},
            {"status": "success", "execution_time": 200},
            {"status": "running", "execution_time": None},
            {"status": "running", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # Average of [100, 200] only
        assert result["avg_duration_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_avg_duration_no_valid_durations(self, monkeypatch):
        """
        GIVEN executions with no valid durations
        WHEN calculating average duration
        THEN result should be 0
        """
        mock_executions = [
            {"status": "running", "execution_time": None},
            {"status": "waiting", "execution_time": None},
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["avg_duration_ms"] == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_mixed_status_comprehensive(self, monkeypatch):
        """
        GIVEN a comprehensive mix of execution statuses
        WHEN calculating all metrics
        THEN all calculations should be correct and consistent
        """
        mock_executions = [
            # 10 successful (durations: 100, 110, ..., 190)
            *[{"status": "success", "execution_time": 100 + (i * 10)} for i in range(10)],
            # 5 errors (durations: 200, 210, ..., 240)
            *[{"status": "error", "execution_time": 200 + (i * 10)} for i in range(5)],
            # 3 running (no durations)
            *[{"status": "running", "execution_time": None} for _ in range(3)],
            # 2 waiting (no durations)
            *[{"status": "waiting", "execution_time": None} for _ in range(2)],
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        # Total executions
        assert result["total_executions"] == 20

        # Success rate: 10/(10+5) * 100 = 66.67%
        assert result["success_count"] == 10
        assert result["failure_count"] == 5
        assert abs(result["success_rate"] - 66.67) < 0.01

        # Average duration of [100, 110, ..., 190, 200, 210, ..., 240]
        durations = [100 + (i * 10) for i in range(10)] + [200 + (i * 10) for i in range(5)]
        expected_avg = sum(durations) / len(durations)
        assert result["avg_duration_ms"] == expected_avg

        # P95 duration
        expected_p95 = float(np.percentile(durations, 95))
        assert result["p95_duration_ms"] == expected_p95

    @pytest.mark.asyncio
    async def test_zero_executions(self, monkeypatch):
        """
        GIVEN zero executions
        WHEN calculating stats
        THEN all metrics should be 0 or None without errors
        """
        mock_executions = []

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["total_executions"] == 0
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_duration_ms"] == 0
        assert result["p95_duration_ms"] is None

    @pytest.mark.asyncio
    async def test_single_execution_edge_case(self, monkeypatch):
        """
        GIVEN a single execution
        WHEN calculating all stats
        THEN percentiles and averages should equal that single value
        """
        mock_executions = [
            {"status": "success", "execution_time": 175}
        ]

        db_service = DatabaseService()
        mock_response = MagicMock()
        mock_response.data = mock_executions
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = mock_response
        db_service.client = mock_client

        result = await db_service.get_execution_stats(
            tenant_id="test-tenant",
            since="2024-01-01T00:00:00Z",
            until="2024-01-02T00:00:00Z"
        )

        assert result["total_executions"] == 1
        assert result["success_count"] == 1
        assert result["success_rate"] == 100.0
        assert result["avg_duration_ms"] == 175.0
        assert result["p95_duration_ms"] == 175.0
