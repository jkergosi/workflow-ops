-- Migration: Backfill tenant provider subscriptions
-- Date: 2026-01-04
-- Description: Create provider subscriptions for existing tenants based on their subscription_tier

-- For each tenant without a provider subscription, create one based on their subscription_tier
-- Maps subscription_tier to provider_plans.name for the n8n provider

INSERT INTO tenant_provider_subscriptions (tenant_id, provider_id, plan_id, status, billing_cycle)
SELECT
    t.id as tenant_id,
    p.id as provider_id,
    pp.id as plan_id,
    'active' as status,
    'monthly' as billing_cycle
FROM tenants t
CROSS JOIN providers p
JOIN provider_plans pp ON pp.provider_id = p.id
WHERE p.name = 'n8n'
  AND pp.name = COALESCE(LOWER(t.subscription_tier), 'free')
  AND NOT EXISTS (
    SELECT 1 FROM tenant_provider_subscriptions tps
    WHERE tps.tenant_id = t.id AND tps.provider_id = p.id
  );

-- Also handle cases where subscription_tier doesn't match a plan name (fallback to free)
INSERT INTO tenant_provider_subscriptions (tenant_id, provider_id, plan_id, status, billing_cycle)
SELECT
    t.id as tenant_id,
    p.id as provider_id,
    pp.id as plan_id,
    'active' as status,
    'monthly' as billing_cycle
FROM tenants t
CROSS JOIN providers p
JOIN provider_plans pp ON pp.provider_id = p.id AND pp.name = 'free'
WHERE p.name = 'n8n'
  AND NOT EXISTS (
    SELECT 1 FROM tenant_provider_subscriptions tps
    WHERE tps.tenant_id = t.id AND tps.provider_id = p.id
  );
