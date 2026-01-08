"""
Downgrade Service

Handles plan downgrade scenarios including:
- Detecting over-limit resources after plan changes
- Applying grace periods and downgrade actions
- Tracking affected resources
- Providing methods for enforcement and cleanup

This service works in conjunction with webhook handlers and scheduled jobs
to ensure smooth downgrade transitions with proper grace periods.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.services.database import db_service
from app.services.entitlements_service import entitlements_service
from app.core.downgrade_policy import (
    ResourceType,
    GracePeriodStatus,
    DowngradeAction,
    get_policy,
    RESOURCE_SELECTION_STRATEGY,
    ResourceSelectionStrategy,
)

logger = logging.getLogger(__name__)


class DowngradeService:
    """
    Service for managing plan downgrades and over-limit scenarios.

    When a tenant downgrades to a plan with lower limits, this service:
    1. Detects which resources are over the new limit
    2. Applies the appropriate downgrade policy (grace period, actions)
    3. Tracks affected resources in the downgrade_grace_periods table
    4. Provides enforcement methods for grace period expiry
    """

    def __init__(self):
        self.db_service = db_service

    # =========================================================================
    # Over-Limit Detection
    # =========================================================================

    async def detect_environment_overlimit(
        self,
        tenant_id: str
    ) -> Tuple[bool, int, int, List[str]]:
        """
        Check if tenant has more environments than their plan allows.

        Args:
            tenant_id: The tenant to check

        Returns:
            Tuple of (is_over_limit, current_count, limit, over_limit_ids)
        """
        try:
            # Get current environment count and IDs
            response = self.db_service.client.table("environments").select(
                "id, created_at"
            ).eq("tenant_id", tenant_id).order("created_at", desc=False).execute()

            environments = response.data or []
            current_count = len(environments)

            # Get the limit from entitlements
            limit = await entitlements_service.get_limit(tenant_id, "environment_limits")

            # Check if over limit
            if current_count <= limit:
                return False, current_count, limit, []

            # Determine which environments are over limit based on policy
            policy = get_policy(ResourceType.ENVIRONMENT)
            over_limit_ids = self._select_over_limit_resources(
                environments,
                current_count - limit,
                policy.selection_strategy
            )

            return True, current_count, limit, over_limit_ids

        except Exception as e:
            logger.error(f"Failed to detect environment over-limit for tenant {tenant_id}: {e}")
            return False, 0, 0, []

    async def detect_team_member_overlimit(
        self,
        tenant_id: str
    ) -> Tuple[bool, int, int, List[str]]:
        """
        Check if tenant has more team members than their plan allows.

        Args:
            tenant_id: The tenant to check

        Returns:
            Tuple of (is_over_limit, current_count, limit, over_limit_ids)
        """
        try:
            # Get current team member count and IDs
            response = self.db_service.client.table("tenant_users").select(
                "id, created_at"
            ).eq("tenant_id", tenant_id).order("created_at", desc=False).execute()

            members = response.data or []
            current_count = len(members)

            # Get the limit from entitlements
            # Note: Assuming team member limits are stored in a feature like "team_member_limits"
            # This may need adjustment based on actual feature name
            limit = await entitlements_service.get_limit(tenant_id, "team_member_limits")

            # If limit is 0 or 9999, it's unlimited
            if limit == 0 or limit >= 9999:
                return False, current_count, limit, []

            # Check if over limit
            if current_count <= limit:
                return False, current_count, limit, []

            # Determine which members are over limit based on policy
            policy = get_policy(ResourceType.TEAM_MEMBER)
            over_limit_ids = self._select_over_limit_resources(
                members,
                current_count - limit,
                policy.selection_strategy
            )

            return True, current_count, limit, over_limit_ids

        except Exception as e:
            logger.error(f"Failed to detect team member over-limit for tenant {tenant_id}: {e}")
            return False, 0, 0, []

    async def detect_workflow_overlimit(
        self,
        tenant_id: str
    ) -> Tuple[bool, int, int, List[str]]:
        """
        Check if tenant has more workflows than their plan allows.

        Args:
            tenant_id: The tenant to check

        Returns:
            Tuple of (is_over_limit, current_count, limit, over_limit_ids)
        """
        try:
            # Get unique canonical workflows
            response = self.db_service.client.table("workflow_env_map").select(
                "canonical_id, created_at"
            ).eq("tenant_id", tenant_id).execute()

            workflows = response.data or []

            # Get unique canonical IDs with their earliest created_at
            canonical_workflows = {}
            for workflow in workflows:
                canonical_id = workflow.get("canonical_id")
                created_at = workflow.get("created_at")

                if canonical_id:
                    if canonical_id not in canonical_workflows:
                        canonical_workflows[canonical_id] = created_at
                    else:
                        # Keep the earliest created_at
                        if created_at < canonical_workflows[canonical_id]:
                            canonical_workflows[canonical_id] = created_at

            current_count = len(canonical_workflows)

            # Get the limit from entitlements
            limit = await entitlements_service.get_limit(tenant_id, "workflow_limits")

            # Check if over limit
            if current_count <= limit:
                return False, current_count, limit, []

            # Sort by creation date and select based on policy
            policy = get_policy(ResourceType.WORKFLOW)
            sorted_workflows = [
                {"id": cid, "created_at": created_at}
                for cid, created_at in canonical_workflows.items()
            ]
            sorted_workflows.sort(key=lambda x: x["created_at"])

            over_limit_ids = self._select_over_limit_resources(
                sorted_workflows,
                current_count - limit,
                policy.selection_strategy
            )

            return True, current_count, limit, over_limit_ids

        except Exception as e:
            logger.error(f"Failed to detect workflow over-limit for tenant {tenant_id}: {e}")
            return False, 0, 0, []

    def _select_over_limit_resources(
        self,
        resources: List[Dict[str, Any]],
        over_count: int,
        strategy: ResourceSelectionStrategy
    ) -> List[str]:
        """
        Select which resources should be marked for downgrade action.

        Args:
            resources: List of resources with 'id' and 'created_at' fields
            over_count: Number of resources over the limit
            strategy: Selection strategy to use

        Returns:
            List of resource IDs to mark for action
        """
        if over_count <= 0 or not resources:
            return []

        # Sort based on strategy
        if strategy == ResourceSelectionStrategy.NEWEST_FIRST:
            # Keep oldest, mark newest
            sorted_resources = sorted(resources, key=lambda x: x.get("created_at", ""), reverse=True)
        elif strategy == ResourceSelectionStrategy.OLDEST_FIRST:
            # Keep newest, mark oldest
            sorted_resources = sorted(resources, key=lambda x: x.get("created_at", ""))
        else:
            # Default to oldest first
            sorted_resources = sorted(resources, key=lambda x: x.get("created_at", ""))

        # Select the first 'over_count' resources
        return [r["id"] for r in sorted_resources[:over_count]]

    # =========================================================================
    # Grace Period Management
    # =========================================================================

    async def initiate_grace_period(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        resource_id: str,
        reason: Optional[str] = None
    ) -> Optional[str]:
        """
        Initiate a grace period for a resource that's over limit.

        Creates a record in the downgrade_grace_periods table to track
        the grace period status and expiry.

        Args:
            tenant_id: The tenant ID
            resource_type: Type of resource (environment, team_member, etc.)
            resource_id: ID of the specific resource
            reason: Optional reason for the grace period

        Returns:
            The grace period record ID, or None if failed
        """
        try:
            policy = get_policy(resource_type)

            # Calculate expiry date
            now = datetime.now(timezone.utc)
            expires_at = now + policy.grace_period_timedelta

            # Create grace period record
            grace_period_data = {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "action": policy.action.value,
                "status": GracePeriodStatus.ACTIVE.value,
                "starts_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "reason": reason or f"Plan downgrade - over limit for {resource_type.value}",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

            response = self.db_service.client.table("downgrade_grace_periods").insert(
                grace_period_data
            ).execute()

            if response.data:
                grace_period_id = response.data[0]["id"]
                logger.info(
                    f"Initiated grace period {grace_period_id} for {resource_type.value} "
                    f"{resource_id} of tenant {tenant_id}, expires at {expires_at}"
                )
                return grace_period_id

            return None

        except Exception as e:
            logger.error(
                f"Failed to initiate grace period for {resource_type.value} "
                f"{resource_id} of tenant {tenant_id}: {e}"
            )
            return None

    async def cancel_grace_period(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        resource_id: str
    ) -> bool:
        """
        Cancel an active grace period (e.g., when user upgrades or removes resource).

        Args:
            tenant_id: The tenant ID
            resource_type: Type of resource
            resource_id: ID of the specific resource

        Returns:
            True if cancelled successfully
        """
        try:
            now = datetime.now(timezone.utc)

            response = self.db_service.client.table("downgrade_grace_periods").update({
                "status": GracePeriodStatus.CANCELLED.value,
                "updated_at": now.isoformat(),
            }).eq("tenant_id", tenant_id).eq(
                "resource_type", resource_type.value
            ).eq("resource_id", resource_id).eq(
                "status", GracePeriodStatus.ACTIVE.value
            ).execute()

            if response.data:
                logger.info(
                    f"Cancelled grace period for {resource_type.value} "
                    f"{resource_id} of tenant {tenant_id}"
                )
                return True

            return False

        except Exception as e:
            logger.error(
                f"Failed to cancel grace period for {resource_type.value} "
                f"{resource_id} of tenant {tenant_id}: {e}"
            )
            return False

    async def get_active_grace_periods(
        self,
        tenant_id: str,
        resource_type: Optional[ResourceType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active grace periods for a tenant.

        Args:
            tenant_id: The tenant ID
            resource_type: Optional filter by resource type

        Returns:
            List of active grace period records
        """
        try:
            query = self.db_service.client.table("downgrade_grace_periods").select(
                "*"
            ).eq("tenant_id", tenant_id).eq("status", GracePeriodStatus.ACTIVE.value)

            if resource_type:
                query = query.eq("resource_type", resource_type.value)

            response = query.order("expires_at", desc=False).execute()
            return response.data or []

        except Exception as e:
            logger.error(f"Failed to get active grace periods for tenant {tenant_id}: {e}")
            return []

    async def get_expiring_grace_periods(
        self,
        days_threshold: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get grace periods expiring within the specified threshold.

        Useful for sending warning notifications.

        Args:
            days_threshold: Number of days threshold (default 7)

        Returns:
            List of grace periods expiring soon
        """
        try:
            now = datetime.now(timezone.utc)
            threshold_date = now + timedelta(days=days_threshold)

            response = self.db_service.client.table("downgrade_grace_periods").select(
                "*"
            ).eq("status", GracePeriodStatus.ACTIVE.value).lte(
                "expires_at", threshold_date.isoformat()
            ).gte("expires_at", now.isoformat()).execute()

            return response.data or []

        except Exception as e:
            logger.error(f"Failed to get expiring grace periods: {e}")
            return []

    async def get_expired_grace_periods(self) -> List[Dict[str, Any]]:
        """
        Get all grace periods that have expired and need action.

        Returns:
            List of expired grace period records
        """
        try:
            now = datetime.now(timezone.utc)

            response = self.db_service.client.table("downgrade_grace_periods").select(
                "*"
            ).eq("status", GracePeriodStatus.ACTIVE.value).lt(
                "expires_at", now.isoformat()
            ).execute()

            if response.data:
                logger.info(f"Found {len(response.data)} expired grace periods requiring action")

            return response.data or []

        except Exception as e:
            logger.error(f"Failed to get expired grace periods: {e}")
            return []

    async def mark_grace_period_expired(
        self,
        grace_period_id: str
    ) -> bool:
        """
        Mark a grace period as expired after taking action.

        Args:
            grace_period_id: The grace period record ID

        Returns:
            True if updated successfully
        """
        return await self._update_grace_period_status(
            grace_period_id,
            GracePeriodStatus.EXPIRED
        )

    async def _update_grace_period_status(
        self,
        grace_period_id: str,
        status: GracePeriodStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update grace period status with optional metadata."""
        try:
            now = datetime.now(timezone.utc)
            update_payload: Dict[str, Any] = {
                "status": status.value,
                "updated_at": now.isoformat(),
            }

            if metadata is not None:
                update_payload["metadata"] = metadata

            response = self.db_service.client.table("downgrade_grace_periods").update(
                update_payload
            ).eq("id", grace_period_id).execute()

            return bool(response.data)

        except Exception as e:
            logger.error(f"Failed to update grace period {grace_period_id} status: {e}")
            return False

    async def enforce_expired_grace_periods(self) -> Dict[str, Any]:
        """
        Execute downgrade actions for all expired grace periods.

        Returns a summary including enforcement counts and any errors.
        """
        expired_periods = await self.get_expired_grace_periods()
        summary = {
            "checked_count": len(expired_periods),
            "enforced_count": 0,
            "skipped_count": 0,
            "errors": [],
        }

        for grace_period in expired_periods:
            if grace_period.get("status") != GracePeriodStatus.ACTIVE.value:
                summary["skipped_count"] += 1
                continue

            action_success = await self.execute_downgrade_action(grace_period)
            if not action_success:
                summary["errors"].append(grace_period.get("id"))
                continue

            metadata = grace_period.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            metadata.update({
                "enforced_at": datetime.now(timezone.utc).isoformat(),
                "enforced_action": grace_period.get("action"),
            })

            updated = await self._update_grace_period_status(
                grace_period_id=grace_period.get("id"),
                status=GracePeriodStatus.EXPIRED,
                metadata=metadata,
            )

            if updated:
                summary["enforced_count"] += 1
            else:
                summary["errors"].append(grace_period.get("id"))

        return summary

    # =========================================================================
    # Downgrade Action Execution
    # =========================================================================

    async def execute_downgrade_action(
        self,
        grace_period: Dict[str, Any]
    ) -> bool:
        """
        Execute the downgrade action for an expired grace period.

        Args:
            grace_period: The grace period record with action details

        Returns:
            True if action was executed successfully
        """
        resource_type = grace_period.get("resource_type")
        resource_id = grace_period.get("resource_id")
        tenant_id = grace_period.get("tenant_id")
        action = grace_period.get("action")

        logger.info(
            f"Executing downgrade action '{action}' for {resource_type} "
            f"{resource_id} of tenant {tenant_id}"
        )

        try:
            if resource_type == ResourceType.ENVIRONMENT.value:
                return await self._execute_environment_action(
                    tenant_id, resource_id, action
                )
            elif resource_type == ResourceType.TEAM_MEMBER.value:
                return await self._execute_team_member_action(
                    tenant_id, resource_id, action
                )
            elif resource_type == ResourceType.WORKFLOW.value:
                return await self._execute_workflow_action(
                    tenant_id, resource_id, action
                )
            else:
                logger.warning(f"Unknown resource type: {resource_type}")
                return False

        except Exception as e:
            logger.error(
                f"Failed to execute action '{action}' for {resource_type} "
                f"{resource_id} of tenant {tenant_id}: {e}"
            )
            return False

    async def _execute_environment_action(
        self,
        tenant_id: str,
        environment_id: str,
        action: str
    ) -> bool:
        """Execute downgrade action for an environment."""
        now = datetime.now(timezone.utc)

        if action == DowngradeAction.READ_ONLY.value:
            # Mark environment as read-only
            response = self.db_service.client.table("environments").update({
                "is_read_only": True,
                "read_only_reason": "Plan limit exceeded - grace period expired",
                "updated_at": now.isoformat(),
            }).eq("id", environment_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Marked environment {environment_id} as read-only")
            return bool(response.data)

        elif action == DowngradeAction.SCHEDULE_DELETION.value:
            # Mark for deletion (actual deletion can be handled by a cleanup job)
            response = self.db_service.client.table("environments").update({
                "is_deleted": True,
                "deleted_at": now.isoformat(),
                "deletion_reason": "Plan limit exceeded - grace period expired",
                "updated_at": now.isoformat(),
            }).eq("id", environment_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Marked environment {environment_id} for deletion")
            return bool(response.data)

        elif action == DowngradeAction.DISABLE.value:
            # Disable the environment
            response = self.db_service.client.table("environments").update({
                "is_active": False,
                "updated_at": now.isoformat(),
            }).eq("id", environment_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Disabled environment {environment_id}")
            return bool(response.data)

        return False

    async def _execute_team_member_action(
        self,
        tenant_id: str,
        member_id: str,
        action: str
    ) -> bool:
        """Execute downgrade action for a team member."""
        now = datetime.now(timezone.utc)

        if action == DowngradeAction.DISABLE.value:
            # Disable team member access
            response = self.db_service.client.table("tenant_users").update({
                "is_active": False,
                "deactivated_at": now.isoformat(),
                "deactivation_reason": "Plan limit exceeded - grace period expired",
                "updated_at": now.isoformat(),
            }).eq("id", member_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Disabled team member {member_id}")
            return bool(response.data)

        elif action == DowngradeAction.SCHEDULE_DELETION.value:
            # Remove team member (soft delete)
            response = self.db_service.client.table("tenant_users").delete().eq(
                "id", member_id
            ).eq("tenant_id", tenant_id).execute()

            logger.info(f"Removed team member {member_id}")
            return bool(response.data)

        return False

    async def _execute_workflow_action(
        self,
        tenant_id: str,
        canonical_id: str,
        action: str
    ) -> bool:
        """Execute downgrade action for a workflow."""
        now = datetime.now(timezone.utc)

        if action == DowngradeAction.READ_ONLY.value:
            # Mark workflow as read-only in canonical_workflows table
            response = self.db_service.client.table("canonical_workflows").update({
                "is_read_only": True,
                "read_only_reason": "Plan limit exceeded - grace period expired",
                "updated_at": now.isoformat(),
            }).eq("id", canonical_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Marked workflow {canonical_id} as read-only")
            return bool(response.data)

        elif action == DowngradeAction.ARCHIVE.value:
            # Archive the workflow
            response = self.db_service.client.table("canonical_workflows").update({
                "is_archived": True,
                "archived_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", canonical_id).eq("tenant_id", tenant_id).execute()

            logger.info(f"Archived workflow {canonical_id}")
            return bool(response.data)

        return False

    # =========================================================================
    # High-Level Downgrade Handler
    # =========================================================================

    async def handle_plan_downgrade(
        self,
        tenant_id: str,
        old_plan: str,
        new_plan: str
    ) -> Dict[str, Any]:
        """
        Handle all aspects of a plan downgrade.

        This is the main entry point called by webhook handlers after
        a subscription downgrade is confirmed.

        Args:
            tenant_id: The tenant being downgraded
            old_plan: Previous plan name
            new_plan: New (lower) plan name

        Returns:
            Summary of actions taken
        """
        logger.info(f"Handling plan downgrade for tenant {tenant_id}: {old_plan} -> {new_plan}")

        summary = {
            "tenant_id": tenant_id,
            "old_plan": old_plan,
            "new_plan": new_plan,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actions_taken": [],
            "grace_periods_created": [],
            "errors": [],
        }

        try:
            # Check environments
            env_over, env_current, env_limit, env_over_ids = await self.detect_environment_overlimit(tenant_id)
            if env_over:
                logger.info(
                    f"Tenant {tenant_id} has {env_current} environments but limit is {env_limit}. "
                    f"Marking {len(env_over_ids)} for grace period."
                )

                for env_id in env_over_ids:
                    grace_id = await self.initiate_grace_period(
                        tenant_id,
                        ResourceType.ENVIRONMENT,
                        env_id,
                        reason=f"Plan downgrade from {old_plan} to {new_plan}"
                    )
                    if grace_id:
                        summary["grace_periods_created"].append({
                            "resource_type": "environment",
                            "resource_id": env_id,
                            "grace_period_id": grace_id,
                        })

                summary["actions_taken"].append(
                    f"Initiated grace period for {len(env_over_ids)} environments"
                )

            # Check team members
            team_over, team_current, team_limit, team_over_ids = await self.detect_team_member_overlimit(tenant_id)
            if team_over:
                logger.info(
                    f"Tenant {tenant_id} has {team_current} team members but limit is {team_limit}. "
                    f"Marking {len(team_over_ids)} for grace period."
                )

                for member_id in team_over_ids:
                    grace_id = await self.initiate_grace_period(
                        tenant_id,
                        ResourceType.TEAM_MEMBER,
                        member_id,
                        reason=f"Plan downgrade from {old_plan} to {new_plan}"
                    )
                    if grace_id:
                        summary["grace_periods_created"].append({
                            "resource_type": "team_member",
                            "resource_id": member_id,
                            "grace_period_id": grace_id,
                        })

                summary["actions_taken"].append(
                    f"Initiated grace period for {len(team_over_ids)} team members"
                )

            # Check workflows
            wf_over, wf_current, wf_limit, wf_over_ids = await self.detect_workflow_overlimit(tenant_id)
            if wf_over:
                logger.info(
                    f"Tenant {tenant_id} has {wf_current} workflows but limit is {wf_limit}. "
                    f"Marking {len(wf_over_ids)} for grace period."
                )

                for wf_id in wf_over_ids:
                    grace_id = await self.initiate_grace_period(
                        tenant_id,
                        ResourceType.WORKFLOW,
                        wf_id,
                        reason=f"Plan downgrade from {old_plan} to {new_plan}"
                    )
                    if grace_id:
                        summary["grace_periods_created"].append({
                            "resource_type": "workflow",
                            "resource_id": wf_id,
                            "grace_period_id": grace_id,
                        })

                summary["actions_taken"].append(
                    f"Initiated grace period for {len(wf_over_ids)} workflows"
                )

            if not summary["actions_taken"]:
                summary["actions_taken"].append("No resources over limit - no action needed")

            logger.info(
                f"Completed downgrade handling for tenant {tenant_id}. "
                f"Created {len(summary['grace_periods_created'])} grace periods."
            )

        except Exception as e:
            error_msg = f"Error during downgrade handling: {str(e)}"
            logger.error(error_msg)
            summary["errors"].append(error_msg)

        return summary

    async def check_resource_in_grace_period(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        resource_id: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if a specific resource is currently in a grace period.

        Args:
            tenant_id: The tenant ID
            resource_type: Type of resource
            resource_id: ID of the resource

        Returns:
            Tuple of (in_grace_period, grace_period_record)
        """
        try:
            response = self.db_service.client.table("downgrade_grace_periods").select(
                "*"
            ).eq("tenant_id", tenant_id).eq(
                "resource_type", resource_type.value
            ).eq("resource_id", resource_id).eq(
                "status", GracePeriodStatus.ACTIVE.value
            ).execute()

            if response.data:
                return True, response.data[0]

            return False, None
        except Exception:
            return False, None

    async def detect_overlimit_for_tenant(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Detect over-limit resources for a tenant and initiate grace periods."""
        summary = {
            "tenant_id": tenant_id,
            "grace_periods_created": 0,
            "resources_over_limit": 0,
            "skipped_existing": 0,
            "errors": [],
        }

        active_grace = await self.get_active_grace_periods(tenant_id)
        active_keys: Set[Tuple[str, str]] = {
            (gp.get("resource_type"), gp.get("resource_id"))
            for gp in active_grace
        }

        async def _handle_overage(
            resource_type: ResourceType,
            over_ids: List[str]
        ) -> None:
            for res_id in over_ids:
                key = (resource_type.value, res_id)
                if key in active_keys:
                    summary["skipped_existing"] += 1
                    continue

                grace_id = await self.initiate_grace_period(
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=res_id,
                    reason="Scheduled over-limit check"
                )
                if grace_id:
                    summary["grace_periods_created"] += 1
                    summary["resources_over_limit"] += 1
                else:
                    summary["errors"].append(res_id)

        try:
            env_over, _, _, env_over_ids = await self.detect_environment_overlimit(tenant_id)
            if env_over:
                await _handle_overage(ResourceType.ENVIRONMENT, env_over_ids)

            team_over, _, _, team_over_ids = await self.detect_team_member_overlimit(tenant_id)
            if team_over:
                await _handle_overage(ResourceType.TEAM_MEMBER, team_over_ids)

            wf_over, _, _, wf_over_ids = await self.detect_workflow_overlimit(tenant_id)
            if wf_over:
                await _handle_overage(ResourceType.WORKFLOW, wf_over_ids)

        except Exception as e:
            logger.error(f"Failed over-limit detection for tenant {tenant_id}: {e}")
            summary["errors"].append(str(e))

        return summary

    async def detect_overlimit_all_tenants(self) -> Dict[str, Any]:
        """Run over-limit detection across all tenants (used by scheduler)."""
        summary = {
            "tenants_checked": 0,
            "grace_periods_created": 0,
            "errors": [],
        }

        try:
            tenant_response = self.db_service.client.table("tenants").select(
                "id, status"
            ).execute()
            tenants = tenant_response.data or []
        except Exception as e:
            logger.error(f"Failed to load tenants for over-limit detection: {e}")
            return summary

        for tenant in tenants:
            tenant_id = tenant.get("id")
            if not tenant_id:
                continue
            if tenant.get("status") and tenant.get("status") != "active":
                continue

            summary["tenants_checked"] += 1
            try:
                tenant_summary = await self.detect_overlimit_for_tenant(tenant_id)
                summary["grace_periods_created"] += tenant_summary.get("grace_periods_created", 0)
                if tenant_summary.get("errors"):
                    summary["errors"].append(tenant_id)
            except Exception as e:
                logger.error(f"Error running over-limit detection for tenant {tenant_id}: {e}")
                summary["errors"].append(tenant_id)

        return summary


# Global service instance
downgrade_service = DowngradeService()
