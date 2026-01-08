"""
Execution Retention Service - Handles time-based cleanup of old execution data.

This service implements the execution retention policy system to prevent unbounded
database growth and improve query performance for large tenants (100k+ executions).

Key Features:
- Tenant-specific retention policies with configurable retention periods
- Batch processing to avoid database lock contention
- Safety thresholds to preserve minimum execution history
- Comprehensive logging and metrics for monitoring
- Integration with system-wide retention configuration

Related Tasks:
- T001: Retention configuration in settings (COMPLETED)
- T002: Database migration for retention tables (COMPLETED)
- T003: Retention service implementation (THIS FILE)

Usage:
    # Cleanup specific tenant
    result = await retention_service.cleanup_tenant_executions(tenant_id)

    # Cleanup all tenants (scheduled job)
    summary = await retention_service.cleanup_all_tenants()

    # Get retention policy for tenant
    policy = await retention_service.get_retention_policy(tenant_id)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.services.database import db_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class RetentionService:
    """Service for managing execution data retention and time-based cleanup."""

    def __init__(self):
        """Initialize the retention service with configuration from settings."""
        self.default_retention_days = settings.EXECUTION_RETENTION_DAYS
        self.default_enabled = settings.EXECUTION_RETENTION_ENABLED
        self.batch_size = settings.RETENTION_JOB_BATCH_SIZE

    async def get_retention_policy(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get the retention policy for a tenant.

        Retrieves tenant-specific retention configuration from the database.
        Falls back to system defaults if no tenant policy exists.

        Args:
            tenant_id: UUID of the tenant

        Returns:
            Dictionary containing:
            - retention_days: int - Number of days to retain executions
            - is_enabled: bool - Whether retention cleanup is active
            - min_executions_to_keep: int - Minimum executions to preserve
            - last_cleanup_at: str|None - ISO timestamp of last cleanup
            - last_cleanup_deleted_count: int - Records deleted in last cleanup

        Example:
            policy = await retention_service.get_retention_policy("tenant-uuid")
            print(f"Retention: {policy['retention_days']} days")
        """
        try:
            # Query retention policy for tenant
            response = (
                db_service.client.table("execution_retention_policies")
                .select("*")
                .eq("tenant_id", tenant_id)
                .single()
                .execute()
            )

            if response.data:
                policy = response.data
                return {
                    "retention_days": policy.get("retention_days", self.default_retention_days),
                    "is_enabled": policy.get("is_enabled", self.default_enabled),
                    "min_executions_to_keep": policy.get("min_executions_to_keep", 100),
                    "last_cleanup_at": policy.get("last_cleanup_at"),
                    "last_cleanup_deleted_count": policy.get("last_cleanup_deleted_count", 0),
                }

        except Exception as e:
            # Policy doesn't exist or query failed - use system defaults
            logger.warning(
                f"Failed to fetch retention policy for tenant {tenant_id}: {e}. "
                f"Using system defaults."
            )

        # Return system defaults
        return {
            "retention_days": self.default_retention_days,
            "is_enabled": self.default_enabled,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

    async def create_retention_policy(
        self,
        tenant_id: str,
        retention_days: int,
        is_enabled: bool = True,
        min_executions_to_keep: int = 100,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a retention policy for a tenant.

        Args:
            tenant_id: UUID of the tenant
            retention_days: Number of days to retain executions
            is_enabled: Whether retention cleanup is active
            min_executions_to_keep: Minimum executions to preserve (safety threshold)
            created_by: UUID of user creating the policy

        Returns:
            Created or updated policy record

        Raises:
            Exception: If policy creation fails

        Example:
            policy = await retention_service.create_retention_policy(
                tenant_id="abc-123",
                retention_days=90,
                is_enabled=True,
                min_executions_to_keep=100
            )
        """
        try:
            policy_data = {
                "tenant_id": tenant_id,
                "retention_days": retention_days,
                "is_enabled": is_enabled,
                "min_executions_to_keep": min_executions_to_keep,
            }

            if created_by:
                policy_data["created_by"] = created_by

            # Upsert policy (insert or update on conflict)
            response = (
                db_service.client.table("execution_retention_policies")
                .upsert(policy_data, on_conflict="tenant_id")
                .execute()
            )

            logger.info(
                f"Created/updated retention policy for tenant {tenant_id}: "
                f"{retention_days} days, enabled={is_enabled}"
            )

            return response.data[0] if response.data else policy_data

        except Exception as e:
            logger.error(f"Failed to create retention policy for tenant {tenant_id}: {e}")
            raise

    async def update_retention_policy(
        self,
        tenant_id: str,
        retention_days: Optional[int] = None,
        is_enabled: Optional[bool] = None,
        min_executions_to_keep: Optional[int] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing retention policy for a tenant.

        Only updates the fields that are provided (not None).

        Args:
            tenant_id: UUID of the tenant
            retention_days: New retention period (optional)
            is_enabled: New enabled status (optional)
            min_executions_to_keep: New minimum threshold (optional)
            updated_by: UUID of user updating the policy

        Returns:
            Updated policy record

        Raises:
            Exception: If update fails
        """
        try:
            update_data: Dict[str, Any] = {}

            if retention_days is not None:
                update_data["retention_days"] = retention_days
            if is_enabled is not None:
                update_data["is_enabled"] = is_enabled
            if min_executions_to_keep is not None:
                update_data["min_executions_to_keep"] = min_executions_to_keep
            if updated_by is not None:
                update_data["updated_by"] = updated_by

            if not update_data:
                # Nothing to update
                return await self.get_retention_policy(tenant_id)

            response = (
                db_service.client.table("execution_retention_policies")
                .update(update_data)
                .eq("tenant_id", tenant_id)
                .execute()
            )

            logger.info(f"Updated retention policy for tenant {tenant_id}: {update_data}")

            return response.data[0] if response.data else {}

        except Exception as e:
            logger.error(f"Failed to update retention policy for tenant {tenant_id}: {e}")
            raise

    async def cleanup_tenant_executions(
        self,
        tenant_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Clean up old executions for a specific tenant based on their retention policy.

        This method:
        1. Loads the tenant's retention policy
        2. Calls the database cleanup function to delete old executions
        3. Updates the policy with cleanup timestamp and deletion count
        4. Returns summary metrics for monitoring

        Args:
            tenant_id: UUID of the tenant
            force: If True, skip the enabled check and cleanup anyway

        Returns:
            Dictionary containing:
            - tenant_id: str
            - deleted_count: int - Number of executions deleted
            - retention_days: int - Retention period used
            - is_enabled: bool - Whether retention was enabled
            - timestamp: str - ISO timestamp of cleanup
            - summary: dict - Detailed execution summary from DB function

        Example:
            result = await retention_service.cleanup_tenant_executions("tenant-uuid")
            print(f"Deleted {result['deleted_count']} old executions")
        """
        policy = await self.get_retention_policy(tenant_id)

        # Check if retention is enabled
        if not policy["is_enabled"] and not force:
            logger.info(
                f"Retention disabled for tenant {tenant_id}, skipping cleanup "
                f"(use force=True to override)"
            )
            return {
                "tenant_id": tenant_id,
                "deleted_count": 0,
                "retention_days": policy["retention_days"],
                "is_enabled": False,
                "skipped": True,
                "reason": "Retention disabled for tenant",
                "timestamp": datetime.utcnow().isoformat(),
            }

        retention_days = policy["retention_days"]
        min_executions = policy["min_executions_to_keep"]

        logger.info(
            f"Starting execution cleanup for tenant {tenant_id}: "
            f"retention={retention_days} days, min_keep={min_executions}, "
            f"batch_size={self.batch_size}"
        )

        try:
            # Call the PostgreSQL cleanup function
            # This function returns (deleted_count, execution_summary)
            response = db_service.client.rpc(
                "cleanup_old_executions",
                {
                    "p_tenant_id": tenant_id,
                    "p_retention_days": retention_days,
                    "p_min_executions_to_keep": min_executions,
                    "p_batch_size": self.batch_size,
                },
            ).execute()

            # Parse response from database function
            result = response.data[0] if response.data else {}
            deleted_count = result.get("deleted_count", 0)
            execution_summary = result.get("execution_summary", {})

            # Update the retention policy with cleanup metadata
            now_iso = datetime.utcnow().isoformat()
            try:
                db_service.client.table("execution_retention_policies").update(
                    {
                        "last_cleanup_at": now_iso,
                        "last_cleanup_deleted_count": deleted_count,
                    }
                ).eq("tenant_id", tenant_id).execute()
            except Exception as update_error:
                logger.warning(
                    f"Failed to update policy metadata for tenant {tenant_id}: {update_error}"
                )

            logger.info(
                f"Execution cleanup completed for tenant {tenant_id}: "
                f"deleted {deleted_count} executions"
            )

            return {
                "tenant_id": tenant_id,
                "deleted_count": deleted_count,
                "retention_days": retention_days,
                "is_enabled": policy["is_enabled"],
                "timestamp": now_iso,
                "summary": execution_summary,
            }

        except Exception as e:
            logger.error(
                f"Error during execution cleanup for tenant {tenant_id}: {e}",
                exc_info=True,
            )
            return {
                "tenant_id": tenant_id,
                "deleted_count": 0,
                "retention_days": retention_days,
                "is_enabled": policy["is_enabled"],
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def cleanup_all_tenants(self) -> Dict[str, Any]:
        """
        Clean up old executions for all tenants with retention policies.

        This is the main entry point for the scheduled retention job.
        It processes all tenants and returns aggregate metrics.

        Returns:
            Dictionary containing:
            - total_deleted: int - Total executions deleted across all tenants
            - tenants_processed: int - Number of tenants processed
            - tenants_with_deletions: int - Number of tenants that had deletions
            - tenants_skipped: int - Number of tenants skipped (retention disabled)
            - errors: list - List of tenant IDs that had errors
            - started_at: str - ISO timestamp when cleanup started
            - completed_at: str - ISO timestamp when cleanup completed
            - duration_seconds: float - Total duration of cleanup job

        Example:
            summary = await retention_service.cleanup_all_tenants()
            print(f"Cleaned up {summary['total_deleted']} executions across "
                  f"{summary['tenants_processed']} tenants")
        """
        started_at = datetime.utcnow()
        logger.info("Starting global execution retention cleanup job")

        try:
            # Get all tenants from the database
            tenants_response = db_service.client.table("tenants").select("id").execute()
            tenants = tenants_response.data or []

            total_deleted = 0
            tenants_processed = 0
            tenants_with_deletions = 0
            tenants_skipped = 0
            errors: List[str] = []

            for tenant in tenants:
                tenant_id = tenant["id"]

                try:
                    result = await self.cleanup_tenant_executions(tenant_id)

                    tenants_processed += 1
                    deleted_count = result.get("deleted_count", 0)
                    total_deleted += deleted_count

                    if result.get("skipped"):
                        tenants_skipped += 1
                    elif deleted_count > 0:
                        tenants_with_deletions += 1

                    if result.get("error"):
                        errors.append(tenant_id)

                except Exception as e:
                    logger.error(f"Failed to cleanup tenant {tenant_id}: {e}", exc_info=True)
                    errors.append(tenant_id)
                    tenants_processed += 1

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            summary = {
                "total_deleted": total_deleted,
                "tenants_processed": tenants_processed,
                "tenants_with_deletions": tenants_with_deletions,
                "tenants_skipped": tenants_skipped,
                "errors": errors,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": duration,
            }

            logger.info(
                f"Global execution retention cleanup completed: "
                f"deleted {total_deleted} executions across {tenants_processed} tenants "
                f"({tenants_with_deletions} with deletions, {tenants_skipped} skipped) "
                f"in {duration:.2f}s"
            )

            return summary

        except Exception as e:
            logger.error(f"Error during global retention cleanup: {e}", exc_info=True)
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            return {
                "total_deleted": 0,
                "tenants_processed": 0,
                "tenants_with_deletions": 0,
                "tenants_skipped": 0,
                "errors": [],
                "error": str(e),
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": duration,
            }

    async def get_cleanup_preview(self, tenant_id: str) -> Dict[str, Any]:
        """
        Preview what would be deleted for a tenant without actually deleting.

        Useful for UI/admin tools to show impact before enabling retention.

        Args:
            tenant_id: UUID of the tenant

        Returns:
            Dictionary containing:
            - tenant_id: str
            - total_executions: int - Current total execution count
            - old_executions_count: int - Executions that would be deleted
            - cutoff_date: str - ISO timestamp of retention cutoff
            - retention_days: int - Retention period
            - min_executions_to_keep: int - Safety threshold
            - would_delete: bool - Whether any deletions would occur

        Example:
            preview = await retention_service.get_cleanup_preview("tenant-uuid")
            print(f"Would delete {preview['old_executions_count']} executions")
        """
        policy = await self.get_retention_policy(tenant_id)
        retention_days = policy["retention_days"]
        min_executions = policy["min_executions_to_keep"]

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_iso = cutoff_date.isoformat()

        try:
            # Count total executions for tenant
            total_response = (
                db_service.client.table("executions")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .execute()
            )
            total_count = total_response.count if hasattr(total_response, "count") else 0

            # Count old executions that would be deleted
            old_response = (
                db_service.client.table("executions")
                .select("id", count="exact")
                .eq("tenant_id", tenant_id)
                .lt("started_at", cutoff_iso)
                .execute()
            )
            old_count = old_response.count if hasattr(old_response, "count") else 0

            # Determine if deletion would occur
            # (respects min_executions_to_keep threshold)
            would_delete = old_count > 0 and total_count > min_executions

            return {
                "tenant_id": tenant_id,
                "total_executions": total_count,
                "old_executions_count": old_count,
                "executions_to_delete": old_count if would_delete else 0,
                "cutoff_date": cutoff_iso,
                "retention_days": retention_days,
                "min_executions_to_keep": min_executions,
                "would_delete": would_delete,
                "is_enabled": policy["is_enabled"],
            }

        except Exception as e:
            logger.error(f"Failed to get cleanup preview for tenant {tenant_id}: {e}")
            return {
                "tenant_id": tenant_id,
                "error": str(e),
            }

    async def get_all_retention_policies(self) -> List[Dict[str, Any]]:
        """
        Get all retention policies across all tenants.

        Useful for admin dashboards and monitoring.

        Returns:
            List of policy dictionaries with tenant information

        Example:
            policies = await retention_service.get_all_retention_policies()
            for policy in policies:
                print(f"Tenant {policy['tenant_id']}: {policy['retention_days']} days")
        """
        try:
            response = (
                db_service.client.table("execution_retention_policies")
                .select("*")
                .order("updated_at", desc=True)
                .execute()
            )

            return response.data or []

        except Exception as e:
            logger.error(f"Failed to fetch all retention policies: {e}")
            return []


# Global singleton instance
retention_service = RetentionService()
