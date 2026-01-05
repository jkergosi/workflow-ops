"""
Drift Retention Service - Handles cleanup of old drift data based on retention policies.

This service implements plan-based retention defaults and cleanup logic for:
- Drift check history
- Incident payloads (soft-delete, metadata preserved)
- Reconciliation artifacts
- Approval records

IMPORTANT: Incidents are never hard-deleted. Only payloads are purged.
Open incidents are never purged regardless of age.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.services.database import db_service
from app.services.feature_service import feature_service

logger = logging.getLogger(__name__)


class DriftRetentionService:
    """Service for managing drift data retention and cleanup."""

    # Cache for retention defaults
    _retention_cache: Dict[str, Dict[str, int]] = {}

    async def _get_retention_defaults(self, plan_name: str) -> Dict[str, int]:
        """Get retention defaults for a plan from database."""
        plan_name = plan_name.lower()
        
        # Check cache first
        if plan_name in self._retention_cache:
            return self._retention_cache[plan_name]
        
        # Fetch from database
        try:
            response = db_service.client.table("plan_retention_defaults").select(
                "drift_checks, closed_incidents, reconciliation_artifacts, approvals"
            ).eq("plan_name", plan_name).single().execute()
            
            if response.data:
                defaults = {
                    "drift_checks": response.data.get("drift_checks", 7),
                    "closed_incidents": response.data.get("closed_incidents", 0),
                    "reconciliation_artifacts": response.data.get("reconciliation_artifacts", 0),
                    "approvals": response.data.get("approvals", 0),
                }
                self._retention_cache[plan_name] = defaults
                return defaults
        except Exception as e:
            logger.warning(f"Failed to fetch retention defaults for plan {plan_name}: {e}")
        
        # Fallback to free plan defaults
        defaults = {
            "drift_checks": 7,
            "closed_incidents": 0,
            "reconciliation_artifacts": 0,
            "approvals": 0,
        }
        self._retention_cache[plan_name] = defaults
        return defaults

    async def get_retention_policy(
        self, tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get retention policy for tenant, with plan-based defaults.

        Returns dict with:
        - retention_enabled: bool
        - retention_days_drift_checks: int
        - retention_days_closed_incidents: int
        - retention_days_reconciliation_artifacts: int
        - retention_days_approvals: int
        - plan: str
        """
        try:
            # Get tenant subscription to determine plan
            subscription = await feature_service.get_tenant_subscription(tenant_id)
            plan = subscription.get("plan", {}).get("name", "free").lower() if subscription else "free"

            # Get drift policy
            policy_response = (
                db_service.client.table("drift_policies")
                .select("*")
                .eq("tenant_id", tenant_id)
                .execute()
            )

            policy = policy_response.data[0] if policy_response.data else None

            # Get plan defaults from database
            plan_defaults = await self._get_retention_defaults(plan)

            # Use policy values if set, otherwise use plan defaults
            retention_enabled = (
                policy.get("retention_enabled", True) if policy else True
            )

            retention_days_drift_checks = (
                policy.get("retention_days_drift_checks")
                if policy and policy.get("retention_days_drift_checks") is not None
                else plan_defaults["drift_checks"]
            )

            retention_days_closed_incidents = (
                policy.get("retention_days_closed_incidents")
                if policy and policy.get("retention_days_closed_incidents") is not None
                else plan_defaults["closed_incidents"]
            )

            retention_days_reconciliation_artifacts = (
                policy.get("retention_days_reconciliation_artifacts")
                if policy and policy.get("retention_days_reconciliation_artifacts") is not None
                else plan_defaults["reconciliation_artifacts"]
            )

            retention_days_approvals = (
                policy.get("retention_days_approvals")
                if policy and policy.get("retention_days_approvals") is not None
                else plan_defaults["approvals"]
            )

            return {
                "retention_enabled": retention_enabled,
                "retention_days_drift_checks": retention_days_drift_checks,
                "retention_days_closed_incidents": retention_days_closed_incidents,
                "retention_days_reconciliation_artifacts": retention_days_reconciliation_artifacts,
                "retention_days_approvals": retention_days_approvals,
                "plan": plan,
            }

        except Exception as e:
            logger.error(f"Failed to get retention policy for tenant {tenant_id}: {e}")
            # Return safe defaults (free tier)
            return {
                "retention_enabled": True,
                "retention_days_drift_checks": 7,
                "retention_days_closed_incidents": 0,
                "retention_days_reconciliation_artifacts": 0,
                "retention_days_approvals": 0,
                "plan": "free",
            }

    async def cleanup_tenant_data(self, tenant_id: str) -> Dict[str, int]:
        """
        Clean up old drift data for a tenant based on retention policy.

        IMPORTANT: Incidents are NEVER hard-deleted. Only payloads are purged.
        Open incidents are never touched regardless of age.

        Returns dict with counts of affected records:
        - drift_checks_deleted: int
        - incident_payloads_purged: int
        - reconciliation_artifacts_deleted: int
        - approvals_deleted: int
        """
        policy = await self.get_retention_policy(tenant_id)

        if not policy["retention_enabled"]:
            logger.info(f"Retention disabled for tenant {tenant_id}, skipping cleanup")
            return {
                "drift_checks_deleted": 0,
                "incident_payloads_purged": 0,
                "reconciliation_artifacts_deleted": 0,
                "approvals_deleted": 0,
            }

        now = datetime.utcnow()
        results = {
            "drift_checks_deleted": 0,
            "incident_payloads_purged": 0,
            "reconciliation_artifacts_deleted": 0,
            "approvals_deleted": 0,
        }

        try:
            # 1. Clean up drift check history
            # Keep at least the most recent check per environment
            if policy["retention_days_drift_checks"] > 0:
                results["drift_checks_deleted"] = await self._cleanup_drift_checks(
                    tenant_id, policy["retention_days_drift_checks"], now
                )

            # 2. Purge incident payloads (NOT delete incidents)
            # Only for CLOSED incidents older than retention period
            if policy["retention_days_closed_incidents"] > 0:
                results["incident_payloads_purged"] = await self._purge_incident_payloads(
                    tenant_id, policy["retention_days_closed_incidents"], now
                )

            # 3. Clean up reconciliation artifacts based on their age
            if policy["retention_days_reconciliation_artifacts"] > 0:
                results["reconciliation_artifacts_deleted"] = await self._cleanup_artifacts(
                    tenant_id, policy["retention_days_reconciliation_artifacts"], now
                )

            # 4. Clean up old approvals
            if policy["retention_days_approvals"] > 0:
                results["approvals_deleted"] = await self._cleanup_approvals(
                    tenant_id, policy["retention_days_approvals"], now
                )

        except Exception as e:
            logger.error(f"Error during cleanup for tenant {tenant_id}: {e}", exc_info=True)

        return results

    async def _cleanup_drift_checks(
        self, tenant_id: str, retention_days: int, now: datetime
    ) -> int:
        """
        Delete drift check history older than retention period.
        Always keeps the most recent check per environment.
        """
        cutoff_date = now - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        try:
            # Get all environments for tenant to preserve latest check for each
            env_response = (
                db_service.client.table("environments")
                .select("id")
                .eq("tenant_id", tenant_id)
                .execute()
            )
            env_ids = [e["id"] for e in (env_response.data or [])]

            if not env_ids:
                return 0

            # For each environment, get the most recent check ID to preserve
            latest_check_ids = []
            for env_id in env_ids:
                latest_response = (
                    db_service.client.table("drift_check_history")
                    .select("id")
                    .eq("environment_id", env_id)
                    .order("checked_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if latest_response.data:
                    latest_check_ids.append(latest_response.data[0]["id"])

            # Count checks older than retention (excluding latest per env)
            count_response = (
                db_service.client.table("drift_check_history")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .lt("checked_at", cutoff_iso)
                .execute()
            )

            # Filter out the latest checks we want to preserve
            checks_to_delete = [
                c["id"] for c in (count_response.data or [])
                if c["id"] not in latest_check_ids
            ]

            if checks_to_delete:
                # Delete old checks (cascade deletes workflow flags)
                for check_id in checks_to_delete:
                    db_service.client.table("drift_check_history").delete().eq(
                        "id", check_id
                    ).execute()

                logger.info(
                    f"Deleted {len(checks_to_delete)} drift checks "
                    f"older than {retention_days} days for tenant {tenant_id}"
                )
                return len(checks_to_delete)

        except Exception as e:
            logger.error(f"Error cleaning drift checks for tenant {tenant_id}: {e}")

        return 0

    async def _purge_incident_payloads(
        self, tenant_id: str, retention_days: int, now: datetime
    ) -> int:
        """
        Purge payloads from closed incidents older than retention period.
        Incident metadata is preserved; only payload data is removed.
        Open incidents are NEVER purged.
        """
        cutoff_date = now - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        try:
            # Find closed incidents older than retention that haven't been purged yet
            incidents_response = (
                db_service.client.table("drift_incidents")
                .select("id")
                .eq("tenant_id", tenant_id)
                .eq("status", "closed")
                .is_("payload_purged_at", "null")
                .lt("closed_at", cutoff_iso)
                .execute()
            )

            incident_ids = [i["id"] for i in (incidents_response.data or [])]

            if not incident_ids:
                return 0

            purged_count = 0
            now_iso = now.isoformat()

            for incident_id in incident_ids:
                try:
                    # Delete from incident_payloads table
                    db_service.client.table("incident_payloads").delete().eq(
                        "incident_id", incident_id
                    ).execute()

                    # Mark incident as payload purged (but keep metadata)
                    db_service.client.table("drift_incidents").update({
                        "payload_purged_at": now_iso,
                        # Clear the inline payload columns too (legacy)
                        "drift_snapshot": None,
                        "affected_workflows": None,
                        "summary": None,
                        "resolution_details": None,
                    }).eq("id", incident_id).execute()

                    purged_count += 1

                except Exception as e:
                    logger.error(f"Error purging payload for incident {incident_id}: {e}")

            if purged_count > 0:
                logger.info(
                    f"Purged payloads from {purged_count} closed incidents "
                    f"older than {retention_days} days for tenant {tenant_id}"
                )

            return purged_count

        except Exception as e:
            logger.error(f"Error purging incident payloads for tenant {tenant_id}: {e}")

        return 0

    async def _cleanup_artifacts(
        self, tenant_id: str, retention_days: int, now: datetime
    ) -> int:
        """Delete reconciliation artifacts older than retention period."""
        cutoff_date = now - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        try:
            # Count artifacts older than retention period
            count_response = (
                db_service.client.table("drift_reconciliation_artifacts")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .lt("created_at", cutoff_iso)
                .execute()
            )

            count = count_response.count if hasattr(count_response, "count") else len(count_response.data or [])

            if count > 0:
                # Delete old reconciliation artifacts
                db_service.client.table("drift_reconciliation_artifacts").delete().eq(
                    "tenant_id", tenant_id
                ).lt("created_at", cutoff_iso).execute()

                logger.info(
                    f"Deleted {count} reconciliation artifacts "
                    f"older than {retention_days} days for tenant {tenant_id}"
                )
                return count

        except Exception as e:
            logger.error(f"Error cleaning artifacts for tenant {tenant_id}: {e}")

        return 0

    async def _cleanup_approvals(
        self, tenant_id: str, retention_days: int, now: datetime
    ) -> int:
        """Delete approval records older than retention period."""
        cutoff_date = now - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        try:
            # Count first
            count_response = (
                db_service.client.table("drift_approvals")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .lt("created_at", cutoff_iso)
                .execute()
            )

            count = count_response.count if hasattr(count_response, "count") else len(count_response.data or [])

            if count > 0:
                # Delete approvals older than retention period
                db_service.client.table("drift_approvals").delete().eq(
                    "tenant_id", tenant_id
                ).lt("created_at", cutoff_iso).execute()

                logger.info(
                    f"Deleted {count} approval records "
                    f"older than {retention_days} days for tenant {tenant_id}"
                )
                return count

        except Exception as e:
            logger.error(f"Error cleaning approvals for tenant {tenant_id}: {e}")

        return 0

    async def cleanup_all_tenants(self) -> Dict[str, Any]:
        """
        Clean up drift data for all tenants.

        Returns summary with total counts per type.
        """
        try:
            # Get all tenants
            tenants_response = db_service.client.table("tenants").select("id").execute()
            tenants = tenants_response.data or []

            total_results = {
                "drift_checks_deleted": 0,
                "incident_payloads_purged": 0,
                "reconciliation_artifacts_deleted": 0,
                "approvals_deleted": 0,
                "tenants_processed": 0,
                "tenants_with_changes": 0,
            }

            for tenant in tenants:
                tenant_id = tenant["id"]
                results = await self.cleanup_tenant_data(tenant_id)

                total_results["drift_checks_deleted"] += results["drift_checks_deleted"]
                total_results["incident_payloads_purged"] += results["incident_payloads_purged"]
                total_results["reconciliation_artifacts_deleted"] += results["reconciliation_artifacts_deleted"]
                total_results["approvals_deleted"] += results["approvals_deleted"]
                total_results["tenants_processed"] += 1

                if any(
                    results[key] > 0
                    for key in [
                        "drift_checks_deleted",
                        "incident_payloads_purged",
                        "reconciliation_artifacts_deleted",
                        "approvals_deleted",
                    ]
                ):
                    total_results["tenants_with_changes"] += 1

            logger.info(
                f"Retention cleanup completed: "
                f"{total_results['drift_checks_deleted']} drift checks deleted, "
                f"{total_results['incident_payloads_purged']} incident payloads purged, "
                f"{total_results['reconciliation_artifacts_deleted']} artifacts deleted, "
                f"{total_results['approvals_deleted']} approvals deleted "
                f"across {total_results['tenants_processed']} tenants"
            )

            return total_results

        except Exception as e:
            logger.error(f"Error during global retention cleanup: {e}", exc_info=True)
            return {
                "drift_checks_deleted": 0,
                "incident_payloads_purged": 0,
                "reconciliation_artifacts_deleted": 0,
                "approvals_deleted": 0,
                "tenants_processed": 0,
                "tenants_with_changes": 0,
                "error": str(e),
            }


drift_retention_service = DriftRetentionService()

