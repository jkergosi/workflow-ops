from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from datetime import datetime

from app.services.database import db_service

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/")
async def get_n8n_users(environment_type: Optional[str] = None):
    """Get all N8N users, optionally filtered by environment type (dev, staging, production)"""
    try:
        # Get all environments first for lookup
        envs_response = db_service.client.table("environments").select(
            "id, n8n_name, n8n_type"
        ).eq("tenant_id", MOCK_TENANT_ID).execute()
        env_lookup = {env["id"]: {"id": env["id"], "name": env["n8n_name"], "type": env["n8n_type"]} for env in envs_response.data}

        if environment_type:
            # Resolve environment type to environment ID
            env_config = await db_service.get_environment_by_type(MOCK_TENANT_ID, environment_type)
            if not env_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Environment '{environment_type}' not configured"
                )
            environment_id = env_config.get("id")

            # Get users for specific environment
            response = db_service.client.table("n8n_users").select(
                "*"
            ).eq("tenant_id", MOCK_TENANT_ID).eq("environment_id", environment_id).eq("is_deleted", False).order("email").execute()
        else:
            # Get all users across all environments
            response = db_service.client.table("n8n_users").select(
                "*"
            ).eq("tenant_id", MOCK_TENANT_ID).eq("is_deleted", False).order("email").execute()

        # Add environment info to each user
        users = []
        for user in response.data:
            user["environment"] = env_lookup.get(user.get("environment_id"))
            users.append(user)

        return users

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch N8N users: {str(e)}"
        )


@router.get("/{user_id}")
async def get_n8n_user(user_id: str):
    """Get a specific N8N user by ID"""
    try:
        response = db_service.client.table("n8n_users").select(
            "*"
        ).eq("id", user_id).eq("tenant_id", MOCK_TENANT_ID).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="N8N user not found"
            )

        user = response.data
        # Add environment info
        if user.get("environment_id"):
            env_response = db_service.client.table("environments").select(
                "id, n8n_name, n8n_type"
            ).eq("id", user["environment_id"]).single().execute()
            if env_response.data:
                user["environment"] = {
                    "id": env_response.data["id"],
                    "name": env_response.data["n8n_name"],
                    "type": env_response.data["n8n_type"]
                }

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch N8N user: {str(e)}"
        )
