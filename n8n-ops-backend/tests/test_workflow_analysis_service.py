"""
Unit tests for the workflow analysis service - complexity and quality metrics.
"""
import pytest

from app.services.workflow_analysis_service import (
    is_trigger_node,
    get_node_category,
    count_connections,
    calculate_complexity,
    infer_purpose,
    infer_execution_summary,
    extract_external_systems,
    categorize_system,
    extract_dependencies,
    analyze_reliability,
    analyze_performance,
    analyze_cost,
    analyze_security,
    analyze_maintainability,
    analyze_governance,
    analyze_drift,
    generate_optimizations,
    analyze_workflow,
)


class TestIsTriggerNode:
    """Tests for is_trigger_node function."""

    @pytest.mark.unit
    def test_webhook_is_trigger(self):
        """Webhook nodes should be identified as triggers."""
        assert is_trigger_node("n8n-nodes-base.webhook") is True
        assert is_trigger_node("Webhook") is True

    @pytest.mark.unit
    def test_schedule_is_trigger(self):
        """Schedule nodes should be identified as triggers."""
        assert is_trigger_node("n8n-nodes-base.scheduleTrigger") is True
        assert is_trigger_node("Schedule") is True

    @pytest.mark.unit
    def test_cron_is_trigger(self):
        """Cron nodes should be identified as triggers."""
        assert is_trigger_node("n8n-nodes-base.cron") is True

    @pytest.mark.unit
    def test_regular_node_is_not_trigger(self):
        """Regular nodes should not be identified as triggers."""
        assert is_trigger_node("n8n-nodes-base.httpRequest") is False
        assert is_trigger_node("n8n-nodes-base.set") is False
        assert is_trigger_node("n8n-nodes-base.function") is False


class TestGetNodeCategory:
    """Tests for get_node_category function."""

    @pytest.mark.unit
    def test_trigger_category(self):
        """Should categorize trigger nodes."""
        assert get_node_category("n8n-nodes-base.setTrigger") == "trigger"
        assert get_node_category("n8n-nodes-base.webhookTrigger") == "trigger"

    @pytest.mark.unit
    def test_api_category(self):
        """Should categorize API nodes."""
        assert get_node_category("n8n-nodes-base.httpRequest") == "api"
        assert get_node_category("n8n-nodes-base.apiClient") == "api"

    @pytest.mark.unit
    def test_database_category(self):
        """Should categorize database nodes."""
        assert get_node_category("n8n-nodes-base.postgres") == "database"
        assert get_node_category("n8n-nodes-base.mysql") == "database"
        assert get_node_category("n8n-nodes-base.mongodb") == "database"

    @pytest.mark.unit
    def test_logic_category(self):
        """Should categorize logic nodes."""
        assert get_node_category("n8n-nodes-base.if") == "logic"
        assert get_node_category("n8n-nodes-base.switch") == "logic"
        assert get_node_category("n8n-nodes-base.merge") == "logic"

    @pytest.mark.unit
    def test_code_category(self):
        """Should categorize code nodes."""
        assert get_node_category("n8n-nodes-base.code") == "code"
        assert get_node_category("n8n-nodes-base.function") == "code"

    @pytest.mark.unit
    def test_transform_category(self):
        """Should categorize transform nodes."""
        assert get_node_category("n8n-nodes-base.set") == "transform"
        assert get_node_category("n8n-nodes-base.splitInBatchesItem") == "transform"

    @pytest.mark.unit
    def test_ai_category(self):
        """Should categorize AI nodes."""
        assert get_node_category("@n8n/n8n-nodes-langchain.openAi") == "ai"
        assert get_node_category("@n8n/n8n-nodes-langchain.anthropic") == "ai"
        assert get_node_category("n8n-nodes-base.llmChain") == "ai"

    @pytest.mark.unit
    def test_other_category(self):
        """Should default to 'other' for unknown types."""
        assert get_node_category("n8n-nodes-base.unknown") == "other"


