from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
import json

from app.services.database import db_service

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


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


@router.get("/")
async def get_credentials(environment_type: Optional[str] = None):
    """Get all credentials, optionally filtered by environment type (dev, staging, production)"""
    try:
        # Get all environments first for lookup (include n8n_base_url for N8N links)
        envs_response = db_service.client.table("environments").select(
            "id, n8n_name, n8n_type, n8n_base_url"
        ).eq("tenant_id", MOCK_TENANT_ID).execute()
        env_lookup = {env["id"]: {"id": env["id"], "name": env["n8n_name"], "type": env["n8n_type"], "n8n_base_url": env["n8n_base_url"]} for env in envs_response.data}

        if environment_type:
            # Resolve environment type to environment ID
            env_config = await db_service.get_environment_by_type(MOCK_TENANT_ID, environment_type)
            if not env_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Environment '{environment_type}' not configured"
                )
            environment_id = env_config.get("id")

            # Get credentials for specific environment
            response = db_service.client.table("credentials").select(
                "*"
            ).eq("tenant_id", MOCK_TENANT_ID).eq("environment_id", environment_id).eq("is_deleted", False).order("name").execute()
        else:
            # Get all credentials across all environments
            response = db_service.client.table("credentials").select(
                "*"
            ).eq("tenant_id", MOCK_TENANT_ID).eq("is_deleted", False).order("name").execute()

        # Add environment info and parse used_by_workflows for each credential
        credentials = []
        for credential in response.data:
            credential["environment"] = env_lookup.get(credential.get("environment_id"))
            credential = parse_used_by_workflows(credential)
            credentials.append(credential)

        return credentials

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch credentials: {str(e)}"
        )


@router.get("/{credential_id}")
async def get_credential(credential_id: str):
    """Get a specific credential by ID"""
    try:
        response = db_service.client.table("credentials").select(
            "*"
        ).eq("id", credential_id).eq("tenant_id", MOCK_TENANT_ID).single().execute()

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
