"""
Promotions API endpoints for environment promotion (Pro/Enterprise feature)
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.services.feature_service import feature_service
from app.core.feature_gate import require_feature

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


# Request/Response Models
class PromoteRequest(BaseModel):
    workflow_id: str
    source_environment_id: str
    target_environment_id: str
    credential_mappings: Optional[dict] = None  # Enterprise only


class PromotionValidationResult(BaseModel):
    valid: bool
    warnings: List[str] = []
    errors: List[str] = []
    credential_issues: List[dict] = []
    missing_nodes: List[str] = []


class PromotionResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    source_environment: str
    target_environment: str
    status: str  # pending_approval, approved, rejected, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    promoted_by: Optional[str] = None
    approved_by: Optional[str] = None
    error_message: Optional[str] = None


class ApprovalRequest(BaseModel):
    action: str  # approve, reject
    comment: Optional[str] = None


@router.get("/")
async def list_promotions(
    status: Optional[str] = None,
    limit: int = 20,
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    List all promotions for the tenant.
    Requires Pro or Enterprise plan with environment_promotion feature.
    """
    # Placeholder - will be implemented in Phase 2
    return {
        "data": [],
        "total": 0,
        "message": "Promotions feature placeholder - coming soon"
    }


@router.post("/validate")
async def validate_promotion(
    request: PromoteRequest,
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    Pre-flight validation for a promotion.
    Checks credentials, nodes, webhooks, and other potential issues.
    """
    # Placeholder validation response
    return PromotionValidationResult(
        valid=True,
        warnings=["This is a placeholder - full validation coming soon"],
        errors=[],
        credential_issues=[],
        missing_nodes=[]
    )


@router.post("/promote")
async def promote_workflow(
    request: PromoteRequest,
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    Promote a workflow from source to target environment.
    Pro: Manual promotion
    Enterprise: Automated promotion with approval workflows
    """
    # Check if user has enterprise features for automated promotion
    features = await feature_service.get_tenant_features(MOCK_TENANT_ID)
    promotion_type = features.get("environment_promotion", False)

    if promotion_type == "automated":
        # Enterprise: Create pending approval
        return {
            "id": "placeholder-promotion-id",
            "status": "pending_approval",
            "message": "Promotion created and pending approval (Enterprise feature placeholder)"
        }
    else:
        # Pro: Manual immediate promotion
        return {
            "id": "placeholder-promotion-id",
            "status": "completed",
            "message": "Promotion completed (placeholder - actual promotion coming soon)"
        }


@router.get("/approvals")
async def get_pending_approvals(
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    Get workflows pending approval (Enterprise only).
    """
    features = await feature_service.get_tenant_features(MOCK_TENANT_ID)
    promotion_type = features.get("environment_promotion", False)

    if promotion_type != "automated":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approval workflows require Enterprise plan with automated promotions"
        )

    return {
        "data": [],
        "total": 0,
        "message": "Approvals placeholder - coming soon"
    }


@router.post("/approvals/{promotion_id}/approve")
async def approve_promotion(
    promotion_id: str,
    request: ApprovalRequest,
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    Approve or reject a pending promotion (Enterprise only).
    """
    features = await feature_service.get_tenant_features(MOCK_TENANT_ID)
    promotion_type = features.get("environment_promotion", False)

    if promotion_type != "automated":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Approval workflows require Enterprise plan with automated promotions"
        )

    return {
        "id": promotion_id,
        "action": request.action,
        "status": "approved" if request.action == "approve" else "rejected",
        "message": f"Promotion {request.action}d (placeholder)"
    }


@router.get("/{promotion_id}")
async def get_promotion(
    promotion_id: str,
    _: None = Depends(require_feature("environment_promotion"))
):
    """
    Get details of a specific promotion.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Promotion not found (placeholder - full implementation coming soon)"
    )
