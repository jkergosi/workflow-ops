"""HTTP mocking helpers for GitHub API."""
import httpx
import respx
from typing import Dict, Any, List, Optional
from ..factories.github_factory import GitHubResponseFactory


class GitHubHttpMock:
    """Helper class for mocking GitHub API HTTP requests."""
    
    def __init__(self, base_url: str = "https://api.github.com"):
        """
        Initialize GitHub HTTP mock.
        
        Args:
            base_url: Base URL of GitHub API (default: https://api.github.com)
        """
        self.base_url = base_url.rstrip("/")
        self.router = respx.Router(base_url=self.base_url)
    
    def mock_get_repo(self, owner: str, repo: str, repo_info: Optional[Dict[str, Any]] = None):
        """
        Mock GET /repos/{owner}/{repo} endpoint.
        
        Args:
            owner: Repository owner
            repo: Repository name
            repo_info: Repository info dictionary (uses default if not provided)
        """
        repo_info = repo_info or GitHubResponseFactory.repo_info()
        self.router.get(f"/repos/{owner}/{repo}").mock(
            return_value=httpx.Response(200, json=repo_info)
        )
    
    def mock_get_commits(self, owner: str, repo: str):
        """
        Mock GET /repos/{owner}/{repo}/commits endpoint.
        
        Args:
            owner: Repository owner
            repo: Repository name
        """
        self.router.get(f"/repos/{owner}/{repo}/commits").mock(
            return_value=httpx.Response(
                200,
                json=GitHubResponseFactory.commit_list()
            )
        )
    
    def mock_get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        content: Optional[Dict[str, Any]] = None
    ):
        """
        Mock GET /repos/{owner}/{repo}/contents/{path} endpoint.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            content: File content dictionary (uses default if not provided)
        """
        content = content or GitHubResponseFactory.file_content({"path": path})
        self.router.get(f"/repos/{owner}/{repo}/contents/{path}").mock(
            return_value=httpx.Response(200, json=content)
        )
    
    def mock_create_file(self, owner: str, repo: str, path: str):
        """
        Mock PUT /repos/{owner}/{repo}/contents/{path} endpoint for file creation.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository
        """
        self.router.put(f"/repos/{owner}/{repo}/contents/{path}").mock(
            return_value=httpx.Response(
                201,
                json={
                    "content": GitHubResponseFactory.file_content({"path": path}),
                    "commit": {"sha": "abc123"}
                }
            )
        )
    
    def mock_404(self, owner: str, repo: str, path: Optional[str] = None):
        """
        Mock 404 error.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Optional file path
        """
        url = f"/repos/{owner}/{repo}"
        if path:
            url += f"/contents/{path}"
        
        self.router.get(url).mock(
            return_value=httpx.Response(
                404,
                json=GitHubResponseFactory.error_404()
            )
        )
    
    def mock_forbidden(self, owner: str, repo: str):
        """
        Mock 403 forbidden error.
        
        Args:
            owner: Repository owner
            repo: Repository name
        """
        self.router.get(f"/repos/{owner}/{repo}").mock(
            return_value=httpx.Response(
                403,
                json=GitHubResponseFactory.error_forbidden()
            )
        )
    
    def mock_timeout(self, endpoint: str):
        """
        Mock timeout scenario.
        
        Args:
            endpoint: API endpoint to mock
        """
        self.router.get(endpoint).mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
    
    def __enter__(self):
        """Context manager entry."""
        self.router.__enter__()
        return self
    
    def __exit__(self, *args):
        """Context manager exit."""
        self.router.__exit__(*args)

