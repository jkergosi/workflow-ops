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
        """Create a new workflow in N8N - only sends required fields"""
        import json
        
        # Clean data - only include fields that N8N API accepts
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
        # Optional: staticData if provided
        if "staticData" in workflow_data and workflow_data["staticData"]:
            cleaned_data["staticData"] = workflow_data["staticData"]
        
        # DO NOT include 'id', 'active', 'shared', 'tags', 'createdAt', 'updatedAt', etc.
        
        # Validate and clean the data before sending
        import json
        try:
            # Test JSON serialization first
            json_str = json.dumps(cleaned_data, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as json_error:
            error_msg = f"Workflow data is not JSON serializable: {str(json_error)}"
            print(f"ERROR: {error_msg}")
            print(f"ERROR: Data keys: {list(cleaned_data.keys())}")
            raise ValueError(error_msg) from json_error
        
        async with httpx.AsyncClient() as client:
            try:
                # Use the pre-serialized JSON string approach to avoid Windows errno 22 issues
                # httpx will handle the json parameter, but we've validated it's serializable
                response = await client.post(
                    f"{self.base_url}/api/v1/workflows",
                    headers=self.headers,
                    json=cleaned_data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"n8n create_workflow returned {e.response.status_code}"
                print(f"ERROR: {error_msg}")
                print(f"ERROR: Response text: {e.response.text[:500] if e.response.text else 'No response text'}")
                try:
                    print(f"ERROR: What we sent (first 1000 chars): {json_str[:1000]}")
                except:
                    print(f"ERROR: Could not serialize sent data for logging")
                raise
            except OSError as e:
                # Windows-specific error handling for errno 22
                if hasattr(e, 'errno') and e.errno == 22:
                    error_msg = f"Windows errno 22 (Invalid argument) - possibly invalid characters or data in workflow"
                    print(f"ERROR: {error_msg}")
                    print(f"ERROR: Exception: {str(e)}")
                    print(f"ERROR: Workflow name: {cleaned_data.get('name', 'unknown')}")
                    print(f"ERROR: Number of nodes: {len(cleaned_data.get('nodes', []))}")
                    print(f"ERROR: Number of connections: {len(str(cleaned_data.get('connections', {})))}")
                    # Try to identify problematic data
                    try:
                        for i, node in enumerate(cleaned_data.get('nodes', [])[:5]):  # Check first 5 nodes
                            try:
                                node_json = json.dumps(node, default=str, ensure_ascii=False)
                                if len(node_json) > 2000:
                                    print(f"ERROR: Node {i} ({node.get('name', 'unnamed')}) is very large: {len(node_json)} chars")
                            except Exception as node_error:
                                print(f"ERROR: Node {i} cannot be serialized: {node_error}")
                    except Exception as node_error:
                        print(f"ERROR: Could not inspect nodes: {node_error}")
                    raise ValueError(error_msg) from e
                raise
            except Exception as e:
                error_msg = f"Unexpected error in create_workflow: {str(e)}"
                print(f"ERROR: {error_msg}")
                print(f"ERROR: Exception type: {type(e).__name__}")
                if hasattr(e, 'errno'):
                    print(f"ERROR: errno: {e.errno}")
                import traceback
                traceback.print_exc()
                raise

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
        print(f"N8NClient.test_connection - base_url: {self.base_url}", flush=True)
        print(f"N8NClient.test_connection - api_key (first 10): {self.api_key[:10] if self.api_key else 'NONE'}...", flush=True)
        print(f"N8NClient.test_connection - api_key length: {len(self.api_key) if self.api_key else 0}", flush=True)
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/api/v1/workflows"
                print(f"N8NClient.test_connection - requesting: {url}", flush=True)
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=10.0
                )
                print(f"N8NClient.test_connection - status: {response.status_code}", flush=True)
                return response.status_code == 200
        except Exception as e:
            print(f"N8NClient.test_connection - exception: {type(e).__name__}: {str(e)}", flush=True)
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
        """Fetch all credentials from N8N via the credentials API.

        N8N's public API supports GET /credentials to list credentials.
        This returns credential metadata (name, type, id) but NOT the actual credential data.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/credentials",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                credentials = data.get("data", []) if isinstance(data, dict) else data

                # Also enrich with workflow usage info by scanning workflows
                workflows = await self.get_workflows()
                credentials_usage = self._extract_credential_usage_from_workflows(workflows)

                # Merge usage info into credentials
                for cred in credentials:
                    cred_id = cred.get("id")
                    if cred_id and cred_id in credentials_usage:
                        cred["used_by_workflows"] = credentials_usage[cred_id]
                    else:
                        cred["used_by_workflows"] = []

                return credentials
        except httpx.HTTPStatusError as e:
            # If credentials endpoint is not accessible (older n8n versions), fall back to workflow extraction
            if e.response.status_code in [401, 403, 404]:
                import logging
                logging.info("N8N credentials API not available, extracting from workflows")
                return await self._extract_credentials_from_workflows()
            raise
        except Exception as e:
            import logging
            logging.warning(f"Failed to fetch credentials: {str(e)}")
            return await self._extract_credentials_from_workflows()

    def _extract_credential_usage_from_workflows(self, workflows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Build a map of credential_id -> list of workflows that use it"""
        usage_map = {}

        for workflow in workflows:
            nodes = workflow.get("nodes", [])
            for node in nodes:
                node_credentials = node.get("credentials", {})
                for cred_type, cred_info in node_credentials.items():
                    if isinstance(cred_info, dict):
                        cred_id = cred_info.get("id")
                        if cred_id:
                            if cred_id not in usage_map:
                                usage_map[cred_id] = []
                            workflow_ref = {
                                "id": workflow.get("id"),
                                "name": workflow.get("name"),
                                "n8n_workflow_id": workflow.get("id")
                            }
                            if workflow_ref not in usage_map[cred_id]:
                                usage_map[cred_id].append(workflow_ref)

        return usage_map

    async def _extract_credentials_from_workflows(self) -> List[Dict[str, Any]]:
        """Fallback: Extract credentials referenced in workflows when API is not available."""
        credentials_map = {}

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
                            cred_id = None
                            cred_name = str(cred_info) if cred_info else "Unknown"

                        key = f"{cred_type}:{cred_name}"
                        if key not in credentials_map:
                            credentials_map[key] = {
                                "id": cred_id or key,
                                "name": cred_name,
                                "type": cred_type,
                                "used_by_workflows": []
                            }

                        workflow_ref = {
                            "id": workflow.get("id"),
                            "name": workflow.get("name"),
                            "n8n_workflow_id": workflow.get("id")
                        }
                        if workflow_ref not in credentials_map[key]["used_by_workflows"]:
                            credentials_map[key]["used_by_workflows"].append(workflow_ref)

            return list(credentials_map.values())

        except Exception as e:
            import logging
            logging.warning(f"Failed to extract credentials from workflows: {str(e)}")
            return []

    async def get_credential(self, credential_id: str) -> Dict[str, Any]:
        """Get a specific credential by ID (metadata only, no secret data)"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/credentials/{credential_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def create_credential(self, credential_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new credential in N8N.

        Args:
            credential_data: Dict containing:
                - name: str - Credential name
                - type: str - Credential type (e.g., 'slackApi', 'githubApi')
                - data: dict - The actual credential data (secrets)

        Returns:
            Created credential metadata (without secret data)
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/credentials",
                headers=self.headers,
                json=credential_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def update_credential(self, credential_id: str, credential_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing credential in N8N.

        Args:
            credential_id: The credential ID
            credential_data: Dict containing fields to update:
                - name: str (optional) - New credential name
                - data: dict (optional) - New credential data (secrets)

        Returns:
            Updated credential metadata
        """
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/api/v1/credentials/{credential_id}",
                headers=self.headers,
                json=credential_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from N8N.

        Args:
            credential_id: The credential ID to delete

        Returns:
            True if successful
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/credentials/{credential_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return True

    async def get_credential_types(self) -> List[Dict[str, Any]]:
        """Get all available credential types from N8N.

        Returns a list of credential type schemas that can be used to
        build forms for creating new credentials.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/credentials/schema",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", []) if isinstance(data, dict) else data
        except httpx.HTTPStatusError:
            # Schema endpoint might not be available
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
