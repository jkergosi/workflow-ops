"""
Pipelines API endpoints for managing promotion pipelines
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime
import uuid

from app.services.feature_service import feature_service
from app.core.feature_gate import require_feature
from app.core.entitlements_gate import require_entitlement
from app.services.database import db_service
from app.schemas.pipeline import PipelineCreate, PipelineUpdate, PipelineResponse

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/", response_model=List[PipelineResponse])
async def get_pipelines(
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get all pipelines for the tenant.
    Requires Pro or Enterprise plan with environment_promotion feature.
    """
    try:
        pipelines = await db_service.get_pipelines(MOCK_TENANT_ID)
        
        # Transform database records to response format
        result = []
        for pipeline in pipelines:
            result.append({
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
            })
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pipelines: {str(e)}"
        )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get a specific pipeline by ID.
    """
    try:
        pipeline = await db_service.get_pipeline(pipeline_id, MOCK_TENANT_ID)
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


@router.post("/", response_model=PipelineResponse)
async def create_pipeline(
    pipeline: PipelineCreate,
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
            "tenant_id": MOCK_TENANT_ID,
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
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Update an existing pipeline.
    """
    try:
        # Get existing pipeline
        existing = await db_service.get_pipeline(pipeline_id, MOCK_TENANT_ID)
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
        
        updated = await db_service.update_pipeline(pipeline_id, MOCK_TENANT_ID, update_data)
        
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
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Delete a pipeline (soft delete by setting is_active=false).
    """
    try:
        existing = await db_service.get_pipeline(pipeline_id, MOCK_TENANT_ID)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        await db_service.delete_pipeline(pipeline_id, MOCK_TENANT_ID)
        
        return {"success": True, "message": "Pipeline deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete pipeline: {str(e)}"
        )

