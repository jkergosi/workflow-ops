from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from app.services.database import db_service
from app.services.auth_service import get_current_user

router = APIRouter()

# Fallback tenant ID (should not be used in production)
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def get_tenant_id(user_info: dict) -> str:
    """Extract tenant_id from user_info, with fallback to MOCK_TENANT_ID"""
    return user_info.get("tenant", {}).get("id", MOCK_TENANT_ID)


@router.get("/", response_model=List[Dict[str, Any]])
async def get_executions(
    environment_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    user_info: dict = Depends(get_current_user)
):
    """Get all executions from the database cache, optionally filtered by environment and workflow"""
    try:
        tenant_id = get_tenant_id(user_info)
        executions = await db_service.get_executions(
            tenant_id,
            environment_id=environment_id,
            workflow_id=workflow_id
        )

        # Transform snake_case to camelCase for frontend
        transformed_executions = []
        for execution in executions:
            transformed_executions.append({
                "id": execution.get("id"),
                "executionId": execution.get("execution_id"),
                "workflowId": execution.get("workflow_id"),
                "workflowName": execution.get("workflow_name"),
                "status": execution.get("status"),
                "mode": execution.get("mode"),
                "startedAt": execution.get("started_at"),
                "finishedAt": execution.get("finished_at"),
                "executionTime": execution.get("execution_time"),
                "data": execution.get("data"),
                "tenantId": execution.get("tenant_id"),
                "environmentId": execution.get("environment_id"),
                "createdAt": execution.get("created_at"),
                "updatedAt": execution.get("updated_at"),
            })

        return transformed_executions

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch executions: {str(e)}"
        )


@router.get("/{execution_id}", response_model=Dict[str, Any])
async def get_execution(
    execution_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Get a specific execution by ID"""
    try:
        tenant_id = get_tenant_id(user_info)
        execution = await db_service.get_execution(execution_id, tenant_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found"
            )

        # Transform snake_case to camelCase for frontend
        return {
            "id": execution.get("id"),
            "executionId": execution.get("execution_id"),
            "workflowId": execution.get("workflow_id"),
            "workflowName": execution.get("workflow_name"),
            "status": execution.get("status"),
            "mode": execution.get("mode"),
            "startedAt": execution.get("started_at"),
            "finishedAt": execution.get("finished_at"),
            "executionTime": execution.get("execution_time"),
            "data": execution.get("data"),
            "tenantId": execution.get("tenant_id"),
            "environmentId": execution.get("environment_id"),
            "createdAt": execution.get("created_at"),
            "updatedAt": execution.get("updated_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch execution: {str(e)}"
        )
