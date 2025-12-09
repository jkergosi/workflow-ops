"""
Workflow Analysis Service

Ports the TypeScript workflow analysis logic to Python.
Computes comprehensive analysis of n8n workflows including:
- Graph structure and complexity
- Reliability and error handling
- Performance characteristics
- Cost analysis
- Security assessment
- Maintainability metrics
- Governance and compliance
"""

from typing import Dict, Any, List, Optional
import json
import math


def is_trigger_node(node_type: str) -> bool:
    """Check if a node is a trigger node"""
    type_lc = node_type.lower()
    return any(keyword in type_lc for keyword in ['trigger', 'webhook', 'schedule', 'cron'])


def get_node_category(node_type: str) -> str:
    """Categorize a node by its type"""
    type_lc = node_type.lower()
    if 'trigger' in type_lc or 'webhook' in type_lc:
        return 'trigger'
    if 'http' in type_lc or 'api' in type_lc:
        return 'api'
    if any(db in type_lc for db in ['postgres', 'mysql', 'mongo', 'database']):
        return 'database'
    if any(logic in type_lc for logic in ['if', 'switch', 'merge']):
        return 'logic'
    if 'code' in type_lc or 'function' in type_lc:
        return 'code'
    if 'set' in type_lc or 'item' in type_lc:
        return 'transform'
    if any(ai in type_lc for ai in ['openai', 'anthropic', 'llm']):
        return 'ai'
    return 'other'


def count_connections(connections: Optional[Dict[str, Any]]) -> int:
    """Count the total number of connections in a workflow"""
    if not connections:
        return 0
    
    count = 0
    for node_conns in connections.values():
        if not isinstance(node_conns, dict):
            continue
        for output_conns in node_conns.values():
            if not isinstance(output_conns, list):
                continue
            for conn_array in output_conns:
                if isinstance(conn_array, list):
                    count += len(conn_array)
    
    return count


def calculate_complexity(node_count: int, edge_count: int, max_branching: int) -> Dict[str, Any]:
    """Calculate workflow complexity score and level"""
    score = min(100, round((node_count * 3 + edge_count * 2 + max_branching * 5)))
    
    if score < 25:
        level = 'simple'
    elif score < 50:
        level = 'moderate'
    elif score < 75:
        level = 'complex'
    else:
        level = 'very-complex'
    
    return {'score': score, 'level': level}


def infer_purpose(nodes: List[Dict[str, Any]]) -> str:
    """Infer the purpose of a workflow from its nodes"""
    types = [node.get('type', '').lower() for node in nodes]
    
    if any('webhook' in t for t in types):
        if any('slack' in t or 'discord' in t for t in types):
            return 'Webhook-triggered workflow that sends notifications'
        return 'Webhook-triggered automation workflow'
    
    if any('schedule' in t or 'cron' in t for t in types):
        return 'Scheduled automation that runs on a regular interval'
    
    if any('openai' in t or 'anthropic' in t for t in types):
        return 'AI-powered workflow using language models'
    
    if any('postgres' in t or 'mysql' in t for t in types):
        return 'Database-driven workflow for data processing'
    
    return 'Automation workflow for data processing and integration'


def infer_execution_summary(nodes: List[Dict[str, Any]]) -> str:
    """Generate an execution summary from workflow nodes"""
    node_count = len(nodes)
    triggers = [n for n in nodes if is_trigger_node(n.get('type', ''))]
    outputs = [n for n in nodes if 'send' in n.get('type', '').lower() or 'write' in n.get('type', '').lower()]
    
    summary = f'Workflow with {node_count} nodes'
    if triggers:
        trigger_names = [t.get('name', '') for t in triggers]
        summary += f", triggered by {', '.join(trigger_names)}"
    if outputs:
        summary += f', outputs to {len(outputs)} destination(s)'
    
    return summary


