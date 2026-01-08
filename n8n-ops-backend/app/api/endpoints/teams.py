from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import secrets
import logging

from app.schemas.team import (
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamMemberResponse,
    TeamLimitsResponse
)
from app.services.database import db_service
from app.core.entitlements_gate import require_entitlement
from app.services.email_service import email_service
from app.services.auth_service import get_current_user
from app.services.feature_service import feature_service
from app.services.entitlements_service import entitlements_service

router = APIRouter()
logger = logging.getLogger(__name__)


# Entitlement gates for RBAC features

def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


@router.get("/", response_model=List[TeamMemberResponse])
async def get_team_members(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get all team members for the current tenant"""
    try:
        response = db_service.client.table("users").select("*").eq(
            "tenant_id", get_tenant_id(user_info)
        ).order("created_at", desc=False).execute()

        return response.data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team members: {str(e)}"
        )


@router.get("/limits", response_model=TeamLimitsResponse)
async def get_team_limits(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get team member limits and current usage based on subscription plan"""
    try:
        tenant_id = get_tenant_id(user_info)

        # Use entitlements_service for consistent limit checking
        can_add, message, current_members, max_members = await entitlements_service.can_add_team_member(tenant_id)

        return {
            "current_members": current_members,
            "max_members": max_members,
            "can_add_more": can_add
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team limits: {str(e)}"
        )


@router.get("/{member_id}", response_model=TeamMemberResponse)
async def get_team_member(
    member_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get a specific team member"""
    try:
        tenant_id = get_tenant_id(user_info)
        response = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        return response.data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team member: {str(e)}"
        )


@router.post("/", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def create_team_member(
    member: TeamMemberCreate,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """
    Add a new team member.

    This endpoint enforces plan-based team member limits server-side.
    The entitlements_service ensures tenants cannot exceed their plan's
    team member quota (e.g., 1 for Free, 10 for Pro, unlimited for Agency/Enterprise).
    """
    try:
        tenant_id = get_tenant_id(user_info)
        user = user_info.get("user", {})
        user_id = user.get("id")

        # Check if email already exists
        existing = db_service.client.table("users").select("id").eq(
            "email", member.email
        ).execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )

        # Enforce team member limit with server-side validation
        # This prevents bypassing the limit through direct API calls
        can_add, message, current, limit = await entitlements_service.can_add_team_member(tenant_id)
        if not can_add:
            logger.warning(
                f"Team member creation blocked for tenant {tenant_id}: "
                f"{current}/{limit} members (limit reached)"
            )
            await entitlements_service.enforce_team_member_limit(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint="/api/teams"
            )

        # Generate invitation token
        invitation_token = secrets.token_urlsafe(32)
        
        # Get tenant info for email
        tenant_response = db_service.client.table("tenants").select("name").eq(
            "id", tenant_id
        ).single().execute()
        org_name = tenant_response.data.get("name", "the organization") if tenant_response.data else "the organization"
        
        # Get current user info for inviter name
        user = user_info.get("user") or {}
        inviter_name = user.get("name") or user.get("email") or "A team administrator"
        
        # Create team member
        from datetime import datetime
        member_data = {
            "tenant_id": tenant_id,
            "email": member.email.lower().strip(),
            "name": member.name,
            "role": member.role,
            "status": "pending",  # Will be active after they accept invitation
            "invitation_token": invitation_token,
            "invited_at": datetime.utcnow().isoformat()
        }

        response = db_service.client.table("users").insert(member_data).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create team member"
            )

        logger.info(
            f"Team member '{member.email}' invited for tenant {tenant_id}. "
            f"Usage: {current + 1}/{limit}"
        )

        # Send invitation email
        try:
            email_sent = await email_service.send_team_invitation(
                to_email=member.email.lower().strip(),
                to_name=member.name,
                organization_name=org_name,
                inviter_name=inviter_name,
                role=member.role,
                invitation_token=invitation_token
            )
            
            if not email_sent:
                logger.warning(f"Failed to send invitation email to {member.email}, but team member was created")
        except Exception as email_error:
            logger.error(f"Error sending invitation email to {member.email}: {str(email_error)}")
            # Don't fail the request if email fails

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        # Check if it's the team member limit trigger
        if "Team member limit reached" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create team member: {str(e)}"
        )


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    member: TeamMemberUpdate,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Update a team member"""
    try:
        tenant_id = get_tenant_id(user_info)
        # Check if member exists
        existing = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        # Build update data
        update_data = {k: v for k, v in member.dict(exclude_unset=True).items() if v is not None}

        if not update_data:
            return existing.data

        # Update team member
        response = db_service.client.table("users").update(update_data).eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update team member: {str(e)}"
        )


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_member(
    member_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Remove a team member"""
    try:
        tenant_id = get_tenant_id(user_info)
        # Check if member exists
        existing = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        # Don't allow deleting the last admin
        if existing.data.get("role") == "admin":
            admin_count_response = db_service.client.table("users").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("role", "admin").eq("status", "active").execute()

            if admin_count_response.count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last admin user"
                )

        # Delete team member
        db_service.client.table("users").delete().eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete team member: {str(e)}"
        )


@router.post("/{member_id}/resend-invite")
async def resend_invitation(
    member_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Resend invitation email to a pending team member"""
    try:
        tenant_id = get_tenant_id(user_info)
        # Check if member exists and is pending
        member = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", tenant_id).single().execute()

        if not member.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        if member.data.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already active"
            )

        # Get tenant and inviter info
        tenant_response = db_service.client.table("tenants").select("name").eq(
            "id", tenant_id
        ).single().execute()
        org_name = tenant_response.data.get("name", "the organization") if tenant_response.data else "the organization"
        
        user = user_info.get("user") or {}
        inviter_name = user.get("name") or user.get("email") or "A team administrator"
        
        # Get or generate invitation token
        invitation_token = member.data.get("invitation_token")
        if not invitation_token:
            invitation_token = secrets.token_urlsafe(32)
            from datetime import datetime
            db_service.client.table("users").update({
                "invitation_token": invitation_token,
                "invited_at": datetime.utcnow().isoformat()
            }).eq("id", member_id).execute()

        # Send invitation email
        try:
            email_sent = await email_service.send_team_invitation(
                to_email=member.data.get("email"),
                to_name=member.data.get("name"),
                organization_name=org_name,
                inviter_name=inviter_name,
                role=member.data.get("role", "developer"),
                invitation_token=invitation_token
            )
            
            if not email_sent:
                logger.warning(f"Failed to resend invitation email to {member.data.get('email')}")
        except Exception as email_error:
            logger.error(f"Error resending invitation email: {str(email_error)}")

        return {"message": "Invitation sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend invitation: {str(e)}"
        )
