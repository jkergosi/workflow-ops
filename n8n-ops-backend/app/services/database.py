import logging
from supabase import create_client, Client
from app.core.config import settings
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for interacting with Supabase database"""

    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )

    # Environment operations
    async def get_environments(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all environments for a tenant"""
        response = self.client.table("environments").select("*").eq("tenant_id", tenant_id).execute()
        environments = response.data or []

        # Sort environments based on Environment Types sort order (system-configurable).
        # Falls back to lexicographic type and then name when types aren't configured.
        try:
            env_types = await self.get_environment_types(tenant_id, ensure_defaults=True)
            order_map = {t.get("key"): int(t.get("sort_order", 0)) for t in (env_types or []) if t.get("key")}

            def sort_key(env: Dict[str, Any]):
                env_type = env.get("n8n_type")
                # Unknown/None types go last
                type_order = order_map.get(env_type, 10_000)
                name = (env.get("n8n_name") or env.get("name") or "").lower()
                return (type_order, str(env_type or "").lower(), name)

            return sorted(environments, key=sort_key)
        except Exception:
            # If environment types table isn't present, don't break.
            return environments

    async def get_environment(self, environment_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific environment"""
        response = self.client.table("environments").select("*").eq("id", environment_id).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def get_environment_by_type(self, tenant_id: str, env_type: str) -> Optional[Dict[str, Any]]:
        """Get environment by type for a tenant"""
        response = self.client.table("environments").select("*").eq("tenant_id", tenant_id).eq("n8n_type", env_type).execute()
        return response.data[0] if response.data else None

    async def create_environment(self, environment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new environment"""
        response = self.client.table("environments").insert(environment_data).execute()
        return response.data[0]

    async def update_environment(self, environment_id: str, tenant_id: str, environment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an environment"""
        response = self.client.table("environments").update(environment_data).eq("id", environment_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_environment(self, environment_id: str, tenant_id: str) -> bool:
        """Delete an environment"""
        self.client.table("environments").delete().eq("id", environment_id).eq("tenant_id", tenant_id).execute()
        return True

    # Drift Incidents
    async def get_drift_incidents(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = self.client.table("drift_incidents").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if status:
            query = query.eq("status", status)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data or []

    async def get_drift_incident(self, tenant_id: str, incident_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("drift_incidents")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", incident_id)
            .single()
            .execute()
        )
        return response.data

    async def create_drift_incident(
        self,
        tenant_id: str,
        environment_id: str,
        title: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "status": "open",
        }
        if title:
            payload["title"] = title
        if created_by:
            payload["created_by"] = created_by

        response = self.client.table("drift_incidents").insert(payload).execute()
        incident = response.data[0] if response.data else None
        if not incident:
            raise Exception("Failed to create incident")

        # Set environment drift pointers (best-effort; keeps changes additive)
        try:
            self.client.table("environments").update(
                {
                    "drift_status": "DRIFT_INCIDENT_ACTIVE",
                    "active_drift_incident_id": incident["id"],
                    "last_drift_detected_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", environment_id).eq("tenant_id", tenant_id).execute()
        except Exception:
            pass

        return incident

    # Environment type operations (system-configurable ordering)
    async def get_environment_types(self, tenant_id: str, ensure_defaults: bool = False) -> List[Dict[str, Any]]:
        """Get environment types for a tenant (sorted by sort_order)."""
        response = self.client.table("environment_types").select("*").eq("tenant_id", tenant_id).order("sort_order").execute()
        types = response.data or []

        if types or not ensure_defaults:
            return types

        # Seed defaults for the tenant if none exist
        defaults = [
            {"tenant_id": tenant_id, "key": "dev", "label": "Development", "sort_order": 10, "is_active": True},
            {"tenant_id": tenant_id, "key": "staging", "label": "Staging", "sort_order": 20, "is_active": True},
            {"tenant_id": tenant_id, "key": "production", "label": "Production", "sort_order": 30, "is_active": True},
        ]
        # Upsert by tenant_id+key (unique constraint in migration)
        self.client.table("environment_types").upsert(defaults).execute()
        response2 = self.client.table("environment_types").select("*").eq("tenant_id", tenant_id).order("sort_order").execute()
        return response2.data or []

    async def create_environment_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("environment_types").insert(data).execute()
        return response.data[0]

    async def update_environment_type(self, env_type_id: str, tenant_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("environment_types")
            .update(data)
            .eq("id", env_type_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def delete_environment_type(self, env_type_id: str, tenant_id: str) -> bool:
        self.client.table("environment_types").delete().eq("id", env_type_id).eq("tenant_id", tenant_id).execute()
        return True

    async def reorder_environment_types(self, tenant_id: str, ordered_ids: List[str]) -> List[Dict[str, Any]]:
        # Fetch existing data before update to preserve all fields
        existing_response = self.client.table("environment_types").select("*").eq("tenant_id", tenant_id).execute()
        existing_data = existing_response.data or []
        
        # Create a map of id -> existing data for quick lookup
        existing_map = {item["id"]: item for item in existing_data}
        
        # Update sort_order for each environment type individually, preserving all existing fields
        for idx, env_type_id in enumerate(ordered_ids):
            if env_type_id not in existing_map:
                continue
            
            existing_item = existing_map[env_type_id]
            
            # Update with sort_order AND preserve key/label to prevent null values
            update_payload = {
                "sort_order": idx * 10,
                "key": existing_item.get("key"),
                "label": existing_item.get("label"),
            }
            
            self.client.table("environment_types").update(
                update_payload
            ).eq("id", env_type_id).eq("tenant_id", tenant_id).execute()
        
        response = self.client.table("environment_types").select("*").eq("tenant_id", tenant_id).order("sort_order").execute()
        return response.data or []

    async def update_environment_workflow_count(self, environment_id: str, tenant_id: str, count: int) -> Optional[Dict[str, Any]]:
        """Update the workflow count for an environment"""
        response = self.client.table("environments").update(
            {"workflow_count": count}
        ).eq("id", environment_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    # Workflow snapshot operations
    async def create_workflow_snapshot(self, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a workflow snapshot"""
        response = self.client.table("workflow_snapshots").insert(snapshot_data).execute()
        return response.data[0]

    async def get_workflow_snapshots(self, tenant_id: str, workflow_id: str = None) -> List[Dict[str, Any]]:
        """Get workflow snapshots"""
        query = self.client.table("workflow_snapshots").select("*").eq("tenant_id", tenant_id)
        if workflow_id:
            query = query.eq("workflow_id", workflow_id)
        response = query.order("created_at", desc=True).execute()
        return response.data

    # Git config operations
    async def get_git_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get git configuration for a tenant"""
        response = self.client.table("git_configs").select("*").eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def upsert_git_config(self, git_config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update git configuration"""
        response = self.client.table("git_configs").upsert(git_config_data).execute()
        return response.data[0]

    # Deployment operations
    async def create_deployment(self, deployment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deployment record"""
        response = self.client.table("deployments").insert(deployment_data).execute()
        return response.data[0]

    async def update_deployment(self, deployment_id: str, deployment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a deployment record - always updates updated_at timestamp"""
        # Always set updated_at to current time
        deployment_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("deployments").update(deployment_data).eq("id", deployment_id).execute()
        return response.data[0]

    async def get_deployments(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all deployments for a tenant"""
        response = self.client.table("deployments").select("*").eq("tenant_id", tenant_id).order("started_at", desc=True).execute()
        return response.data

    async def get_deployment(self, deployment_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific deployment"""
        response = self.client.table("deployments").select("*").eq("id", deployment_id).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def delete_deployment(self, deployment_id: str, tenant_id: str, deleted_by_user_id: str) -> Dict[str, Any]:
        """Soft delete a deployment"""
        update_data = {
            "deleted_at": datetime.utcnow().isoformat(),
            "deleted_by_user_id": deleted_by_user_id
        }
        response = self.client.table("deployments").update(update_data).eq("id", deployment_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    # Snapshot operations (new Git-backed snapshots)
    async def create_snapshot(self, snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a snapshot record"""
        response = self.client.table("snapshots").insert(snapshot_data).execute()
        return response.data[0]

    async def get_snapshot(self, snapshot_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific snapshot"""
        response = self.client.table("snapshots").select("*").eq("id", snapshot_id).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def get_snapshots(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        snapshot_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get snapshots with optional filtering"""
        query = self.client.table("snapshots").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if snapshot_type:
            query = query.eq("type", snapshot_type)
        response = query.order("created_at", desc=True).execute()
        return response.data

    # Deployment workflow operations
    async def create_deployment_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deployment workflow record"""
        response = self.client.table("deployment_workflows").insert(workflow_data).execute()
        return response.data[0]

    async def get_deployment_workflows(self, deployment_id: str) -> List[Dict[str, Any]]:
        """Get all workflows for a deployment"""
        response = self.client.table("deployment_workflows").select("*").eq("deployment_id", deployment_id).execute()
        return response.data

    async def update_deployment_workflow(self, deployment_id: str, workflow_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a deployment workflow record by deployment_id and workflow_id"""
        response = self.client.table("deployment_workflows").update(update_data).eq(
            "deployment_id", deployment_id
        ).eq("workflow_id", workflow_id).execute()
        return response.data[0] if response.data else None

    async def create_deployment_workflows_batch(self, workflows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple deployment workflow records in a batch"""
        if not workflows:
            return []
        response = self.client.table("deployment_workflows").insert(workflows).execute()
        return response.data

    # Execution operations
    async def create_execution(self, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an execution record"""
        response = self.client.table("executions").insert(execution_data).execute()
        return response.data[0]

    async def get_executions(self, tenant_id: str, environment_id: str = None, workflow_id: str = None) -> List[Dict[str, Any]]:
        """Get executions for a tenant, optionally filtered by environment and workflow"""
        query = self.client.table("executions").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if workflow_id:
            query = query.eq("workflow_id", workflow_id)
        response = query.order("started_at", desc=True).execute()

        # Enrich executions with workflow names from canonical workflow system
        executions = response.data
        if executions:
            # Group executions by environment to fetch workflows efficiently
            env_workflow_map = {}  # {env_id: {workflow_id: workflow_name}}

            for execution in executions:
                exec_env_id = execution.get("environment_id")
                if exec_env_id and exec_env_id not in env_workflow_map:
                    # Fetch all workflow mappings for this environment from canonical system
                    mappings_response = (
                        self.client.table("workflow_env_map")
                        .select("n8n_workflow_id, workflow_data, canonical_id")
                        .eq("tenant_id", tenant_id)
                        .eq("environment_id", exec_env_id)
                        .not_.is_("n8n_workflow_id", "null")
                        .execute()
                    )

                    # Get canonical IDs to fetch display names
                    canonical_ids = [m.get("canonical_id") for m in (mappings_response.data or []) if m.get("canonical_id")]
                    canonical_map = {}
                    if canonical_ids:
                        canonical_response = (
                            self.client.table("canonical_workflows")
                            .select("canonical_id, display_name")
                            .eq("tenant_id", tenant_id)
                            .in_("canonical_id", canonical_ids)
                            .execute()
                        )
                        for canonical in (canonical_response.data or []):
                            canonical_map[canonical.get("canonical_id")] = canonical

                    # Create a mapping of workflow_id to workflow_name for this environment
                    workflow_name_map = {}
                    for mapping in (mappings_response.data or []):
                        n8n_id = mapping.get("n8n_workflow_id")
                        if n8n_id:
                            workflow_data = mapping.get("workflow_data") or {}
                            canonical_id = mapping.get("canonical_id")
                            canonical = canonical_map.get(canonical_id, {}) if canonical_id else {}
                            workflow_name = (
                                workflow_data.get("name") or 
                                canonical.get("display_name") or 
                                "Unknown"
                            )
                            workflow_name_map[n8n_id] = workflow_name
                    
                    env_workflow_map[exec_env_id] = workflow_name_map

            # Enrich executions with workflow names
            for execution in executions:
                exec_env_id = execution.get("environment_id")
                workflow_id = execution.get("workflow_id")

                if exec_env_id and workflow_id and exec_env_id in env_workflow_map:
                    execution["workflow_name"] = env_workflow_map[exec_env_id].get(workflow_id)

        return executions

    async def get_execution(self, execution_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific execution"""
        response = self.client.table("executions").select("*").eq("id", execution_id).eq("tenant_id", tenant_id).single().execute()
        execution = response.data

        # Enrich with workflow name from canonical workflow system
        if execution and execution.get("workflow_id") and execution.get("environment_id"):
            # Get workflow name from canonical system
            try:
                mapping_response = (
                    self.client.table("workflow_env_map")
                    .select("workflow_data, canonical_id")
                    .eq("tenant_id", tenant_id)
                    .eq("environment_id", execution["environment_id"])
                    .eq("n8n_workflow_id", execution["workflow_id"])
                    .single()
                    .execute()
                )
                
                if mapping_response.data:
                    workflow_data = mapping_response.data.get("workflow_data") or {}
                    canonical_id = mapping_response.data.get("canonical_id")
                    
                    # Get canonical workflow display name if needed
                    display_name = None
                    if canonical_id:
                        canonical_response = (
                            self.client.table("canonical_workflows")
                            .select("display_name")
                            .eq("tenant_id", tenant_id)
                            .eq("canonical_id", canonical_id)
                            .single()
                            .execute()
                        )
                        if canonical_response.data:
                            display_name = canonical_response.data.get("display_name")
                    
                    execution["workflow_name"] = (
                        workflow_data.get("name") or 
                        display_name or 
                        "Unknown"
                    )
            except Exception:
                # If mapping not found, leave workflow_name as None
                pass

        return execution

    async def update_execution(self, execution_id: str, tenant_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an execution record"""
        response = self.client.table("executions").update(execution_data).eq("id", execution_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_execution(self, execution_id: str, tenant_id: str) -> bool:
        """Delete an execution record"""
        self.client.table("executions").delete().eq("id", execution_id).eq("tenant_id", tenant_id).execute()
        return True

    async def get_failed_executions(
        self,
        tenant_id: str,
        since: str,
        until: str,
        environment_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get failed executions in a time period for error intelligence"""
        query = self.client.table("executions").select(
            "id, workflow_id, environment_id, status, started_at, finished_at, data"
        ).eq("tenant_id", tenant_id).eq("status", "error")

        if environment_id:
            query = query.eq("environment_id", environment_id)

        # Apply time range filter
        query = query.gte("started_at", since).lte("started_at", until)
        query = query.order("started_at", desc=True).limit(500)

        response = query.execute()
        return response.data

    async def get_last_workflow_failure(
        self,
        tenant_id: str,
        workflow_id: str,
        environment_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get the last failed execution for a specific workflow"""
        query = self.client.table("executions").select(
            "id, workflow_id, environment_id, status, started_at, finished_at, data"
        ).eq("tenant_id", tenant_id).eq("workflow_id", workflow_id).eq("status", "error")

        if environment_id:
            query = query.eq("environment_id", environment_id)

        query = query.order("started_at", desc=True).limit(1)

        response = query.execute()
        return response.data[0] if response.data else None

    # Tag operations
    async def create_tag(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a tag record"""
        response = self.client.table("tags").insert(tag_data).execute()
        return response.data[0]

    async def get_tags(self, tenant_id: str, environment_id: str = None) -> List[Dict[str, Any]]:
        """Get tags for a tenant, optionally filtered by environment"""
        query = self.client.table("tags").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        response = query.order("name").execute()
        return response.data

    async def get_tag(self, tag_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific tag"""
        response = self.client.table("tags").select("*").eq("id", tag_id).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def update_tag(self, tag_id: str, tenant_id: str, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a tag record"""
        response = self.client.table("tags").update(tag_data).eq("id", tag_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_tag(self, tag_id: str, tenant_id: str) -> bool:
        """Delete a tag record"""
        self.client.table("tags").delete().eq("id", tag_id).eq("tenant_id", tenant_id).execute()
        return True

    async def upsert_tag(self, tenant_id: str, environment_id: str, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a tag in the cache"""
        from datetime import datetime

        # Extract fields from N8N tag data
        tag_record = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "tag_id": tag_data.get("id"),
            "name": tag_data.get("name"),
            "created_at": tag_data.get("createdAt"),
            "updated_at": tag_data.get("updatedAt"),
            "last_synced_at": datetime.utcnow().isoformat()
        }

        response = self.client.table("tags").upsert(tag_record, on_conflict="tenant_id,environment_id,tag_id").execute()
        return response.data[0] if response.data else None

    async def sync_tags_from_n8n(self, tenant_id: str, environment_id: str, n8n_tags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sync tags from N8N API to database cache"""
        from datetime import datetime

        # Get current tag IDs from N8N
        n8n_tag_ids = {tag.get("id") for tag in n8n_tags}

        # Delete tags that no longer exist in N8N
        existing_tags = await self.get_tags(tenant_id, environment_id)
        for existing in existing_tags:
            if existing["tag_id"] not in n8n_tag_ids:
                await self.delete_tag(existing["id"], tenant_id)

        # Upsert all tags from N8N
        results = []
        for tag_data in n8n_tags:
            result = await self.upsert_tag(tenant_id, environment_id, tag_data)
            if result:
                results.append(result)

        return results

    # Workflow cache operations
    async def get_workflows(self, tenant_id: str, environment_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Use get_workflows_from_canonical() instead.
        This method is kept for backward compatibility and will be removed in a future version.
        
        Get all cached workflows for a tenant and environment.

        Args:
            tenant_id: The tenant ID
            environment_id: The environment ID
            include_archived: If True, include archived workflows. Default False.
        """
        import logging
        logging.warning("get_workflows() is deprecated. Use get_workflows_from_canonical() instead.")
        return await self.get_workflows_from_canonical(
            tenant_id=tenant_id,
            environment_id=environment_id,
            include_deleted=False,
            include_ignored=False
        )

    async def get_workflow(self, tenant_id: str, environment_id: str, n8n_workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Use canonical workflow system instead.
        Get workflow by n8n_workflow_id from canonical system.
        """
        # Query workflow_env_map
        try:
            mapping_response = (
                self.client.table("workflow_env_map")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", n8n_workflow_id)
                .single()
                .execute()
            )
        except Exception:
            # If no mapping found, return None
            return None
        
        if not mapping_response.data:
            return None
        
        mapping = mapping_response.data
        workflow_data = mapping.get("workflow_data") or {}
        canonical_id = mapping.get("canonical_id")
        
        # Get canonical workflow display name if needed
        display_name = None
        if canonical_id:
            try:
                canonical_response = (
                    self.client.table("canonical_workflows")
                    .select("display_name")
                    .eq("tenant_id", tenant_id)
                    .eq("canonical_id", canonical_id)
                    .single()
                    .execute()
                )
                if canonical_response.data:
                    display_name = canonical_response.data.get("display_name")
            except Exception:
                pass
        
        # Transform to legacy format for backward compatibility
        return {
            "n8n_workflow_id": n8n_workflow_id,
            "name": workflow_data.get("name") or display_name or "Unknown",
            "workflow_data": workflow_data,
            "canonical_id": canonical_id,
            "active": workflow_data.get("active", False),
            "tags": workflow_data.get("tags", []),
            "created_at": workflow_data.get("createdAt") or mapping.get("linked_at"),
            "updated_at": workflow_data.get("updatedAt") or mapping.get("last_env_sync_at"),
            "is_deleted": False,
            "is_archived": False
        }

    async def upsert_workflow(self, tenant_id: str, environment_id: str, workflow_data: Dict[str, Any], analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Insert or update a workflow in the cache"""
        from datetime import datetime
        import json

        # Transform tags from objects to strings (N8N returns tag objects with id and name)
        tags = workflow_data.get("tags", [])
        tag_strings = []
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, dict):
                    # Tag is already a dict object
                    tag_strings.append(tag.get("name", ""))
                elif isinstance(tag, str):
                    # Tag might be a JSON string, try to parse it
                    try:
                        tag_obj = json.loads(tag)
                        if isinstance(tag_obj, dict):
                            tag_strings.append(tag_obj.get("name", ""))
                        else:
                            tag_strings.append(tag)
                    except (json.JSONDecodeError, TypeError):
                        # If not JSON, treat as plain string
                        tag_strings.append(tag)

        # Extract fields from N8N workflow data
        workflow_record = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "n8n_workflow_id": workflow_data.get("id"),
            "name": workflow_data.get("name"),
            "active": workflow_data.get("active", False),
            "workflow_data": workflow_data,  # Store complete workflow JSON
            "tags": tag_strings,  # Store tag names only
            "created_at": workflow_data.get("createdAt"),
            "updated_at": workflow_data.get("updatedAt"),
            "last_synced_at": datetime.utcnow().isoformat(),
            "is_deleted": False
        }
        
        # Add analysis if provided
        if analysis is not None:
            workflow_record["analysis"] = analysis

        response = self.client.table("workflows").upsert(workflow_record, on_conflict="tenant_id,environment_id,n8n_workflow_id").execute()
        return response.data[0] if response.data else None

    async def update_workflow_sync_status(
        self,
        tenant_id: str,
        environment_id: str,
        n8n_workflow_id: str,
        sync_status: str
    ) -> bool:
        """
        DEPRECATED: Sync status is managed automatically by canonical env sync.
        This method is kept for backward compatibility but does nothing.
        """
        # Sync status is now managed by canonical env sync service
        # The last_env_sync_at timestamp in workflow_env_map serves as sync status
        logger.debug(f"update_workflow_sync_status called (deprecated) for workflow {n8n_workflow_id}")
        return True

    async def sync_workflows_from_n8n(self, tenant_id: str, environment_id: str, n8n_workflows: List[Dict[str, Any]], workflows_with_analysis: Optional[Dict[str, Dict[str, Any]]] = None, provider: str = "n8n") -> List[Dict[str, Any]]:
        """Sync workflows from N8N API to database cache (batch operation)"""
        from datetime import datetime

        # Get current workflow IDs from N8N
        n8n_workflow_ids = {workflow.get("id") for workflow in n8n_workflows}

        # Mark workflows as deleted if they no longer exist in N8N
        existing_workflows = await self.get_workflows(tenant_id, environment_id)
        for existing in existing_workflows:
            if existing["n8n_workflow_id"] not in n8n_workflow_ids:
                self.client.table("workflows").update({
                    "is_deleted": True,
                    "last_synced_at": datetime.utcnow().isoformat()
                }).eq("id", existing["id"]).execute()

        # Upsert all workflows from N8N
        results = []
        for workflow_data in n8n_workflows:
            workflow_id = workflow_data.get("id")
            analysis = None
            if workflows_with_analysis and workflow_id in workflows_with_analysis:
                analysis = workflows_with_analysis[workflow_id]
            
            result = await self.upsert_workflow(tenant_id, environment_id, workflow_data, analysis=analysis)
            if result:
                results.append(result)

        # Refresh dependency index
        try:
            await self.refresh_workflow_dependencies_for_env(tenant_id, environment_id, provider)
        except Exception:
            # Best-effort; do not fail sync
            pass

        return results

    async def delete_workflow_from_cache(self, tenant_id: str, environment_id: str, n8n_workflow_id: str) -> bool:
        """
        DEPRECATED: Use canonical workflow system instead.
        Mark workflow mapping as deleted in canonical system.
        """
        try:
            # Find mapping by n8n_workflow_id and mark as deleted
            response = (
                self.client.table("workflow_env_map")
                .update({
                    "status": "deleted",
                    "n8n_workflow_id": None  # Clear n8n_workflow_id since workflow is deleted
                })
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", n8n_workflow_id)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            logger.warning(f"Failed to delete workflow from cache: {str(e)}")
            return False

    async def archive_workflow(
        self,
        tenant_id: str,
        environment_id: str,
        workflow_id: str,
        archived_by: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Use canonical workflow system instead.
        Mark workflow mapping as ignored (archived) in canonical system.
        
        This hides the workflow from the default list but does NOT remove it from n8n.

        Args:
            tenant_id: The tenant ID
            environment_id: The environment ID
            workflow_id: The N8N workflow ID
            archived_by: User ID of who archived the workflow

        Returns:
            The updated workflow mapping or None if not found
        """
        try:
            # Find mapping and mark as ignored (equivalent to archived)
            response = (
                self.client.table("workflow_env_map")
                .update({
                    "status": "ignored"
                })
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", workflow_id)
                .execute()
            )
            
            if response.data:
                mapping = response.data[0]
                # Get workflow data for backward compatibility
                workflow_data = mapping.get("workflow_data") or {}
                return {
                    "n8n_workflow_id": workflow_id,
                    "name": workflow_data.get("name") or "Unknown",
                    "workflow_data": workflow_data
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to archive workflow: {str(e)}")
            return None

    async def unarchive_workflow(
        self,
        tenant_id: str,
        environment_id: str,
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Use canonical workflow system instead.
        Restore an archived workflow by marking mapping as linked.

        Args:
            tenant_id: The tenant ID
            environment_id: The environment ID
            workflow_id: The N8N workflow ID

        Returns:
            The updated workflow mapping or None if not found
        """
        try:
            # Find mapping and mark as linked (unarchive)
            response = (
                self.client.table("workflow_env_map")
                .update({
                    "status": "linked"
                })
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", workflow_id)
                .execute()
            )
            
            if response.data:
                mapping = response.data[0]
                # Get workflow data for backward compatibility
                workflow_data = mapping.get("workflow_data") or {}
                return {
                    "n8n_workflow_id": workflow_id,
                    "name": workflow_data.get("name") or "Unknown",
                    "workflow_data": workflow_data
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to unarchive workflow: {str(e)}")
            return None

    async def update_workflow_in_cache(self, tenant_id: str, environment_id: str, n8n_workflow_id: str, workflow_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Use canonical workflow system instead.
        Update workflow mapping with new workflow data in canonical system.
        """
        try:
            # Find mapping by n8n_workflow_id
            mapping_response = (
                self.client.table("workflow_env_map")
                .select("canonical_id")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", n8n_workflow_id)
                .single()
                .execute()
            )
            
            if not mapping_response.data:
                return None
            
            canonical_id = mapping_response.data.get("canonical_id")
            
            # Update workflow_data in mapping
            from app.services.canonical_workflow_service import compute_workflow_hash
            content_hash = compute_workflow_hash(workflow_data)
            
            update_response = (
                self.client.table("workflow_env_map")
                .update({
                    "workflow_data": workflow_data,
                    "env_content_hash": content_hash,
                    "last_env_sync_at": datetime.utcnow().isoformat()
                })
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("canonical_id", canonical_id)
                .execute()
            )
            
            if update_response.data:
                mapping = update_response.data[0]
                return {
                    "n8n_workflow_id": n8n_workflow_id,
                    "name": workflow_data.get("name") or "Unknown",
                    "workflow_data": workflow_data
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to update workflow in cache: {str(e)}")
            return None

    async def refresh_workflow_dependencies_for_env(
        self,
        tenant_id: str,
        environment_id: str,
        provider: str,
    ) -> None:
        """
        DEPRECATED: Refresh workflow credential dependencies for all workflows in an environment.
        Call this after sync workflows to keep dependency index fresh.
        Uses canonical system.
        """
        from app.services.adapters.n8n_adapter import N8NProviderAdapter

        # Use canonical system to get workflows
        workflows = await self.get_workflows_from_canonical(
            tenant_id=tenant_id,
            environment_id=environment_id,
            include_deleted=False,
            include_ignored=False
        )
        for wf in workflows:
            wf_data = wf.get("workflow_data") or {}
            if not wf_data:
                # Try to get from workflow_data field in mapping
                continue
            logical_keys = N8NProviderAdapter.extract_logical_credentials(wf_data)
            await self.upsert_workflow_dependencies(
                tenant_id=tenant_id,
                workflow_id=str(wf.get("id") or wf.get("n8n_workflow_id")),
                provider=provider,
                logical_credential_ids=logical_keys,
            )

    # Execution cache operations
    async def upsert_execution(self, tenant_id: str, environment_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update an execution in the cache"""
        from datetime import datetime

        # Calculate execution time as milliseconds difference between startedAt and finishedAt
        execution_time = None
        started_at = execution_data.get("startedAt")
        finished_at = execution_data.get("stoppedAt")

        if started_at and finished_at:
            try:
                # Parse ISO format datetime strings
                start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                finish_dt = datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
                # Calculate difference in milliseconds
                execution_time = int((finish_dt - start_dt).total_seconds() * 1000)
            except (ValueError, AttributeError):
                # If parsing fails, fall back to the original value if available
                execution_time = execution_data.get("executionTime")

        # Extract fields from N8N execution data
        execution_record = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "execution_id": execution_data.get("id"),
            "workflow_id": execution_data.get("workflowId"),
            "workflow_name": execution_data.get("workflowData", {}).get("name") if execution_data.get("workflowData") else None,
            "status": execution_data.get("status", "unknown"),
            "mode": execution_data.get("mode"),
            "started_at": started_at,
            "finished_at": finished_at,
            "execution_time": execution_time,
            "data": execution_data,  # Store complete execution JSON
            "last_synced_at": datetime.utcnow().isoformat()
        }

        response = self.client.table("executions").upsert(execution_record, on_conflict="tenant_id,environment_id,execution_id").execute()
        return response.data[0] if response.data else None

    async def sync_executions_from_n8n(self, tenant_id: str, environment_id: str, n8n_executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sync executions from N8N API to database cache"""
        results = []
        for execution_data in n8n_executions:
            result = await self.upsert_execution(tenant_id, environment_id, execution_data)
            if result:
                results.append(result)
        return results

    # Credential cache operations
    async def get_credentials(self, tenant_id: str, environment_id: str) -> List[Dict[str, Any]]:
        """Get all cached credentials for a tenant and environment"""
        response = self.client.table("credentials").select("*").eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("is_deleted", False).order("name").execute()
        return response.data

    async def upsert_credential(self, tenant_id: str, environment_id: str, credential_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a credential in the cache"""
        from datetime import datetime
        import json

        # Extract fields from credential data (either from N8N API or extracted from workflows)
        # Generate a unique key for credentials extracted from workflows
        cred_id = credential_data.get("id")
        cred_type = credential_data.get("type", "")
        cred_name = credential_data.get("name", "")

        # If no ID provided, generate one from type:name
        if not cred_id or ":" in str(cred_id):
            cred_id = f"{cred_type}:{cred_name}"

        # Store used_by_workflows in credential_data since table might not have the column
        credential_data_with_workflows = {
            **credential_data,
            "used_by_workflows": credential_data.get("used_by_workflows", [])
        }

        credential_record = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "n8n_credential_id": cred_id,
            "name": cred_name,
            "type": cred_type,
            "credential_data": credential_data_with_workflows,  # Store complete credential JSON including used_by_workflows
            "created_at": credential_data.get("createdAt"),
            "updated_at": credential_data.get("updatedAt"),
            "last_synced_at": datetime.utcnow().isoformat(),
            "is_deleted": False
        }

        response = self.client.table("credentials").upsert(credential_record, on_conflict="tenant_id,environment_id,n8n_credential_id").execute()
        return response.data[0] if response.data else None

    async def sync_credentials_from_n8n(self, tenant_id: str, environment_id: str, n8n_credentials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sync credentials extracted from N8N workflows to database cache"""
        from datetime import datetime

        # Build set of credential keys (type:name) from incoming data
        n8n_credential_keys = set()
        for credential in n8n_credentials:
            cred_id = credential.get("id")
            cred_type = credential.get("type", "")
            cred_name = credential.get("name", "")
            # Use the same key format as upsert_credential
            if not cred_id or ":" in str(cred_id):
                key = f"{cred_type}:{cred_name}"
            else:
                key = cred_id
            n8n_credential_keys.add(key)

        # Mark credentials as deleted if they no longer exist in N8N workflows
        existing_credentials = await self.get_credentials(tenant_id, environment_id)
        for existing in existing_credentials:
            if existing["n8n_credential_id"] not in n8n_credential_keys:
                self.client.table("credentials").update({
                    "is_deleted": True,
                    "last_synced_at": datetime.utcnow().isoformat()
                }).eq("id", existing["id"]).execute()

        # Upsert all credentials from N8N workflows
        results = []
        for credential_data in n8n_credentials:
            result = await self.upsert_credential(tenant_id, environment_id, credential_data)
            if result:
                results.append(result)

        return results

    # N8N User cache operations
    async def get_n8n_users(self, tenant_id: str, environment_id: str) -> List[Dict[str, Any]]:
        """Get all cached N8N users for a tenant and environment"""
        response = self.client.table("n8n_users").select("*").eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("is_deleted", False).order("email").execute()
        return response.data

    async def upsert_n8n_user(self, tenant_id: str, environment_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update an N8N user in the cache"""
        from datetime import datetime

        # Extract fields from N8N user data
        user_record = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "n8n_user_id": user_data.get("id"),
            "email": user_data.get("email"),
            "first_name": user_data.get("firstName"),
            "last_name": user_data.get("lastName"),
            "is_pending": user_data.get("isPending", False),
            "role": user_data.get("role") or user_data.get("globalRole", {}).get("name"),
            "settings": user_data.get("settings"),
            "user_data": user_data,  # Store complete user JSON
            "created_at": user_data.get("createdAt"),
            "updated_at": user_data.get("updatedAt"),
            "last_synced_at": datetime.utcnow().isoformat(),
            "is_deleted": False
        }

        response = self.client.table("n8n_users").upsert(user_record, on_conflict="tenant_id,environment_id,n8n_user_id").execute()
        return response.data[0] if response.data else None

    async def sync_n8n_users_from_n8n(self, tenant_id: str, environment_id: str, n8n_users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sync N8N users from N8N API to database cache"""
        from datetime import datetime

        # Get current user IDs from N8N
        n8n_user_ids = {user.get("id") for user in n8n_users}

        # Mark users as deleted if they no longer exist in N8N
        existing_users = await self.get_n8n_users(tenant_id, environment_id)
        for existing in existing_users:
            if existing["n8n_user_id"] not in n8n_user_ids:
                self.client.table("n8n_users").update({
                    "is_deleted": True,
                    "last_synced_at": datetime.utcnow().isoformat()
                }).eq("id", existing["id"]).execute()

        # Upsert all users from N8N
        results = []
        for user_data in n8n_users:
            result = await self.upsert_n8n_user(tenant_id, environment_id, user_data)
            if result:
                results.append(result)

        return results

    # Pipeline operations
    async def get_pipelines(self, tenant_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """
        Get all pipelines for a tenant.
        
        Args:
            tenant_id: Tenant ID
            include_inactive: If True (default), returns all pipelines. If False, filters out inactive pipelines.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        query = self.client.table("pipelines").select("*").eq("tenant_id", tenant_id)
        
        logger.debug(f"get_pipelines: tenant_id={tenant_id}, include_inactive={include_inactive} (type: {type(include_inactive).__name__})")
        
        if not include_inactive:
            query = query.eq("is_active", True)
            logger.debug("Applied filter: is_active = True")
        else:
            logger.debug("No filter applied - returning all pipelines")
        
        response = query.order("created_at", desc=True).execute()
        result_count = len(response.data) if response.data else 0
        logger.info(f"Database query returned {result_count} pipelines (include_inactive={include_inactive})")
        
        # Debug: log what we're actually getting
        if response.data:
            active_in_result = sum(1 for p in response.data if p.get("is_active", True))
            inactive_in_result = sum(1 for p in response.data if not p.get("is_active", True))
            logger.info(f"Result breakdown: {active_in_result} active, {inactive_in_result} inactive")
        
        return response.data

    async def get_pipeline(self, pipeline_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific pipeline"""
        response = self.client.table("pipelines").select("*").eq("id", pipeline_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def create_pipeline(self, pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new pipeline"""
        response = self.client.table("pipelines").insert(pipeline_data).execute()
        return response.data[0]

    async def update_pipeline(self, pipeline_id: str, tenant_id: str, pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a pipeline"""
        from datetime import datetime
        pipeline_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("pipelines").update(pipeline_data).eq("id", pipeline_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_pipeline(self, pipeline_id: str, tenant_id: str) -> bool:
        """Delete a pipeline (hard delete)"""
        response = self.client.table("pipelines").delete().eq("id", pipeline_id).eq("tenant_id", tenant_id).execute()
        return True

    # Promotion operations
    async def create_promotion(self, promotion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a promotion record"""
        response = self.client.table("promotions").insert(promotion_data).execute()
        return response.data[0]

    async def get_promotion(self, promotion_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific promotion"""
        response = self.client.table("promotions").select("*").eq("id", promotion_id).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def get_promotions(self, tenant_id: str, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get promotions for a tenant"""
        query = self.client.table("promotions").select("*").eq("tenant_id", tenant_id)
        if status:
            query = query.eq("status", status)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data

    async def update_promotion(self, promotion_id: str, tenant_id: str, promotion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a promotion"""
        from datetime import datetime
        promotion_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("promotions").update(promotion_data).eq("id", promotion_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    # Health check operations
    async def create_health_check(self, health_check_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a health check record"""
        response = self.client.table("health_checks").insert(health_check_data).execute()
        return response.data[0] if response.data else None

    async def get_recent_health_checks(
        self,
        tenant_id: str,
        environment_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent health checks for an environment"""
        response = self.client.table("health_checks").select("*").eq(
            "tenant_id", tenant_id
        ).eq(
            "environment_id", environment_id
        ).order("checked_at", desc=True).limit(limit).execute()
        return response.data

    async def get_latest_health_check(
        self,
        tenant_id: str,
        environment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent health check for an environment"""
        response = self.client.table("health_checks").select("*").eq(
            "tenant_id", tenant_id
        ).eq(
            "environment_id", environment_id
        ).order("checked_at", desc=True).limit(1).execute()
        return response.data[0] if response.data else None

    async def get_uptime_stats(
        self,
        tenant_id: str,
        environment_id: str,
        since: str
    ) -> Dict[str, Any]:
        """Calculate uptime stats for an environment since a given time"""
        response = self.client.table("health_checks").select("status").eq(
            "tenant_id", tenant_id
        ).eq(
            "environment_id", environment_id
        ).gte("checked_at", since).execute()

        checks = response.data
        total = len(checks)
        healthy = sum(1 for c in checks if c.get("status") == "healthy")

        return {
            "total_checks": total,
            "healthy_checks": healthy,
            "uptime_percent": (healthy / total * 100) if total > 0 else 100.0
        }

    # Notification channel operations
    async def create_notification_channel(self, channel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a notification channel"""
        response = self.client.table("notification_channels").insert(channel_data).execute()
        return response.data[0] if response.data else None

    async def get_notification_channels(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all notification channels for a tenant"""
        response = self.client.table("notification_channels").select("*").eq(
            "tenant_id", tenant_id
        ).order("created_at", desc=True).execute()
        return response.data

    async def get_notification_channel(
        self,
        channel_id: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific notification channel"""
        response = self.client.table("notification_channels").select("*").eq(
            "id", channel_id
        ).eq("tenant_id", tenant_id).single().execute()
        return response.data

    async def update_notification_channel(
        self,
        channel_id: str,
        tenant_id: str,
        channel_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a notification channel"""
        from datetime import datetime
        channel_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("notification_channels").update(channel_data).eq(
            "id", channel_id
        ).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_notification_channel(self, channel_id: str, tenant_id: str) -> bool:
        """Delete a notification channel"""
        self.client.table("notification_channels").delete().eq(
            "id", channel_id
        ).eq("tenant_id", tenant_id).execute()
        return True

    # Notification rule operations
    async def create_notification_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a notification rule"""
        response = self.client.table("notification_rules").insert(rule_data).execute()
        return response.data[0] if response.data else None

    async def get_notification_rules(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all notification rules for a tenant"""
        response = self.client.table("notification_rules").select("*").eq(
            "tenant_id", tenant_id
        ).order("event_type").execute()
        return response.data

    async def get_notification_rule_by_event(
        self,
        tenant_id: str,
        event_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get a notification rule by event type"""
        response = self.client.table("notification_rules").select("*").eq(
            "tenant_id", tenant_id
        ).eq("event_type", event_type).execute()
        return response.data[0] if response.data else None

    async def update_notification_rule(
        self,
        rule_id: str,
        tenant_id: str,
        rule_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a notification rule"""
        from datetime import datetime
        rule_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("notification_rules").update(rule_data).eq(
            "id", rule_id
        ).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_notification_rule(self, rule_id: str, tenant_id: str) -> bool:
        """Delete a notification rule"""
        self.client.table("notification_rules").delete().eq(
            "id", rule_id
        ).eq("tenant_id", tenant_id).execute()
        return True

    # Event operations
    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an event record"""
        response = self.client.table("events").insert(event_data).execute()
        return response.data[0] if response.data else None

    async def get_events(
        self,
        tenant_id: str,
        limit: int = 50,
        event_type: Optional[str] = None,
        environment_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent events for a tenant"""
        query = self.client.table("events").select("*").eq("tenant_id", tenant_id)
        if event_type:
            query = query.eq("event_type", event_type)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        response = query.order("timestamp", desc=True).limit(limit).execute()
        return response.data

    async def update_event_notification_status(
        self,
        event_id: str,
        status: str,
        channels: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Update event notification status"""
        response = self.client.table("events").update({
            "notification_status": status,
            "channels_notified": channels
        }).eq("id", event_id).execute()
        return response.data[0] if response.data else None

    # Execution stats for observability
    async def get_execution_stats(
        self,
        tenant_id: str,
        since: str,
        until: str,
        environment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get execution statistics for a time range"""
        import logging
        logger = logging.getLogger(__name__)
        
        query = self.client.table("executions").select("status, execution_time").eq(
            "tenant_id", tenant_id
        ).gte("started_at", since).lt("started_at", until)

        if environment_id:
            query = query.eq("environment_id", environment_id)
            logger.info(f"get_execution_stats: Filtering by environment_id={environment_id}")

        logger.info(f"get_execution_stats: Query params - tenant_id={tenant_id}, since={since}, until={until}, environment_id={environment_id}")
        response = query.execute()
        executions = response.data
        logger.info(f"get_execution_stats: Found {len(executions)} executions")

        total = len(executions)
        success = sum(1 for e in executions if e.get("status") == "success")
        failed = sum(1 for e in executions if e.get("status") == "error")

        # Calculate average duration (filter out None values)
        durations = [e.get("execution_time") for e in executions if e.get("execution_time") is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Calculate p95 duration
        p95_duration = None
        if durations:
            sorted_durations = sorted(durations)
            p95_index = int(len(sorted_durations) * 0.95)
            p95_duration = sorted_durations[min(p95_index, len(sorted_durations) - 1)]

        return {
            "total_executions": total,
            "success_count": success,
            "failure_count": failed,
            "success_rate": (success / total * 100) if total > 0 else 100.0,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration
        }

    async def get_workflow_execution_stats(
        self,
        tenant_id: str,
        since: str,
        until: str,
        limit: int = 10,
        sort_by: str = "executions",
        environment_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get per-workflow execution statistics"""
        query = self.client.table("executions").select(
            "workflow_id, workflow_name, status, execution_time"
        ).eq("tenant_id", tenant_id).gte("started_at", since).lt("started_at", until)

        if environment_id:
            query = query.eq("environment_id", environment_id)

        response = query.execute()
        executions = response.data

        # Group by workflow
        workflow_stats = {}
        for e in executions:
            wf_id = e.get("workflow_id")
            if not wf_id:
                continue

            if wf_id not in workflow_stats:
                workflow_stats[wf_id] = {
                    "workflow_id": wf_id,
                    "workflow_name": e.get("workflow_name"),  # May be None, we'll look it up later
                    "execution_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "durations": []
                }

            stats = workflow_stats[wf_id]
            stats["execution_count"] += 1
            if e.get("status") == "success":
                stats["success_count"] += 1
            elif e.get("status") == "error":
                stats["failure_count"] += 1

            if e.get("execution_time") is not None:
                stats["durations"].append(e["execution_time"])

        # Look up workflow names from canonical system for any missing names
        missing_name_ids = [wf_id for wf_id, stats in workflow_stats.items() if not stats["workflow_name"]]
        if missing_name_ids:
            try:
                # Build query to get workflow names from workflow_env_map
                query = (
                    self.client.table("workflow_env_map")
                    .select("n8n_workflow_id, workflow_data, canonical_workflows(display_name)")
                    .eq("tenant_id", tenant_id)
                    .in_("n8n_workflow_id", missing_name_ids)
                )
                
                if environment_id:
                    query = query.eq("environment_id", environment_id)

                mappings_response = query.execute()
                
                # Get canonical IDs to fetch display names separately (Supabase doesn't support nested joins)
                canonical_ids = [m.get("canonical_id") for m in (mappings_response.data or []) if m.get("canonical_id")]
                canonical_map = {}
                if canonical_ids:
                    canonical_response = (
                        self.client.table("canonical_workflows")
                        .select("canonical_id, display_name")
                        .eq("tenant_id", tenant_id)
                        .in_("canonical_id", canonical_ids)
                        .execute()
                    )
                    for canonical in (canonical_response.data or []):
                        canonical_map[canonical.get("canonical_id")] = canonical
                
                # Build workflow name map
                workflow_name_map = {}
                for mapping in (mappings_response.data or []):
                    n8n_id = mapping.get("n8n_workflow_id")
                    if n8n_id:
                        workflow_data = mapping.get("workflow_data") or {}
                        canonical_id = mapping.get("canonical_id")
                        canonical = canonical_map.get(canonical_id, {}) if canonical_id else {}
                        workflow_name = (
                            workflow_data.get("name") or 
                            canonical.get("display_name") or 
                            n8n_id  # Fallback to ID
                        )
                        workflow_name_map[n8n_id] = workflow_name

                # Update workflow_stats with looked-up names
                for wf_id in missing_name_ids:
                    if wf_id in workflow_name_map:
                        workflow_stats[wf_id]["workflow_name"] = workflow_name_map[wf_id]
                    else:
                        workflow_stats[wf_id]["workflow_name"] = wf_id  # Fallback to ID
            except Exception as e:
                logger.warning(f"Failed to look up workflow names: {e}")
                # Fallback to using IDs
                for wf_id in missing_name_ids:
                    workflow_stats[wf_id]["workflow_name"] = wf_id

        # Calculate final stats and sort
        result = []
        for wf_id, stats in workflow_stats.items():
            avg_duration = sum(stats["durations"]) / len(stats["durations"]) if stats["durations"] else 0

            # Calculate p95
            p95_duration = None
            if stats["durations"]:
                sorted_durations = sorted(stats["durations"])
                p95_index = int(len(sorted_durations) * 0.95)
                p95_duration = sorted_durations[min(p95_index, len(sorted_durations) - 1)]

            result.append({
                "workflow_id": stats["workflow_id"],
                "workflow_name": stats["workflow_name"],
                "execution_count": stats["execution_count"],
                "success_count": stats["success_count"],
                "failure_count": stats["failure_count"],
                "error_rate": (stats["failure_count"] / stats["execution_count"] * 100) if stats["execution_count"] > 0 else 0,
                "avg_duration_ms": avg_duration,
                "p95_duration_ms": p95_duration
            })

        # Sort based on sort_by parameter
        if sort_by == "failures":
            result.sort(key=lambda x: x["failure_count"], reverse=True)
        else:  # default: executions
            result.sort(key=lambda x: x["execution_count"], reverse=True)

        return result[:limit]

    # Deployment stats for observability
    async def get_deployment_stats(
        self,
        tenant_id: str,
        since: str
    ) -> Dict[str, Any]:
        """Get deployment statistics since a given time"""
        response = self.client.table("deployments").select("status").eq(
            "tenant_id", tenant_id
        ).gte("started_at", since).execute()

        deployments = response.data
        total = len(deployments)
        success = sum(1 for d in deployments if d.get("status") == "success")
        failed = sum(1 for d in deployments if d.get("status") == "failed")
        blocked = sum(1 for d in deployments if d.get("status") == "canceled")

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "blocked": blocked
        }

    async def get_recent_deployments_with_details(
        self,
        tenant_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent deployments with environment names"""
        response = self.client.table("deployments").select("*").eq(
            "tenant_id", tenant_id
        ).order("started_at", desc=True).limit(limit).execute()

        deployments = response.data

        # Get environment names
        env_ids = set()
        for d in deployments:
            if d.get("source_environment_id"):
                env_ids.add(d["source_environment_id"])
            if d.get("target_environment_id"):
                env_ids.add(d["target_environment_id"])

        env_names = {}
        if env_ids:
            env_response = self.client.table("environments").select("id, n8n_name").in_(
                "id", list(env_ids)
            ).execute()
            env_names = {e["id"]: e["n8n_name"] for e in env_response.data}

        # Get pipeline names
        pipeline_ids = [d.get("pipeline_id") for d in deployments if d.get("pipeline_id")]
        pipeline_names = {}
        if pipeline_ids:
            pipeline_response = self.client.table("pipelines").select("id, name").in_(
                "id", pipeline_ids
            ).execute()
            pipeline_names = {p["id"]: p["name"] for p in pipeline_response.data}

        # Enrich deployments
        for d in deployments:
            d["source_environment_name"] = env_names.get(d.get("source_environment_id"), "Unknown")
            d["target_environment_name"] = env_names.get(d.get("target_environment_id"), "Unknown")
            d["pipeline_name"] = pipeline_names.get(d.get("pipeline_id"))

        return deployments

    # Snapshot stats for observability
    async def get_snapshot_stats(
        self,
        tenant_id: str,
        since: str
    ) -> Dict[str, Any]:
        """Get snapshot statistics since a given time"""
        response = self.client.table("snapshots").select("type").eq(
            "tenant_id", tenant_id
        ).gte("created_at", since).execute()

        snapshots = response.data
        created = len(snapshots)

        # For restored count, we'd need to track restore events
        # For now, just return created count
        return {
            "created": created,
            "restored": 0  # TODO: track restore events
        }


    # ---------- Logical Credentials, Mappings, Dependencies ----------

    async def create_logical_credential(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("logical_credentials").insert(data).execute()
        return response.data[0]

    async def list_logical_credentials(self, tenant_id: str) -> List[Dict[str, Any]]:
        response = (
            self.client.table("logical_credentials")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("name")
            .execute()
        )
        return response.data or []

    async def find_logical_credential_by_name(self, tenant_id: str, name: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("logical_credentials")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("name", name)
            .single()
            .execute()
        )
        return response.data

    async def get_logical_credential(self, tenant_id: str, logical_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("logical_credentials")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", logical_id)
            .single()
            .execute()
        )
        return response.data

    async def update_logical_credential(self, tenant_id: str, logical_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("logical_credentials")
            .update(data)
            .eq("tenant_id", tenant_id)
            .eq("id", logical_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def delete_logical_credential(self, tenant_id: str, logical_id: str) -> bool:
        self.client.table("logical_credentials").delete().eq("tenant_id", tenant_id).eq("id", logical_id).execute()
        return True

    async def create_credential_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("credential_mappings").insert(data).execute()
        return response.data[0]

    async def list_credential_mappings(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = self.client.table("credential_mappings").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if provider:
            query = query.eq("provider", provider)
        response = query.order("created_at", desc=True).execute()
        return response.data or []

    async def get_credential_mapping(self, tenant_id: str, mapping_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("credential_mappings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", mapping_id)
            .single()
            .execute()
        )
        return response.data

    async def update_credential_mapping(self, tenant_id: str, mapping_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("credential_mappings")
            .update(data)
            .eq("tenant_id", tenant_id)
            .eq("id", mapping_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def delete_credential_mapping(self, tenant_id: str, mapping_id: str) -> bool:
        self.client.table("credential_mappings").delete().eq("tenant_id", tenant_id).eq("id", mapping_id).execute()
        return True

    async def get_mapping_for_logical(
        self,
        tenant_id: str,
        environment_id: str,
        provider: str,
        logical_credential_id: str,
    ) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("credential_mappings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", environment_id)
            .eq("provider", provider)
            .eq("logical_credential_id", logical_credential_id)
            .single()
            .execute()
        )
        return response.data

    async def upsert_workflow_dependencies(
        self,
        tenant_id: str,
        workflow_id: str,
        provider: str,
        logical_credential_ids: List[str],
    ) -> Dict[str, Any]:
        record = {
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "provider": provider,
            "logical_credential_ids": logical_credential_ids,
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = self.client.table("workflow_credential_dependencies").upsert(
            record,
            on_conflict="workflow_id,provider",
        ).execute()
        return response.data[0] if response.data else record

    async def get_workflow_dependencies(self, workflow_id: str, provider: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("workflow_credential_dependencies")
            .select("*")
            .eq("workflow_id", workflow_id)
            .eq("provider", provider)
            .single()
            .execute()
        )
        return response.data

    # ---------- Support Config ----------

    async def get_support_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get support configuration for a tenant"""
        try:
            response = (
                self.client.table("support_config")
                .select("*")
                .eq("tenant_id", tenant_id)
                .single()
                .execute()
            )
            return response.data
        except Exception:
            return None

    async def upsert_support_config(self, tenant_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update support configuration for a tenant"""
        data["tenant_id"] = tenant_id
        response = self.client.table("support_config").upsert(
            data,
            on_conflict="tenant_id"
        ).execute()
        return response.data[0] if response.data else data

    # Background job operations
    async def create_background_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a background job record"""
        response = self.client.table("background_jobs").insert(job_data).execute()
        return response.data[0] if response.data else None

    async def update_background_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a background job record"""
        response = self.client.table("background_jobs").update(job_data).eq("id", job_id).execute()
        return response.data[0] if response.data else None

    async def get_background_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a background job by ID"""
        try:
            response = self.client.table("background_jobs").select("*").eq("id", job_id).single().execute()
            return response.data
        except Exception:
            return None

    async def get_background_jobs_by_resource(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get background jobs for a specific resource"""
        query = self.client.table("background_jobs").select("*").eq("resource_type", resource_type).eq("resource_id", resource_id)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data


    # ---------- Provider Operations ----------

    async def get_providers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all providers"""
        query = self.client.table("providers").select("*")
        if active_only:
            query = query.eq("is_active", True)
        response = query.order("name").execute()
        return response.data or []

    async def get_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific provider by ID"""
        try:
            response = self.client.table("providers").select("*").eq("id", provider_id).single().execute()
            return response.data
        except Exception:
            return None

    async def get_provider_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a provider by name"""
        try:
            response = self.client.table("providers").select("*").eq("name", name).single().execute()
            return response.data
        except Exception:
            return None

    async def get_provider_plans(self, provider_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get plans for a specific provider"""
        query = self.client.table("provider_plans").select("*").eq("provider_id", provider_id)
        if active_only:
            query = query.eq("is_active", True)
        response = query.order("sort_order").execute()
        return response.data or []

    async def get_provider_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by ID"""
        try:
            response = self.client.table("provider_plans").select("*").eq("id", plan_id).single().execute()
            return response.data
        except Exception:
            return None

    async def get_providers_with_plans(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all providers with their plans"""
        providers = await self.get_providers(active_only)
        for provider in providers:
            provider["plans"] = await self.get_provider_plans(provider["id"], active_only)
        return providers

    # Tenant Provider Subscription operations
    async def get_tenant_provider_subscriptions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all provider subscriptions for a tenant"""
        response = self.client.table("tenant_provider_subscriptions").select("*").eq("tenant_id", tenant_id).execute()
        subscriptions = response.data or []

        # Enrich with provider and plan details
        for sub in subscriptions:
            sub["provider"] = await self.get_provider(sub["provider_id"])
            sub["plan"] = await self.get_provider_plan(sub["plan_id"]) if sub.get("plan_id") else None

        return subscriptions

    async def get_tenant_provider_subscription(
        self,
        tenant_id: str,
        provider_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific provider subscription for a tenant"""
        try:
            response = (
                self.client.table("tenant_provider_subscriptions")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("provider_id", provider_id)
                .single()
                .execute()
            )
            sub = response.data
            if sub:
                sub["provider"] = await self.get_provider(sub["provider_id"])
                sub["plan"] = await self.get_provider_plan(sub["plan_id"]) if sub.get("plan_id") else None
            return sub
        except Exception:
            return None

    async def get_tenant_provider_subscription_by_stripe_id(
        self,
        stripe_subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a subscription by its Stripe subscription ID"""
        try:
            response = (
                self.client.table("tenant_provider_subscriptions")
                .select("*")
                .eq("stripe_subscription_id", stripe_subscription_id)
                .single()
                .execute()
            )
            return response.data
        except Exception:
            return None

    async def create_tenant_provider_subscription(
        self,
        subscription_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a provider subscription for a tenant"""
        subscription_data["created_at"] = datetime.utcnow().isoformat()
        subscription_data["updated_at"] = datetime.utcnow().isoformat()
        response = self.client.table("tenant_provider_subscriptions").insert(subscription_data).execute()
        return response.data[0]

    async def update_tenant_provider_subscription(
        self,
        subscription_id: str,
        tenant_id: str,
        subscription_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a provider subscription"""
        subscription_data["updated_at"] = datetime.utcnow().isoformat()
        response = (
            self.client.table("tenant_provider_subscriptions")
            .update(subscription_data)
            .eq("id", subscription_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def update_tenant_provider_subscription_by_provider(
        self,
        tenant_id: str,
        provider_id: str,
        subscription_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a provider subscription by provider ID"""
        subscription_data["updated_at"] = datetime.utcnow().isoformat()
        response = (
            self.client.table("tenant_provider_subscriptions")
            .update(subscription_data)
            .eq("tenant_id", tenant_id)
            .eq("provider_id", provider_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def delete_tenant_provider_subscription(
        self,
        subscription_id: str,
        tenant_id: str
    ) -> bool:
        """Delete a provider subscription"""
        self.client.table("tenant_provider_subscriptions").delete().eq("id", subscription_id).eq("tenant_id", tenant_id).execute()
        return True

    async def get_active_provider_subscriptions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get only active provider subscriptions for a tenant"""
        response = (
            self.client.table("tenant_provider_subscriptions")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("status", "active")
            .execute()
        )
        subscriptions = response.data or []

        # Enrich with provider and plan details
        for sub in subscriptions:
            sub["provider"] = await self.get_provider(sub["provider_id"])
            sub["plan"] = await self.get_provider_plan(sub["plan_id"]) if sub.get("plan_id") else None

        return subscriptions

    # Admin Provider Management
    async def update_provider(self, provider_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a provider"""
        response = (
            self.client.table("providers")
            .update(update_data)
            .eq("id", provider_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_all_provider_plans(self, provider_id: str) -> List[Dict[str, Any]]:
        """Get all plans for a provider (including inactive)"""
        response = (
            self.client.table("provider_plans")
            .select("*")
            .eq("provider_id", provider_id)
            .order("sort_order")
            .execute()
        )
        return response.data or []

    async def create_provider_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new provider plan"""
        plan_data["created_at"] = datetime.utcnow().isoformat()
        response = self.client.table("provider_plans").insert(plan_data).execute()
        return response.data[0]

    async def update_provider_plan(self, plan_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a provider plan"""
        response = (
            self.client.table("provider_plans")
            .update(update_data)
            .eq("id", plan_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def delete_provider_plan(self, plan_id: str) -> bool:
        """Delete a provider plan"""
        self.client.table("provider_plans").delete().eq("id", plan_id).execute()
        return True

    # Canonical Workflow Operations
    
    async def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        response = self.client.table("tenants").select("*").eq("id", tenant_id).single().execute()
        return response.data if response.data else None
    
    async def update_tenant_onboarding(
        self,
        tenant_id: str,
        anchor_environment_id: Optional[str] = None,
        onboarded_at: Optional[datetime] = None,
        onboarding_version: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Update tenant onboarding status"""
        update_data = {}
        if anchor_environment_id is not None:
            update_data["canonical_anchor_environment_id"] = anchor_environment_id
        if onboarded_at is not None:
            update_data["canonical_onboarded_at"] = onboarded_at.isoformat() if isinstance(onboarded_at, datetime) else onboarded_at
        if onboarding_version is not None:
            update_data["canonical_onboarding_version"] = onboarding_version
        
        if not update_data:
            return None
        
        response = self.client.table("tenants").update(update_data).eq("id", tenant_id).execute()
        return response.data[0] if response.data else None
    
    async def get_canonical_workflows(
        self,
        tenant_id: str,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all canonical workflows for a tenant"""
        query = self.client.table("canonical_workflows").select("*").eq("tenant_id", tenant_id)
        if not include_deleted:
            query = query.is_("deleted_at", "null")
        response = query.order("created_at", desc=True).execute()
        return response.data or []
    
    async def get_workflow_mappings(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        canonical_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow environment mappings"""
        query = self.client.table("workflow_env_map").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if canonical_id:
            query = query.eq("canonical_id", canonical_id)
        if status:
            query = query.eq("status", status)
        response = query.execute()
        return response.data or []
    
    async def get_workflows_from_canonical(
        self,
        tenant_id: str,
        environment_id: str,
        include_deleted: bool = False,
        include_ignored: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get workflows for an environment from canonical system.
        
        Returns workflows with full workflow_data from workflow_env_map,
        joined with canonical_workflows for display names.
        
        This replaces the legacy get_workflows() method.
        """
        # Get workflow mappings for this environment
        query = (
            self.client.table("workflow_env_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", environment_id)
        )
        
        # Filter by status
        if not include_deleted:
            query = query.neq("status", "deleted").or_("status.is.null")
        if not include_ignored:
            query = query.neq("status", "ignored").or_("status.is.null")
        
        # Only get workflows that have n8n_workflow_id (exist in n8n)
        query = query.not_.is_("n8n_workflow_id", "null")
        
        response = query.execute()
        mappings = response.data or []
        
        # Get canonical workflows for display names (batch fetch)
        canonical_ids = [m.get("canonical_id") for m in mappings if m.get("canonical_id")]
        canonical_map = {}
        if canonical_ids:
            canonical_response = (
                self.client.table("canonical_workflows")
                .select("*")
                .eq("tenant_id", tenant_id)
                .in_("canonical_id", canonical_ids)
                .execute()
            )
            for canonical in (canonical_response.data or []):
                canonical_map[canonical.get("canonical_id")] = canonical
        
        # Transform to match legacy workflow format for backward compatibility
        workflows = []
        for mapping in mappings:
            workflow_data = mapping.get("workflow_data") or {}
            canonical_id = mapping.get("canonical_id")
            canonical = canonical_map.get(canonical_id, {}) if canonical_id else {}
            
            # Build workflow object matching legacy format
            workflow_obj = {
                "id": mapping.get("n8n_workflow_id"),
                "name": workflow_data.get("name") or canonical.get("display_name") or "Unknown",
                "description": workflow_data.get("description") or "",
                "active": workflow_data.get("active", False),
                "tags": workflow_data.get("tags", []),
                "createdAt": workflow_data.get("createdAt") or mapping.get("linked_at"),
                "updatedAt": workflow_data.get("updatedAt") or mapping.get("last_env_sync_at"),
                "nodes": workflow_data.get("nodes", []),
                "connections": workflow_data.get("connections", {}),
                "settings": workflow_data.get("settings", {}),
                "lastSyncedAt": mapping.get("last_env_sync_at"),
                "syncStatus": "synced" if mapping.get("status") == "linked" else "pending",
                "canonical_id": canonical_id,
                "canonical_display_name": canonical.get("display_name")
            }
            
            workflows.append(workflow_obj)
        
        return workflows
    
    async def get_workflow_diff_states(
        self,
        tenant_id: str,
        source_env_id: Optional[str] = None,
        target_env_id: Optional[str] = None,
        canonical_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow diff states"""
        query = self.client.table("workflow_diff_state").select("*").eq("tenant_id", tenant_id)
        if source_env_id:
            query = query.eq("source_env_id", source_env_id)
        if target_env_id:
            query = query.eq("target_env_id", target_env_id)
        if canonical_id:
            query = query.eq("canonical_id", canonical_id)
        response = query.order("computed_at", desc=True).execute()
        return response.data or []
    
    async def get_workflow_link_suggestions(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow link suggestions"""
        query = self.client.table("workflow_link_suggestions").select("*").eq("tenant_id", tenant_id)
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if status:
            query = query.eq("status", status)
        response = query.order("created_at", desc=True).execute()
        return response.data or []
    
    async def update_workflow_link_suggestion(
        self,
        suggestion_id: str,
        tenant_id: str,
        status: str,
        resolved_by_user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update workflow link suggestion status"""
        update_data = {
            "status": status,
            "resolved_at": datetime.utcnow().isoformat(),
            "resolved_by_user_id": resolved_by_user_id
        }
        response = (
            self.client.table("workflow_link_suggestions")
            .update(update_data)
            .eq("id", suggestion_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return response.data[0] if response.data else None
    
    async def check_onboarding_gate(self, tenant_id: str) -> bool:
        """
        Check if promotions are allowed (onboarding complete).
        
        Returns True if onboarding is complete, False otherwise.
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        # Check if onboarded
        if not tenant.get("canonical_onboarded_at"):
            return False
        
        # Check for untracked workflows in anchor environment
        anchor_env_id = tenant.get("canonical_anchor_environment_id")
        if not anchor_env_id:
            return False
        
        # Check for unresolved link suggestions
        suggestions = await self.get_workflow_link_suggestions(
            tenant_id=tenant_id,
            status="open"
        )
        if suggestions:
            return False
        
        # Additional checks can be added here (e.g., untracked workflows)
        
        return True


# Global instance
db_service = DatabaseService()
