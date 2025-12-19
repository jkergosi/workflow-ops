import json
import base64
import re
from typing import Dict, Any, List, Optional
from github import Github, GithubException
from app.core.config import settings


class GitHubService:
    """Service for syncing workflows to GitHub"""

    def __init__(self, token: str = None, repo_owner: str = None, repo_name: str = None, branch: str = None):
        self.token = token or settings.GITHUB_TOKEN
        self.repo_owner = repo_owner or settings.GITHUB_REPO_OWNER
        self.repo_name = repo_name or settings.GITHUB_REPO_NAME
        self.branch = branch or settings.GITHUB_BRANCH

        if self.token:
            self.github = Github(self.token)
        else:
            self.github = None

        self._repo = None

    @property
    def repo(self):
        """Lazy load the repository connection"""
        if self._repo is None and self.github and self.repo_owner and self.repo_name:
            try:
                self._repo = self.github.get_repo(f"{self.repo_owner}/{self.repo_name}")
            except Exception:
                # Return None if repo can't be accessed
                pass
        return self._repo

    def is_configured(self) -> bool:
        """Check if GitHub is properly configured"""
        return all([self.token, self.repo_owner, self.repo_name, self.branch])

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize workflow name for use as filename"""
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Ensure it's not empty
        return sanitized if sanitized else 'unnamed_workflow'

    async def sync_workflow_to_github(
        self,
        workflow_id: str,
        workflow_name: str,
        workflow_data: Dict[str, Any],
        commit_message: Optional[str] = None,
        environment_type: Optional[str] = None
    ) -> bool:
        """Sync a workflow to GitHub repository"""
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")

        try:
            # Use sanitized workflow name as filename
            sanitized_name = self._sanitize_filename(workflow_name)
            # Use environment-specific path if provided (e.g., workflows/dev/, workflows/staging/)
            if environment_type:
                file_path = f"workflows/{environment_type}/{sanitized_name}.json"
            else:
                file_path = f"workflows/{sanitized_name}.json"

            # Add workflow ID comment to the data
            workflow_with_comment = {
                "_comment": f"Workflow ID: {workflow_id}",
                **workflow_data
            }

            # Convert workflow data to JSON string
            content = json.dumps(workflow_with_comment, indent=2)

            # Default commit message
            if not commit_message:
                commit_message = f"Update workflow: {workflow_name}"

            try:
                # Try to get existing file
                existing_file = self.repo.get_contents(file_path, ref=self.branch)
                # Update existing file
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=self.branch
                )
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create it
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch=self.branch
                    )
                else:
                    raise

            return True

        except Exception as e:
            print(f"Error syncing workflow to GitHub: {str(e)}")
            raise

    async def get_workflow_from_github(self, workflow_id: str, environment_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a single workflow from GitHub by ID"""
        if not self.is_configured() or not self.repo:
            return None

        try:
            # Try with environment_type path first if provided
            if environment_type:
                file_path = f"workflows/{environment_type}/{workflow_id}.json"
                try:
                    file_content = self.repo.get_contents(file_path, ref=self.branch)
                    content = base64.b64decode(file_content.content).decode('utf-8')
                    return json.loads(content)
                except GithubException:
                    pass  # Fall through to try without environment_type
            
            # Try without environment_type path
            file_path = f"workflows/{workflow_id}.json"
            file_content = self.repo.get_contents(file_path, ref=self.branch)
            content = base64.b64decode(file_content.content).decode('utf-8')
            return json.loads(content)
        except GithubException:
            return None

    async def get_all_workflows_from_github(
        self,
        environment_type: Optional[str] = None,
        commit_sha: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all workflows from GitHub, optionally at a specific commit.
        
        Args:
            environment_type: Filter by environment folder (e.g., 'dev', 'staging', 'prod')
            commit_sha: Specific Git commit SHA to fetch from. If None, uses current branch HEAD.
            
        Returns:
            Dict mapping workflow_id to workflow_data
        """
        if not self.is_configured() or not self.repo:
            return {}

        try:
            workflows = {}
            ref = commit_sha or self.branch
            
            if environment_type:
                base_path = f"workflows/{environment_type}"
            else:
                base_path = "workflows"
            
            try:
                contents = self.repo.get_contents(base_path, ref=ref)
            except GithubException as e:
                if e.status == 404:
                    return {}
                raise
            
            if not isinstance(contents, list):
                contents = [contents]

            for content_file in contents:
                if content_file.type == "dir":
                    subdir_contents = self.repo.get_contents(content_file.path, ref=ref)
                    if not isinstance(subdir_contents, list):
                        subdir_contents = [subdir_contents]
                    for subfile in subdir_contents:
                        if subfile.name.endswith('.json'):
                            workflow_data = self._parse_workflow_file(subfile, ref)
                            if workflow_data:
                                workflow_id = workflow_data.get("id") or self._extract_workflow_id(workflow_data)
                                if workflow_id:
                                    workflows[workflow_id] = workflow_data
                elif content_file.name.endswith('.json'):
                    workflow_data = self._parse_workflow_file(content_file, ref)
                    if workflow_data:
                        workflow_id = workflow_data.get("id") or self._extract_workflow_id(workflow_data)
                        if workflow_id:
                            workflows[workflow_id] = workflow_data

            return workflows
        except GithubException as e:
            print(f"Error fetching workflows from GitHub: {str(e)}")
            return {}
    
    def _parse_workflow_file(self, content_file, ref: str) -> Optional[Dict[str, Any]]:
        """Parse a workflow JSON file from GitHub."""
        try:
            if hasattr(content_file, 'content') and content_file.content:
                decoded_content = base64.b64decode(content_file.content).decode('utf-8')
            else:
                file_content = self.repo.get_contents(content_file.path, ref=ref)
                decoded_content = base64.b64decode(file_content.content).decode('utf-8')
            return json.loads(decoded_content)
        except Exception as e:
            print(f"Error parsing workflow file {content_file.path}: {str(e)}")
            return None
    
    def _extract_workflow_id(self, workflow_data: Dict[str, Any]) -> Optional[str]:
        """Extract workflow ID from workflow data or _comment field."""
        if workflow_data.get("id"):
            return workflow_data["id"]
        comment = workflow_data.get("_comment", "")
        if "Workflow ID:" in comment:
            return comment.split("Workflow ID:")[-1].strip()
        return None

    async def get_workflow_by_name(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a workflow from GitHub by its name.

        Args:
            workflow_name: The workflow name (will be sanitized to match filename)

        Returns:
            Workflow data dict with commit info, or None if not found
        """
        if not self.is_configured() or not self.repo:
            return None

        try:
            sanitized_name = self._sanitize_filename(workflow_name)
            file_path = f"workflows/{sanitized_name}.json"

            file_content = self.repo.get_contents(file_path, ref=self.branch)

            # Decode base64 content
            content = base64.b64decode(file_content.content).decode('utf-8')
            workflow_data = json.loads(content)

            # Get commit info for this file
            commits = self.repo.get_commits(path=file_path, sha=self.branch)
            latest_commit = None
            try:
                latest_commit = commits[0] if commits.totalCount > 0 else None
            except Exception:
                pass

            # Add metadata
            result = {
                "workflow": workflow_data,
                "commit_sha": latest_commit.sha if latest_commit else None,
                "commit_date": latest_commit.commit.author.date.isoformat() if latest_commit else None,
                "commit_message": latest_commit.commit.message if latest_commit else None,
                "file_path": file_path
            }

            return result

        except GithubException as e:
            if e.status == 404:
                return None
            raise

    async def get_workflow_commit_info(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """
        Get just the commit info for a workflow without fetching content.

        Args:
            workflow_name: The workflow name

        Returns:
            Dict with commit info or None
        """
        if not self.is_configured() or not self.repo:
            return None

        try:
            sanitized_name = self._sanitize_filename(workflow_name)
            file_path = f"workflows/{sanitized_name}.json"

            # Check if file exists
            try:
                self.repo.get_contents(file_path, ref=self.branch)
            except GithubException as e:
                if e.status == 404:
                    return None
                raise

            # Get commit info
            commits = self.repo.get_commits(path=file_path, sha=self.branch)
            latest_commit = None
            try:
                latest_commit = commits[0] if commits.totalCount > 0 else None
            except Exception:
                pass

            if latest_commit:
                return {
                    "sha": latest_commit.sha,
                    "date": latest_commit.commit.author.date.isoformat(),
                    "message": latest_commit.commit.message,
                    "author": latest_commit.commit.author.name
                }

            return None

        except Exception:
            return None

    async def delete_workflow_from_github(
        self,
        workflow_id: str,
        workflow_name: str,
        commit_message: Optional[str] = None
    ) -> bool:
        """Delete a workflow from GitHub"""
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")

        try:
            file_path = f"workflows/{workflow_id}.json"

            if not commit_message:
                commit_message = f"Delete workflow: {workflow_name}"

            # Get file to get its SHA
            file_content = self.repo.get_contents(file_path, ref=self.branch)

            # Delete the file
            self.repo.delete_file(
                path=file_path,
                message=commit_message,
                sha=file_content.sha,
                branch=self.branch
            )

            return True

        except GithubException as e:
            if e.status == 404:
                return True  # File already doesn't exist
            raise

    async def test_connection(self) -> bool:
        """Test GitHub connection"""
        try:
            if not self.is_configured():
                return False

            # Try to get repo info
            self.repo.get_branch(self.branch)
            return True
        except Exception:
            return False


# Global instance (will use settings defaults)
github_service = GitHubService()
