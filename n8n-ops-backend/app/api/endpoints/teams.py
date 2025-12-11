from fastapi import APIRouter, HTTPException, status, Depends
from typing import List

from app.schemas.team import (
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamMemberResponse,
    TeamLimitsResponse
)
from app.services.database import db_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()


# Entitlement gates for RBAC features

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/", response_model=List[TeamMemberResponse])
async def get_team_members(
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get all team members for the current tenant"""
    try:
        response = db_service.client.table("users").select("*").eq(
            "tenant_id", MOCK_TENANT_ID
        ).order("created_at", desc=False).execute()

        return response.data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team members: {str(e)}"
        )


@router.get("/limits", response_model=TeamLimitsResponse)
async def get_team_limits(
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get team member limits based on subscription plan"""
    try:
        # Get current active team members count
        members_response = db_service.client.table("users").select(
            "id", count="exact"
        ).eq("tenant_id", MOCK_TENANT_ID).eq("status", "active").execute()

        current_members = members_response.count or 0

        # Get plan limits
        sub_response = db_service.client.table("subscriptions").select(
            "*, plan:plan_id(max_team_members)"
        ).eq("tenant_id", MOCK_TENANT_ID).single().execute()

        max_members = None
        if sub_response.data and sub_response.data.get("plan"):
            max_members = sub_response.data["plan"].get("max_team_members")

        can_add_more = True
        if max_members is not None:
            can_add_more = current_members < max_members

        return {
            "current_members": current_members,
            "max_members": max_members,
            "can_add_more": can_add_more
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team limits: {str(e)}"
        )


@router.get("/{member_id}", response_model=TeamMemberResponse)
async def get_team_member(
    member_id: str,
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Get a specific team member"""
    try:
        response = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", MOCK_TENANT_ID).single().execute()

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
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Add a new team member"""
    try:
        # Check if email already exists
        existing = db_service.client.table("users").select("id").eq(
            "email", member.email
        ).execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )

        # Check team member limits (trigger will enforce this, but check anyway)
        limits = await get_team_limits()
        if not limits["can_add_more"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Team member limit reached ({limits['max_members']}). Upgrade your plan to add more members."
            )

        # Create team member
        member_data = {
            "tenant_id": MOCK_TENANT_ID,
            "email": member.email,
            "name": member.name,
            "role": member.role,
            "status": "pending"  # Will be active after they accept invitation
        }

        response = db_service.client.table("users").insert(member_data).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create team member"
            )

        # TODO: Send invitation email

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
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Update a team member"""
    try:
        # Check if member exists
        existing = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", MOCK_TENANT_ID).single().execute()

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
        ).eq("tenant_id", MOCK_TENANT_ID).execute()

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
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Remove a team member"""
    try:
        # Check if member exists
        existing = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", MOCK_TENANT_ID).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )

        # Don't allow deleting the last admin
        if existing.data.get("role") == "admin":
            admin_count_response = db_service.client.table("users").select(
                "id", count="exact"
            ).eq("tenant_id", MOCK_TENANT_ID).eq("role", "admin").eq("status", "active").execute()

            if admin_count_response.count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last admin user"
                )

        # Delete team member
        db_service.client.table("users").delete().eq(
            "id", member_id
        ).eq("tenant_id", MOCK_TENANT_ID).execute()

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
    _: dict = Depends(require_entitlement("rbac_basic"))
):
    """Resend invitation email to a pending team member"""
    try:
        # Check if member exists and is pending
        member = db_service.client.table("users").select("*").eq(
            "id", member_id
        ).eq("tenant_id", MOCK_TENANT_ID).single().execute()

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

        # TODO: Send invitation email

        return {"message": "Invitation sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend invitation: {str(e)}"
        )
