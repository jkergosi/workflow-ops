from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)

from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.services.auth_service import get_current_user
from app.schemas.credential import (
    CredentialCreate,
    CredentialUpdate,
    CredentialResponse,
    CredentialTypeSchema,
    CredentialSyncResult,
)
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter()


def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


def parse_used_by_workflows(credential: dict) -> dict:
    """Extract used_by_workflows from credential_data"""
    # First check if it's stored directly on the credential
    used_by = credential.get("used_by_workflows")

    # If not, check credential_data (where it's stored in the JSON)
    if not used_by:
        credential_data = credential.get("credential_data", {})
        if isinstance(credential_data, dict):
            used_by = credential_data.get("used_by_workflows")

    # Parse if it's a JSON string
    if isinstance(used_by, str):
        try:
            credential["used_by_workflows"] = json.loads(used_by)
        except (json.JSONDecodeError, TypeError):
            credential["used_by_workflows"] = []
    elif isinstance(used_by, list):
        credential["used_by_workflows"] = used_by
    else:
        credential["used_by_workflows"] = []

    return credential


@router.get("/", response_model=PaginatedResponse[dict])
async def get_credentials(
    environment_type: Optional[str] = None,
    environment_id: Optional[str] = None,
    search: Optional[str] = Query(None, description="Search by name or type"),
    credential_type: Optional[str] = Query(None, description="Filter by credential type"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    user_info: dict = Depends(get_current_user),
):
    """Get credentials with pagination and optional filters.

    Returns a paginated list of credentials with the standard pagination envelope.
    Credentials are ordered by name ASC for deterministic pagination.

    Query Parameters:
    - page: Page number (1-indexed, default: 1)
    - page_size: Items per page (default: 50, max: 100)
    - environment_type: Filter by environment type (optional)
    - environment_id: Filter by environment ID (optional)
    - search: Search by name or type (optional)
    - credential_type: Filter by credential type (optional)
    """
    try:
        tenant_id = get_tenant_id(user_info)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        offset = (page - 1) * page_size

        # Get all environments first for lookup (include n8n_base_url for N8N links)
        envs_response = db_service.client.table("environments").select(
            "id, n8n_name, n8n_type, n8n_base_url"
        ).eq("tenant_id", tenant_id).execute()
        env_lookup = {env["id"]: {"id": env["id"], "name": env["n8n_name"], "type": env["n8n_type"], "n8n_base_url": env["n8n_base_url"]} for env in envs_response.data}

        # Resolve environment_id from either parameter
        resolved_env_id = environment_id
        if not resolved_env_id and environment_type:
            # Resolve environment type to environment ID
            env_config = await db_service.get_environment_by_type(tenant_id, environment_type)
            if not env_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Environment '{environment_type}' not configured"
                )
            resolved_env_id = env_config.get("id")

        # Build base query for counting
        count_query = db_service.client.table("credentials").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).eq("is_deleted", False)

        # Build base query for fetching
        data_query = db_service.client.table("credentials").select(
            "*"
        ).eq("tenant_id", tenant_id).eq("is_deleted", False)

        # Apply environment filter
        if resolved_env_id:
            count_query = count_query.eq("environment_id", resolved_env_id)
            data_query = data_query.eq("environment_id", resolved_env_id)

        # Apply credential type filter
        if credential_type:
            count_query = count_query.eq("type", credential_type)
            data_query = data_query.eq("type", credential_type)

        # Apply search filter (ilike for case-insensitive)
        if search:
            search_pattern = f"%{search}%"
            count_query = count_query.or_(f"name.ilike.{search_pattern},type.ilike.{search_pattern}")
            data_query = data_query.or_(f"name.ilike.{search_pattern},type.ilike.{search_pattern}")

        # Get total count
        count_response = count_query.execute()
        total = count_response.count if count_response.count is not None else 0

        # Get paginated data
        response = data_query.order("name").range(offset, offset + page_size - 1).execute()

        # Add environment info and parse used_by_workflows for each credential
        credentials = []
        for credential in response.data:
            credential["environment"] = env_lookup.get(credential.get("environment_id"))
            credential = parse_used_by_workflows(credential)
            credentials.append(credential)

        return PaginatedResponse.create(
            items=credentials,
            total=total,
            page=page,
            page_size=page_size
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credentials: {str(e)}"
        )