def extract_external_systems(nodes: List[Dict[str, Any]]) -> List[str]:
    """Extract external systems used by the workflow"""
    systems = set()
    
    for node in nodes:
        type_lc = node.get('type', '').lower()
        if 'http' in type_lc:
            systems.add('HTTP/REST APIs')
        if 'postgres' in type_lc:
            systems.add('PostgreSQL')
        if 'mysql' in type_lc:
            systems.add('MySQL')
        if 'mongo' in type_lc:
            systems.add('MongoDB')
        if 'slack' in type_lc:
            systems.add('Slack')
        if 'discord' in type_lc:
            systems.add('Discord')
        if 'google' in type_lc:
            systems.add('Google Services')
        if 'openai' in type_lc:
            systems.add('OpenAI')
        if 'anthropic' in type_lc:
            systems.add('Anthropic')
        if 'github' in type_lc:
            systems.add('GitHub')
        if 'email' in type_lc or 'smtp' in type_lc:
            systems.add('Email')
        if 's3' in type_lc or 'aws' in type_lc:
            systems.add('AWS')
    
    return list(systems)


def categorize_system(name: str) -> str:
    """Categorize an external system"""
    name_lc = name.lower()
    if 'api' in name_lc or 'http' in name_lc:
        return 'api'
    if any(db in name_lc for db in ['sql', 'mongo', 'database']):
        return 'database'
    if 's3' in name_lc or 'file' in name_lc:
        return 'file'
    return 'service'