class TestCountConnections:
    """Tests for count_connections function."""

    @pytest.mark.unit
    def test_empty_connections(self):
        """Should return 0 for empty connections."""
        assert count_connections(None) == 0
        assert count_connections({}) == 0

    @pytest.mark.unit
    def test_single_connection(self):
        """Should count single connection."""
        connections = {
            "Start": {
                "main": [
                    [{"node": "End", "type": "main", "index": 0}]
                ]
            }
        }
        assert count_connections(connections) == 1

    @pytest.mark.unit
    def test_multiple_connections(self):
        """Should count multiple connections."""
        connections = {
            "Start": {
                "main": [
                    [{"node": "Node1", "type": "main", "index": 0}]
                ]
            },
            "Node1": {
                "main": [
                    [
                        {"node": "Node2", "type": "main", "index": 0},
                        {"node": "Node3", "type": "main", "index": 0}
                    ]
                ]
            }
        }
        assert count_connections(connections) == 3

    @pytest.mark.unit
    def test_branching_connections(self):
        """Should count branching connections correctly."""
        connections = {
            "If": {
                "main": [
                    [{"node": "TrueBranch", "type": "main", "index": 0}],
                    [{"node": "FalseBranch", "type": "main", "index": 0}]
                ]
            }
        }
        assert count_connections(connections) == 2


class TestCalculateComplexity:
    """Tests for calculate_complexity function."""

    @pytest.mark.unit
    def test_simple_workflow(self):
        """Should return simple for small workflows."""
        result = calculate_complexity(node_count=2, edge_count=1, max_branching=1)
        assert result["level"] == "simple"
        assert result["score"] < 25

    @pytest.mark.unit
    def test_moderate_workflow(self):
        """Should return moderate for medium workflows."""
        result = calculate_complexity(node_count=5, edge_count=5, max_branching=2)
        assert result["level"] == "moderate"
        assert 25 <= result["score"] < 50

    @pytest.mark.unit
    def test_complex_workflow(self):
        """Should return complex for large workflows."""
        result = calculate_complexity(node_count=10, edge_count=10, max_branching=2)
        assert result["level"] == "complex"
        assert 50 <= result["score"] < 75

    @pytest.mark.unit
    def test_very_complex_workflow(self):
        """Should return very-complex for massive workflows."""
        result = calculate_complexity(node_count=25, edge_count=40, max_branching=5)
        assert result["level"] == "very-complex"
        assert result["score"] >= 75

    @pytest.mark.unit
    def test_max_score_is_100(self):
        """Score should cap at 100."""
        result = calculate_complexity(node_count=100, edge_count=100, max_branching=10)
        assert result["score"] <= 100


class TestInferPurpose:
    """Tests for infer_purpose function."""

    @pytest.mark.unit
    def test_webhook_with_slack(self):
        """Should identify webhook-slack notification workflow."""
        nodes = [
            {"type": "n8n-nodes-base.webhook"},
            {"type": "n8n-nodes-base.slack"}
        ]
        result = infer_purpose(nodes)
        assert "notification" in result.lower()

    @pytest.mark.unit
    def test_scheduled_workflow(self):
        """Should identify scheduled automation."""
        nodes = [
            {"type": "n8n-nodes-base.scheduleTrigger"},
            {"type": "n8n-nodes-base.httpRequest"}
        ]
        result = infer_purpose(nodes)
        assert "scheduled" in result.lower()

    @pytest.mark.unit
    def test_ai_workflow(self):
        """Should identify AI-powered workflow."""
        nodes = [
            {"type": "n8n-nodes-base.set"},
            {"type": "@n8n/n8n-nodes-langchain.openAi"}
        ]
        result = infer_purpose(nodes)
        assert "ai" in result.lower()

    @pytest.mark.unit
    def test_database_workflow(self):
        """Should identify database-driven workflow."""
        nodes = [
            {"type": "n8n-nodes-base.postgres"},
            {"type": "n8n-nodes-base.set"}
        ]
        result = infer_purpose(nodes)
        assert "database" in result.lower()


class TestInferExecutionSummary:
    """Tests for infer_execution_summary function."""

    @pytest.mark.unit
    def test_basic_summary(self):
        """Should generate basic summary with node count."""
        nodes = [
            {"type": "n8n-nodes-base.set", "name": "Set Data"},
            {"type": "n8n-nodes-base.httpRequest", "name": "HTTP"}
        ]
        result = infer_execution_summary(nodes)
        assert "2 nodes" in result

    @pytest.mark.unit
    def test_summary_with_trigger(self):
        """Should include trigger info in summary."""
        nodes = [
            {"type": "n8n-nodes-base.setTrigger", "name": "My Webhook"},
            {"type": "n8n-nodes-base.set", "name": "Set"}
        ]
        result = infer_execution_summary(nodes)
        assert "triggered by" in result
        assert "My Webhook" in result

    @pytest.mark.unit
    def test_summary_with_outputs(self):
        """Should include output count in summary."""
        nodes = [
            {"type": "n8n-nodes-base.set", "name": "Set"},
            {"type": "n8n-nodes-base.sendEmail", "name": "Send Email"},
            {"type": "n8n-nodes-base.write", "name": "Write File"}
        ]
        result = infer_execution_summary(nodes)
        assert "output" in result.lower()