@router.get("/by-environment/{environment_id}")
async def get_credentials_by_environment(environment_id: str, user_info: dict = Depends(get_current_user)):
    """Get all credentials directly from N8N for a specific environment.

    Used for populating dropdowns when creating credential mappings.
    Returns fresh data from N8N, not from cache.
    """
    try:
        env = await db_service.get_environment(environment_id, get_tenant_id(user_info))
        if not env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        adapter = ProviderRegistry.get_adapter_for_environment(env)
        credentials = await adapter.get_credentials()

        return [
            {
                "id": cred.get("id"),
                "name": cred.get("name"),
                "type": cred.get("type"),
                "createdAt": cred.get("createdAt"),
                "updatedAt": cred.get("updatedAt"),
            }
            for cred in credentials
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credentials from N8N: {str(e)}"
        )


@router.get("/{credential_id}")
async def get_credential(credential_id: str, user_info: dict = Depends(get_current_user)):
    """Get a specific credential by ID"""
    try:
        tenant_id = get_tenant_id(user_info)
        response = db_service.client.table("credentials").select(
            "*"
        ).eq("id", credential_id).eq("tenant_id", tenant_id).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )

        credential = response.data
        # Add environment info
        if credential.get("environment_id"):
            env_response = db_service.client.table("environments").select(
                "id, n8n_name, n8n_type, n8n_base_url"
            ).eq("id", credential["environment_id"]).single().execute()
            if env_response.data:
                credential["environment"] = {
                    "id": env_response.data["id"],
                    "name": env_response.data["n8n_name"],
                    "type": env_response.data["n8n_type"],
                    "n8n_base_url": env_response.data["n8n_base_url"]
                }

        # Parse used_by_workflows
        credential = parse_used_by_workflows(credential)

        return credential

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credential: {str(e)}"
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_credential(credential: CredentialCreate, user_info: dict = Depends(get_current_user)):
    """Create a new credential in N8N and cache it in the database.

    The credential data (secrets) is sent to N8N where it's encrypted and stored.
    Only metadata is cached locally - actual secrets are never stored in our database.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get environment to verify it exists and get connection info
        env = await db_service.get_environment(credential.environment_id, tenant_id)
        if not env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(env)

        # Create credential in provider
        n8n_credential = await adapter.create_credential({
            "name": credential.name,
            "type": credential.type,
            "data": credential.data
        })

        # Cache the credential metadata (without secrets) in our database
        cached_credential = await db_service.upsert_credential(
            tenant_id,
            credential.environment_id,
            {
                "id": n8n_credential.get("id"),
                "name": n8n_credential.get("name"),
                "type": n8n_credential.get("type"),
                "createdAt": n8n_credential.get("createdAt"),
                "updatedAt": n8n_credential.get("updatedAt"),
                "used_by_workflows": []
            }
        )

        # Add environment info to response
        cached_credential["environment"] = {
            "id": env["id"],
            "name": env["n8n_name"],
            "type": env["n8n_type"],
            "n8n_base_url": env["n8n_base_url"]
        }

        return cached_credential

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create credential: {str(e)}"
        )


@router.put("/{credential_id}")
async def update_credential(credential_id: str, credential: CredentialUpdate, user_info: dict = Depends(get_current_user)):
    """Update an existing credential in N8N.

    Only provided fields will be updated. The credential data (secrets) is sent
    to N8N where it's encrypted. Secrets are never stored locally.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get existing credential to find the environment
        existing = db_service.client.table("credentials").select(
            "*"
        ).eq("id", credential_id).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )

        credential_record = existing.data
        n8n_credential_id = credential_record.get("n8n_credential_id")
        environment_id = credential_record.get("environment_id")

        # Get environment connection info
        env = await db_service.get_environment(environment_id, tenant_id)
        if not env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(env)

        # Build update payload (only include non-None fields)
        update_data = {}
        if credential.name is not None:
            update_data["name"] = credential.name
        if credential.data is not None:
            update_data["data"] = credential.data

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Update credential in provider
        n8n_updated = await adapter.update_credential(n8n_credential_id, update_data)

        # Update our cached metadata
        cache_update = {
            "name": n8n_updated.get("name"),
            "type": n8n_updated.get("type"),
            "updated_at": n8n_updated.get("updatedAt")
        }
        db_service.client.table("credentials").update(cache_update).eq(
            "id", credential_id
        ).eq("tenant_id", tenant_id).execute()

        # Return updated credential
        updated_response = db_service.client.table("credentials").select(
            "*"
        ).eq("id", credential_id).eq("tenant_id", tenant_id).single().execute()

        credential_response = updated_response.data
        credential_response["environment"] = {
            "id": env["id"],
            "name": env["n8n_name"],
            "type": env["n8n_type"],
            "n8n_base_url": env["n8n_base_url"]
        }
        credential_response = parse_used_by_workflows(credential_response)

        return credential_response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update credential: {str(e)}"
        )


