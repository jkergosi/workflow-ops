import json
import base64
import re
import logging
from typing import Dict, Any, List, Optional
from github import Github, GithubException
from app.core.config import settings

logger = logging.getLogger(__name__)


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

    def _sanitize_foldername(self, name: str) -> str:
        """Sanitize environment type key for use as folder name"""
        # Replace spaces and invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*\s]', '_', name)
        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip('_.')
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Ensure it's not empty
        return sanitized if sanitized else 'default'

    def _workflows_base_path(self, environment_type: str = None, git_folder: str = None) -> str:
        """
        Return the workflows folder path.
        
        Args:
            environment_type: Legacy parameter (deprecated, use git_folder)
            git_folder: Git folder name (e.g., 'dev', 'staging', 'prod')
        """
        if git_folder:
            # Validate git_folder (alphanumeric + hyphens only)
            if not re.match(r'^[a-zA-Z0-9-]+$', git_folder):
                raise ValueError(f"git_folder must contain only alphanumeric characters and hyphens: {git_folder}")
            return f"workflows/{git_folder}"
        elif environment_type:
            # Legacy support for environment_type
            sanitized_folder = self._sanitize_foldername(str(environment_type))
            return f"workflows/{sanitized_folder}"
        else:
            raise ValueError("Either git_folder or environment_type is required")

    async def sync_workflow_to_github(
        self,
        workflow_id: str,
        workflow_name: str,
        workflow_data: Dict[str, Any],
        commit_message: Optional[str] = None,
        environment_type: str = None,
    ) -> bool:
        """Sync a workflow to GitHub repository.

        Args:
            workflow_id: The workflow ID (used for filename)
            workflow_name: The workflow name (stored in comment for reference)
            workflow_data: The workflow data to save
            commit_message: Optional commit message
            environment_type: Environment type key for folder path (e.g., 'dev', 'staging', 'production')
        """
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")

        try:
            # Use workflow ID as filename (IDs are unique and stable)
            sanitized_id = self._sanitize_filename(workflow_id)
            base_path = self._workflows_base_path(environment_type)
            file_path = f"{base_path}/{sanitized_id}.json"

            # Add workflow name comment to the data (name for human readability, ID is the filename)
            workflow_with_comment = {
                "_comment": f"Workflow: {workflow_name} (ID: {workflow_id})",
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

    async def get_all_workflows_from_github(
        self,
        environment_type: str = None,
        commit_sha: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all workflows from GitHub, optionally at a specific commit.

        Args:
            environment_type: Environment type key for folder path (e.g., 'dev', 'staging', 'production')
            commit_sha: Specific Git commit SHA to fetch from. If None, uses current branch HEAD.

        Returns:
            Dict mapping workflow_id to workflow_data
        """
        if not self.is_configured() or not self.repo:
            return {}

        try:
            workflows = {}
            ref = commit_sha or self.branch

            base_path = self._workflows_base_path(environment_type)
            
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
        # Handle new format: "Workflow: {name} (ID: {id})"
        if "(ID:" in comment:
            id_part = comment.split("(ID:")[-1]
            return id_part.rstrip(")").strip()
        # Handle old format: "Workflow ID: {id}"
        if "Workflow ID:" in comment:
            return comment.split("Workflow ID:")[-1].strip()
        return None

    def _extract_workflow_name(self, workflow_data: Dict[str, Any]) -> Optional[str]:
        """Extract workflow name from workflow data or _comment field."""
        if workflow_data.get("name"):
            return workflow_data["name"]
        comment = workflow_data.get("_comment", "")
        # Handle new format: "Workflow: {name} (ID: {id})"
        if comment.startswith("Workflow:") and "(ID:" in comment:
            name_part = comment.split("Workflow:")[-1].split("(ID:")[0]
            return name_part.strip()
        return None

    async def get_workflow_by_name(self, workflow_name: str, environment_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a workflow from GitHub by its name.

        Since files are saved by ID, this method scans all workflow files
        and searches by name inside the workflow data.

        Args:
            workflow_name: The workflow name to search for
            environment_type: Environment type key for folder path

        Returns:
            Workflow data dict with commit info, or None if not found
        """
        if not self.is_configured() or not self.repo:
            return None

        try:
            base_path = self._workflows_base_path(environment_type)

            # Get all files in the workflows folder
            try:
                contents = self.repo.get_contents(base_path, ref=self.branch)
            except GithubException as e:
                if e.status == 404:
                    return None
                raise

            if not isinstance(contents, list):
                contents = [contents]

            # Scan each file and look for matching name
            for content_file in contents:
                if content_file.type == "dir":
                    continue  # Skip subdirectories when searching at top level
                if not content_file.name.endswith('.json'):
                    continue

                # Parse the file and check the name
                workflow_data = self._parse_workflow_file(content_file, self.branch)
                if not workflow_data:
                    continue

                # Check if name matches (from workflow data or comment)
                wf_name = workflow_data.get("name") or self._extract_workflow_name(workflow_data)
                if wf_name == workflow_name:
                    # Found the workflow, get commit info
                    file_path = content_file.path
                    commits = self.repo.get_commits(path=file_path, sha=self.branch)
                    latest_commit = None
                    try:
                        latest_commit = commits[0] if commits.totalCount > 0 else None
                    except Exception:
                        pass

                    return {
                        "workflow": workflow_data,
                        "commit_sha": latest_commit.sha if latest_commit else None,
                        "commit_date": latest_commit.commit.author.date.isoformat() if latest_commit else None,
                        "commit_message": latest_commit.commit.message if latest_commit else None,
                        "file_path": file_path
                    }

            return None

        except GithubException as e:
            if e.status == 404:
                return None
            raise

    async def get_workflow_by_id(self, workflow_id: str, environment_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a workflow from GitHub by its ID (direct file lookup).

        Since files are saved by ID, this is a direct file lookup.

        Args:
            workflow_id: The workflow ID (matches filename)
            environment_type: Environment type key for folder path

        Returns:
            Workflow data dict with commit info, or None if not found
        """
        if not self.is_configured() or not self.repo:
            return None

        try:
            sanitized_id = self._sanitize_filename(workflow_id)
            base_path = self._workflows_base_path(environment_type)
            file_path = f"{base_path}/{sanitized_id}.json"

            try:
                file_content = self.repo.get_contents(file_path, ref=self.branch)
            except GithubException as e:
                if e.status == 404:
                    return None
                raise

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

            return {
                "workflow": workflow_data,
                "commit_sha": latest_commit.sha if latest_commit else None,
                "commit_date": latest_commit.commit.author.date.isoformat() if latest_commit else None,
                "commit_message": latest_commit.commit.message if latest_commit else None,
                "file_path": file_path
            }

        except GithubException as e:
            if e.status == 404:
                return None
            raise

    async def get_workflow_commit_info(self, workflow_name: str, environment_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Get just the commit info for a workflow by name without fetching full content.

        Since files are saved by ID, this scans files to find matching name.

        Args:
            workflow_name: The workflow name to search for
            environment_type: Environment type key for folder path

        Returns:
            Dict with commit info or None
        """
        # Reuse get_workflow_by_name which already handles the scanning
        result = await self.get_workflow_by_name(workflow_name, environment_type)
        if not result:
            return None

        return {
            "sha": result.get("commit_sha"),
            "date": result.get("commit_date"),
            "message": result.get("commit_message"),
            "author": None  # Not available from get_workflow_by_name, but rarely needed
        }

    async def get_workflow_commit_info_by_id(self, workflow_id: str, environment_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Get just the commit info for a workflow by ID (direct file lookup).

        Args:
            workflow_id: The workflow ID (matches filename)
            environment_type: Environment type key for folder path

        Returns:
            Dict with commit info or None
        """
        if not self.is_configured() or not self.repo:
            return None

        try:
            sanitized_id = self._sanitize_filename(workflow_id)
            base_path = self._workflows_base_path(environment_type)
            file_path = f"{base_path}/{sanitized_id}.json"

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
        commit_message: Optional[str] = None,
        environment_type: str = None
    ) -> bool:
        """Delete a workflow from GitHub.

        Args:
            workflow_id: The workflow ID (used for filename)
            workflow_name: The workflow name (used for commit message)
            commit_message: Optional commit message
            environment_type: Environment type key for folder path
        """
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")

        try:
            # Use workflow ID as filename (consistent with sync_workflow_to_github)
            sanitized_id = self._sanitize_filename(workflow_id)
            base_path = self._workflows_base_path(environment_type)
            file_path = f"{base_path}/{sanitized_id}.json"

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
    
    # =============================================================================
    # Canonical Workflow Methods (new API)
    # =============================================================================
    
    async def get_all_workflow_files_from_github(
        self,
        git_folder: str,
        commit_sha: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all canonical workflow files from GitHub.
        
        Returns Dict mapping file_path to workflow_data.
        File paths are relative to repo root (e.g., 'workflows/dev/{canonical_id}.json').
        
        Args:
            git_folder: Git folder name (e.g., 'dev', 'staging', 'prod')
            commit_sha: Optional specific commit to fetch from
            
        Returns:
            Dict mapping file_path to workflow_data
        """
        if not self.is_configured() or not self.repo:
            return {}
        
        try:
            workflows = {}
            ref = commit_sha or self.branch
            base_path = self._workflows_base_path(git_folder=git_folder)
            
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
                    continue
                if not content_file.name.endswith('.json') or content_file.name.endswith('.env-map.json'):
                    continue
                
                # Only process workflow files, not sidecars
                if content_file.name.endswith('.env-map.json'):
                    continue
                
                workflow_data = self._parse_workflow_file(content_file, ref)
                if workflow_data:
                    workflows[content_file.path] = workflow_data
            
            return workflows
        except GithubException as e:
            logger.error(f"Error fetching workflow files from GitHub: {str(e)}")
            return {}
    
    async def get_file_content(
        self,
        file_path: str,
        ref: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get file content from GitHub as parsed JSON.
        
        Args:
            file_path: Relative path from repo root
            ref: Git ref (branch, commit SHA, etc.)
            
        Returns:
            Parsed JSON content or None if file doesn't exist
        """
        if not self.is_configured() or not self.repo:
            return None
        
        try:
            ref = ref or self.branch
            file_content = self.repo.get_contents(file_path, ref=ref)
            decoded_content = base64.b64decode(file_content.content).decode('utf-8')
            return json.loads(decoded_content)
        except GithubException as e:
            if e.status == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return None
    
    async def write_workflow_file(
        self,
        canonical_id: str,
        workflow_data: Dict[str, Any],
        git_folder: str,
        commit_message: Optional[str] = None
    ) -> bool:
        """
        Write a canonical workflow file to GitHub.
        
        Args:
            canonical_id: Canonical workflow ID (used as filename)
            workflow_data: Workflow data (pure n8n format, no metadata)
            git_folder: Git folder name
            commit_message: Optional commit message
            
        Returns:
            True if successful
        """
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")
        
        try:
            base_path = self._workflows_base_path(git_folder=git_folder)
            file_path = f"{base_path}/{canonical_id}.json"
            
            # Workflow data must be pure n8n format (no WorkflowOps metadata)
            content = json.dumps(workflow_data, indent=2)
            
            if not commit_message:
                workflow_name = workflow_data.get("name", "Unknown")
                commit_message = f"Update canonical workflow: {workflow_name}"
            
            try:
                existing_file = self.repo.get_contents(file_path, ref=self.branch)
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=self.branch
                )
            except GithubException as e:
                if e.status == 404:
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
            logger.error(f"Error writing workflow file: {str(e)}")
            raise
    
    async def write_sidecar_file(
        self,
        canonical_id: str,
        sidecar_data: Dict[str, Any],
        git_folder: str,
        commit_message: Optional[str] = None
    ) -> bool:
        """
        Write a sidecar env-map file to GitHub.
        
        Args:
            canonical_id: Canonical workflow ID
            sidecar_data: Sidecar data (see spec for format)
            git_folder: Git folder name
            commit_message: Optional commit message
            
        Returns:
            True if successful
        """
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")
        
        try:
            base_path = self._workflows_base_path(git_folder=git_folder)
            file_path = f"{base_path}/{canonical_id}.env-map.json"
            
            content = json.dumps(sidecar_data, indent=2)
            
            if not commit_message:
                commit_message = f"Update sidecar mapping for {canonical_id}"
            
            try:
                existing_file = self.repo.get_contents(file_path, ref=self.branch)
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=self.branch
                )
            except GithubException as e:
                if e.status == 404:
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
            logger.error(f"Error writing sidecar file: {str(e)}")
            raise
    
    async def create_migration_branch_and_pr(
        self,
        tenant_slug: str,
        workflow_files: Dict[str, str],
        sidecar_files: Dict[str, Dict[str, Any]],
        migration_map: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a migration branch and PR for canonical workflow migration.
        
        Args:
            tenant_slug: Validated tenant slug for branch name
            workflow_files: Dict mapping file_path to workflow JSON content (as string)
            sidecar_files: Dict mapping file_path to sidecar data
            migration_map: Migration map data to write to migration-map.json
            
        Returns:
            Dict with pr_url, branch_name, commit_sha, or error
        """
        if not self.is_configured() or not self.repo:
            raise ValueError("GitHub is not properly configured")
        
        branch_name = f"migration/canonical-workflows/{tenant_slug}"
        
        try:
            # Check if branch already exists
            try:
                self.repo.get_branch(branch_name)
                # Branch exists - check if it's an open migration PR
                # For MVP, we'll fail with clear error
                raise ValueError(
                    f"Migration branch '{branch_name}' already exists. "
                    "Please merge or delete the existing migration PR before continuing."
                )
            except GithubException as e:
                if e.status != 404:
                    raise
            
            # Get base branch SHA
            base_branch = self.repo.get_branch(self.branch)
            base_sha = base_branch.commit.sha
            
            # Create new branch
            self.repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_sha
            )
            
            # Commit all workflow files
            for file_path, content in workflow_files.items():
                try:
                    # Check if file exists in base branch
                    try:
                        existing = self.repo.get_contents(file_path, ref=self.branch)
                        self.repo.update_file(
                            path=file_path,
                            message=f"Add canonical workflow: {file_path}",
                            content=content,
                            sha=existing.sha,
                            branch=branch_name
                        )
                    except GithubException as e:
                        if e.status == 404:
                            self.repo.create_file(
                                path=file_path,
                                message=f"Add canonical workflow: {file_path}",
                                content=content,
                                branch=branch_name
                            )
                        else:
                            raise
                except Exception as e:
                    logger.error(f"Error committing workflow file {file_path}: {str(e)}")
                    raise
            
            # Commit all sidecar files
            for file_path, sidecar_data in sidecar_files.items():
                content = json.dumps(sidecar_data, indent=2)
                try:
                    try:
                        existing = self.repo.get_contents(file_path, ref=self.branch)
                        self.repo.update_file(
                            path=file_path,
                            message=f"Add sidecar mapping: {file_path}",
                            content=content,
                            sha=existing.sha,
                            branch=branch_name
                        )
                    except GithubException as e:
                        if e.status == 404:
                            self.repo.create_file(
                                path=file_path,
                                message=f"Add sidecar mapping: {file_path}",
                                content=content,
                                branch=branch_name
                            )
                        else:
                            raise
                except Exception as e:
                    logger.error(f"Error committing sidecar file {file_path}: {str(e)}")
                    raise
            
            # Write migration-map.json at repo root
            migration_map_content = json.dumps(migration_map, indent=2)
            try:
                try:
                    existing = self.repo.get_contents("migration-map.json", ref=self.branch)
                    self.repo.update_file(
                        path="migration-map.json",
                        message="Add migration map",
                        content=migration_map_content,
                        sha=existing.sha,
                        branch=branch_name
                    )
                except GithubException as e:
                    if e.status == 404:
                        self.repo.create_file(
                            path="migration-map.json",
                            message="Add migration map",
                            content=migration_map_content,
                            branch=branch_name
                        )
                    else:
                        raise
            except Exception as e:
                logger.warning(f"Error writing migration-map.json: {str(e)}")
            
            # Get latest commit SHA
            branch = self.repo.get_branch(branch_name)
            commit_sha = branch.commit.sha
            
            # Create PR
            pr_title = f"Canonical Workflow Migration: {tenant_slug}"
            pr_body = (
                f"This PR migrates workflows to the canonical workflow system.\n\n"
                f"**Branch:** `{branch_name}`\n"
                f"**Workflows:** {len(workflow_files)} files\n"
                f"**Sidecars:** {len(sidecar_files)} files\n\n"
                f"Please review and merge to activate the canonical workflow system."
            )
            
            pr = self.repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=self.branch
            )
            
            return {
                "pr_url": pr.html_url,
                "branch_name": branch_name,
                "commit_sha": commit_sha
            }
            
        except Exception as e:
            logger.error(f"Error creating migration PR: {str(e)}")
            return {
                "error": str(e),
                "branch_name": branch_name
            }


# Global instance (will use settings defaults)
github_service = GitHubService()
