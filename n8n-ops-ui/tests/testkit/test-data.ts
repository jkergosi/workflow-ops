/**
 * Test data fixtures for frontend E2E tests.
 * 
 * Provides stable, realistic test data matching backend responses.
 */

export const TestData = {
  auth: {
    admin: {
      user: {
        id: '00000000-0000-0000-0000-000000000001',
        email: 'admin@test.com',
        name: 'Admin User',
        role: 'admin',
      },
      tenant: {
        id: '00000000-0000-0000-0000-000000000002',
        name: 'Test Organization',
        subscription_tier: 'pro',
      },
    },
    developer: {
      user: {
        id: '00000000-0000-0000-0000-000000000003',
        email: 'dev@test.com',
        name: 'Developer User',
        role: 'developer',
      },
      tenant: {
        id: '00000000-0000-0000-0000-000000000002',
        name: 'Test Organization',
        subscription_tier: 'pro',
      },
    },
    platform_admin: {
      user: {
        id: '00000000-0000-0000-0000-000000000004',
        email: 'platformadmin@test.com',
        name: 'Platform Admin',
        role: 'admin',
      },
      is_platform_admin: true,
      tenant: {
        id: '00000000-0000-0000-0000-000000000002',
        name: 'Test Organization',
        subscription_tier: 'pro',
      },
    },
  },

  environments: {
    list: [
      {
        id: 'env-dev',
        tenant_id: '00000000-0000-0000-0000-000000000002',
        n8n_name: 'Development',
        n8n_type: 'development',
        n8n_base_url: 'https://dev.n8n.example.com',
        is_active: true,
        workflow_count: 5,
      },
      {
        id: 'env-prod',
        tenant_id: '00000000-0000-0000-0000-000000000002',
        n8n_name: 'Production',
        n8n_type: 'production',
        n8n_base_url: 'https://prod.n8n.example.com',
        is_active: true,
        workflow_count: 10,
      },
    ],
  },

  pipelines: {
    list: [
      {
        id: 'pipeline-1',
        tenant_id: '00000000-0000-0000-0000-000000000002',
        name: 'Dev to Prod',
        description: 'Promote workflows from development to production',
        is_active: true,
        stages: [
          {
            source_environment_id: 'env-dev',
            target_environment_id: 'env-prod',
            gates: {
              require_clean_drift: false,
              run_pre_flight_validation: true,
            },
          },
        ],
      },
    ],
  },

  promotions: {
    created: {
      id: 'promotion-1',
      pipeline_id: 'pipeline-1',
      source_environment_id: 'env-dev',
      target_environment_id: 'env-prod',
      status: 'PENDING',
      workflow_selections: ['wf-1', 'wf-2'],
      created_at: '2024-01-08T00:00:00.000Z',
    },
    executing: {
      id: 'promotion-1',
      status: 'RUNNING',
      progress: 50,
    },
    list: [
      {
        id: 'promotion-1',
        pipeline_id: 'pipeline-1',
        status: 'COMPLETED',
        created_at: '2024-01-07T10:00:00.000Z',
      },
    ],
  },

  drift: {
    incidents: [
      {
        id: 'incident-1',
        tenant_id: '00000000-0000-0000-0000-000000000002',
        environment_id: 'env-prod',
        status: 'DETECTED',
        title: 'Drift detected in Customer Onboarding',
        severity: 'high',
        detected_at: '2024-01-08T00:00:00.000Z',
        affected_workflows: ['wf-1'],
      },
    ],
    acknowledged: {
      id: 'incident-1',
      status: 'ACKNOWLEDGED',
      acknowledged_at: '2024-01-08T00:05:00.000Z',
    },
    stabilized: {
      id: 'incident-1',
      status: 'STABILIZED',
      stabilized_at: '2024-01-08T00:10:00.000Z',
      reason: 'Root cause identified',
    },
    reconciled: {
      id: 'incident-1',
      status: 'RECONCILED',
      reconciled_at: '2024-01-08T00:15:00.000Z',
      resolution_type: 'promote',
    },
  },

  canonical: {
    preflightSuccess: {
      ready: true,
      errors: [],
      warnings: [],
    },
    inventoryStarted: {
      job_id: 'job-1',
      status: 'RUNNING',
    },
    untrackedWorkflows: [
      {
        id: 'wf-untracked',
        environment_id: 'env-prod',
        name: 'Untracked Workflow',
        status: 'UNTRACKED',
      },
    ],
    matrix: {
      workflows: [
        {
          canonical_id: 'canonical-1',
          name: 'Customer Onboarding',
          environments: {
            'env-dev': {
              status: 'linked',
              synced: true,
            },
            'env-prod': {
              status: 'drift',
              synced: false,
            },
          },
        },
      ],
    },
  },

  impersonation: {
    started: {
      session_id: 'session-1',
      token: 'imp_test_token',
      impersonated_user_id: '00000000-0000-0000-0000-000000000003',
      expires_at: '2024-01-08T08:00:00.000Z',
    },
    ended: {
      session_id: 'session-1',
      ended_at: '2024-01-08T01:00:00.000Z',
    },
  },
};

