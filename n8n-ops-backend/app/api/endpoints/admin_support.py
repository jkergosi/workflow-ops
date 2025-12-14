from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any

from app.schemas.support import (
    SupportConfigResponse,
    SupportConfigUpdate,
)
from app.services.support_service import support_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()

# TODO: Replace with real auth when implemented
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@router.get("/config", response_model=SupportConfigResponse)
async def get_support_config(
    # _: dict = Depends(require_entitlement("admin_settings"))
) -> SupportConfigResponse:
    """
    Get support configuration for the tenant.

    Returns n8n webhook URL, JSM portal settings, and request type IDs.
    """
    try:
        config = await support_service.get_config(MOCK_TENANT_ID)

        if not config:
            # Return empty config if none exists
            return SupportConfigResponse(tenant_id=MOCK_TENANT_ID)

        return config

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get support config: {str(e)}"
        )


@router.put("/config", response_model=SupportConfigResponse)
async def update_support_config(
    data: SupportConfigUpdate,
    # _: dict = Depends(require_entitlement("admin_settings"))
) -> SupportConfigResponse:
    """
    Update support configuration for the tenant.

    Configures n8n webhook URL, JSM portal settings, and request type IDs.
    """
    try:
        config = await support_service.update_config(MOCK_TENANT_ID, data)
        return config

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update support config: {str(e)}"
        )


@router.post("/test-n8n", response_model=Dict[str, Any])
async def test_n8n_connection(
    # _: dict = Depends(require_entitlement("admin_settings"))
) -> Dict[str, Any]:
    """
    Test the n8n webhook connection.

    Sends a test payload to verify connectivity.
    """
    try:
        result = await support_service.test_n8n_connection(MOCK_TENANT_ID)
        return result

    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }
