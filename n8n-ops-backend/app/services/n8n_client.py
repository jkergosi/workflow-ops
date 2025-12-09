import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings


class N8NClient:
    """Client for interacting with N8N API"""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or settings.N8N_API_URL
        self.api_key = api_key or settings.N8N_API_KEY
        self.headers = {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    async def get_workflows(self) -> List[Dict[str, Any]]:
        """Fetch all workflows from N8N"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get a specific workflow by ID"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows/{workflow_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow in N8N"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/workflows",
                headers=self.headers,
                json=workflow_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing workflow - only sends required fields: name, nodes, connections, settings"""
        import json

        # ONLY include these fields - nothing else! Remove ALL other fields including 'shared'
        cleaned_data = {}

        # Required fields
        if "name" in workflow_data:
            cleaned_data["name"] = workflow_data["name"]
        if "nodes" in workflow_data:
            cleaned_data["nodes"] = workflow_data["nodes"]
        if "connections" in workflow_data:
            cleaned_data["connections"] = workflow_data["connections"]
        if "settings" in workflow_data:
            cleaned_data["settings"] = workflow_data["settings"]

        # DO NOT include 'shared' field - it contains read-only nested objects that n8n rejects

        # Debug: print what we're sending
        print("="*80)
        print("DEBUG N8N CLIENT: Input keys:", list(workflow_data.keys()))
        print("DEBUG N8N CLIENT: Cleaned keys:", list(cleaned_data.keys()))
        print("DEBUG N8N CLIENT: Cleaned payload:")
        print(json.dumps(cleaned_data, indent=2))
        print("="*80)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.base_url}/api/v1/workflows/{workflow_id}",
                    headers=self.headers,
                    json=cleaned_data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"ERROR: n8n returned {e.response.status_code}")
                print(f"ERROR: Response text: {e.response.text}")
                print(f"ERROR: What we sent: {json.dumps(cleaned_data, indent=2)}")
                raise

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/workflows/{workflow_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return True

    async def update_workflow_tags(self, workflow_id: str, tag_ids: List[str]) -> Dict[str, Any]:
        """Update workflow tags"""
        async with httpx.AsyncClient() as client:
            tag_objects = [{"id": tag_id} for tag_id in tag_ids]
            response = await client.put(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/tags",
                headers=self.headers,
                json=tag_objects,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Activate a workflow"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/activate",
                headers=self.headers,
                json={"versionId": "", "name": "", "description": ""},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Deactivate a workflow"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/deactivate",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> bool:
        """Test if the N8N instance is reachable and credentials are valid"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/workflows",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception:
            return False

    async def get_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch executions from N8N"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/executions",
                headers=self.headers,
                params={"limit": limit},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", []) if isinstance(data, dict) else data

    async def get_credentials(self) -> List[Dict[str, Any]]:
        """Extract credentials referenced in workflows.

        Note: N8N's public API does not support GET /credentials to list all credentials.
        Instead, we extract credential references from workflow nodes.
        Each node that uses credentials has a 'credentials' property with the credential name and type.
        """
        credentials_map = {}  # Use dict to dedupe by name+type

        try:
            workflows = await self.get_workflows()

            for workflow in workflows:
                nodes = workflow.get("nodes", [])
                for node in nodes:
                    node_credentials = node.get("credentials", {})
                    for cred_type, cred_info in node_credentials.items():
                        if isinstance(cred_info, dict):
                            cred_id = cred_info.get("id")
                            cred_name = cred_info.get("name", "Unknown")
                        else:
                            # Sometimes it's just the credential name as a string
                            cred_id = None
                            cred_name = str(cred_info) if cred_info else "Unknown"

                        # Create unique key for deduplication
                        key = f"{cred_type}:{cred_name}"
                        if key not in credentials_map:
                            credentials_map[key] = {
                                "id": cred_id or key,  # Use key as fallback ID
                                "name": cred_name,
                                "type": cred_type,
                                "used_by_workflows": []
                            }

                        # Track which workflows use this credential
                        workflow_ref = {
                            "id": workflow.get("id"),
                            "name": workflow.get("name")
                        }
                        if workflow_ref not in credentials_map[key]["used_by_workflows"]:
                            credentials_map[key]["used_by_workflows"].append(workflow_ref)

            return list(credentials_map.values())

        except Exception as e:
            # If we can't get workflows, return empty list
            import logging
            logging.warning(f"Failed to extract credentials from workflows: {str(e)}")
            return []

    async def get_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from N8N instance"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/users",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", []) if isinstance(data, dict) else data
            except httpx.HTTPStatusError as e:
                # If users endpoint returns 401/403, it may not be accessible
                # Return empty list instead of failing
                if e.response.status_code in [401, 403, 404]:
                    return []
                raise

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Fetch all tags from N8N instance"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/tags",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", []) if isinstance(data, dict) else data
            except httpx.HTTPStatusError as e:
                # If tags endpoint is not accessible, return empty list
                if e.response.status_code in [401, 403, 404]:
                    return []
                raise


# Global instance
n8n_client = N8NClient()
