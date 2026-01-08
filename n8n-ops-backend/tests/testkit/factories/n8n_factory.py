"""Factory for generating n8n API responses."""
from typing import Any, Dict, List, Optional
from ..fixture_loader import load_fixture, deep_merge


class N8nResponseFactory:
    """Factory for creating n8n API response data."""
    
    @staticmethod
    def workflow(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a simple workflow response.
        
        Args:
            overrides: Dictionary of fields to override in the base workflow
        
        Returns:
            Workflow response dictionary
        """
        base = load_fixture("n8n/workflow_simple.json")
        if overrides:
            return deep_merge(base, overrides)
        return base
    
    @staticmethod
    def workflow_complex() -> Dict[str, Any]:
        """
        Generate a complex workflow with multiple nodes and connections.
        
        Returns:
            Complex workflow response dictionary
        """
        return load_fixture("n8n/workflow_complex.json")
    
    @staticmethod
    def workflows_list(workflows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Generate a workflows list response.
        
        Args:
            workflows: List of workflow dictionaries (uses default if not provided)
        
        Returns:
            Workflows list response with data array
        """
        if workflows is None:
            workflows = [N8nResponseFactory.workflow()]
        
        return {
            "data": workflows
        }
    
    @staticmethod
    def executions_list() -> Dict[str, Any]:
        """
        Generate an executions list response.
        
        Returns:
            Executions list response
        """
        return load_fixture("n8n/executions_list.json")
    
    @staticmethod
    def credentials_list() -> Dict[str, Any]:
        """
        Generate a credentials list response.
        
        Returns:
            Credentials list response
        """
        return load_fixture("n8n/credentials_list.json")
    
    @staticmethod
    def error_404(message: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a 404 error response.
        
        Args:
            message: Optional custom error message
        
        Returns:
            404 error response dictionary
        """
        error = load_fixture("n8n/error_404.json")
        if message:
            error["message"] = message
        return error
    
    @staticmethod
    def error_rate_limit() -> Dict[str, Any]:
        """
        Generate a 429 rate limit error response.
        
        Returns:
            429 error response dictionary
        """
        return load_fixture("n8n/error_429.json")
    
    @staticmethod
    def error_server() -> Dict[str, Any]:
        """
        Generate a 500 server error response.
        
        Returns:
            500 error response dictionary
        """
        return load_fixture("n8n/error_500.json")
    
    @staticmethod
    def malformed_json() -> str:
        """
        Generate malformed JSON for error testing.
        
        Returns:
            Invalid JSON string
        """
        return '{"id": "1", "name": "Test", invalid json here}'

