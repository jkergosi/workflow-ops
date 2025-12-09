# Workflow Details Page - Data Sources & Persistence

## Data Sources Summary

| Item | Section | How Derived | Persisted? |
|------|---------|-------------|------------|
| **HERO SECTION** |
| Workflow Name | Hero | From `workflow.name` (N8N API) | No (real-time) |
| Workflow Status (Active/Inactive) | Hero | From `workflow.active` (N8N API) | No (real-time) |
| Health Status | Hero | Computed from analysis + drift + execution metrics | No (computed) |
| What It Does (Purpose) | Hero | From `analysis.summary.purpose` (client-side analysis) | No (computed) |
| Trigger Types | Hero | From `analysis.summary.triggerTypes` (client-side analysis) | No (computed) |
| External Systems | Hero | From `analysis.summary.externalSystems` (client-side analysis) | No (computed) |
| Is It Healthy? | Hero | Computed from security/reliability/drift/failure rate | No (computed) |
| Health Issues List | Hero | Aggregated from analysis + drift + metrics | No (computed) |
| Quick Actions | Hero | From `executionMetrics` (DB cache) | No (computed) |
| **QUICK STATS CARDS** |
| Status (Active/Inactive) | Quick Stats | From `workflow.active` (N8N API) | No (real-time) |
| Complexity Score | Quick Stats | From `analysis.graph.complexityScore` (client-side) | No (computed) |
| Complexity Level | Quick Stats | From `analysis.graph.complexityLevel` (client-side) | No (computed) |
| Node Count | Quick Stats | From `analysis.graph.nodeCount` (client-side) | No (computed) |
| Edge Count | Quick Stats | From `analysis.graph.edgeCount` (client-side) | No (computed) |
| Dependencies Count | Quick Stats | From `analysis.dependencies.length` (client-side) | No (computed) |
| Health Level | Quick Stats | From `analysis.security.level` (client-side) | No (computed) |
| **OVERVIEW TAB** |
| Purpose | Overview | From `analysis.summary.purpose` (client-side) | No (computed) |
| Execution Summary | Overview | From `analysis.summary.executionSummary` (client-side) | No (computed) |
| Trigger Types | Overview | From `analysis.summary.triggerTypes` (client-side) | No (computed) |
| External Systems | Overview | From `analysis.summary.externalSystems` (client-side) | No (computed) |
| Workflow ID | Overview | From `workflow.id` (N8N API) | No (real-time) |
| Description | Overview | From `workflow.description` (N8N API) | No (real-time) |
| Created Date | Overview | From `workflow.createdAt` (N8N API) | No (real-time) |
| Updated Date | Overview | From `workflow.updatedAt` (N8N API) | No (real-time) |
| Tags | Overview | From `workflow.tags` (N8N API) | No (real-time) |
| External Dependencies Table | Overview | From `analysis.dependencies` (client-side) | No (computed) |
| Nodes Used Table | Overview | From `analysis.nodes` (client-side) | No (computed) |
| Triggers List | Overview | Filtered from `workflow.nodes` (N8N API) | No (real-time) |
| **STRUCTURE TAB** |
| Complexity Score | Structure | From `analysis.graph.complexityScore` (client-side) | No (computed) |
| Complexity Level | Structure | From `analysis.graph.complexityLevel` (client-side) | No (computed) |
| Total Nodes | Structure | From `analysis.graph.nodeCount` (client-side) | No (computed) |
| Connections | Structure | From `analysis.graph.edgeCount` (client-side) | No (computed) |
| Max Depth | Structure | From `analysis.graph.maxDepth` (client-side) | No (computed) |
| Max Branching | Structure | From `analysis.graph.maxBranching` (client-side) | No (computed) |
| Flow Patterns (Linear/Fan-out/Fan-in/Cycles) | Structure | From `analysis.graph` flags (client-side) | No (computed) |
| Trigger Count | Structure | From `analysis.graph.triggerCount` (client-side) | No (computed) |
| Sink Count | Structure | From `analysis.graph.sinkCount` (client-side) | No (computed) |
| **RELIABILITY TAB** |
| Reliability Score | Reliability | From `analysis.reliability.score` (client-side) | No (computed) |
| Reliability Level | Reliability | From `analysis.reliability.level` (client-side) | No (computed) |
| Continue-on-Fail Count | Reliability | From `analysis.reliability.continueOnFailCount` (client-side) | No (computed) |
| Error Handling Nodes | Reliability | From `analysis.reliability.errorHandlingNodes` (client-side) | No (computed) |
| Retry-Enabled Nodes | Reliability | From `analysis.reliability.retryNodes` (client-side) | No (computed) |
| Missing Error Handling | Reliability | From `analysis.reliability.missingErrorHandling` (client-side) | No (computed) |
| Failure Hotspots | Reliability | From `analysis.reliability.failureHotspots` (client-side) | No (computed) |
| Recommendations | Reliability | From `analysis.reliability.recommendations` (client-side) | No (computed) |
| **PERFORMANCE TAB** |
| Performance Score | Performance | From `analysis.performance.score` (client-side) | No (computed) |
| Performance Level | Performance | From `analysis.performance.level` (client-side) | No (computed) |
| Has Parallelism | Performance | From `analysis.performance.hasParallelism` (client-side) | No (computed) |
| Estimated Complexity | Performance | From `analysis.performance.estimatedComplexity` (client-side) | No (computed) |
| Sequential Bottlenecks | Performance | From `analysis.performance.sequentialBottlenecks` (client-side) | No (computed) |
| Redundant Calls | Performance | From `analysis.performance.redundantCalls` (client-side) | No (computed) |
| Large Payload Risks | Performance | From `analysis.performance.largePayloadRisks` (client-side) | No (computed) |
| Recommendations | Performance | From `analysis.performance.recommendations` (client-side) | No (computed) |
| **COST TAB** |
| Cost Level | Cost | From `analysis.cost.level` (client-side) | No (computed) |
| Trigger Frequency | Cost | From `analysis.cost.triggerFrequency` (client-side) | No (computed) |
| API-Heavy Nodes | Cost | From `analysis.cost.apiHeavyNodes` (client-side) | No (computed) |
| LLM/AI Nodes | Cost | From `analysis.cost.llmNodes` (client-side) | No (computed) |
| Cost Amplifiers | Cost | From `analysis.cost.costAmplifiers` (client-side) | No (computed) |
| Throttling Candidates | Cost | From `analysis.cost.throttlingCandidates` (client-side) | No (computed) |
| Recommendations | Cost | From `analysis.cost.recommendations` (client-side) | No (computed) |
| **SECURITY TAB** |
| Security Score | Security | From `analysis.security.score` (client-side) | No (computed) |
| Security Level | Security | From `analysis.security.level` (client-side) | No (computed) |
| Credential Count | Security | From `analysis.security.credentialCount` (client-side) | No (computed) |
| Credential Types | Security | From `analysis.security.credentialTypes` (client-side) | No (computed) |
| Hardcoded Secret Signals | Security | From `analysis.security.hardcodedSecretSignals` (client-side) | No (computed) |
| Over-Privileged Risks | Security | From `analysis.security.overPrivilegedRisks` (client-side) | No (computed) |
| Secret Reuse Risks | Security | From `analysis.security.secretReuseRisks` (client-side) | No (computed) |
| Recommendations | Security | From `analysis.security.recommendations` (client-side) | No (computed) |
| **MAINTAINABILITY TAB** |
| Maintainability Score | Maintainability | From `analysis.maintainability.score` (client-side) | No (computed) |
| Maintainability Level | Maintainability | From `analysis.maintainability.level` (client-side) | No (computed) |
| Naming Consistency % | Maintainability | From `analysis.maintainability.namingConsistency` (client-side) | No (computed) |
| Logical Grouping Score % | Maintainability | From `analysis.maintainability.logicalGroupingScore` (client-side) | No (computed) |
| Readability Score % | Maintainability | From `analysis.maintainability.readabilityScore` (client-side) | No (computed) |
| Missing Descriptions | Maintainability | From `analysis.maintainability.missingDescriptions` (client-side) | No (computed) |
| Missing Annotations | Maintainability | From `analysis.maintainability.missingAnnotations` (client-side) | No (computed) |
| Node Reuse Opportunities | Maintainability | From `analysis.maintainability.nodeReuseOpportunities` (client-side) | No (computed) |
| Recommendations | Maintainability | From `analysis.maintainability.recommendations` (client-side) | No (computed) |
| **GOVERNANCE TAB** |
| Governance Score | Governance | From `analysis.governance.score` (client-side) | No (computed) |
| Governance Level | Governance | From `analysis.governance.level` (client-side) | No (computed) |
| Auditability % | Governance | From `analysis.governance.auditability` (client-side) | No (computed) |
| Environment Portability % | Governance | From `analysis.governance.environmentPortability` (client-side) | No (computed) |
| Promotion Safety | Governance | From `analysis.governance.promotionSafety` (client-side) | No (computed) |
| PII Exposure Risks | Governance | From `analysis.governance.piiExposureRisks` (client-side) | No (computed) |
| Retention Issues | Governance | From `analysis.governance.retentionIssues` (client-side) | No (computed) |
| Recommendations | Governance | From `analysis.governance.recommendations` (client-side) | No (computed) |
| **DRIFT TAB** |
| Git Configured Status | Drift | From `driftData.gitConfigured` (Backend API - real-time) | No (real-time) |
| Not In Git Status | Drift | From `driftData.notInGit` (Backend API - real-time) | No (real-time) |
| Has Drift | Drift | From `driftData.hasDrift` (Backend API - real-time comparison) | No (real-time) |
| Last Commit SHA | Drift | From `driftData.lastCommitSha` (GitHub API via backend) | No (real-time) |
| Last Commit Date | Drift | From `driftData.lastCommitDate` (GitHub API via backend) | No (real-time) |
| Nodes Added | Drift | From `driftData.summary.nodesAdded` (Backend comparison) | No (real-time) |
| Nodes Removed | Drift | From `driftData.summary.nodesRemoved` (Backend comparison) | No (real-time) |
| Nodes Modified | Drift | From `driftData.summary.nodesModified` (Backend comparison) | No (real-time) |
| Connections Changed | Drift | From `driftData.summary.connectionsChanged` (Backend comparison) | No (real-time) |
| Settings Changed | Drift | From `driftData.summary.settingsChanged` (Backend comparison) | No (real-time) |
| Differences List | Drift | From `driftData.differences` (Backend comparison) | No (real-time) |
| Environment Divergence | Drift | From `analysis.drift.environmentDivergence` (client-side) | No (computed) |
| Duplicate Suspects | Drift | From `analysis.drift.duplicateSuspects` (client-side) | No (computed) |
| Recommendations | Drift | From `analysis.drift.recommendations` (client-side) | No (computed) |
| **OPTIMIZE TAB** |
| Optimization Opportunities | Optimize | From `analysis.optimizations` (client-side) | No (computed) |
| **EXECUTION METRICS** (Used in Hero Section) |
| Total Executions | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Success Count | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Failure Count | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Success Rate % | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Avg Duration (ms) | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| P95 Duration (ms) | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Last Executed At | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |
| Recent Executions | Metrics | Computed from `executionsData` (DB cache) | Yes (DB: executions table) |

## Data Source Types

### 1. **N8N API (Real-time)**
- Workflow metadata (id, name, active, description, tags, createdAt, updatedAt)
- Workflow structure (nodes, connections, settings)
- **Not persisted** - fetched fresh on each page load

### 2. **Client-Side Analysis (Computed)**
- All analysis scores, levels, recommendations
- Graph structure analysis
- Dependency detection
- Security, reliability, performance, cost, maintainability, governance assessments
- **Not persisted** - computed from workflow data in browser

### 3. **Backend API - Drift Detection (Real-time)**
- Git vs N8N comparison
- Commit information from GitHub
- Drift differences
- **Not persisted** - computed on-demand (5 min cache in React Query)

### 4. **Database Cache (Persisted)**
- Execution history and metrics
- **Persisted** - stored in `executions` table, synced from N8N via sync operations
- **Note**: Executions are not real-time - require manual sync to update

## Key Points

1. **Workflow data** is always fresh from N8N API (not cached)
2. **Analysis** is computed client-side from workflow data (not stored)
3. **Drift detection** compares N8N + GitHub in real-time (not stored)
4. **Execution metrics** come from database cache (requires sync to update)
5. **Nothing is persisted** except execution history in the database