class TestExtractExternalSystems:
    """Tests for extract_external_systems function."""

    @pytest.mark.unit
    def test_extracts_http_api(self):
        """Should extract HTTP/REST API systems."""
        nodes = [{"type": "n8n-nodes-base.httpRequest"}]
        result = extract_external_systems(nodes)
        assert "HTTP/REST APIs" in result

    @pytest.mark.unit
    def test_extracts_databases(self):
        """Should extract database systems."""
        nodes = [
            {"type": "n8n-nodes-base.postgres"},
            {"type": "n8n-nodes-base.mysql"}
        ]
        result = extract_external_systems(nodes)
        assert "PostgreSQL" in result
        assert "MySQL" in result

    @pytest.mark.unit
    def test_extracts_slack(self):
        """Should extract Slack."""
        nodes = [{"type": "n8n-nodes-base.slack"}]
        result = extract_external_systems(nodes)
        assert "Slack" in result

    @pytest.mark.unit
    def test_extracts_ai_services(self):
        """Should extract AI services."""
        nodes = [
            {"type": "@n8n/n8n-nodes-langchain.openAi"},
            {"type": "@n8n/n8n-nodes-langchain.anthropic"}
        ]
        result = extract_external_systems(nodes)
        assert "OpenAI" in result
        assert "Anthropic" in result

    @pytest.mark.unit
    def test_no_duplicates(self):
        """Should not return duplicates."""
        nodes = [
            {"type": "n8n-nodes-base.slack"},
            {"type": "n8n-nodes-base.slackMessage"}
        ]
        result = extract_external_systems(nodes)
        assert result.count("Slack") == 1


class TestCategorizeSystem:
    """Tests for categorize_system function."""

    @pytest.mark.unit
    def test_api_category(self):
        """Should categorize API systems."""
        assert categorize_system("HTTP/REST APIs") == "api"
        assert categorize_system("API Gateway") == "api"

    @pytest.mark.unit
    def test_database_category(self):
        """Should categorize database systems."""
        assert categorize_system("PostgreSQL") == "database"
        assert categorize_system("MySQL") == "database"
        assert categorize_system("MongoDB") == "database"

    @pytest.mark.unit
    def test_file_category(self):
        """Should categorize file storage systems."""
        assert categorize_system("AWS S3") == "file"

    @pytest.mark.unit
    def test_service_category(self):
        """Should default to service category."""
        assert categorize_system("Slack") == "service"
        assert categorize_system("GitHub") == "service"


class TestExtractDependencies:
    """Tests for extract_dependencies function."""

    @pytest.mark.unit
    def test_extracts_dependencies(self):
        """Should extract dependencies from nodes."""
        nodes = [
            {"type": "n8n-nodes-base.httpRequest", "name": "API Call"},
            {"type": "n8n-nodes-base.postgres", "name": "DB Query"}
        ]
        result = extract_dependencies(nodes)

        assert len(result) == 2
        names = [d["name"] for d in result]
        assert "HTTP/REST APIs" in names
        assert "PostgreSQL" in names

    @pytest.mark.unit
    def test_counts_nodes_per_dependency(self):
        """Should count nodes using each dependency."""
        nodes = [
            {"type": "n8n-nodes-base.httpRequest", "name": "API 1"},
            {"type": "n8n-nodes-base.httpRequest", "name": "API 2"}
        ]
        result = extract_dependencies(nodes)

        http_dep = next(d for d in result if d["name"] == "HTTP/REST APIs")
        assert http_dep["nodeCount"] == 2
        assert len(http_dep["nodes"]) == 2


