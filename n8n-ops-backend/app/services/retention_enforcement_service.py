"""
Retention Enforcement Service

Enforces plan-based retention policies for executions and audit logs.
This service works in conjunction with entitlements to automatically clean up
old data based on each tenant's subscription plan retention limits.

Key Features:
- Plan-based retention periods (e.g., 7 days for Free, 30 days for Pro)
- Automatic enforcement for executions and audit logs
- Integration with entitlements service for plan determination
- Batch processing to avoid database lock contention
- Comprehensive logging and metrics for monitoring

Related Components:
- T009: Retention enforcement service implementation (THIS FILE)
- T010: Add retention policy enforcement for executions
- T011: Add retention policy enforcement for audit logs
- T012: Create scheduled retention job

Usage:
    # Enforce retention for a specific tenant
    result = await retention_enforcement_service.enforce_execution_retention(tenant_id)

    # Enforce retention for all tenants (scheduled job)
    summary = await retention_enforcement_service.enforce_all_tenants_retention()

    # Get retention policy for tenant based on plan
    policy = await retention_enforcement_service.get_tenant_retention_policy(tenant_id)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone

from app.services.database import db_service
from app.services.entitlements_service import entitlements_service
from app.core.config import settings

logger = logging.getLogger(__name__)


# Default retention periods by plan (in days)
# These map to the observability_limits feature in entitlements
PLAN_RETENTION_PERIODS: Dict[str, int] = {
    "free": 7,  # 7 days for Free plan
    "pro": 30,  # 30 days for Pro plan
    "agency": 90,  # 90 days for Agency plan
    "enterprise": 365,  # 1 year for Enterprise plan
}

# Default batch size for deletion operations
DEFAULT_BATCH_SIZE = 1000

# Minimum records to keep regardless of retention policy (safety threshold)
MIN_RECORDS_TO_KEEP = 100


class RetentionEnforcementService:
    """
    Service for enforcing plan-based retention policies on executions and audit logs.

    This service automatically cleans up old records based on each tenant's
    subscription plan limits, ensuring compliance with plan-based entitlements.
    """

    def __init__(self):
        """Initialize the retention enforcement service."""
        self.batch_size = getattr(settings, 'RETENTION_JOB_BATCH_SIZE', DEFAULT_BATCH_SIZE)
        self.default_retention_days = getattr(settings, 'DEFAULT_RETENTION_DAYS', 7)

    # =========================================================================
    # Retention Policy Determination
    # =========================================================================

    async def get_tenant_retention_policy(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get the retention policy for a tenant based on their subscription plan.

        Queries the entitlements service to determine the tenant's current plan
        and returns the appropriate retention period for that plan.

        Args:
            tenant_id: The tenant ID

        Returns:
            Dictionary containing:
            - plan_name: str - Name of the tenant's plan
            - retention_days: int - Number of days to retain data
            - execution_retention_days: int - Retention for executions
            - audit_log_retention_days: int - Retention for audit logs

        Example:
            policy = await retention_enforcement_service.get_tenant_retention_policy("tenant-uuid")
            print(f"Retention: {policy['retention_days']} days for {policy['plan_name']} plan")
        """
        try:
            # Get tenant's entitlements (includes plan information)
            entitlements = await entitlements_service.get_tenant_entitlements(tenant_id)
            plan_name = entitlements.get("plan_name", "free")

            # Get retention limit from entitlements features
            # The observability_limits feature contains retention period in days
            retention_days = entitlements.get("features", {}).get("observability_limits", self.default_retention_days)

            # If observability_limits is 0 or None, fallback to plan-based default
            if not retention_days or retention_days == 0:
                retention_days = PLAN_RETENTION_PERIODS.get(plan_name, self.default_retention_days)

            logger.info(
                f"Tenant {tenant_id} on {plan_name} plan has {retention_days} days retention"
            )

            return {
                "plan_name": plan_name,
                "retention_days": retention_days,
                "execution_retention_days": retention_days,
                "audit_log_retention_days": retention_days,
            }

        except Exception as e:
            logger.error(f"Failed to get retention policy for tenant {tenant_id}: {e}")
            # Fallback to safe default
            return {
                "plan_name": "free",
                "retention_days": self.default_retention_days,
                "execution_retention_days": self.default_retention_days,
                "audit_log_retention_days": self.default_retention_days,
            }

    # =========================================================================
    # Execution Retention Enforcement
    # =========================================================================

    async def enforce_execution_retention(
        self,
        tenant_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce execution retention policy for a specific tenant.

        Deletes executions older than the tenant's plan-based retention period.
        Respects minimum record threshold to preserve execution history.

        Args:
            tenant_id: The tenant ID
            dry_run: If True, only preview what would be deleted without actually deleting

        Returns:
            Dictionary containing:
            - tenant_id: str
            - plan_name: str
            - retention_days: int
            - deleted_count: int - Number of executions deleted (or would be deleted)
            - total_count: int - Total executions before cleanup
            - remaining_count: int - Executions remaining after cleanup
            - cutoff_date: str - ISO timestamp of retention cutoff
            - timestamp: str - ISO timestamp of enforcement
            - dry_run: bool - Whether this was a dry run

        Example:
            result = await retention_enforcement_service.enforce_execution_retention("tenant-uuid")
            print(f"Deleted {result['deleted_count']} old executions")
        """
        logger.info(f"Enforcing execution retention for tenant {tenant_id} (dry_run={dry_run})")

        try:
            # Get retention policy for tenant
            policy = await self.get_tenant_retention_policy(tenant_id)
            retention_days = policy["execution_retention_days"]

            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_iso = cutoff_date.isoformat()

            # Count total executions for tenant
            total_response = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            total_count = total_response.count or 0

            # Count old executions that would be deleted
            old_response = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).lt("started_at", cutoff_iso).execute()
            old_count = old_response.count or 0

            # Check if we should skip deletion (preserve minimum records)
            if total_count <= MIN_RECORDS_TO_KEEP:
                logger.info(
                    f"Skipping deletion for tenant {tenant_id}: "
                    f"total_count ({total_count}) <= MIN_RECORDS_TO_KEEP ({MIN_RECORDS_TO_KEEP})"
                )
                return {
                    "tenant_id": tenant_id,
                    "plan_name": policy["plan_name"],
                    "retention_days": retention_days,
                    "deleted_count": 0,
                    "total_count": total_count,
                    "remaining_count": total_count,
                    "cutoff_date": cutoff_iso,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "dry_run": dry_run,
                    "skipped": True,
                    "reason": f"Total count ({total_count}) below minimum threshold ({MIN_RECORDS_TO_KEEP})",
                }

            deleted_count = 0

            if not dry_run and old_count > 0:
                # Perform deletion in batches
                deleted_count = await self._delete_old_executions_batch(
                    tenant_id,
                    cutoff_iso,
                    old_count
                )

                logger.info(
                    f"Deleted {deleted_count} executions for tenant {tenant_id} "
                    f"older than {retention_days} days"
                )
            else:
                deleted_count = old_count
                logger.info(
                    f"Dry run: Would delete {old_count} executions for tenant {tenant_id}"
                )

            remaining_count = total_count - deleted_count

            return {
                "tenant_id": tenant_id,
                "plan_name": policy["plan_name"],
                "retention_days": retention_days,
                "deleted_count": deleted_count,
                "total_count": total_count,
                "remaining_count": remaining_count,
                "cutoff_date": cutoff_iso,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(
                f"Error enforcing execution retention for tenant {tenant_id}: {e}",
                exc_info=True
            )
            return {
                "tenant_id": tenant_id,
                "deleted_count": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }

    async def _delete_old_executions_batch(
        self,
        tenant_id: str,
        cutoff_iso: str,
        expected_count: int
    ) -> int:
        """
        Delete old executions in batches to avoid long-running transactions.

        Args:
            tenant_id: The tenant ID
            cutoff_iso: ISO timestamp cutoff
            expected_count: Expected number of records to delete

        Returns:
            Total number of records deleted
        """
        total_deleted = 0

        # Delete in batches until no more old records exist
        while total_deleted < expected_count:
            try:
                # Delete a batch
                response = db_service.client.table("executions").delete().eq(
                    "tenant_id", tenant_id
                ).lt("started_at", cutoff_iso).limit(self.batch_size).execute()

                batch_deleted = len(response.data) if response.data else 0

                if batch_deleted == 0:
                    # No more records to delete
                    break

                total_deleted += batch_deleted
                logger.debug(
                    f"Deleted batch of {batch_deleted} executions for tenant {tenant_id} "
                    f"(total: {total_deleted}/{expected_count})"
                )

            except Exception as e:
                logger.error(
                    f"Error deleting execution batch for tenant {tenant_id}: {e}",
                    exc_info=True
                )
                break

        return total_deleted

    # =========================================================================
    # Audit Log Retention Enforcement
    # =========================================================================

    async def enforce_audit_log_retention(
        self,
        tenant_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce audit log retention policy for a specific tenant.

        Deletes audit logs older than the tenant's plan-based retention period.
        Respects minimum record threshold to preserve audit history.

        Args:
            tenant_id: The tenant ID
            dry_run: If True, only preview what would be deleted without actually deleting

        Returns:
            Dictionary containing:
            - tenant_id: str
            - plan_name: str
            - retention_days: int
            - deleted_count: int - Number of logs deleted (or would be deleted)
            - total_count: int - Total logs before cleanup
            - remaining_count: int - Logs remaining after cleanup
            - cutoff_date: str - ISO timestamp of retention cutoff
            - timestamp: str - ISO timestamp of enforcement
            - dry_run: bool - Whether this was a dry run

        Example:
            result = await retention_enforcement_service.enforce_audit_log_retention("tenant-uuid")
            print(f"Deleted {result['deleted_count']} old audit logs")
        """
        logger.info(f"Enforcing audit log retention for tenant {tenant_id} (dry_run={dry_run})")

        try:
            # Get retention policy for tenant
            policy = await self.get_tenant_retention_policy(tenant_id)
            retention_days = policy["audit_log_retention_days"]

            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_iso = cutoff_date.isoformat()

            # Count total audit logs for tenant
            total_response = db_service.client.table("feature_access_log").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            total_count = total_response.count or 0

            # Count old logs that would be deleted
            old_response = db_service.client.table("feature_access_log").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).lt("accessed_at", cutoff_iso).execute()
            old_count = old_response.count or 0

            # Check if we should skip deletion (preserve minimum records)
            if total_count <= MIN_RECORDS_TO_KEEP:
                logger.info(
                    f"Skipping deletion for tenant {tenant_id}: "
                    f"total_count ({total_count}) <= MIN_RECORDS_TO_KEEP ({MIN_RECORDS_TO_KEEP})"
                )
                return {
                    "tenant_id": tenant_id,
                    "plan_name": policy["plan_name"],
                    "retention_days": retention_days,
                    "deleted_count": 0,
                    "total_count": total_count,
                    "remaining_count": total_count,
                    "cutoff_date": cutoff_iso,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "dry_run": dry_run,
                    "skipped": True,
                    "reason": f"Total count ({total_count}) below minimum threshold ({MIN_RECORDS_TO_KEEP})",
                }

            deleted_count = 0

            if not dry_run and old_count > 0:
                # Perform deletion in batches
                deleted_count = await self._delete_old_audit_logs_batch(
                    tenant_id,
                    cutoff_iso,
                    old_count
                )

                logger.info(
                    f"Deleted {deleted_count} audit logs for tenant {tenant_id} "
                    f"older than {retention_days} days"
                )
            else:
                deleted_count = old_count
                logger.info(
                    f"Dry run: Would delete {old_count} audit logs for tenant {tenant_id}"
                )

            remaining_count = total_count - deleted_count

            return {
                "tenant_id": tenant_id,
                "plan_name": policy["plan_name"],
                "retention_days": retention_days,
                "deleted_count": deleted_count,
                "total_count": total_count,
                "remaining_count": remaining_count,
                "cutoff_date": cutoff_iso,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error(
                f"Error enforcing audit log retention for tenant {tenant_id}: {e}",
                exc_info=True
            )
            return {
                "tenant_id": tenant_id,
                "deleted_count": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }

    async def _delete_old_audit_logs_batch(
        self,
        tenant_id: str,
        cutoff_iso: str,
        expected_count: int
    ) -> int:
        """
        Delete old audit logs in batches to avoid long-running transactions.

        Args:
            tenant_id: The tenant ID
            cutoff_iso: ISO timestamp cutoff
            expected_count: Expected number of records to delete

        Returns:
            Total number of records deleted
        """
        total_deleted = 0

        # Delete in batches until no more old records exist
        while total_deleted < expected_count:
            try:
                # Delete a batch
                response = db_service.client.table("feature_access_log").delete().eq(
                    "tenant_id", tenant_id
                ).lt("accessed_at", cutoff_iso).limit(self.batch_size).execute()

                batch_deleted = len(response.data) if response.data else 0

                if batch_deleted == 0:
                    # No more records to delete
                    break

                total_deleted += batch_deleted
                logger.debug(
                    f"Deleted batch of {batch_deleted} audit logs for tenant {tenant_id} "
                    f"(total: {total_deleted}/{expected_count})"
                )

            except Exception as e:
                logger.error(
                    f"Error deleting audit log batch for tenant {tenant_id}: {e}",
                    exc_info=True
                )
                break

        return total_deleted

    # =========================================================================
    # Combined Retention Enforcement
    # =========================================================================

    async def enforce_tenant_retention(
        self,
        tenant_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce both execution and audit log retention for a tenant.

        This is a convenience method that enforces all retention policies
        for a tenant in a single call.

        Args:
            tenant_id: The tenant ID
            dry_run: If True, only preview what would be deleted

        Returns:
            Dictionary containing results from both enforcements

        Example:
            result = await retention_enforcement_service.enforce_tenant_retention("tenant-uuid")
            print(f"Deleted {result['execution_result']['deleted_count']} executions")
            print(f"Deleted {result['audit_log_result']['deleted_count']} audit logs")
        """
        logger.info(f"Enforcing all retention policies for tenant {tenant_id} (dry_run={dry_run})")

        # Get retention policy once
        policy = await self.get_tenant_retention_policy(tenant_id)

        # Enforce execution retention
        execution_result = await self.enforce_execution_retention(tenant_id, dry_run)

        # Enforce audit log retention
        audit_log_result = await self.enforce_audit_log_retention(tenant_id, dry_run)

        total_deleted = execution_result.get("deleted_count", 0) + audit_log_result.get("deleted_count", 0)

        return {
            "tenant_id": tenant_id,
            "plan_name": policy["plan_name"],
            "retention_days": policy["retention_days"],
            "total_deleted": total_deleted,
            "execution_result": execution_result,
            "audit_log_result": audit_log_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
        }

    async def enforce_all_tenants_retention(
        self,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce retention policies for all tenants.

        This is the main entry point for the scheduled retention job.
        It processes all tenants and returns aggregate metrics.

        Args:
            dry_run: If True, only preview what would be deleted

        Returns:
            Dictionary containing:
            - total_executions_deleted: int
            - total_audit_logs_deleted: int
            - total_deleted: int
            - tenants_processed: int
            - tenants_with_deletions: int
            - tenants_skipped: int
            - errors: list - Tenant IDs with errors
            - started_at: str - ISO timestamp
            - completed_at: str - ISO timestamp
            - duration_seconds: float
            - dry_run: bool

        Example:
            summary = await retention_enforcement_service.enforce_all_tenants_retention()
            print(f"Cleaned up {summary['total_deleted']} records across "
                  f"{summary['tenants_processed']} tenants")
        """
        started_at = datetime.now(timezone.utc)
        logger.info(f"Starting global retention enforcement job (dry_run={dry_run})")

        try:
            # Get all tenants
            tenants_response = db_service.client.table("tenants").select("id").execute()
            tenants = tenants_response.data or []

            total_executions_deleted = 0
            total_audit_logs_deleted = 0
            tenants_processed = 0
            tenants_with_deletions = 0
            tenants_skipped = 0
            errors: List[str] = []

            for tenant in tenants:
                tenant_id = tenant["id"]

                try:
                    result = await self.enforce_tenant_retention(tenant_id, dry_run)

                    tenants_processed += 1

                    exec_deleted = result.get("execution_result", {}).get("deleted_count", 0)
                    audit_deleted = result.get("audit_log_result", {}).get("deleted_count", 0)
                    total_deleted = exec_deleted + audit_deleted

                    total_executions_deleted += exec_deleted
                    total_audit_logs_deleted += audit_deleted

                    if total_deleted > 0:
                        tenants_with_deletions += 1

                    # Check if any enforcement was skipped
                    if (result.get("execution_result", {}).get("skipped") and
                        result.get("audit_log_result", {}).get("skipped")):
                        tenants_skipped += 1

                except Exception as e:
                    logger.error(f"Failed to enforce retention for tenant {tenant_id}: {e}", exc_info=True)
                    errors.append(tenant_id)
                    tenants_processed += 1

            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            summary = {
                "total_executions_deleted": total_executions_deleted,
                "total_audit_logs_deleted": total_audit_logs_deleted,
                "total_deleted": total_executions_deleted + total_audit_logs_deleted,
                "tenants_processed": tenants_processed,
                "tenants_with_deletions": tenants_with_deletions,
                "tenants_skipped": tenants_skipped,
                "errors": errors,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": duration,
                "dry_run": dry_run,
            }

            logger.info(
                f"Global retention enforcement completed: "
                f"deleted {summary['total_deleted']} records "
                f"({total_executions_deleted} executions, {total_audit_logs_deleted} audit logs) "
                f"across {tenants_processed} tenants "
                f"({tenants_with_deletions} with deletions, {tenants_skipped} skipped) "
                f"in {duration:.2f}s (dry_run={dry_run})"
            )

            return summary

        except Exception as e:
            logger.error(f"Error during global retention enforcement: {e}", exc_info=True)
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            return {
                "total_executions_deleted": 0,
                "total_audit_logs_deleted": 0,
                "total_deleted": 0,
                "tenants_processed": 0,
                "tenants_with_deletions": 0,
                "tenants_skipped": 0,
                "errors": [],
                "error": str(e),
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": duration,
                "dry_run": dry_run,
            }

    # =========================================================================
    # Preview and Analytics
    # =========================================================================

    async def get_retention_preview(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Preview what would be deleted for a tenant without actually deleting.

        Useful for UI/admin tools to show impact before running enforcement.

        Args:
            tenant_id: The tenant ID

        Returns:
            Dictionary containing preview information for executions and audit logs

        Example:
            preview = await retention_enforcement_service.get_retention_preview("tenant-uuid")
            print(f"Would delete {preview['executions_to_delete']} executions")
            print(f"Would delete {preview['audit_logs_to_delete']} audit logs")
        """
        try:
            # Get retention policy
            policy = await self.get_tenant_retention_policy(tenant_id)
            retention_days = policy["retention_days"]

            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            cutoff_iso = cutoff_date.isoformat()

            # Preview executions
            exec_total = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            exec_old = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).lt("started_at", cutoff_iso).execute()

            # Preview audit logs
            audit_total = db_service.client.table("feature_access_log").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            audit_old = db_service.client.table("feature_access_log").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).lt("accessed_at", cutoff_iso).execute()

            exec_total_count = exec_total.count or 0
            exec_old_count = exec_old.count or 0
            audit_total_count = audit_total.count or 0
            audit_old_count = audit_old.count or 0

            # Determine if deletion would occur (respects minimum threshold)
            exec_would_delete = exec_old_count > 0 and exec_total_count > MIN_RECORDS_TO_KEEP
            audit_would_delete = audit_old_count > 0 and audit_total_count > MIN_RECORDS_TO_KEEP

            return {
                "tenant_id": tenant_id,
                "plan_name": policy["plan_name"],
                "retention_days": retention_days,
                "cutoff_date": cutoff_iso,
                "executions": {
                    "total_count": exec_total_count,
                    "old_count": exec_old_count,
                    "to_delete": exec_old_count if exec_would_delete else 0,
                    "would_delete": exec_would_delete,
                    "remaining": exec_total_count - (exec_old_count if exec_would_delete else 0),
                },
                "audit_logs": {
                    "total_count": audit_total_count,
                    "old_count": audit_old_count,
                    "to_delete": audit_old_count if audit_would_delete else 0,
                    "would_delete": audit_would_delete,
                    "remaining": audit_total_count - (audit_old_count if audit_would_delete else 0),
                },
                "total_to_delete": (
                    (exec_old_count if exec_would_delete else 0) +
                    (audit_old_count if audit_would_delete else 0)
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get retention preview for tenant {tenant_id}: {e}")
            return {
                "tenant_id": tenant_id,
                "error": str(e),
            }


# Global singleton instance
retention_enforcement_service = RetentionEnforcementService()
