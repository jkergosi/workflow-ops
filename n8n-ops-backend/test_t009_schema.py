"""
Quick test to verify T009 enhanced schema models
"""
from app.schemas.canonical_workflow import (
    OnboardingInventoryResults,
    WorkflowInventoryResult,
    EnvironmentInventoryResult
)

# Test that the schema models are properly defined
print('Testing schema models...')

# Create a sample result
result = OnboardingInventoryResults(
    workflows_inventoried=10,
    canonical_ids_generated=5,
    auto_links=3,
    suggested_links=1,
    untracked_workflows=2,
    errors=['Sample error'],
    has_errors=True,
    workflow_results=[
        WorkflowInventoryResult(
            environment_id='env-1',
            environment_name='Production',
            workflow_id='wf-123',
            workflow_name='Test Workflow',
            canonical_id='canonical-456',
            status='success',
            error=None,
            is_new_untracked=False
        ),
        WorkflowInventoryResult(
            environment_id='env-2',
            environment_name='Staging',
            workflow_id='wf-789',
            workflow_name='Failed Workflow',
            canonical_id=None,
            status='error',
            error='Connection timeout',
            is_new_untracked=None
        )
    ],
    environment_results={
        'env-1': EnvironmentInventoryResult(
            environment_id='env-1',
            environment_name='Production',
            success_count=5,
            error_count=0,
            skipped_count=1,
            linked_count=3,
            untracked_count=2
        ),
        'env-2': EnvironmentInventoryResult(
            environment_id='env-2',
            environment_name='Staging',
            success_count=3,
            error_count=2,
            skipped_count=0
        )
    }
)

# Verify serialization
print('✓ Schema models created successfully')
print(f'✓ Workflow results count: {len(result.workflow_results)}')
print(f'✓ Environment results count: {len(result.environment_results)}')
print(f'✓ Has errors flag: {result.has_errors}')
print(f'✓ Total errors: {len(result.errors)}')

# Test JSON serialization
json_output = result.model_dump_json(indent=2)
print('\n✓ JSON serialization successful')
print(f'Output length: {len(json_output)} characters')

# Show sample output
print('\nSample JSON output (first 500 chars):')
print(json_output[:500])

print('\n✅ All schema model tests passed!')
