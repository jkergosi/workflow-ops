"""HTTP mocking helpers for n8n API."""
import httpx
import respx
from typing import List, Dict, Any, Optional
from ..factories.n8n_factory import N8nResponseFactory


class N8nHttpMock:
    """Helper class for mocking n8n API HTTP requests."""
    
    def __init__(self, base_url: str):
        """
        Initialize n8n HTTP mock.
        
        Args:
            base_url: Base URL of the n8n instance (e.g., "https://dev.n8n.example.com")
        """
        self.base_url = base_url.rstrip("/")
        self.router = respx.Router(base_url=self.base_url)
    
    def mock_get_workflows(self, workflows: Optional[List[Dict[str, Any]]] = None):
        """
        Mock GET /workflows endpoint.
        
        Args:
            workflows: List of workflow dictionaries (uses defaults if not provided)
        """
        workflows = workflows or [N8nResponseFactory.workflow()]
        self.router.get("/workflows").mock(
            return_value=httpx.Response(
                200,
                json={"data": workflows}
            )
        )
    
    def mock_get_workflow(self, workflow_id: str, workflow: Optional[Dict[str, Any]] = None):
        """
        Mock GET /workflows/{id} endpoint.
        
        Args:
            workflow_id: Workflow ID
            workflow: Workflow dictionary (uses default if not provided)
        """
        workflow = workflow or N8nResponseFactory.workflow({"id": workflow_id})
        self.router.get(f"/workflows/{workflow_id}").mock(
            return_value=httpx.Response(200, json=workflow)
        )
    
    def mock_create_workflow(self, workflow: Optional[Dict[str, Any]] = None):
        """
        Mock POST /workflows endpoint.
        
        Args:
            workflow: Workflow dictionary to return (uses default if not provided)
        """
        workflow = workflow or N8nResponseFactory.workflow()
        self.router.post("/workflows").mock(
            return_value=httpx.Response(201, json=workflow)
        )
    
    def mock_update_workflow(self, workflow_id: str, workflow: Optional[Dict[str, Any]] = None):
        """
        Mock PATCH/PUT /workflows/{id} endpoint.
        
        Args:
            workflow_id: Workflow ID
            workflow: Updated workflow dictionary (uses default if not provided)
        """
        workflow = workflow or N8nResponseFactory.workflow({"id": workflow_id})
        self.router.route(method__in=["PATCH", "PUT"], path=f"/workflows/{workflow_id}").mock(
            return_value=httpx.Response(200, json=workflow)
        )
    
    def mock_delete_workflow(self, workflow_id: str):
        """
        Mock DELETE /workflows/{id} endpoint.
        
        Args:
            workflow_id: Workflow ID
        """
        self.router.delete(f"/workflows/{workflow_id}").mock(
            return_value=httpx.Response(204)
        )
    
    def mock_get_executions(self):
        """Mock GET /executions endpoint."""
        self.router.get("/executions").mock(
            return_value=httpx.Response(
                200,
                json=N8nResponseFactory.executions_list()
            )
        )
    
    def mock_get_credentials(self):
        """Mock GET /credentials endpoint."""
        self.router.get("/credentials").mock(
            return_value=httpx.Response(
                200,
                json=N8nResponseFactory.credentials_list()
            )
        )
    
    def mock_workflow_404(self, workflow_id: str, message: Optional[str] = None):
        """
        Mock 404 error for specific workflow.
        
        Args:
            workflow_id: Workflow ID that doesn't exist
            message: Optional custom error message
        """
        self.router.get(f"/workflows/{workflow_id}").mock(
            return_value=httpx.Response(
                404,
                json=N8nResponseFactory.error_404(message)
            )
        )
    
    def mock_rate_limit(self, endpoint: str = "/workflows"):
        """
        Mock 429 rate limit error.
        
        Args:
            endpoint: API endpoint to mock (default: /workflows)
        """
        self.router.get(endpoint).mock(
            return_value=httpx.Response(
                429,
                json=N8nResponseFactory.error_rate_limit()
            )
        )
    
    def mock_server_error(self, endpoint: str = "/workflows"):
        """
        Mock 500 server error.
        
        Args:
            endpoint: API endpoint to mock (default: /workflows)
        """
        self.router.get(endpoint).mock(
            return_value=httpx.Response(
                500,
                json=N8nResponseFactory.error_server()
            )
        )
    
    def mock_timeout(self, endpoint: str = "/workflows"):
        """
        Mock timeout scenario.
        
        Args:
            endpoint: API endpoint to mock (default: /workflows)
        """
        self.router.get(endpoint).mock(side_effect=httpx.TimeoutException("Request timed out"))
    
    def mock_connection_error(self, endpoint: str = "/workflows"):
        """
        Mock connection error.
        
        Args:
            endpoint: API endpoint to mock (default: /workflows)
        """
        self.router.get(endpoint).mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
    
    def __enter__(self):
        """Context manager entry."""
        self.router.__enter__()
        return self
    
    def __exit__(self, *args):
        """Context manager exit."""
        self.router.__exit__(*args)