def extract_dependencies(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract external dependencies from workflow nodes"""
    deps = {}
    
    for node in nodes:
        systems = extract_external_systems([node])
        for sys in systems:
            if sys in deps:
                deps[sys]['nodeCount'] += 1
                deps[sys]['nodes'].append(node.get('name', ''))
            else:
                deps[sys] = {
                    'name': sys,
                    'type': categorize_system(sys),
                    'nodeCount': 1,
                    'nodes': [node.get('name', '')]
                }
    
    return list(deps.values())


def analyze_reliability(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze workflow reliability and error handling"""
    error_handling_nodes = len([
        n for n in nodes
        if any(keyword in n.get('type', '').lower() for keyword in ['error', 'try', 'catch'])
    ])
    
    retry_nodes = len([
        n for n in nodes
        if (n.get('parameters', {}).get('retry') or 'retry' in n.get('type', '').lower())
    ])
    
    continue_on_fail_count = len([
        n for n in nodes
        if n.get('parameters', {}).get('continueOnFail') is True
    ])
    
    score = min(100, 50 + error_handling_nodes * 10 + retry_nodes * 10 + continue_on_fail_count * 5)
    
    if score >= 80:
        level = 'excellent'
    elif score >= 60:
        level = 'good'
    elif score >= 40:
        level = 'warning'
    else:
        level = 'critical'
    
    missing_error_handling = [
        f"{n.get('name', '')} lacks error handling"
        for n in nodes
        if ('http' in n.get('type', '').lower() or 'api' in n.get('type', '').lower())
        and not n.get('parameters', {}).get('continueOnFail')
    ]
    
    failure_hotspots = [
        f"{n.get('name', '')} is a potential failure point"
        for n in nodes
        if 'code' in n.get('type', '').lower() or 'function' in n.get('type', '').lower()
    ]
    
    recommendations = []
    if error_handling_nodes == 0 and len(nodes) > 3:
        recommendations.append('Add error handling nodes to catch and handle failures gracefully')
    if retry_nodes == 0 and len(nodes) > 5:
        recommendations.append('Consider adding retry logic for external API calls')
    if not recommendations:
        recommendations.append('Reliability looks good! Consider adding monitoring for production use.')
    
    return {
        'score': score,
        'level': level,
        'continueOnFailCount': continue_on_fail_count,
        'errorHandlingNodes': error_handling_nodes,
        'retryNodes': retry_nodes,
        'missingErrorHandling': missing_error_handling,
        'failureHotspots': failure_hotspots,
        'recommendations': recommendations
    }


def analyze_performance(nodes: List[Dict[str, Any]], edge_count: int) -> Dict[str, Any]:
    """Analyze workflow performance characteristics"""
    has_parallelism = edge_count > len(nodes)
    api_calls = len([n for n in nodes if 'http' in n.get('type', '').lower()])
    db_calls = len([
        n for n in nodes
        if 'postgres' in n.get('type', '').lower() or 'mysql' in n.get('type', '').lower()
    ])
    
    total_calls = api_calls + db_calls
    if total_calls > 5:
        complexity = 'high'
    elif total_calls > 2:
        complexity = 'medium'
    else:
        complexity = 'low'
    
    score = max(0, min(100, 100 - (api_calls * 5 + db_calls * 5)))
    
    if score >= 80:
        level = 'excellent'
    elif score >= 60:
        level = 'good'
    elif score >= 40:
        level = 'warning'
    else:
        level = 'critical'
    
    sequential_bottlenecks = [
        f"{n.get('name', '')} introduces delay"
        for n in nodes
        if 'wait' in n.get('type', '').lower()
    ]
    
    large_payload_risks = [
        f"{n.get('name', '')} may process large payloads"
        for n in nodes
        if 'batch' in n.get('type', '').lower()
    ]
    
    recommendations = ['Good use of parallelism'] if has_parallelism else ['Consider parallelizing independent operations']
    
    return {
        'score': score,
        'level': level,
        'hasParallelism': has_parallelism,
        'estimatedComplexity': complexity,
        'sequentialBottlenecks': sequential_bottlenecks,
        'redundantCalls': [],
        'largePayloadRisks': large_payload_risks,
        'recommendations': recommendations
    }


def analyze_cost(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze workflow cost characteristics"""
    triggers = [n for n in nodes if is_trigger_node(n.get('type', ''))]
    has_schedule = any('schedule' in t.get('type', '').lower() or 'cron' in t.get('type', '').lower() for t in triggers)
    has_webhook = any('webhook' in t.get('type', '').lower() for t in triggers)
    
    llm_nodes = [
        n for n in nodes
        if any(keyword in n.get('type', '').lower() for keyword in ['openai', 'anthropic', 'llm'])
    ]
    
    api_heavy_nodes = [n for n in nodes if 'http' in n.get('type', '').lower()]
    
    if len(llm_nodes) > 2:
        level = 'very-high'
    elif len(llm_nodes) > 0:
        level = 'high'
    elif len(api_heavy_nodes) > 3:
        level = 'medium'
    else:
        level = 'low'
    
    if has_schedule:
        trigger_frequency = 'Scheduled execution'
    elif has_webhook:
        trigger_frequency = 'On-demand (webhook)'
    else:
        trigger_frequency = 'Manual'
    
    cost_amplifiers = ['LLM usage significantly impacts costs'] if llm_nodes else []
    throttling_candidates = ['Consider rate limiting API calls'] if len(api_heavy_nodes) > 3 else []
    
    recommendations = []
    if llm_nodes:
        recommendations.extend(['Consider caching LLM responses', 'Use smaller models where appropriate'])
    else:
        recommendations.append('Cost profile looks reasonable')
    
    return {
        'level': level,
        'triggerFrequency': trigger_frequency,
        'apiHeavyNodes': [n.get('name', '') for n in api_heavy_nodes],
        'llmNodes': [n.get('name', '') for n in llm_nodes],
        'costAmplifiers': cost_amplifiers,
        'throttlingCandidates': throttling_candidates,
        'recommendations': recommendations
    }


def analyze_security(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze workflow security characteristics"""
    credentialed_nodes = [
        n for n in nodes
        if n.get('credentials') and len(n.get('credentials', {})) > 0
    ]
    
    credential_types = set()
    for node in credentialed_nodes:
        creds = node.get('credentials', {})
        if isinstance(creds, dict):
            credential_types.update(creds.keys())
    
    hardcoded_secret_signals = []
    for node in nodes:
        params_str = json.dumps(node.get('parameters', {})).lower()
        if any(keyword in params_str for keyword in ['password', 'api_key', 'secret']):
            hardcoded_secret_signals.append(f"{node.get('name', '')} may contain hardcoded secrets")
    
    score = max(0, min(100, 100 - (len(hardcoded_secret_signals) * 20)))
    
    if score >= 80:
        level = 'excellent'
    elif score >= 60:
        level = 'good'
    elif score >= 40:
        level = 'warning'
    else:
        level = 'critical'
    
    secret_reuse_risks = []
    if len(credential_types) > 5:
        secret_reuse_risks.append('Many credential types in use - review for least privilege')
    
    recommendations = []
    if hardcoded_secret_signals:
        recommendations.extend(['Move hardcoded secrets to credential store', 'Review credential usage'])
    else:
        recommendations.append('Security practices look good')
    
    return {
        'score': score,
        'level': level,
        'credentialCount': len(credentialed_nodes),
        'credentialTypes': list(credential_types),
        'hardcodedSecretSignals': hardcoded_secret_signals,
        'overPrivilegedRisks': [],
        'secretReuseRisks': secret_reuse_risks,
        'recommendations': recommendations
    }


def analyze_maintainability(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze workflow maintainability"""
    missing_descriptions = [
        f"{n.get('name', n.get('id', ''))} has a default name"
        for n in nodes
        if not n.get('name') or n.get('name', '').startswith('Node')
    ]
    
    well_named = [
        n for n in nodes
        if n.get('name') and not n.get('name', '').startswith('Node') and len(n.get('name', '')) > 3
    ]
    
    naming_consistency = round((len(well_named) / len(nodes) * 100)) if nodes else 100
    readability_score = naming_consistency
    logical_grouping_score = min(100, naming_consistency + 20)
    
    score = round((naming_consistency + readability_score + logical_grouping_score) / 3)
    
    if score >= 80:
        level = 'excellent'
    elif score >= 60:
        level = 'good'
    elif score >= 40:
        level = 'warning'
    else:
        level = 'critical'
    
    missing_annotations = [
        n.get('name', n.get('id', ''))
        for n in nodes
        if not n.get('name') or len(n.get('name', '')) < 4
    ]
    
    recommendations = []
    if naming_consistency < 80:
        recommendations.extend(['Improve node naming for better readability', 'Add descriptions to complex nodes'])
    else:
        recommendations.append('Maintainability looks good')
    
    return {
        'score': score,
        'level': level,
        'namingConsistency': naming_consistency,
        'logicalGroupingScore': logical_grouping_score,
        'readabilityScore': readability_score,
        'missingDescriptions': missing_descriptions,
        'missingAnnotations': missing_annotations,
        'nodeReuseOpportunities': [],
        'recommendations': recommendations
    }


def analyze_governance(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze workflow governance and compliance"""
    has_env_vars = any(
        '$env' in json.dumps(n.get('parameters', {})) or 'process.env' in json.dumps(n.get('parameters', {}))
        for n in nodes
    )
    
    environment_portability = 80 if has_env_vars else 60
    auditability = 90 if all(n.get('name') and len(n.get('name', '')) > 3 for n in nodes) else 60
    
    pii_exposure_risks = []
    for node in nodes:
        params_str = json.dumps(node.get('parameters', {})).lower()
        if any(keyword in params_str for keyword in ['email', 'phone', 'ssn']):
            pii_exposure_risks.append(f"{node.get('name', '')} may handle PII data")
    
    score = round((environment_portability + auditability) / 2)
    
    if score >= 80:
        level = 'excellent'
    elif score >= 60:
        level = 'good'
    elif score >= 40:
        level = 'warning'
    else:
        level = 'critical'
    
    recommendations = []
    if pii_exposure_risks:
        recommendations.extend(['Review PII handling practices', 'Ensure data retention policies are followed'])
    else:
        recommendations.append('Governance looks good')
    
    return {
        'score': score,
        'level': level,
        'auditability': auditability,
        'environmentPortability': environment_portability,
        'promotionSafety': len(pii_exposure_risks) == 0,
        'piiExposureRisks': pii_exposure_risks,
        'retentionIssues': [],
        'recommendations': recommendations
    }


def analyze_drift() -> Dict[str, Any]:
    """Analyze workflow drift (static analysis)"""
    return {
        'hasGitMismatch': False,
        'environmentDivergence': [],
        'duplicateSuspects': [],
        'partialCopies': [],
        'recommendations': ['Regularly sync with version control to track changes']
    }


def generate_optimizations(nodes: List[Dict[str, Any]], partial_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate optimization suggestions"""
    suggestions = []
    
    if len(nodes) > 20:
        suggestions.append({
            'title': 'Split into sub-workflows',
            'description': 'Large workflows are harder to maintain. Consider breaking into smaller, reusable sub-workflows.',
            'impact': 'high',
            'effort': 'medium',
            'category': 'maintainability'
        })
    
    cost_analysis = partial_analysis.get('cost', {})
    if cost_analysis.get('llmNodes') and len(cost_analysis.get('llmNodes', [])) > 1:
        suggestions.append({
            'title': 'Implement LLM response caching',
            'description': 'Cache responses for similar inputs to reduce API costs and improve performance.',
            'impact': 'high',
            'effort': 'medium',
            'category': 'cost'
        })
    
    reliability_analysis = partial_analysis.get('reliability', {})
    if reliability_analysis.get('errorHandlingNodes', 0) == 0:
        suggestions.append({
            'title': 'Add error handling',
            'description': 'Implement try-catch patterns and error handling nodes for robust execution.',
            'impact': 'high',
            'effort': 'low',
            'category': 'reliability'
        })
    
    return suggestions


def analyze_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main analysis function - computes comprehensive workflow analysis
    
    Args:
        workflow: Workflow dictionary from N8N API
        
    Returns:
        Dictionary matching WorkflowAnalysis interface structure
    """
    try:
        nodes = workflow.get('nodes', [])
        connections = workflow.get('connections', {})
        
        # Graph analysis
        node_count = len(nodes)
        edge_count = count_connections(connections)
        trigger_count = len([n for n in nodes if is_trigger_node(n.get('type', ''))])
        
        # Calculate sink count
        sink_count = 0
        for node in nodes:
            node_id = node.get('id', '')
            if not connections or node_id not in connections:
                sink_count += 1
            else:
                node_conns = connections.get(node_id, {})
                if not node_conns or not any(node_conns.values()):
                    sink_count += 1
        
        # Calculate max branching
        max_branching = 1
        if connections:
            for node_conns in connections.values():
                if isinstance(node_conns, dict):
                    for output_conns in node_conns.values():
                        if isinstance(output_conns, list):
                            for conn_array in output_conns:
                                if isinstance(conn_array, list):
                                    max_branching = max(max_branching, len(conn_array))
        
        complexity_result = calculate_complexity(node_count, edge_count, max_branching)
        complexity_score = complexity_result['score']
        complexity_level = complexity_result['level']
        
        graph = {
            'nodeCount': node_count,
            'edgeCount': edge_count,
            'complexityScore': complexity_score,
            'complexityLevel': complexity_level,
            'maxDepth': math.ceil(math.log2(node_count + 1)) if node_count > 0 else 0,
            'maxBranching': max_branching,
            'isLinear': max_branching <= 1,
            'hasFanOut': max_branching > 2,
            'hasFanIn': sink_count < node_count - trigger_count,
            'hasCycles': False,  # Would need proper cycle detection
            'triggerCount': trigger_count,
            'sinkCount': sink_count
        }
        
        # Node analysis
        node_analysis = []
        for node in nodes:
            node_analysis.append({
                'id': node.get('id', ''),
                'name': node.get('name', ''),
                'type': node.get('type', ''),
                'category': get_node_category(node.get('type', '')),
                'isCredentialed': bool(node.get('credentials') and len(node.get('credentials', {})) > 0),
                'isTrigger': is_trigger_node(node.get('type', ''))
            })
        
        # Dependencies
        dependencies = extract_dependencies(nodes)
        
        # Summary
        summary = {
            'purpose': infer_purpose(nodes),
            'executionSummary': infer_execution_summary(nodes),
            'triggerTypes': [n.get('type', '') for n in nodes if is_trigger_node(n.get('type', ''))],
            'externalSystems': extract_external_systems(nodes)
        }
        
        # Detailed analyses
        reliability = analyze_reliability(nodes)
        performance = analyze_performance(nodes, edge_count)
        cost = analyze_cost(nodes)
        security = analyze_security(nodes)
        maintainability = analyze_maintainability(nodes)
        governance = analyze_governance(nodes)
        drift = analyze_drift()
        
        partial_analysis = {'cost': cost, 'reliability': reliability}
        optimizations = generate_optimizations(nodes, partial_analysis)
        
        return {
            'graph': graph,
            'nodes': node_analysis,
            'dependencies': dependencies,
            'summary': summary,
            'reliability': reliability,
            'performance': performance,
            'cost': cost,
            'security': security,
            'maintainability': maintainability,
            'governance': governance,
            'drift': drift,
            'optimizations': optimizations
        }
    except Exception as e:
        # Return minimal analysis structure on error
        return {
            'graph': {
                'nodeCount': len(workflow.get('nodes', [])),
                'edgeCount': 0,
                'complexityScore': 0,
                'complexityLevel': 'simple',
                'maxDepth': 0,
                'maxBranching': 1,
                'isLinear': True,
                'hasFanOut': False,
                'hasFanIn': False,
                'hasCycles': False,
                'triggerCount': 0,
                'sinkCount': 0
            },
            'nodes': [],
            'dependencies': [],
            'summary': {
                'purpose': 'Unable to analyze workflow',
                'executionSummary': 'Analysis failed',
                'triggerTypes': [],
                'externalSystems': []
            },
            'reliability': {
                'score': 0,
                'level': 'critical',
                'continueOnFailCount': 0,
                'errorHandlingNodes': 0,
                'retryNodes': 0,
                'missingErrorHandling': [],
                'failureHotspots': [],
                'recommendations': [f'Analysis error: {str(e)}']
            },
            'performance': {
                'score': 0,
                'level': 'critical',
                'hasParallelism': False,
                'estimatedComplexity': 'low',
                'sequentialBottlenecks': [],
                'redundantCalls': [],
                'largePayloadRisks': [],
                'recommendations': []
            },
            'cost': {
                'level': 'low',
                'triggerFrequency': 'Unknown',
                'apiHeavyNodes': [],
                'llmNodes': [],
                'costAmplifiers': [],
                'throttlingCandidates': [],
                'recommendations': []
            },
            'security': {
                'score': 0,
                'level': 'critical',
                'credentialCount': 0,
                'credentialTypes': [],
                'hardcodedSecretSignals': [],
                'overPrivilegedRisks': [],
                'secretReuseRisks': [],
                'recommendations': []
            },
            'maintainability': {
                'score': 0,
                'level': 'critical',
                'namingConsistency': 0,
                'logicalGroupingScore': 0,
                'readabilityScore': 0,
                'missingDescriptions': [],
                'missingAnnotations': [],
                'nodeReuseOpportunities': [],
                'recommendations': []
            },
            'governance': {
                'score': 0,
                'level': 'critical',
                'auditability': 0,
                'environmentPortability': 0,
                'promotionSafety': False,
                'piiExposureRisks': [],
                'retentionIssues': [],
                'recommendations': []
            },
            'drift': {
                'hasGitMismatch': False,
                'environmentDivergence': [],
                'duplicateSuspects': [],
                'partialCopies': [],
                'recommendations': []
            },
            'optimizations': []
        }

