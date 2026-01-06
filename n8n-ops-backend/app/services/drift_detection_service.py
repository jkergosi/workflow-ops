"""
Drift Detection Service - Centralized environment-level drift detection

Compares all workflows in an environment against their GitHub source of truth
and updates environment drift status.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.services.github_service import GitHubService
from app.services.diff_service import compare_workflows, DriftResult

logger = logging.getLogger(__name__)


class DriftStatus:
    """Drift status constants"""
    UNKNOWN = "UNKNOWN"
    IN_SYNC = "IN_SYNC"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    UNTRACKED = "UNTRACKED"
    ERROR = "ERROR"


@dataclass
class WorkflowDriftInfo:
    """Drift info for a single workflow"""
    workflow_id: str
    workflow_name: str
    active: bool
    has_drift: bool
    not_in_git: bool
    drift_type: str  # 'none', 'modified', 'added_in_runtime', 'missing_from_runtime'
    nodes_added: int = 0
    nodes_removed: int = 0
    nodes_modified: int = 0
    connections_changed: bool = False
    settings_changed: bool = False


@dataclass
class EnvironmentDriftSummary:
    """Complete drift summary for an environment"""
    total_workflows: int
    in_sync: int
    with_drift: int
    not_in_git: int
    git_configured: bool
    last_detected_at: str
    affected_workflows: List[Dict[str, Any]]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totalWorkflows": self.total_workflows,
            "inSync": self.in_sync,
            "withDrift": self.with_drift,
            "notInGit": self.not_in_git,
            "gitConfigured": self.git_configured,
            "lastDetectedAt": self.last_detected_at,
            "affectedWorkflows": self.affected_workflows,
            "error": self.error
        }


class DriftDetectionService:
    """Service for detecting and managing drift between environments and GitHub"""

    async def detect_drift(
        self,
        tenant_id: str,
        environment_id: str,
        update_status: bool = True
    ) -> EnvironmentDriftSummary:
        """
        Detect drift for all workflows in an environment.

        Args:
            tenant_id: The tenant ID
            environment_id: The environment to check
            update_status: Whether to update the environment's drift_status in DB

        Returns:
            EnvironmentDriftSummary with detailed drift information
        """
        try:
            # Get environment details
            environment = await db_service.get_environment(environment_id, tenant_id)
            if not environment:
                return EnvironmentDriftSummary(
                    total_workflows=0,
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=False,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error="Environment not found"
                )

            # Check if GitHub is configured
            if not environment.get("git_repo_url") or not environment.get("git_pat"):
                summary = EnvironmentDriftSummary(
                    total_workflows=environment.get("workflow_count", 0),
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=False,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error="GitHub is not configured for this environment"
                )

                if update_status:
                    await self._update_environment_drift_status(
                        tenant_id, environment_id, DriftStatus.UNKNOWN, summary
                    )

                return summary

            # Create provider adapter
            adapter = ProviderRegistry.get_adapter_for_environment(environment)

            # Create GitHub service
            repo_url = environment.get("git_repo_url", "").rstrip('/').replace('.git', '')
            repo_parts = repo_url.split("/")
            github_service = GitHubService(
                token=environment.get("git_pat"),
                repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
                repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
                branch=environment.get("git_branch", "main")
            )

            if not github_service.is_configured():
                summary = EnvironmentDriftSummary(
                    total_workflows=environment.get("workflow_count", 0),
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=False,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error="GitHub is not properly configured"
                )

                if update_status:
                    await self._update_environment_drift_status(
                        tenant_id, environment_id, DriftStatus.UNKNOWN, summary
                    )

                return summary

            # Fetch all workflows from provider
            try:
                runtime_workflows = await adapter.get_workflows()
            except Exception as e:
                logger.error(f"Failed to fetch workflows from provider: {e}")
                summary = EnvironmentDriftSummary(
                    total_workflows=0,
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=True,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error=f"Failed to fetch workflows from provider: {str(e)}"
                )

                if update_status:
                    await self._update_environment_drift_status(
                        tenant_id, environment_id, DriftStatus.ERROR, summary
                    )

                return summary

            # Fetch all workflows from GitHub
            env_type = environment.get("n8n_type")
            if not env_type:
                summary = EnvironmentDriftSummary(
                    total_workflows=len(runtime_workflows),
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=True,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error="Environment type is required for drift detection"
                )

                if update_status:
                    await self._update_environment_drift_status(
                        tenant_id, environment_id, DriftStatus.ERROR, summary
                    )

                return summary

            try:
                git_workflows_map = await github_service.get_all_workflows_from_github(environment_type=env_type)
            except Exception as e:
                logger.error(f"Failed to fetch workflows from GitHub: {e}")
                summary = EnvironmentDriftSummary(
                    total_workflows=len(runtime_workflows),
                    in_sync=0,
                    with_drift=0,
                    not_in_git=0,
                    git_configured=True,
                    last_detected_at=datetime.utcnow().isoformat(),
                    affected_workflows=[],
                    error=f"Failed to fetch workflows from GitHub: {str(e)}"
                )

                if update_status:
                    await self._update_environment_drift_status(
                        tenant_id, environment_id, DriftStatus.ERROR, summary
                    )

                return summary

            # Create map of git workflows by name
            git_by_name = {}
            for wf_id, gw in git_workflows_map.items():
                name = gw.get("name", "")
                if name:
                    git_by_name[name] = gw

            # Compare each runtime workflow
            affected_workflows = []
            in_sync_count = 0
            with_drift_count = 0
            not_in_git_count = 0

            for runtime_wf in runtime_workflows:
                wf_name = runtime_wf.get("name", "")
                wf_id = runtime_wf.get("id", "")
                active = runtime_wf.get("active", False)

                git_entry = git_by_name.get(wf_name)

                if git_entry is None:
                    # Not in Git
                    not_in_git_count += 1
                    affected_workflows.append({
                        "id": wf_id,
                        "name": wf_name,
                        "active": active,
                        "hasDrift": False,
                        "notInGit": True,
                        "driftType": "added_in_runtime"
                    })
                else:
                    # Compare workflows
                    drift_result = compare_workflows(
                        git_workflow=git_entry,
                        runtime_workflow=runtime_wf
                    )

                    if drift_result.has_drift:
                        with_drift_count += 1
                        affected_workflows.append({
                            "id": wf_id,
                            "name": wf_name,
                            "active": active,
                            "hasDrift": True,
                            "notInGit": False,
                            "driftType": "modified",
                            "summary": {
                                "nodesAdded": drift_result.summary.nodes_added,
                                "nodesRemoved": drift_result.summary.nodes_removed,
                                "nodesModified": drift_result.summary.nodes_modified,
                                "connectionsChanged": drift_result.summary.connections_changed,
                                "settingsChanged": drift_result.summary.settings_changed
                            },
                            "differenceCount": len(drift_result.differences)
                        })
                    else:
                        in_sync_count += 1

            # Check if any workflows are tracked/linked for this environment
            tracked_workflows = await db_service.get_workflows_from_canonical(
                tenant_id=tenant_id,
                environment_id=environment_id,
                include_deleted=False,
                include_ignored=False
            )
            
            # If no workflows are tracked, set status to untracked
            if len(tracked_workflows) == 0:
                drift_status = DriftStatus.UNTRACKED
            else:
                # Determine overall status based on drift detection
                has_drift = with_drift_count > 0 or not_in_git_count > 0
                drift_status = DriftStatus.DRIFT_DETECTED if has_drift else DriftStatus.IN_SYNC

            # Sort affected workflows: drift first, then not in git
            affected_workflows.sort(key=lambda x: (
                0 if x.get("hasDrift") else (1 if x.get("notInGit") else 2),
                x.get("name", "").lower()
            ))

            summary = EnvironmentDriftSummary(
                total_workflows=len(runtime_workflows),
                in_sync=in_sync_count,
                with_drift=with_drift_count,
                not_in_git=not_in_git_count,
                git_configured=True,
                last_detected_at=datetime.utcnow().isoformat(),
                affected_workflows=affected_workflows
            )

            if update_status:
                await self._update_environment_drift_status(
                    tenant_id, environment_id, drift_status, summary
                )

            return summary

        except Exception as e:
            logger.error(f"Failed to detect drift for environment {environment_id}: {e}")
            summary = EnvironmentDriftSummary(
                total_workflows=0,
                in_sync=0,
                with_drift=0,
                not_in_git=0,
                git_configured=False,
                last_detected_at=datetime.utcnow().isoformat(),
                affected_workflows=[],
                error=str(e)
            )

            if update_status:
                await self._update_environment_drift_status(
                    tenant_id, environment_id, DriftStatus.ERROR, summary
                )

            return summary

    async def get_cached_drift_status(
        self,
        tenant_id: str,
        environment_id: str
    ) -> Dict[str, Any]:
        """
        Get the cached drift status for an environment without running detection.

        Returns the last known drift status from the database.
        """
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            return {
                "driftStatus": DriftStatus.UNKNOWN,
                "lastDriftDetectedAt": None,
                "summary": None
            }

        return {
            "driftStatus": environment.get("drift_status", DriftStatus.UNKNOWN),
            "lastDriftDetectedAt": environment.get("last_drift_detected_at"),
            "activeDriftIncidentId": environment.get("active_drift_incident_id"),
            "summary": None  # Summary not cached in environment table for now
        }

    async def _update_environment_drift_status(
        self,
        tenant_id: str,
        environment_id: str,
        drift_status: str,
        summary: EnvironmentDriftSummary
    ) -> None:
        """Update the environment's drift status in the database"""
        try:
            now = datetime.utcnow().isoformat()
            update_data = {
                "drift_status": drift_status,
                "last_drift_check_at": now
            }
            
            # Only update last_drift_detected_at if drift was actually detected
            if drift_status == DriftStatus.DRIFT_DETECTED:
                update_data["last_drift_detected_at"] = now

            await db_service.update_environment(environment_id, tenant_id, update_data)

            logger.info(
                f"Updated drift status for environment {environment_id}: "
                f"{drift_status} ({summary.with_drift} drifted, {summary.not_in_git} not in git)"
            )
        except Exception as e:
            logger.error(f"Failed to update drift status for environment {environment_id}: {e}")


# Singleton instance
drift_detection_service = DriftDetectionService()
