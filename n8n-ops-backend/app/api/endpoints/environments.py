from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime

from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvironmentResponse,
    EnvironmentTestConnection,
    GitTestConnection
)
from app.services.database import db_service
from app.services.n8n_client import N8NClient
from app.services.github_service import GitHubService
from app.services.feature_service import feature_service
from app.core.feature_gate import require_environment_limit

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Environments router is working"}


@router.get("/", response_model=List[EnvironmentResponse], response_model_exclude_none=False)
async def get_environments():
    """Get all environments for the current tenant"""
    try:
        environments = await db_service.get_environments(MOCK_TENANT_ID)
        return environments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environments: {str(e)}"
        )


@router.get("/limits")
async def get_environment_limits():
    """Get environment limits and current usage for the tenant"""
    try:
        can_add, message, current, max_allowed = await feature_service.can_add_environment(MOCK_TENANT_ID)
        return {
            "can_add": can_add,
            "message": message,
            "current": current,
            "max": max_allowed if max_allowed != float('inf') else "unlimited"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environment limits: {str(e)}"
        )


@router.post("/test-connection")
async def test_environment_connection(connection: EnvironmentTestConnection):
    """Test connection to an N8N instance"""
    try:
        # Create a temporary N8N client with the provided credentials
        test_client = N8NClient(base_url=connection.n8n_base_url, api_key=connection.n8n_api_key)
        is_connected = await test_client.test_connection()

        if is_connected:
            return {
                "success": True,
                "message": "Successfully connected to N8N instance"
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to N8N instance. Please check your URL and API key."
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }


@router.post("/test-git-connection")
async def test_git_connection(connection: GitTestConnection):
    """Test connection to a GitHub repository"""
    try:
        # Parse repo URL to extract owner and repo name
        # Expected format: https://github.com/owner/repo or https://github.com/owner/repo.git
        repo_url = connection.git_repo_url.rstrip('/')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        parts = repo_url.split('github.com/')
        if len(parts) != 2:
            return {
                "success": False,
                "message": "Invalid GitHub repository URL format. Expected: https://github.com/owner/repo"
            }

        repo_path = parts[1].strip('/')
        path_parts = repo_path.split('/')
        if len(path_parts) < 2:
            return {
                "success": False,
                "message": "Invalid GitHub repository path. Expected format: owner/repo"
            }

        owner = path_parts[0]
        repo_name = path_parts[1]

        # Create GitHub service with provided credentials
        github_service = GitHubService(
            token=connection.git_pat,
            repo_owner=owner,
            repo_name=repo_name,
            branch=connection.git_branch
        )

        # Test access by trying to access the repo
        if not github_service.is_configured():
            return {
                "success": False,
                "message": "GitHub configuration is incomplete"
            }

        repo = github_service.repo
        if repo is None:
            return {
                "success": False,
                "message": "Failed to access repository. Please check your repository URL and Personal Access Token."
            }

        # Try to verify the branch exists
        try:
            repo.get_branch(connection.git_branch)
        except Exception:
            return {
                "success": False,
                "message": f"Branch '{connection.git_branch}' not found in repository. Please check the branch name."
            }

        return {
            "success": True,
            "message": f"Successfully connected to {owner}/{repo_name} (branch: {connection.git_branch})"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }


@router.get("/{environment_id}", response_model=EnvironmentResponse, response_model_exclude_none=False)
async def get_environment(environment_id: str):
    """Get a specific environment by ID"""
    try:
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )
        return environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environment: {str(e)}"
        )


@router.post("/", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED, response_model_exclude_none=False)
async def create_environment(
    environment: EnvironmentCreate,
    _: dict = Depends(require_environment_limit())
):
    """Create a new environment"""
    try:
        # Type is now optional metadata - no uniqueness check needed
        # Multiple environments can have the same type

        environment_data = {
            "tenant_id": MOCK_TENANT_ID,
            "n8n_name": environment.n8n_name,
            "n8n_type": environment.n8n_type,  # Optional, can be None
            "n8n_base_url": environment.n8n_base_url,
            "n8n_api_key": environment.n8n_api_key,
            "n8n_encryption_key": environment.n8n_encryption_key,
            "is_active": environment.is_active,
            "allow_upload": environment.allow_upload,
            "git_repo_url": environment.git_repo_url,
            "git_branch": environment.git_branch,
            "git_pat": environment.git_pat
        }

        created_environment = await db_service.create_environment(environment_data)
        return created_environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create environment: {str(e)}"
        )


