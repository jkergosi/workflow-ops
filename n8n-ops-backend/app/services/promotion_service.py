"""
Promotion Service - Implements pipeline-aware promotion flow
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import logging
from uuid import uuid4

from app.services.n8n_client import N8NClient
from app.services.github_service import GitHubService
from app.services.database import db_service
from app.services.notification_service import notification_service
from app.schemas.promotion import (
    PromotionStatus,
    WorkflowChangeType,
    WorkflowSelection,
    GateResult,
    PromotionExecutionResult,
    PromotionDriftCheck,
    DependencyWarning,
)
from app.schemas.pipeline import PipelineStage, PipelineStageGates

logger = logging.getLogger(__name__)


class PromotionService:
    """Service for handling pipeline-aware promotions"""

    def __init__(self):
        self.db = db_service

    async def create_snapshot(
        self,
        tenant_id: str,
        environment_id: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Create a snapshot by exporting all workflows from N8N and committing to GitHub.
        Returns (snapshot_id, commit_sha)
        """
        # Get environment config
        env_config = await self.db.get_environment(environment_id, tenant_id)
        if not env_config:
            raise ValueError(f"Environment {environment_id} not found")

        # Create N8N client
        n8n_client = N8NClient(
            base_url=env_config.get("n8n_base_url"),
            api_key=env_config.get("n8n_api_key")
        )

        # Get all workflows from N8N
        workflows = await n8n_client.get_workflows()
        if not workflows:
            raise ValueError(f"No workflows found in environment {environment_id}")

        # Create GitHub service
        if not env_config.get("git_repo_url"):
            raise ValueError(f"GitHub not configured for environment {environment_id}")

        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

        if not github_service.is_configured():
            raise ValueError("GitHub is not properly configured")

        # Export all workflows to GitHub
        env_type = env_config.get("n8n_type", "dev")
        commit_sha = None
        workflows_synced = 0

        for workflow in workflows:
            try:
                workflow_id = workflow.get("id")
                full_workflow = await n8n_client.get_workflow(workflow_id)
                
                # Sync to GitHub with environment-specific path
                await github_service.sync_workflow_to_github(
                    workflow_id=workflow_id,
                    workflow_name=full_workflow.get("name"),
                    workflow_data=full_workflow,
                    commit_message=f"Auto backup before promotion: {reason}",
                    environment_type=env_type
                )
                workflows_synced += 1
            except Exception as e:
                logger.error(f"Failed to sync workflow {workflow.get('id')}: {str(e)}")
                continue

        # Get the latest commit SHA
        try:
            commits = github_service.repo.get_commits(path=f"workflows/{env_type}", sha=github_service.branch)
            if commits:
                commit_sha = commits[0].sha
        except Exception as e:
            logger.warning(f"Could not get commit SHA: {str(e)}")

        # Create snapshot record using new snapshot table structure
        from app.schemas.deployment import SnapshotType
        snapshot_id = str(uuid4())
        
        # Determine snapshot type from metadata
        snapshot_type = SnapshotType.AUTO_BACKUP
        if metadata:
            if metadata.get("type") == "pre_promotion":
                snapshot_type = SnapshotType.PRE_PROMOTION
            elif metadata.get("type") == "post_promotion":
                snapshot_type = SnapshotType.POST_PROMOTION
            elif metadata.get("manual"):
                snapshot_type = SnapshotType.MANUAL_BACKUP
        
        snapshot_data = {
            "id": snapshot_id,
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "git_commit_sha": commit_sha or "",
            "type": snapshot_type.value,
            "created_by_user_id": "current_user",  # TODO: Get from auth
            "related_deployment_id": metadata.get("deployment_id") if metadata else None,
            "metadata_json": {
                **(metadata or {}),
                "reason": reason,
                "workflows_count": workflows_synced,
            },
        }

        # Store snapshot in new snapshots table
        await self.db.create_snapshot(snapshot_data)
        
        # Emit snapshot.created event
        try:
            await notification_service.emit_event(
                tenant_id=tenant_id,
                event_type="snapshot.created",
                environment_id=environment_id,
                metadata={
                    "snapshot_id": snapshot_id,
                    "environment_id": environment_id,
                    "reason": reason,
                    "type": snapshot_type.value,
                    "workflows_count": workflows_synced,
                    "commit_sha": commit_sha,
                    **(metadata or {})
                }
            )
        except Exception as e:
            logger.error(f"Failed to emit snapshot.created event: {str(e)}")
        
        return snapshot_id, commit_sha or ""

    async def check_drift(
        self,
        tenant_id: str,
        environment_id: str,
        snapshot_id: str
    ) -> PromotionDriftCheck:
        """
        Check if environment has drifted from its GitHub snapshot.
        """
        # Get environment config
        env_config = await self.db.get_environment(environment_id, tenant_id)
        if not env_config:
            return PromotionDriftCheck(has_drift=True, can_proceed=False, requires_sync=True)

        # Create N8N client
        n8n_client = N8NClient(
            base_url=env_config.get("n8n_base_url"),
            api_key=env_config.get("n8n_api_key")
        )

        # Get workflows from N8N runtime
        runtime_workflows = await n8n_client.get_workflows()
        runtime_workflow_map = {wf.get("id"): wf for wf in runtime_workflows}

        # Get workflows from GitHub snapshot
        if not env_config.get("git_repo_url"):
            return PromotionDriftCheck(has_drift=False, can_proceed=True)

        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

        env_type = env_config.get("n8n_type", "dev")
        github_workflows = await github_service.get_all_workflows_from_github()
        github_workflow_map = {wf.get("id"): wf for wf in github_workflows}

        # Compare
        drift_details = []
        has_drift = False

        # Check for workflows in runtime but not in GitHub
        for wf_id, wf in runtime_workflow_map.items():
            if wf_id not in github_workflow_map:
                drift_details.append({
                    "workflow_id": wf_id,
                    "workflow_name": wf.get("name"),
                    "type": "added_in_runtime",
                    "message": "Workflow exists in runtime but not in GitHub"
                })
                has_drift = True

        # Check for workflows in GitHub but not in runtime
        for wf_id, wf in github_workflow_map.items():
            if wf_id not in runtime_workflow_map:
                drift_details.append({
                    "workflow_id": wf_id,
                    "workflow_name": wf.get("name"),
                    "type": "missing_in_runtime",
                    "message": "Workflow exists in GitHub but not in runtime"
                })
                has_drift = True

        # Check for modified workflows (simplified - compare updatedAt)
        for wf_id in set(runtime_workflow_map.keys()) & set(github_workflow_map.keys()):
            runtime_wf = runtime_workflow_map[wf_id]
            github_wf = github_workflow_map[wf_id]
            
            # Simple comparison - in production, use proper diff
            if runtime_wf.get("updatedAt") != github_wf.get("updatedAt"):
                drift_details.append({
                    "workflow_id": wf_id,
                    "workflow_name": runtime_wf.get("name"),
                    "type": "modified",
                    "message": "Workflow has been modified in runtime"
                })
                has_drift = True

        drift_result = PromotionDriftCheck(
            has_drift=has_drift,
            drift_details=drift_details,
            can_proceed=not has_drift,
            requires_sync=has_drift
        )
        
        # Emit drift_detected event if drift is found
        if has_drift:
            try:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="sync.drift_detected",
                    environment_id=environment_id,
                    metadata={
                        "environment_id": environment_id,
                        "snapshot_id": snapshot_id,
                        "drift_details": drift_details,
                        "requires_sync": has_drift
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit sync.drift_detected event: {str(e)}")
        
        return drift_result

    def _extract_workflow_dependencies(self, workflow_data: Dict[str, Any]) -> List[str]:
        """
        Extract workflow IDs that this workflow depends on.
        Looks for:
        - Execute Workflow nodes (n8n-nodes-base.executeWorkflow)
        - Webhook triggers that reference other workflows
        """
        dependencies = []
        nodes = workflow_data.get("nodes", [])
        
        for node in nodes:
            node_type = node.get("type", "")
            
            # Check for Execute Workflow node
            if node_type == "n8n-nodes-base.executeWorkflow":
                parameters = node.get("parameters", {})
                # The workflow ID might be in different places depending on n8n version
                workflow_id = (
                    parameters.get("workflowId") or
                    parameters.get("workflow") or
                    node.get("parameters", {}).get("workflow", {}).get("value")
                )
                if workflow_id:
                    dependencies.append(str(workflow_id))
            
            # Check for sub-workflow references in other node types
            # Some nodes might reference workflows in their parameters
            parameters = node.get("parameters", {})
            if isinstance(parameters, dict):
                # Recursively search for workflow references
                for key, value in parameters.items():
                    if isinstance(value, dict) and "workflowId" in value:
                        dependencies.append(str(value["workflowId"]))
                    elif key == "workflowId" and value:
                        dependencies.append(str(value))
        
        return list(set(dependencies))  # Remove duplicates

    async def detect_dependencies(
        self,
        selected_workflow_ids: List[str],
        all_workflow_selections: List[WorkflowSelection],
        source_workflows: Dict[str, Dict[str, Any]],
        target_workflows: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect workflow dependencies for selected workflows.
        Returns a dict mapping workflow_id to list of missing dependencies.
        """
        dependency_warnings = {}
        
        for workflow_id in selected_workflow_ids:
            source_wf = source_workflows.get(workflow_id)
            if not source_wf:
                continue
            
            # Extract dependencies from source workflow
            dependencies = self._extract_workflow_dependencies(source_wf)
            
            missing_deps = []
            for dep_id in dependencies:
                # Check if dependency is selected
                dep_selected = any(ws.workflow_id == dep_id for ws in all_workflow_selections if ws.selected)
                
                if not dep_selected:
                    # Check if dependency differs between source and target
                    source_dep = source_workflows.get(dep_id)
                    target_dep = target_workflows.get(dep_id)
                    
                    if source_dep and target_dep:
                        # Compare to see if they differ
                        source_json = json.dumps(source_dep, sort_keys=True)
                        target_json = json.dumps(target_dep, sort_keys=True)
                        if source_json != target_json:
                            missing_deps.append({
                                "workflow_id": dep_id,
                                "workflow_name": source_dep.get("name", "Unknown"),
                                "reason": "differs_in_target",
                                "message": f"Workflow '{source_dep.get('name', dep_id)}' differs between source and target"
                            })
                    elif source_dep:
                        # Dependency exists in source but not in target
                        missing_deps.append({
                            "workflow_id": dep_id,
                            "workflow_name": source_dep.get("name", "Unknown"),
                            "reason": "missing_in_target",
                            "message": f"Workflow '{source_dep.get('name', dep_id)}' exists in source but not in target"
                        })
            
            if missing_deps:
                dependency_warnings[workflow_id] = missing_deps
        
        return dependency_warnings

    async def compare_workflows(
        self,
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        source_snapshot_id: str,
        target_snapshot_id: str
    ) -> List[WorkflowSelection]:
        """
        Compare workflows between source and target GitHub snapshots.
        Returns list of workflow selections with change types.
        """
        # Get environment configs
        source_env = await self.db.get_environment(source_env_id, tenant_id)
        target_env = await self.db.get_environment(target_env_id, tenant_id)

        if not source_env or not target_env:
            return []

        # Get workflows from GitHub for both environments
        source_github = self._get_github_service(source_env)
        target_github = self._get_github_service(target_env)

        source_workflows = await source_github.get_all_workflows_from_github()
        target_workflows = await target_github.get_all_workflows_from_github()

        source_map = {wf.get("id"): wf for wf in source_workflows}
        target_map = {wf.get("id"): wf for wf in target_workflows}

        selections = []

        # Find all unique workflow IDs
        all_workflow_ids = set(source_map.keys()) | set(target_map.keys())

        for wf_id in all_workflow_ids:
            source_wf = source_map.get(wf_id)
            target_wf = target_map.get(wf_id)

            if source_wf and not target_wf:
                # New in source
                selections.append(WorkflowSelection(
                    workflow_id=wf_id,
                    workflow_name=source_wf.get("name", "Unknown"),
                    change_type=WorkflowChangeType.NEW,
                    enabled_in_source=source_wf.get("active", False),
                    selected=True  # Auto-select new workflows
                ))
            elif source_wf and target_wf:
                # Compare workflows
                source_json = json.dumps(source_wf, sort_keys=True)
                target_json = json.dumps(target_wf, sort_keys=True)

                if source_json != target_json:
                    # Check if target was modified independently
                    # (Simplified - in production, check commit history)
                    if target_wf.get("updatedAt") and source_wf.get("updatedAt"):
                        target_updated = datetime.fromisoformat(target_wf.get("updatedAt").replace('Z', '+00:00'))
                        source_updated = datetime.fromisoformat(source_wf.get("updatedAt").replace('Z', '+00:00'))
                        
                        if target_updated > source_updated:
                            # Target was modified more recently - potential hotfix
                            selections.append(WorkflowSelection(
                                workflow_id=wf_id,
                                workflow_name=source_wf.get("name", "Unknown"),
                                change_type=WorkflowChangeType.STAGING_HOTFIX,
                                enabled_in_source=source_wf.get("active", False),
                                enabled_in_target=target_wf.get("active", False),
                                selected=False,
                                requires_overwrite=True
                            ))
                        else:
                            # Source changed - normal change
                            selections.append(WorkflowSelection(
                                workflow_id=wf_id,
                                workflow_name=source_wf.get("name", "Unknown"),
                                change_type=WorkflowChangeType.CHANGED,
                                enabled_in_source=source_wf.get("active", False),
                                enabled_in_target=target_wf.get("active", False),
                                selected=True  # Auto-select changed workflows
                            ))
                    else:
                        # Can't determine timing - treat as changed
                        selections.append(WorkflowSelection(
                            workflow_id=wf_id,
                            workflow_name=source_wf.get("name", "Unknown"),
                            change_type=WorkflowChangeType.CHANGED,
                            enabled_in_source=source_wf.get("active", False),
                            enabled_in_target=target_wf.get("active", False),
                            selected=True
                        ))
                else:
                    # Unchanged
                    selections.append(WorkflowSelection(
                        workflow_id=wf_id,
                        workflow_name=source_wf.get("name", "Unknown"),
                        change_type=WorkflowChangeType.UNCHANGED,
                        enabled_in_source=source_wf.get("active", False),
                        enabled_in_target=target_wf.get("active", False),
                        selected=False
                    ))

        return selections

    async def _check_credentials(
        self,
        tenant_id: str,
        workflow_selections: List[WorkflowSelection],
        source_env_id: str,
        target_env_id: str,
        allow_placeholders: bool
    ) -> List[Dict[str, Any]]:
        """
        Check if credentials exist in target environment for selected workflows.
        Returns list of credential issues.
        """
        credential_issues = []
        
        # Get environment configs
        source_env = await self.db.get_environment(source_env_id, tenant_id)
        target_env = await self.db.get_environment(target_env_id, tenant_id)
        
        if not source_env or not target_env:
            return credential_issues
        
        # Create N8N clients
        source_n8n = N8NClient(
            base_url=source_env.get("n8n_base_url"),
            api_key=source_env.get("n8n_api_key")
        )
        target_n8n = N8NClient(
            base_url=target_env.get("n8n_base_url"),
            api_key=target_env.get("n8n_api_key")
        )
        
        # Get credentials from both environments
        source_credentials = await source_n8n.get_credentials()
        target_credentials = await target_n8n.get_credentials()
        
        # Build credential maps
        source_cred_map = {(c.get("type"), c.get("name")): c for c in source_credentials}
        target_cred_map = {(c.get("type"), c.get("name")): c for c in target_credentials}
        
        # Get workflows from source to check their credentials
        source_github = self._get_github_service(source_env)
        source_workflows = await source_github.get_all_workflows_from_github()
        source_workflow_map = {wf.get("id"): wf for wf in source_workflows}
        
        # Check credentials for each selected workflow
        for selection in workflow_selections:
            if not selection.selected:
                continue
            
            workflow = source_workflow_map.get(selection.workflow_id)
            if not workflow:
                continue
            
            # Extract credentials from workflow nodes
            nodes = workflow.get("nodes", [])
            for node in nodes:
                node_credentials = node.get("credentials", {})
                for cred_type, cred_info in node_credentials.items():
                    if isinstance(cred_info, dict):
                        cred_name = cred_info.get("name", "Unknown")
                    else:
                        cred_name = str(cred_info) if cred_info else "Unknown"
                    
                    cred_key = (cred_type, cred_name)
                    
                    # Check if credential exists in target
                    if cred_key not in target_cred_map:
                        if allow_placeholders:
                            # Create placeholder credential
                            placeholder_created = await self._create_placeholder_credential(
                                target_n8n, cred_type, cred_name, tenant_id, target_env_id
                            )
                            credential_issues.append({
                                "workflow_id": selection.workflow_id,
                                "workflow_name": selection.workflow_name,
                                "credential_type": cred_type,
                                "credential_name": cred_name,
                                "placeholder_created": placeholder_created
                            })
                        else:
                            # Emit credential.missing event when placeholders are not allowed
                            try:
                                await notification_service.emit_event(
                                    tenant_id=tenant_id,
                                    event_type="credential.missing",
                                    environment_id=target_env_id,
                                    metadata={
                                        "credential_type": cred_type,
                                        "credential_name": cred_name,
                                        "workflow_id": selection.workflow_id,
                                        "workflow_name": selection.workflow_name
                                    }
                                )
                            except Exception as e:
                                logger.error(f"Failed to emit credential.missing event: {str(e)}")
                            
                            credential_issues.append({
                                "workflow_id": selection.workflow_id,
                                "workflow_name": selection.workflow_name,
                                "credential_type": cred_type,
                                "credential_name": cred_name,
                                "placeholder_created": False
                            })
        
        return credential_issues

    async def _create_placeholder_credential(
        self,
        n8n_client: N8NClient,
        cred_type: str,
        cred_name: str,
        tenant_id: Optional[str] = None,
        environment_id: Optional[str] = None
    ) -> bool:
        """
        Create a placeholder credential in target environment.
        Returns True if created successfully.
        """
        try:
            # Create placeholder credential data
            # Note: N8N API structure may vary - this is a simplified version
            placeholder_data = {
                "name": f"{cred_name} (Placeholder)",
                "type": cred_type,
                "data": {}  # Empty data for placeholder
            }
            
            # Attempt to create credential via N8N API
            # Note: This would need to be implemented based on N8N's credential API
            # For now, return False as placeholder creation needs N8N API support
            logger.info(f"Would create placeholder credential: {cred_name} of type {cred_type}")
            created = False  # Placeholder - needs N8N credential API implementation
            
            # Emit credential.placeholder_created event if created successfully
            # Note: Currently always False, but when implemented, emit event on success
            if created and tenant_id and environment_id:
                try:
                    await notification_service.emit_event(
                        tenant_id=tenant_id,
                        event_type="credential.placeholder_created",
                        environment_id=environment_id,
                        metadata={
                            "credential_type": cred_type,
                            "credential_name": cred_name
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to emit credential.placeholder_created event: {str(e)}")
            
            return created
        except Exception as e:
            logger.error(f"Failed to create placeholder credential: {str(e)}")
            return False

    def _get_github_service(self, env_config: Dict[str, Any]) -> GitHubService:
        """Helper to create GitHub service from environment config"""
        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        return GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

    def _check_schedule_restrictions(self, stage: PipelineStage) -> Tuple[bool, Optional[str]]:
        """
        Check if current time is within allowed promotion window.
        Returns (is_allowed, error_message)
        """
        if not stage.schedule or not stage.schedule.restrict_promotion_times:
            return True, None
        
        from datetime import datetime, time
        
        now = datetime.now()
        current_day = now.strftime('%A')  # Monday, Tuesday, etc.
        current_time = now.time()
        
        # Check if current day is allowed
        allowed_days = stage.schedule.allowed_days or []
        if allowed_days and current_day not in allowed_days:
            return False, f"Promotions are not allowed on {current_day}. Allowed days: {', '.join(allowed_days)}"
        
        # Check if current time is within window
        start_time_str = stage.schedule.start_time
        end_time_str = stage.schedule.end_time
        
        if start_time_str and end_time_str:
            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                if not (start_time <= current_time <= end_time):
                    return False, f"Promotions are only allowed between {start_time_str} and {end_time_str}. Current time: {current_time.strftime('%H:%M')}"
            except ValueError:
                logger.warning(f"Invalid time format in schedule: {start_time_str} or {end_time_str}")
        
        return True, None

    async def check_gates(
        self,
        tenant_id: str,
        stage: PipelineStage,
        source_env_id: str,
        target_env_id: str,
        workflow_selections: List[WorkflowSelection]
    ) -> GateResult:
        """
        Check all gates configured for the promotion stage.
        """
        errors = []
        warnings = []

        # Get environment configs
        source_env = await self.db.get_environment(source_env_id, tenant_id)
        target_env = await self.db.get_environment(target_env_id, tenant_id)

        if not source_env or not target_env:
            errors.append("Source or target environment not found")
            return GateResult(
                require_clean_drift=stage.gates.require_clean_drift,
                drift_detected=True,
                run_pre_flight_validation=stage.gates.run_pre_flight_validation,
                errors=errors
            )

        # Check drift if required
        drift_detected = False
        if stage.gates.require_clean_drift:
            # This would use the snapshot_id from the promotion context
            # For now, simplified check
            drift_detected = False  # Would call check_drift here

        # Pre-flight validation
        credential_issues = []
        if stage.gates.run_pre_flight_validation:
            # Check credentials for selected workflows
            if stage.gates.credentials_exist_in_target:
                credential_issues = await self._check_credentials(
                    tenant_id=tenant_id,
                    workflow_selections=workflow_selections,
                    source_env_id=source_env_id,
                    target_env_id=target_env_id,
                    allow_placeholders=stage.policy_flags.allow_placeholder_credentials
                )
                
                if credential_issues:
                    if not stage.policy_flags.allow_placeholder_credentials:
                        errors.extend([f"Missing credential: {issue['credential_name']} for workflow {issue['workflow_name']}" 
                                      for issue in credential_issues if not issue.get('placeholder_created')])
                    else:
                        warnings.extend([f"Placeholder created for credential: {issue['credential_name']} in workflow {issue['workflow_name']}"
                                        for issue in credential_issues if issue.get('placeholder_created')])
        
        # Store credential_issues for later use in execution
        # We'll return them separately and they'll be stored in gate_results

            # Check nodes (simplified)
            if not stage.gates.nodes_supported_in_target:
                warnings.append("Some nodes may not be supported in target environment")

            # Check webhooks
            if not stage.gates.webhooks_available:
                warnings.append("Some webhooks may not be available in target environment")

        # Check target health (simplified)
        target_healthy = True
        if stage.gates.target_environment_healthy:
            # Would check actual environment health
            target_healthy = target_env.get("is_active", True)

        # Risk level check (simplified - would analyze workflows)
        risk_allowed = True

        # Check schedule restrictions
        schedule_allowed, schedule_error = self._check_schedule_restrictions(stage)
        if not schedule_allowed and schedule_error:
            errors.append(schedule_error)

        gate_result = GateResult(
            require_clean_drift=stage.gates.require_clean_drift,
            drift_detected=drift_detected,
            drift_resolved=not drift_detected,
            run_pre_flight_validation=stage.gates.run_pre_flight_validation,
            credentials_exist=stage.gates.credentials_exist_in_target if stage.gates.run_pre_flight_validation else True,
            nodes_supported=stage.gates.nodes_supported_in_target if stage.gates.run_pre_flight_validation else True,
            webhooks_available=stage.gates.webhooks_available if stage.gates.run_pre_flight_validation else True,
            target_environment_healthy=target_healthy,
            risk_level_allowed=risk_allowed,
            errors=errors,
            warnings=warnings
        )
        
        # Store credential_issues as an attribute for access during execution
        # (GateResult doesn't have this field, so we'll store it separately in the promotion record)
        gate_result.credential_issues = credential_issues  # type: ignore
        
        return gate_result

    async def create_pre_promotion_snapshot(
        self,
        tenant_id: str,
        target_env_id: str,
        promotion_id: str
    ) -> str:
        """
        Create pre-promotion snapshot of target environment (rollback point).
        Returns snapshot_id.
        """
        snapshot_id, _ = await self.create_snapshot(
            tenant_id=tenant_id,
            environment_id=target_env_id,
            reason=f"Pre-promotion snapshot for promotion {promotion_id}",
            metadata={"promotion_id": promotion_id, "type": "pre_promotion"}
        )
        return snapshot_id

    async def create_post_promotion_snapshot(
        self,
        tenant_id: str,
        target_env_id: str,
        promotion_id: str,
        source_snapshot_id: str
    ) -> str:
        """
        Create post-promotion snapshot of target environment.
        Returns snapshot_id.
        """
        snapshot_id, _ = await self.create_snapshot(
            tenant_id=tenant_id,
            environment_id=target_env_id,
            reason=f"Post-promotion snapshot for promotion {promotion_id}",
            metadata={
                "promotion_id": promotion_id,
                "type": "post_promotion",
                "source_snapshot_id": source_snapshot_id
            }
        )
        return snapshot_id

    async def execute_promotion(
        self,
        tenant_id: str,
        promotion_id: str,
        source_env_id: str,
        target_env_id: str,
        workflow_selections: List[WorkflowSelection],
        source_snapshot_id: str,
        policy_flags: Dict[str, Any],
        credential_issues: List[Dict[str, Any]] = None
    ) -> PromotionExecutionResult:
        """
        Execute the promotion by copying selected workflows to target environment.
        """
        # Get environment configs
        source_env = await self.db.get_environment(source_env_id, tenant_id)
        target_env = await self.db.get_environment(target_env_id, tenant_id)

        if not source_env or not target_env:
            return PromotionExecutionResult(
                promotion_id=promotion_id,
                status=PromotionStatus.FAILED,
                workflows_promoted=0,
                workflows_failed=0,
                workflows_skipped=0,
                source_snapshot_id=source_snapshot_id,
                errors=["Source or target environment not found"]
            )

        # Create clients
        source_n8n = N8NClient(
            base_url=source_env.get("n8n_base_url"),
            api_key=source_env.get("n8n_api_key")
        )
        target_n8n = N8NClient(
            base_url=target_env.get("n8n_base_url"),
            api_key=target_env.get("n8n_api_key")
        )

        # Get GitHub service for source to load workflows
        source_github = self._get_github_service(source_env)

        workflows_promoted = 0
        workflows_failed = 0
        workflows_skipped = 0
        errors = []
        warnings = []
        created_placeholders = []

        # Get workflows from GitHub snapshot
        source_workflows = await source_github.get_all_workflows_from_github()
        source_workflow_map = {wf.get("id"): wf for wf in source_workflows}

        # Track which workflows have placeholder credentials
        workflows_with_placeholders = set()
        if credential_issues:
            for issue in credential_issues:
                if issue.get("placeholder_created"):
                    workflows_with_placeholders.add(issue["workflow_id"])
                    created_placeholders.append(f"{issue['credential_name']} ({issue['workflow_name']})")

        # Promote each selected workflow
        for selection in workflow_selections:
            if not selection.selected:
                workflows_skipped += 1
                continue

            try:
                workflow_data = source_workflow_map.get(selection.workflow_id)
                if not workflow_data:
                    errors.append(f"Workflow {selection.workflow_name} not found in source snapshot")
                    workflows_failed += 1
                    continue

                # Apply enabled/disabled state
                # If placeholders were created, force disabled
                if selection.workflow_id in workflows_with_placeholders:
                    workflow_data["active"] = False
                    warnings.append(f"Workflow {selection.workflow_name} disabled due to placeholder credentials")
                else:
                    workflow_data["active"] = selection.enabled_in_source

                # Write to target N8N
                workflow_id = workflow_data.get("id")
                await target_n8n.update_workflow(workflow_id, workflow_data)
                
                workflows_promoted += 1
            except Exception as e:
                error_msg = f"Failed to promote {selection.workflow_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                workflows_failed += 1

        # Create audit log entry
        await self._create_audit_log(
            tenant_id=tenant_id,
            promotion_id=promotion_id,
            action="execute",
            result={
                "workflows_promoted": workflows_promoted,
                "workflows_failed": workflows_failed,
                "workflows_skipped": workflows_skipped,
                "created_placeholders": created_placeholders,
                "errors": errors,
                "warnings": warnings
            }
        )

        return PromotionExecutionResult(
            promotion_id=promotion_id,
            status=PromotionStatus.COMPLETED if workflows_failed == 0 else PromotionStatus.FAILED,
            workflows_promoted=workflows_promoted,
            workflows_failed=workflows_failed,
            workflows_skipped=workflows_skipped,
            source_snapshot_id=source_snapshot_id,
            target_pre_snapshot_id="",  # Will be set by caller
            target_post_snapshot_id="",  # Will be set by caller
            errors=errors,
            warnings=warnings,
            created_placeholders=created_placeholders
        )

    async def _create_audit_log(
        self,
        tenant_id: str,
        promotion_id: str,
        action: str,
        result: Dict[str, Any]
    ):
        """
        Create audit log entry for promotion action.
        """
        audit_data = {
            "tenant_id": tenant_id,
            "promotion_id": promotion_id,
            "action": action,
            "actor": "current_user",  # TODO: Get from auth
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
            "metadata": {}
        }
        
        # Store audit log (would use database)
        # await self.db.create_audit_log(audit_data)
        logger.info(f"Audit log: {action} for promotion {promotion_id}: {result}")


promotion_service = PromotionService()

