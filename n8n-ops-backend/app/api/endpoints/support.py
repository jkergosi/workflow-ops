from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any

from app.schemas.support import (
    SupportRequestCreate,
    SupportRequestResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.support_service import support_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()

# TODO: Replace with real auth when implemented
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_EMAIL = "dev@example.com"
MOCK_USER_ID = "user-001"


@router.post("/requests", response_model=SupportRequestResponse)
async def create_support_request(
    data: SupportRequestCreate,
    # _: dict = Depends(require_entitlement("support_enabled"))
) -> SupportRequestResponse:
    """
    Create a support request (bug report, feature request, or help request).

    The request is forwarded to n8n which creates the JSM ticket.
    Returns the JSM request key immediately.
    """
    try:
        # Build Issue Contract from request data
        contract = support_service.build_issue_contract(
            request=data,
            user_email=MOCK_USER_EMAIL,
            user_id=MOCK_USER_ID,
            tenant_id=MOCK_TENANT_ID,
            diagnostics=data.diagnostics
        )

        # Forward to n8n and get JSM key
        response = await support_service.forward_to_n8n(contract, MOCK_TENANT_ID)

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support request: {str(e)}"
        )


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    data: UploadUrlRequest,
    # _: dict = Depends(require_entitlement("support_enabled"))
) -> UploadUrlResponse:
    """
    Get a signed upload URL for file attachments.

    The frontend uses this URL to upload files directly to storage.
    """
    try:
        # For now, return mock URLs
        # TODO: Implement actual Supabase Storage signed URL generation
        import uuid
        file_id = str(uuid.uuid4())

        return UploadUrlResponse(
            upload_url=f"https://storage.example.com/upload/{file_id}",
            public_url=f"https://storage.example.com/public/{file_id}/{data.filename}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )
