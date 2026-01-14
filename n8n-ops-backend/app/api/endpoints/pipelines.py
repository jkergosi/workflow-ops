"""
Pipelines API endpoints for managing promotion pipelines
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Any, Dict
from datetime import datetime
import uuid
import logging

from app.services.feature_service import feature_service
from app.core.feature_gate import require_feature
from app.core.entitlements_gate import require_entitlement
from app.services.database import db_service
from app.schemas.pipeline import PipelineCreate, PipelineUpdate, PipelineResponse
from app.schemas.pagination import PaginatedResponse
from app.services.auth_service import get_current_user
from app.core.rbac import require_tenant_admin

logger = logging.getLogger(__name__)

router = APIRouter()

def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


def transform_pipeline(pipeline: Dict[str, Any]) -> Dict[str, Any]:
    """Transform database pipeline record to response format."""
    return {
        "id": pipeline.get("id"),
        "tenant_id": pipeline.get("tenant_id"),
        "name": pipeline.get("name"),
        "description": pipeline.get("description"),
        "is_active": pipeline.get("is_active", True),
        "environment_ids": pipeline.get("environment_ids", []),
        "stages": pipeline.get("stages", []),
        "last_modified_by": pipeline.get("last_modified_by"),
        "last_modified_at": pipeline.get("last_modified_at", pipeline.get("updated_at")),
        "created_at": pipeline.get("created_at"),
        "updated_at": pipeline.get("updated_at"),
    }


@router.get("", response_model=PaginatedResponse[PipelineResponse])
@router.get("/", response_model=PaginatedResponse[PipelineResponse])
async def get_pipelines(
    include_inactive: bool = Query(True, description="Include inactive/deactivated pipelines"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get all pipelines for the tenant with pagination.
    Requires Pro or Enterprise plan with environment_promotion feature.

    Args:
        include_inactive: If True (default), returns all pipelines. If False, returns only active pipelines.
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
    """
    try:
        logger.info(f"API get_pipelines called: include_inactive={include_inactive}, page={page}, page_size={page_size}")
        tenant_id = get_tenant_id(user_info)

        # Get total count for pagination
        all_pipelines = await db_service.get_pipelines(tenant_id, include_inactive=include_inactive)
        total = len(all_pipelines)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_pipelines = all_pipelines[start_idx:end_idx]

        logger.info(f"Database returned {total} total pipelines, returning page {page} with {len(paginated_pipelines)} items")

        # Transform database records to response format
        result = []
        for pipeline in paginated_pipelines:
            try:
                result.append(transform_pipeline(pipeline))
            except Exception as e:
                logger.error(f"Error transforming pipeline {pipeline.get('id', 'unknown')}: {str(e)}", exc_info=True)
                continue

        has_more = page < total_pages

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "hasMore": has_more,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pipelines: {str(e)}"
        )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get a specific pipeline by ID.
    """
    try:
        pipeline = await db_service.get_pipeline(pipeline_id, get_tenant_id(user_info))
        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        return {
            "id": pipeline.get("id"),
            "tenant_id": pipeline.get("tenant_id"),
            "name": pipeline.get("name"),
            "description": pipeline.get("description"),
            "is_active": pipeline.get("is_active", True),
            "environment_ids": pipeline.get("environment_ids", []),
            "stages": pipeline.get("stages", []),
            "last_modified_by": pipeline.get("last_modified_by"),
            "last_modified_at": pipeline.get("last_modified_at", pipeline.get("updated_at")),
            "created_at": pipeline.get("created_at"),
            "updated_at": pipeline.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pipeline: {str(e)}"
        )


@router.post("", response_model=PipelineResponse)
@router.post("/", response_model=PipelineResponse)
async def create_pipeline(
    pipeline: PipelineCreate,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Create a new pipeline.
    """
    try:
        # Validate minimum 2 environments
        if len(pipeline.environment_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 environments are required"
            )

        # MVP: Enforce single-hop pipelines (exactly 2 environments, 1 stage)
        if len(pipeline.environment_ids) > 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multi-stage pipelines are not supported in MVP. Create separate pipelines for each hop."
            )

        # Validate no duplicate environments
        if len(pipeline.environment_ids) != len(set(pipeline.environment_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate environments are not allowed"
            )
        
        # Validate stages match environment pairs
        expected_stages = len(pipeline.environment_ids) - 1
        if len(pipeline.stages) != expected_stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Expected {expected_stages} stages for {len(pipeline.environment_ids)} environments"
            )
        
        # Validate stage environment IDs are valid UUIDs and not undefined
        for i, stage in enumerate(pipeline.stages):
            if not stage.source_environment_id or stage.source_environment_id == "undefined":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stage {i + 1} has invalid source_environment_id: {stage.source_environment_id}"
                )
            if not stage.target_environment_id or stage.target_environment_id == "undefined":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stage {i + 1} has invalid target_environment_id: {stage.target_environment_id}"
                )
            # Validate UUID format
            try:
                uuid.UUID(stage.source_environment_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stage {i + 1} source_environment_id is not a valid UUID: {stage.source_environment_id}"
                )
            try:
                uuid.UUID(stage.target_environment_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stage {i + 1} target_environment_id is not a valid UUID: {stage.target_environment_id}"
                )
        
        # Prepare data for database
        pipeline_data = {
            "tenant_id": get_tenant_id(user_info),
            "name": pipeline.name,
            "description": pipeline.description,
            "is_active": pipeline.is_active,
            "environment_ids": pipeline.environment_ids,
            "stages": [stage.dict() for stage in pipeline.stages],
            "last_modified_by": None,  # TODO: Get from auth
            "last_modified_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        created = await db_service.create_pipeline(pipeline_data)
        
        return {
            "id": created.get("id"),
            "tenant_id": created.get("tenant_id"),
            "name": created.get("name"),
            "description": created.get("description"),
            "is_active": created.get("is_active", True),
            "environment_ids": created.get("environment_ids", []),
            "stages": created.get("stages", []),
            "last_modified_by": created.get("last_modified_by"),
            "last_modified_at": created.get("last_modified_at", created.get("updated_at")),
            "created_at": created.get("created_at"),
            "updated_at": created.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create pipeline: {str(e)}"
        )


@router.patch("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    pipeline: PipelineUpdate,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Update an existing pipeline.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get existing pipeline
        existing = await db_service.get_pipeline(pipeline_id, tenant_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        # Prepare update data
        update_data = {}
        if pipeline.name is not None:
            update_data["name"] = pipeline.name
        if pipeline.description is not None:
            update_data["description"] = pipeline.description
        if pipeline.is_active is not None:
            update_data["is_active"] = pipeline.is_active
        if pipeline.environment_ids is not None:
            # Validate minimum 2 environments
            if len(pipeline.environment_ids) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 2 environments are required"
                )
            # MVP: Enforce single-hop pipelines (exactly 2 environments, 1 stage)
            if len(pipeline.environment_ids) > 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Multi-stage pipelines are not supported in MVP. Create separate pipelines for each hop."
                )
            # Validate no duplicates
            if len(pipeline.environment_ids) != len(set(pipeline.environment_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate environments are not allowed"
                )
            update_data["environment_ids"] = pipeline.environment_ids
        if pipeline.stages is not None:
            # Validate stages match environment pairs
            env_ids = pipeline.environment_ids if pipeline.environment_ids else existing.get("environment_ids", [])
            expected_stages = len(env_ids) - 1
            if len(pipeline.stages) != expected_stages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Expected {expected_stages} stages for {len(env_ids)} environments"
                )

            # Validate stage environment IDs are valid UUIDs and not undefined
            for i, stage in enumerate(pipeline.stages):
                if not stage.source_environment_id or stage.source_environment_id == "undefined":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stage {i + 1} has invalid source_environment_id: {stage.source_environment_id}"
                    )
                if not stage.target_environment_id or stage.target_environment_id == "undefined":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stage {i + 1} has invalid target_environment_id: {stage.target_environment_id}"
                    )
                # Validate UUID format
                try:
                    uuid.UUID(stage.source_environment_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stage {i + 1} source_environment_id is not a valid UUID: {stage.source_environment_id}"
                    )
                try:
                    uuid.UUID(stage.target_environment_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Stage {i + 1} target_environment_id is not a valid UUID: {stage.target_environment_id}"
                    )

            update_data["stages"] = [stage.dict() for stage in pipeline.stages]
        
        update_data["last_modified_by"] = None  # TODO: Get from auth
        update_data["last_modified_at"] = datetime.utcnow().isoformat()
        
        updated = await db_service.update_pipeline(pipeline_id, tenant_id, update_data)
        
        return {
            "id": updated.get("id"),
            "tenant_id": updated.get("tenant_id"),
            "name": updated.get("name"),
            "description": updated.get("description"),
            "is_active": updated.get("is_active", True),
            "environment_ids": updated.get("environment_ids", []),
            "stages": updated.get("stages", []),
            "last_modified_by": updated.get("last_modified_by"),
            "last_modified_at": updated.get("last_modified_at", updated.get("updated_at")),
            "created_at": updated.get("created_at"),
            "updated_at": updated.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update pipeline: {str(e)}"
        )


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Delete a pipeline.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        existing = await db_service.get_pipeline(pipeline_id, tenant_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        await db_service.delete_pipeline(pipeline_id, tenant_id)
        
        return {"success": True, "message": "Pipeline deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete pipeline: {str(e)}"
        )

