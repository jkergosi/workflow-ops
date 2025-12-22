from fastapi import APIRouter, HTTPException, status, Depends
from typing import List

from app.schemas.environment_type import (
    EnvironmentTypeCreate,
    EnvironmentTypeUpdate,
    EnvironmentTypeResponse,
    EnvironmentTypeReorderRequest,
)
from app.services.database import db_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()

# TODO: Replace with real auth when implemented
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/", response_model=List[EnvironmentTypeResponse])
async def list_environment_types(
    _: dict = Depends(require_entitlement("environment_basic")),
):
    try:
        types = await db_service.get_environment_types(MOCK_TENANT_ID, ensure_defaults=True)
        return types
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list environment types: {str(e)}",
        )


@router.post("/", response_model=EnvironmentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_environment_type(
    payload: EnvironmentTypeCreate,
    _: dict = Depends(require_entitlement("environment_basic")),
):
    try:
        created = await db_service.create_environment_type(
            {
                "tenant_id": MOCK_TENANT_ID,
                "key": payload.key,
                "label": payload.label,
                "sort_order": payload.sort_order,
                "is_active": payload.is_active,
            }
        )
        return created
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create environment type: {str(e)}",
        )


@router.patch("/{environment_type_id}", response_model=EnvironmentTypeResponse)
async def update_environment_type(
    environment_type_id: str,
    payload: EnvironmentTypeUpdate,
    _: dict = Depends(require_entitlement("environment_basic")),
):
    try:
        update_data = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
        updated = await db_service.update_environment_type(environment_type_id, MOCK_TENANT_ID, update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment type not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update environment type: {str(e)}",
        )


@router.delete("/{environment_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment_type(
    environment_type_id: str,
    _: dict = Depends(require_entitlement("environment_basic")),
):
    try:
        await db_service.delete_environment_type(environment_type_id, MOCK_TENANT_ID)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete environment type: {str(e)}",
        )


@router.post("/reorder", response_model=List[EnvironmentTypeResponse])
async def reorder_environment_types(
    payload: EnvironmentTypeReorderRequest,
    _: dict = Depends(require_entitlement("environment_basic")),
):
    try:
        if not payload.ordered_ids:
            return await db_service.get_environment_types(MOCK_TENANT_ID, ensure_defaults=True)
        updated = await db_service.reorder_environment_types(MOCK_TENANT_ID, payload.ordered_ids)
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reorder environment types: {str(e)}",
        )

