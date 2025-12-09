from supabase import create_client, Client
from app.core.config import settings
from typing import List, Dict, Any, Optional


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
        return response.data

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
        """Update a deployment record"""
        response = self.client.table("deployments").update(deployment_data).eq("id", deployment_id).execute()
        return response.data[0]

    async def get_deployments(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all deployments for a tenant"""
        response = self.client.table("deployments").select("*").eq("tenant_id", tenant_id).order("started_at", desc=True).execute()
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

        # Enrich executions with workflow names from the workflows table
        executions = response.data
        if executions:
            # Group executions by environment to fetch workflows efficiently
            env_workflow_map = {}  # {env_id: {workflow_id: workflow_name}}

            for execution in executions:
                exec_env_id = execution.get("environment_id")
                if exec_env_id and exec_env_id not in env_workflow_map:
                    # Fetch all workflows for this environment
                    workflows_response = self.client.table("workflows").select(
                        "n8n_workflow_id, name"
                    ).eq("tenant_id", tenant_id).eq("environment_id", exec_env_id).eq("is_deleted", False).execute()

                    # Create a mapping of workflow_id to workflow_name for this environment
                    env_workflow_map[exec_env_id] = {wf["n8n_workflow_id"]: wf["name"] for wf in workflows_response.data if wf.get("n8n_workflow_id")}

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

        # Enrich with workflow name from the workflows table
        if execution and execution.get("workflow_id") and execution.get("environment_id"):
            workflow_response = self.client.table("workflows").select(
                "name"
            ).eq("tenant_id", tenant_id).eq("environment_id", execution["environment_id"]).eq("n8n_workflow_id", execution["workflow_id"]).eq("is_deleted", False).execute()

            if workflow_response.data and len(workflow_response.data) > 0:
                execution["workflow_name"] = workflow_response.data[0].get("name")

        return execution

    async def update_execution(self, execution_id: str, tenant_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an execution record"""
        response = self.client.table("executions").update(execution_data).eq("id", execution_id).eq("tenant_id", tenant_id).execute()
        return response.data[0] if response.data else None

    async def delete_execution(self, execution_id: str, tenant_id: str) -> bool:
        """Delete an execution record"""
        self.client.table("executions").delete().eq("id", execution_id).eq("tenant_id", tenant_id).execute()
        return True

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
    async def get_workflows(self, tenant_id: str, environment_id: str) -> List[Dict[str, Any]]:
        """Get all cached workflows for a tenant and environment"""
        response = self.client.table("workflows").select("*").eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("is_deleted", False).order("name").execute()
        return response.data

    async def get_workflow(self, tenant_id: str, environment_id: str, n8n_workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific cached workflow"""
        response = self.client.table("workflows").select("*").eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("n8n_workflow_id", n8n_workflow_id).eq("is_deleted", False).single().execute()
        return response.data if response.data else None

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

    async def sync_workflows_from_n8n(self, tenant_id: str, environment_id: str, n8n_workflows: List[Dict[str, Any]], workflows_with_analysis: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
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

        return results

    async def delete_workflow_from_cache(self, tenant_id: str, environment_id: str, n8n_workflow_id: str) -> bool:
        """Soft delete a workflow from cache"""
        from datetime import datetime

        response = self.client.table("workflows").update({
            "is_deleted": True,
            "last_synced_at": datetime.utcnow().isoformat()
        }).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("n8n_workflow_id", n8n_workflow_id).execute()

        return bool(response.data)

    async def update_workflow_in_cache(self, tenant_id: str, environment_id: str, n8n_workflow_id: str, workflow_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing workflow in cache with new data"""
        return await self.upsert_workflow(tenant_id, environment_id, workflow_data)

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


# Global instance
db_service = DatabaseService()
