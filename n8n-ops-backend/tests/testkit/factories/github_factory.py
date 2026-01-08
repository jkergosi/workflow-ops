"""Factory for generating GitHub API responses."""
from typing import Any, Dict, List, Optional
from ..fixture_loader import load_fixture, deep_merge


class GitHubResponseFactory:
    """Factory for creating GitHub API response data."""
    
    @staticmethod
    def repo_info(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate repository information response.
        
        Args:
            overrides: Dictionary of fields to override
        
        Returns:
            Repository info response dictionary
        """
        base = load_fixture("github/repo_info.json")
        if overrides:
            return deep_merge(base, overrides)
        return base
    
    @staticmethod
    def commit_list() -> List[Dict[str, Any]]:
        """
        Generate commit list response.
        
        Returns:
            List of commit dictionaries
        """
        return load_fixture("github/commit_list.json")
    
    @staticmethod
    def file_content(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate file content response.
        
        Args:
            overrides: Dictionary of fields to override
        
        Returns:
            File content response dictionary
        """
        base = load_fixture("github/file_content.json")
        if overrides:
            return deep_merge(base, overrides)
        return base
    
    @staticmethod
    def error_404() -> Dict[str, Any]:
        """
        Generate 404 error response.
        
        Returns:
            404 error response dictionary
        """
        errors = load_fixture("github/error_responses.json")
        return errors["404"]
    
    @staticmethod
    def error_forbidden() -> Dict[str, Any]:
        """
        Generate 403 forbidden error response.
        
        Returns:
            403 error response dictionary
        """
        errors = load_fixture("github/error_responses.json")
        return errors["403"]
    
    @staticmethod
    def error_timeout() -> Dict[str, Any]:
        """
        Generate timeout error response.
        
        Returns:
            Timeout error response dictionary
        """
        errors = load_fixture("github/error_responses.json")
        return errors["timeout"]