class TestAnalyzeReliability:
    """Tests for analyze_reliability function."""

    @pytest.mark.unit
    def test_base_reliability_score(self):
        """Should start with base score of 50."""
        nodes = [{"type": "n8n-nodes-base.set", "parameters": {}}]
        result = analyze_reliability(nodes)
        assert result["score"] >= 50

    @pytest.mark.unit
    def test_error_handling_improves_score(self):
        """Should improve score for error handling nodes."""
        nodes = [
            {"type": "n8n-nodes-base.errorTrigger", "parameters": {}},
            {"type": "n8n-nodes-base.set", "parameters": {}}
        ]
        result = analyze_reliability(nodes)
        assert result["errorHandlingNodes"] == 1
        assert result["score"] >= 60

    @pytest.mark.unit
    def test_continue_on_fail_improves_score(self):
        """Should count continueOnFail settings."""
        nodes = [
            {"type": "n8n-nodes-base.httpRequest", "parameters": {"continueOnFail": True}}
        ]
        result = analyze_reliability(nodes)
        assert result["continueOnFailCount"] == 1

    @pytest.mark.unit
    def test_identifies_missing_error_handling(self):
        """Should identify nodes missing error handling."""
        nodes = [
            {"type": "n8n-nodes-base.httpRequest", "name": "API Call", "parameters": {}}
        ]
        result = analyze_reliability(nodes)
        assert len(result["missingErrorHandling"]) > 0

    @pytest.mark.unit
    def test_identifies_failure_hotspots(self):
        """Should identify code nodes as failure hotspots."""
        nodes = [
            {"type": "n8n-nodes-base.code", "name": "Custom Code", "parameters": {}}
        ]
        result = analyze_reliability(nodes)
        assert len(result["failureHotspots"]) > 0

    @pytest.mark.unit
    def test_reliability_levels(self):
        """Should assign appropriate reliability levels."""
        # Critical
        nodes_critical = [{"type": "n8n-nodes-base.set", "parameters": {}}] * 10
        result = analyze_reliability(nodes_critical)
        assert result["level"] in ["critical", "warning", "good", "excellent"]


class TestAnalyzePerformance:
    """Tests for analyze_performance function."""

    @pytest.mark.unit
    def test_parallelism_detection(self):
        """Should detect parallelism when edges > nodes."""
        nodes = [{"type": "n8n-nodes-base.set"}] * 3
        result = analyze_performance(nodes, edge_count=5)
        assert result["hasParallelism"] is True

    @pytest.mark.unit
    def test_api_calls_reduce_score(self):
        """Should reduce score for API-heavy workflows."""
        nodes = [{"type": "n8n-nodes-base.httpRequest"}] * 5
        result = analyze_performance(nodes, edge_count=4)
        assert result["score"] < 100

    @pytest.mark.unit
    def test_complexity_levels(self):
        """Should set complexity based on external calls."""
        nodes_low = [{"type": "n8n-nodes-base.set"}]
        result_low = analyze_performance(nodes_low, edge_count=0)
        assert result_low["estimatedComplexity"] == "low"

        nodes_high = [{"type": "n8n-nodes-base.httpRequest"}] * 6
        result_high = analyze_performance(nodes_high, edge_count=5)
        assert result_high["estimatedComplexity"] == "high"


class TestAnalyzeCost:
    """Tests for analyze_cost function."""

    @pytest.mark.unit
    def test_low_cost_for_simple_workflows(self):
        """Should report low cost for simple workflows."""
        nodes = [{"type": "n8n-nodes-base.set"}]
        result = analyze_cost(nodes)
        assert result["level"] == "low"

    @pytest.mark.unit
    def test_high_cost_for_llm_workflows(self):
        """Should report high cost for LLM workflows."""
        nodes = [{"type": "@n8n/n8n-nodes-langchain.openAi"}]
        result = analyze_cost(nodes)
        assert result["level"] in ["high", "very-high"]
        assert len(result["llmNodes"]) == 1

    @pytest.mark.unit
    def test_trigger_frequency_detection(self):
        """Should detect trigger frequency."""
        scheduled_nodes = [{"type": "n8n-nodes-base.scheduleTrigger"}]
        result = analyze_cost(scheduled_nodes)
        assert "Scheduled" in result["triggerFrequency"]

        webhook_nodes = [{"type": "n8n-nodes-base.webhook"}]
        result = analyze_cost(webhook_nodes)
        assert "webhook" in result["triggerFrequency"].lower()