@router.delete("/{credential_id}")
async def delete_credential(credential_id: str, delete_from_n8n: bool = True, user_info: dict = Depends(get_current_user)):
    """Delete a credential.

    By default, this deletes the credential from both N8N and our cache.
    Set delete_from_n8n=false to only remove from our cache (useful when
    the credential was already deleted in N8N).
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get existing credential
        existing = db_service.client.table("credentials").select(
            "*"
        ).eq("id", credential_id).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )

        credential_record = existing.data
        n8n_credential_id = credential_record.get("n8n_credential_id")
        environment_id = credential_record.get("environment_id")

        # Check if credential is being used by workflows
        used_by = credential_record.get("used_by_workflows", [])
        credential_data = credential_record.get("credential_data", {})
        if isinstance(credential_data, dict):
            used_by = used_by or credential_data.get("used_by_workflows", [])

        if used_by and len(used_by) > 0:
            workflow_names = [wf.get("name", "Unknown") for wf in used_by[:3]]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete credential: it is used by {len(used_by)} workflow(s): {', '.join(workflow_names)}"
            )

        # Delete from provider if requested
        if delete_from_n8n and n8n_credential_id and ":" not in n8n_credential_id:
            # Only attempt provider deletion if we have a valid ID (not a generated key)
            env = await db_service.get_environment(environment_id, tenant_id)
            if env:
                adapter = ProviderRegistry.get_adapter_for_environment(env)
                try:
                    await adapter.delete_credential(n8n_credential_id)
                except Exception as n8n_error:
                    # If N8N deletion fails, still allow local cache deletion
                    # but warn the user
                    pass

        # Soft delete in our cache
        db_service.client.table("credentials").update({
            "is_deleted": True
        }).eq("id", credential_id).eq("tenant_id", tenant_id).execute()

        return {"success": True, "message": "Credential deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete credential: {str(e)}"
        )


@router.get("/types/schema")
async def get_credential_types(environment_id: str, user_info: dict = Depends(get_current_user)):
    """Get available credential types from N8N.

    Returns the schema for each credential type, which can be used
    to build dynamic forms for creating credentials.
    """
    try:
        # Get environment connection info
        env = await db_service.get_environment(environment_id, get_tenant_id(user_info))
        if not env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(env)

        # Get credential types from provider
        types = await adapter.get_credential_types()

        return types

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credential types: {str(e)}"
        )


@router.post("/sync/{environment_id}")
async def sync_credentials(environment_id: str, user_info: dict = Depends(get_current_user)):
    """Sync credentials from N8N for a specific environment.

    Fetches all credentials from N8N and updates the local cache.
    This only syncs metadata - no secrets are stored locally.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get environment connection info
        env = await db_service.get_environment(environment_id, tenant_id)
        if not env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(env)

        # Test connection first
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to provider instance. Please check environment configuration."
            )

        # Fetch credentials from provider
        n8n_credentials = await adapter.get_credentials()
        
        if not n8n_credentials:
            logger.warning(f"No credentials returned from N8N for environment {environment_id}")
        
        logger.info(f"Fetched {len(n8n_credentials) if n8n_credentials else 0} credentials from N8N for environment {environment_id}")

        # Sync to database
        results = await db_service.sync_credentials_from_n8n(
            tenant_id,
            environment_id,
            n8n_credentials or []
        )

        return {
            "success": True,
            "synced": len(results),
            "message": f"Synced {len(results)} credentials from N8N"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync credentials for environment {environment_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync credentials: {str(e)}"
        )