@router.patch("/{environment_id}", response_model=EnvironmentResponse, response_model_exclude_none=False)
async def update_environment(environment_id: str, environment: EnvironmentUpdate):
    """Update an environment"""
    try:
        # Check if environment exists
        existing = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Build update data (only include non-None fields)
        update_data = {k: v for k, v in environment.dict(exclude_unset=True).items() if v is not None}

        if not update_data:
            return existing

        updated_environment = await db_service.update_environment(
            environment_id,
            MOCK_TENANT_ID,
            update_data
        )

        if not updated_environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        return updated_environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update environment: {str(e)}"
        )


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(environment_id: str):
    """Delete an environment"""
    try:
        # Check if environment exists
        existing = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        await db_service.delete_environment(environment_id, MOCK_TENANT_ID)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete environment: {str(e)}"
        )


@router.post("/{environment_id}/update-connection-status")
async def update_connection_status(environment_id: str):
    """Update the last_connected timestamp for an environment"""
    try:
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Test connection
        test_client = N8NClient(
            base_url=environment.get("n8n_base_url"),
            api_key=environment.get("n8n_api_key")
        )
        is_connected = await test_client.test_connection()

        if is_connected:
            # Update last_connected timestamp
            await db_service.update_environment(
                environment_id,
                MOCK_TENANT_ID,
                {"last_connected": datetime.utcnow().isoformat()}
            )

        return {
            "success": is_connected,
            "message": "Connected" if is_connected else "Connection failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update connection status: {str(e)}"
        )


@router.post("/{environment_id}/sync")
async def sync_environment(environment_id: str):
    """
    Sync workflows, executions, credentials, tags, and users from N8N to database.
    This will:
    - Query N8N API for workflows, executions, credentials, tags, and users
    - Delete rows that don't exist in N8N
    - Add rows that exist in N8N but not in database
    - Update rows that exist in both
    """
    try:
        # Get environment details
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create N8N client for this environment
        n8n_client = N8NClient(
            base_url=environment.get("n8n_base_url"),
            api_key=environment.get("n8n_api_key")
        )

        # Test connection first
        is_connected = await n8n_client.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to N8N instance. Please check environment configuration."
            )

        sync_results = {
            "workflows": {"synced": 0, "errors": []},
            "executions": {"synced": 0, "errors": []},
            "credentials": {"synced": 0, "errors": []},
            "users": {"synced": 0, "errors": []},
            "tags": {"synced": 0, "errors": []}
        }

        # Sync workflows
        try:
            workflows = await n8n_client.get_workflows()
            
            # Compute analysis for each workflow
            from app.services.workflow_analysis_service import analyze_workflow
            workflows_with_analysis = {}
            for workflow in workflows:
                try:
                    analysis = analyze_workflow(workflow)
                    workflows_with_analysis[workflow.get("id")] = analysis
                except Exception as e:
                    # Log error but continue sync - analysis is optional
                    import logging
                    logging.warning(f"Failed to analyze workflow {workflow.get('id', 'unknown')}: {str(e)}")
                    # Continue without analysis for this workflow
            
            synced_workflows = await db_service.sync_workflows_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                workflows,
                workflows_with_analysis=workflows_with_analysis if workflows_with_analysis else None
            )
            sync_results["workflows"]["synced"] = len(synced_workflows)

            # Update workflow count on environment
            await db_service.update_environment_workflow_count(
                environment_id,
                MOCK_TENANT_ID,
                len(synced_workflows)
            )
        except Exception as e:
            sync_results["workflows"]["errors"].append(str(e))

        # Sync executions
        try:
            executions = await n8n_client.get_executions(limit=100)
            synced_executions = await db_service.sync_executions_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                executions
            )
            sync_results["executions"]["synced"] = len(synced_executions)
        except Exception as e:
            sync_results["executions"]["errors"].append(str(e))

        # Sync credentials
        try:
            credentials = await n8n_client.get_credentials()
            synced_credentials = await db_service.sync_credentials_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                credentials
            )
            sync_results["credentials"]["synced"] = len(synced_credentials)
        except Exception as e:
            sync_results["credentials"]["errors"].append(str(e))

        # Sync users
        try:
            users = await n8n_client.get_users()
            synced_users = await db_service.sync_n8n_users_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                users
            )
            sync_results["users"]["synced"] = len(synced_users)
        except Exception as e:
            sync_results["users"]["errors"].append(str(e))

        # Sync tags
        try:
            tags = await n8n_client.get_tags()
            synced_tags = await db_service.sync_tags_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                tags
            )
            sync_results["tags"]["synced"] = len(synced_tags)
        except Exception as e:
            sync_results["tags"]["errors"].append(str(e))

        # Update last_connected timestamp
        await db_service.update_environment(
            environment_id,
            MOCK_TENANT_ID,
            {"last_connected": datetime.utcnow().isoformat()}
        )

        # Check if all syncs were successful
        has_errors = any(
            sync_results[key]["errors"]
            for key in ["workflows", "executions", "credentials", "users", "tags"]
        )

        return {
            "success": not has_errors,
            "message": "Sync completed successfully" if not has_errors else "Sync completed with errors",
            "results": sync_results
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync environment: {str(e)}"
        )