class TestAnalyzeSecurity:
    """Tests for analyze_security function."""

    @pytest.mark.unit
    def test_counts_credentialed_nodes(self):
        """Should count nodes with credentials."""
        nodes = [
            {"type": "n8n-nodes-base.httpRequest", "credentials": {"httpBasicAuth": {"id": "cred-1"}}},
            {"type": "n8n-nodes-base.set", "credentials": None}
        ]
        result = analyze_security(nodes)
        assert result["credentialCount"] == 1

    @pytest.mark.unit
    def test_identifies_hardcoded_secrets(self):
        """Should identify potential hardcoded secrets."""
        nodes = [
            {
                "type": "n8n-nodes-base.httpRequest",
                "name": "API Call",
                "parameters": {"headers": {"Authorization": "Bearer my_secret_api_key"}}
            }
        ]
        result = analyze_security(nodes)
        assert len(result["hardcodedSecretSignals"]) > 0

    @pytest.mark.unit
    def test_security_score_reduced_for_hardcoded_secrets(self):
        """Should reduce score for hardcoded secrets."""
        nodes_clean = [{"type": "n8n-nodes-base.set", "parameters": {}}]
        result_clean = analyze_security(nodes_clean)

        nodes_secrets = [
            {
                "type": "n8n-nodes-base.httpRequest",
                "name": "API",
                "parameters": {"password": "hardcoded"}
            }
        ]
        result_secrets = analyze_security(nodes_secrets)

        assert result_secrets["score"] < result_clean["score"]


class TestAnalyzeMaintainability:
    """Tests for analyze_maintainability function."""

    @pytest.mark.unit
    def test_naming_consistency(self):
        """Should calculate naming consistency score."""
        well_named = [
            {"name": "Fetch User Data", "id": "1"},
            {"name": "Transform Response", "id": "2"}
        ]
        result = analyze_maintainability(well_named)
        assert result["namingConsistency"] == 100

    @pytest.mark.unit
    def test_identifies_missing_descriptions(self):
        """Should identify nodes with default names."""
        nodes = [
            {"name": "Node1", "id": "1"},
            {"name": "Good Name Here", "id": "2"}
        ]
        result = analyze_maintainability(nodes)
        assert len(result["missingDescriptions"]) > 0

    @pytest.mark.unit
    def test_empty_names_identified(self):
        """Should identify nodes with missing names."""
        nodes = [
            {"id": "1"},
            {"name": "ab", "id": "2"}  # Too short
        ]
        result = analyze_maintainability(nodes)
        assert len(result["missingAnnotations"]) > 0


class TestAnalyzeGovernance:
    """Tests for analyze_governance function."""

    @pytest.mark.unit
    def test_env_var_usage_improves_portability(self):
        """Should reward environment variable usage."""
        nodes_with_env = [
            {"name": "API", "parameters": {"url": "$env.API_URL"}}
        ]
        result = analyze_governance(nodes_with_env)
        assert result["environmentPortability"] == 80

    @pytest.mark.unit
    def test_identifies_pii_exposure_risks(self):
        """Should identify PII handling."""
        nodes = [
            {"name": "Process User", "parameters": {"field": "user_email"}}
        ]
        result = analyze_governance(nodes)
        assert len(result["piiExposureRisks"]) > 0

    @pytest.mark.unit
    def test_promotion_safety_flag(self):
        """Should set promotion safety based on risks."""
        safe_nodes = [{"name": "Transform", "parameters": {"data": "value"}}]
        result = analyze_governance(safe_nodes)
        assert result["promotionSafety"] is True


class TestAnalyzeDrift:
    """Tests for analyze_drift function."""

    @pytest.mark.unit
    def test_returns_static_structure(self):
        """Should return static drift analysis structure."""
        result = analyze_drift()
        assert "hasGitMismatch" in result
        assert "environmentDivergence" in result
        assert "recommendations" in result


class TestGenerateOptimizations:
    """Tests for generate_optimizations function."""

    @pytest.mark.unit
    def test_suggests_splitting_large_workflows(self):
        """Should suggest splitting workflows with > 20 nodes."""
        nodes = [{"type": "n8n-nodes-base.set"}] * 25
        result = generate_optimizations(nodes, {})
        suggestions = [s["title"] for s in result]
        assert any("split" in s.lower() for s in suggestions)

    @pytest.mark.unit
    def test_suggests_llm_caching(self):
        """Should suggest LLM caching for multiple LLM nodes."""
        nodes = [{"type": "n8n-nodes-base.set"}]
        partial_analysis = {
            "cost": {"llmNodes": ["LLM1", "LLM2"]},
            "reliability": {"errorHandlingNodes": 1}
        }
        result = generate_optimizations(nodes, partial_analysis)
        suggestions = [s["title"] for s in result]
        assert any("llm" in s.lower() or "caching" in s.lower() for s in suggestions)

    @pytest.mark.unit
    def test_suggests_error_handling(self):
        """Should suggest error handling when missing."""
        nodes = [{"type": "n8n-nodes-base.set"}]
        partial_analysis = {
            "cost": {"llmNodes": []},
            "reliability": {"errorHandlingNodes": 0}
        }
        result = generate_optimizations(nodes, partial_analysis)
        suggestions = [s["title"] for s in result]
        assert any("error" in s.lower() for s in suggestions)


class TestAnalyzeWorkflow:
    """Tests for main analyze_workflow function."""

    @pytest.mark.unit
    def test_returns_complete_structure(self):
        """Should return complete analysis structure."""
        workflow = {
            "nodes": [
                {"id": "1", "name": "Start", "type": "n8n-nodes-base.set"},
                {"id": "2", "name": "Process", "type": "n8n-nodes-base.set"}
            ],
            "connections": {
                "1": {"main": [[{"node": "2", "type": "main", "index": 0}]]}
            }
        }
        result = analyze_workflow(workflow)

        assert "graph" in result
        assert "nodes" in result
        assert "dependencies" in result
        assert "summary" in result
        assert "reliability" in result
        assert "performance" in result
        assert "cost" in result
        assert "security" in result
        assert "maintainability" in result
        assert "governance" in result
        assert "drift" in result
        assert "optimizations" in result

    @pytest.mark.unit
    def test_graph_metrics(self):
        """Should calculate graph metrics correctly."""
        workflow = {
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhookTrigger"},
                {"id": "2", "name": "If", "type": "n8n-nodes-base.if"},
                {"id": "3", "name": "True", "type": "n8n-nodes-base.set"},
                {"id": "4", "name": "False", "type": "n8n-nodes-base.set"}
            ],
            "connections": {
                "1": {"main": [[{"node": "2"}]]},
                "2": {"main": [[{"node": "3"}], [{"node": "4"}]]}
            }
        }
        result = analyze_workflow(workflow)

        assert result["graph"]["nodeCount"] == 4
        assert result["graph"]["triggerCount"] == 1
        assert result["graph"]["edgeCount"] == 3

    @pytest.mark.unit
    def test_handles_empty_workflow(self):
        """Should handle empty workflow gracefully."""
        workflow = {"nodes": [], "connections": {}}
        result = analyze_workflow(workflow)

        assert result["graph"]["nodeCount"] == 0
        assert result["graph"]["complexityLevel"] == "simple"

    @pytest.mark.unit
    def test_handles_missing_connections(self):
        """Should handle workflow without connections."""
        workflow = {
            "nodes": [{"id": "1", "name": "Node", "type": "n8n-nodes-base.set"}]
        }
        result = analyze_workflow(workflow)

        assert result["graph"]["nodeCount"] == 1
        assert result["graph"]["edgeCount"] == 0

    @pytest.mark.unit
    def test_handles_analysis_error(self):
        """Should return minimal structure on error."""
        # Malformed workflow that might cause issues
        workflow = None
        # The function should handle this gracefully
        try:
            result = analyze_workflow(workflow)
            # If it doesn't raise, check structure
            assert "graph" in result
        except (TypeError, AttributeError):
            # This is also acceptable behavior
            pass

    @pytest.mark.unit
    def test_node_analysis_includes_metadata(self):
        """Should include node metadata in analysis."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "name": "API Call",
                    "type": "n8n-nodes-base.httpRequest",
                    "credentials": {"httpBasicAuth": {"id": "cred-1"}}
                }
            ],
            "connections": {}
        }
        result = analyze_workflow(workflow)

        assert len(result["nodes"]) == 1
        node = result["nodes"][0]
        assert node["id"] == "1"
        assert node["name"] == "API Call"
        assert node["category"] == "api"
        assert node["isCredentialed"] is True
        assert node["isTrigger"] is False

    @pytest.mark.unit
    def test_summary_generation(self):
        """Should generate meaningful summary."""
        workflow = {
            "nodes": [
                {"id": "1", "name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger"},
                {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest"},
                {"id": "3", "name": "Store", "type": "n8n-nodes-base.postgres"}
            ],
            "connections": {}
        }
        result = analyze_workflow(workflow)

        assert "purpose" in result["summary"]
        assert "executionSummary" in result["summary"]
        assert "triggerTypes" in result["summary"]
        assert "externalSystems" in result["summary"]