@router.post("/{environment_id}/sync-users")
async def sync_users_only(environment_id: str):
    """
    Sync only users from N8N to database.
    """
    try:
        # Get environment details
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create N8N client for this environment
        n8n_client = N8NClient(
            base_url=environment.get("n8n_base_url"),
            api_key=environment.get("n8n_api_key")
        )

        # Test connection first
        is_connected = await n8n_client.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to N8N instance. Please check environment configuration."
            )

        # Sync users only
        try:
            users = await n8n_client.get_users()
            synced_users = await db_service.sync_n8n_users_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                users
            )

            return {
                "success": True,
                "message": "Users synced successfully",
                "synced": len(synced_users)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to sync users: {str(e)}",
                "synced": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync users: {str(e)}"
        )


@router.post("/{environment_id}/sync-executions")
async def sync_executions_only(environment_id: str):
    """
    Sync only executions from N8N to database.
    """
    try:
        # Get environment details
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create N8N client for this environment
        n8n_client = N8NClient(
            base_url=environment.get("n8n_base_url"),
            api_key=environment.get("n8n_api_key")
        )

        # Test connection first
        is_connected = await n8n_client.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to N8N instance. Please check environment configuration."
            )

        # Sync executions only
        try:
            executions = await n8n_client.get_executions(limit=100)
            synced_executions = await db_service.sync_executions_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                executions
            )

            return {
                "success": True,
                "message": "Executions synced successfully",
                "synced": len(synced_executions)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to sync executions: {str(e)}",
                "synced": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync executions: {str(e)}"
        )


@router.post("/{environment_id}/sync-tags")
async def sync_tags_only(environment_id: str):
    """
    Sync only tags from N8N to database.
    """
    try:
        # Get environment details
        environment = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create N8N client for this environment
        n8n_client = N8NClient(
            base_url=environment.get("n8n_base_url"),
            api_key=environment.get("n8n_api_key")
        )

        # Test connection first
        is_connected = await n8n_client.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to N8N instance. Please check environment configuration."
            )

        # Sync tags only
        try:
            tags = await n8n_client.get_tags()
            synced_tags = await db_service.sync_tags_from_n8n(
                MOCK_TENANT_ID,
                environment_id,
                tags
            )

            return {
                "success": True,
                "message": "Tags synced successfully",
                "synced": len(synced_tags)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to sync tags: {str(e)}",
                "synced": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync tags: {str(e)}"
        )


