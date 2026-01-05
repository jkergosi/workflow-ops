"""Admin endpoints for entitlements management (Phase 4)."""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.schemas.entitlements import (
    FeatureType,
    FeatureStatus,
    PlanResponse,
    FeatureMatrixEntry,
    FeatureMatrixResponse,
    PlanFeatureUpdate,
    PlanFeatureValueResponse,
    AdminFeatureResponse,
    AdminFeatureListResponse,
    AdminPlanResponse,
    AdminPlanListResponse,
    AuditAction,
    AuditEntityType,
)
from app.schemas.billing import (
    PlanMetadataUpdate,
    PlanLimitsUpdate,
    PlanRetentionDefaultsUpdate,
    PlanFeatureRequirementUpdate,
    PlanMetadataResponse,
    PlanLimitsResponse,
    PlanRetentionDefaultsResponse,
    PlanFeatureRequirementResponse,
)
from app.services.database import db_service
from app.services.audit_service import audit_service
from app.services.entitlements_service import entitlements_service
from app.core.platform_admin import require_platform_admin

router = APIRouter()


# =============================================================================
# Feature Management
# =============================================================================

@router.get("/features", response_model=AdminFeatureListResponse)
async def get_all_features(
    status_filter: Optional[str] = Query(None, description="Filter by status (active, deprecated, hidden)"),
    type_filter: Optional[str] = Query(None, description="Filter by type (flag, limit)"),
    _: dict = Depends(require_platform_admin()),
):
    """Get all features (admin only)."""
    try:
        query = db_service.client.table("features").select("*")

        if status_filter:
            query = query.eq("status", status_filter)
        if type_filter:
            query = query.eq("type", type_filter)

        response = query.order("name").execute()

        features = []
        for row in response.data or []:
            features.append(AdminFeatureResponse(
                id=row["id"],
                key=row["name"],
                display_name=row["display_name"],
                description=row.get("description"),
                type=row["type"],
                default_value=row.get("default_value", {}),
                status=row.get("status", "active"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        return AdminFeatureListResponse(
            features=features,
            total=len(features)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch features: {str(e)}"
        )


# Feature Matrix must come before /features/{feature_id} to avoid route conflict
@router.get("/features/matrix", response_model=FeatureMatrixResponse)
async def get_feature_matrix(_: dict = Depends(require_platform_admin())):
    """
    Get the full feature matrix showing all features and their values across all plans.
    This is the main admin view for managing entitlements.
    """
    try:
        # Get all plans
        plans_response = db_service.client.table("plans").select("*").order("sort_order").execute()
        plans = plans_response.data or []

        # Get all features
        features_response = db_service.client.table("features").select("*").order("name").execute()
        features = features_response.data or []

        # Get all plan-feature mappings
        plan_features_response = db_service.client.table("plan_features").select(
            "plan_id, feature_id, value"
        ).execute()
        plan_features = plan_features_response.data or []

        # Build lookup: {feature_id: {plan_id: value}}
        feature_plan_values = {}
        for pf in plan_features:
            feature_id = pf["feature_id"]
            plan_id = pf["plan_id"]
            if feature_id not in feature_plan_values:
                feature_plan_values[feature_id] = {}
            feature_plan_values[feature_id][plan_id] = pf["value"]

        # Build plan_id to plan_name lookup
        plan_id_to_name = {p["id"]: p["name"] for p in plans}

        # Build matrix entries
        matrix_entries = []
        for feature in features:
            feature_id = feature["id"]
            feature_type = feature["type"]

            # Build plan_values dict with plan names as keys
            plan_values = {}
            for plan in plans:
                plan_id = plan["id"]
                plan_name = plan["name"]
                if feature_id in feature_plan_values and plan_id in feature_plan_values[feature_id]:
                    raw_value = feature_plan_values[feature_id][plan_id]
                    # Extract the actual value based on feature type
                    if feature_type == "flag":
                        plan_values[plan_name] = raw_value.get("enabled", False)
                    else:  # limit
                        plan_values[plan_name] = raw_value.get("value", 0)
                else:
                    # Default value if no mapping exists
                    if feature_type == "flag":
                        plan_values[plan_name] = False
                    else:
                        plan_values[plan_name] = 0

            matrix_entries.append(FeatureMatrixEntry(
                feature_id=feature_id,
                feature_key=feature["name"],
                feature_display_name=feature["display_name"],
                feature_type=feature_type,
                description=feature.get("description"),
                status=feature.get("status", "active"),
                plan_values=plan_values,
            ))

        # Build plan responses
        plan_responses = [
            PlanResponse(
                id=p["id"],
                name=p["name"],
                display_name=p["display_name"],
                description=p.get("description"),
                sort_order=p.get("sort_order", 0),
                is_active=p.get("is_active", True),
            )
            for p in plans
        ]

        return FeatureMatrixResponse(
            features=matrix_entries,
            plans=plan_responses,
            total_features=len(matrix_entries),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feature matrix: {str(e)}"
        )


@router.get("/features/{feature_id}", response_model=AdminFeatureResponse)
async def get_feature(feature_id: str, _: dict = Depends(require_platform_admin())):
    """Get a specific feature (admin only)."""
    try:
        response = db_service.client.table("features").select("*").eq(
            "id", feature_id
        ).single().execute()

        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")

        row = response.data
        return AdminFeatureResponse(
            id=row["id"],
            key=row["name"],
            display_name=row["display_name"],
            description=row.get("description"),
            type=row["type"],
            default_value=row.get("default_value", {}),
            status=row.get("status", "active"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feature: {str(e)}"
        )


# =============================================================================
# Plan Management
# =============================================================================

@router.get("/plans", response_model=AdminPlanListResponse)
async def get_all_plans(_: dict = Depends(require_platform_admin())):
    """Get all plans with tenant counts (admin only)."""
    try:
        response = db_service.client.table("plans").select("*").order("sort_order").execute()

        plans = []
        for row in response.data or []:
            # Get tenant count for this plan
            tenant_count_response = db_service.client.table("tenant_plans").select(
                "id", count="exact"
            ).eq("plan_id", row["id"]).eq("is_active", True).execute()
            tenant_count = tenant_count_response.count or 0

            plans.append(AdminPlanResponse(
                id=row["id"],
                name=row["name"],
                display_name=row["display_name"],
                description=row.get("description"),
                sort_order=row.get("sort_order", 0),
                is_active=row.get("is_active", True),
                tenant_count=tenant_count,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        return AdminPlanListResponse(
            plans=plans,
            total=len(plans)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plans: {str(e)}"
        )


@router.get("/plans/{plan_id}", response_model=AdminPlanResponse)
async def get_plan(plan_id: str, _: dict = Depends(require_platform_admin())):
    """Get a specific plan (admin only)."""
    try:
        response = db_service.client.table("plans").select("*").eq(
            "id", plan_id
        ).single().execute()

        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

        row = response.data

        # Get tenant count
        tenant_count_response = db_service.client.table("tenant_plans").select(
            "id", count="exact"
        ).eq("plan_id", plan_id).eq("is_active", True).execute()
        tenant_count = tenant_count_response.count or 0

        return AdminPlanResponse(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row.get("description"),
            sort_order=row.get("sort_order", 0),
            is_active=row.get("is_active", True),
            tenant_count=tenant_count,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan: {str(e)}"
        )


# =============================================================================
# Plan-Feature Value Editing
# =============================================================================

@router.patch("/plans/{plan_id}/features/{feature_key}", response_model=PlanFeatureValueResponse)
async def update_plan_feature_value(
    plan_id: str,
    feature_key: str,
    update: PlanFeatureUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """
    Update a plan-feature value (admin only).
    This changes the base entitlement for all tenants on this plan.
    """
    try:
        # Verify plan exists
        plan_response = db_service.client.table("plans").select("id, name").eq(
            "id", plan_id
        ).single().execute()
        if not plan_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        plan = plan_response.data

        # Find feature by key
        feature_response = db_service.client.table("features").select("id, name, type").eq(
            "name", feature_key
        ).single().execute()
        if not feature_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Feature '{feature_key}' not found"
            )
        feature = feature_response.data

        # Validate value format based on feature type
        feature_type = feature["type"]
        if feature_type == "flag":
            if "enabled" not in update.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Flag features require {'enabled': true/false}"
                )
        elif feature_type == "limit":
            if "value" not in update.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Limit features require {'value': number}"
                )

        # Check if plan_feature mapping exists
        existing = db_service.client.table("plan_features").select("id, value").eq(
            "plan_id", plan_id
        ).eq("feature_id", feature["id"]).execute()

        old_value = None
        if existing.data:
            # Update existing mapping
            old_value = existing.data[0]["value"]
            db_service.client.table("plan_features").update({
                "value": update.value
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            # Create new mapping
            db_service.client.table("plan_features").insert({
                "plan_id": plan_id,
                "feature_id": feature["id"],
                "value": update.value,
            }).execute()

        # Log the change to audit
        await audit_service.log_config_change(
            tenant_id=None,  # System-wide change
            entity_type=AuditEntityType.PLAN_FEATURE,
            entity_id=f"{plan_id}:{feature['id']}",
            action=AuditAction.UPDATE if old_value else AuditAction.CREATE,
            old_value=old_value,
            new_value=update.value,
            feature_key=feature_key,
            reason=update.reason,
        )

        # Clear all caches since this affects all tenants on this plan
        entitlements_service.clear_cache()

        return PlanFeatureValueResponse(
            plan_id=plan_id,
            plan_name=plan["name"],
            feature_id=feature["id"],
            feature_key=feature_key,
            value=update.value,
            updated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan feature: {str(e)}"
        )


@router.get("/plans/{plan_id}/features", response_model=List[PlanFeatureValueResponse])
async def get_plan_features(plan_id: str, _: dict = Depends(require_platform_admin())):
    """Get all feature values for a specific plan (admin only)."""
    try:
        # Verify plan exists
        plan_response = db_service.client.table("plans").select("id, name").eq(
            "id", plan_id
        ).single().execute()
        if not plan_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        plan = plan_response.data

        # Get all plan-feature mappings with feature details
        response = db_service.client.table("plan_features").select(
            "*, feature:feature_id(id, name)"
        ).eq("plan_id", plan_id).execute()

        features = []
        for row in response.data or []:
            feature = row.get("feature", {}) or {}
            features.append(PlanFeatureValueResponse(
                plan_id=plan_id,
                plan_name=plan["name"],
                feature_id=feature.get("id", row["feature_id"]),
                feature_key=feature.get("name", ""),
                value=row["value"],
                updated_at=row.get("updated_at", datetime.utcnow()),
            ))

        return features

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan features: {str(e)}"
        )


# =============================================================================
# Bulk Operations
# =============================================================================

@router.post("/cache/clear")
async def clear_entitlements_cache(_: dict = Depends(require_platform_admin())):
    """Clear all entitlements caches (admin only). Use after bulk updates."""
    try:
        entitlements_service.clear_cache()
        return {"message": "Entitlements cache cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/debug/{tenant_id}")
async def debug_tenant_entitlements(tenant_id: str, _: dict = Depends(require_platform_admin())):
    """
    Debug endpoint to inspect tenant entitlements configuration.
    Shows tenant plan assignment, plan features, and computed entitlements.
    """
    try:
        # Get tenant plan assignment
        tenant_plan_response = db_service.client.table("tenant_plans").select(
            "*, plan:plan_id(id, name, display_name)"
        ).eq("tenant_id", tenant_id).execute()
        
        tenant_plan_data = None
        plan_id = None
        plan_name = None
        if tenant_plan_response.data and len(tenant_plan_response.data) > 0:
            tp = tenant_plan_response.data[0]
            plan = tp.get("plan", {})
            tenant_plan_data = {
                "plan_id": plan.get("id"),
                "plan_name": plan.get("name"),
                "plan_display_name": plan.get("display_name"),
                "entitlements_version": tp.get("entitlements_version", 1),
                "is_active": tp.get("is_active", True),
            }
            plan_id = plan.get("id")
            plan_name = plan.get("name")

        # Get all plans to find pro plan
        plans_response = db_service.client.table("plans").select("*").execute()
        plans = {p["name"]: p for p in (plans_response.data or [])}
        pro_plan_id = plans.get("pro", {}).get("id") if plans.get("pro") else None

        # Get workflow_ci_cd feature
        feature_response = db_service.client.table("features").select("*").eq(
            "name", "workflow_ci_cd"
        ).execute()
        workflow_ci_cd_feature = feature_response.data[0] if feature_response.data else None

        # Get plan features for the tenant's plan
        plan_features_data = []
        if plan_id:
            pf_response = db_service.client.table("plan_features").select(
                "*, feature:feature_id(id, name, type, display_name)"
            ).eq("plan_id", plan_id).execute()
            plan_features_data = pf_response.data or []

        # Get plan features for pro plan (for comparison)
        pro_plan_features = []
        if pro_plan_id:
            pf_pro_response = db_service.client.table("plan_features").select(
                "*, feature:feature_id(id, name, type, display_name)"
            ).eq("plan_id", pro_plan_id).execute()
            pro_plan_features = pf_pro_response.data or []

        # Get tenant overrides
        overrides_response = db_service.client.table("tenant_feature_overrides").select(
            "*, feature:feature_id(id, name, type)"
        ).eq("tenant_id", tenant_id).eq("is_active", True).execute()
        overrides = overrides_response.data or []

        # Get computed entitlements
        computed_entitlements = await entitlements_service.get_tenant_entitlements(tenant_id)
        workflow_ci_cd_enabled = computed_entitlements.get("features", {}).get("workflow_ci_cd", False)

        return {
            "tenant_id": tenant_id,
            "tenant_plan": tenant_plan_data,
            "pro_plan_id": pro_plan_id,
            "workflow_ci_cd_feature": {
                "id": workflow_ci_cd_feature.get("id"),
                "name": workflow_ci_cd_feature.get("name"),
                "type": workflow_ci_cd_feature.get("type"),
            } if workflow_ci_cd_feature else None,
            "current_plan_features": [
                {
                    "feature_id": pf.get("feature", {}).get("id"),
                    "feature_name": pf.get("feature", {}).get("name"),
                    "feature_type": pf.get("feature", {}).get("type"),
                    "value": pf.get("value"),
                }
                for pf in plan_features_data
            ],
            "pro_plan_features": [
                {
                    "feature_id": pf.get("feature", {}).get("id"),
                    "feature_name": pf.get("feature", {}).get("name"),
                    "feature_type": pf.get("feature", {}).get("type"),
                    "value": pf.get("value"),
                }
                for pf in pro_plan_features
            ],
            "tenant_overrides": [
                {
                    "feature_id": ov.get("feature", {}).get("id"),
                    "feature_name": ov.get("feature", {}).get("name"),
                    "value": ov.get("value"),
                    "expires_at": ov.get("expires_at"),
                }
                for ov in overrides
            ],
            "computed_entitlements": {
                "plan_name": computed_entitlements.get("plan_name"),
                "workflow_ci_cd_enabled": workflow_ci_cd_enabled,
                "all_features": computed_entitlements.get("features", {}),
            },
        }

    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug failed: {str(e)}\n{traceback.format_exc()}"
        )


# =============================================================================
# Plan Features - Get all plans with all features (for frontend PLAN_FEATURES)
# =============================================================================

@router.get("/plan-features/all", response_model=Dict[str, Dict[str, Any]])
async def get_all_plan_features(_: dict = Depends(require_platform_admin())):
    """
    Get all plan features in a format suitable for frontend PLAN_FEATURES object.
    Returns: { "free": { "feature1": value, ... }, "pro": { ... }, ... }
    """
    try:
        # Get all plans
        plans_response = db_service.client.table("plans").select("id, name").eq("is_active", True).execute()
        plans = {p["id"]: p["name"] for p in (plans_response.data or [])}
        
        # Get all features
        features_response = db_service.client.table("features").select("id, name, type").execute()
        features = {f["id"]: f for f in (features_response.data or [])}
        
        # Get all plan-feature mappings
        plan_features_response = db_service.client.table("plan_features").select(
            "plan_id, feature_id, value"
        ).execute()
        
        # Build result structure
        result: Dict[str, Dict[str, Any]] = {}
        
        # Initialize all plans with empty dicts
        for plan_name in plans.values():
            result[plan_name] = {}
        
        # Populate with plan-feature values
        for pf in (plan_features_response.data or []):
            plan_id = pf.get("plan_id")
            feature_id = pf.get("feature_id")
            value = pf.get("value", {})
            
            if plan_id in plans and feature_id in features:
                plan_name = plans[plan_id]
                feature = features[feature_id]
                feature_name = feature["name"]
                feature_type = feature["type"]
                
                # Convert value based on type
                if feature_type == "flag":
                    result[plan_name][feature_name] = value.get("enabled", False)
                elif feature_type == "limit":
                    result[plan_name][feature_name] = value.get("value", 0)
                else:
                    result[plan_name][feature_name] = value
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch all plan features: {str(e)}"
        )


# =============================================================================
# Plan Configuration Management (Metadata, Limits, Retention, Feature Requirements)
# =============================================================================

@router.patch("/plan-configurations/metadata/{plan_name}", response_model=PlanMetadataResponse)
async def update_plan_metadata(
    plan_name: str,
    update: PlanMetadataUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update plan metadata (icon, color, precedence, sort_order)."""
    try:
        # Verify plan exists
        plan_response = db_service.client.table("plans").select("id, name, display_name, sort_order").eq(
            "name", plan_name.lower()
        ).single().execute()
        
        if not plan_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        
        plan_id = plan_response.data["id"]
        update_data = {}
        if update.icon is not None:
            update_data["icon"] = update.icon
        if update.color_class is not None:
            update_data["color_class"] = update.color_class
        if update.precedence is not None:
            update_data["precedence"] = update.precedence
        if update.sort_order is not None:
            update_data["sort_order"] = update.sort_order
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            db_service.client.table("plans").update(update_data).eq("id", plan_id).execute()
        
        # Fetch updated plan
        updated = db_service.client.table("plans").select(
            "name, display_name, icon, color_class, precedence, sort_order"
        ).eq("id", plan_id).single().execute()
        
        return PlanMetadataResponse(
            name=updated.data["name"],
            display_name=updated.data["display_name"],
            icon=updated.data.get("icon"),
            color_class=updated.data.get("color_class"),
            precedence=updated.data.get("precedence", 0),
            sort_order=updated.data.get("sort_order", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan metadata: {str(e)}"
        )


@router.patch("/plan-configurations/limits/{plan_name}", response_model=PlanLimitsResponse)
async def update_plan_limits(
    plan_name: str,
    update: PlanLimitsUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update plan limits."""
    try:
        update_data = {}
        if update.max_workflows is not None:
            update_data["max_workflows"] = update.max_workflows
        if update.max_environments is not None:
            update_data["max_environments"] = update.max_environments
        if update.max_users is not None:
            update_data["max_users"] = update.max_users
        if update.max_executions_daily is not None:
            update_data["max_executions_daily"] = update.max_executions_daily
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            db_service.client.table("plan_limits").update(update_data).eq("plan_name", plan_name.lower()).execute()
        
        # Fetch updated limits
        updated = db_service.client.table("plan_limits").select("*").eq("plan_name", plan_name.lower()).single().execute()
        
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan limits not found")
        
        return PlanLimitsResponse(
            plan_name=updated.data["plan_name"],
            max_workflows=updated.data["max_workflows"],
            max_environments=updated.data["max_environments"],
            max_users=updated.data["max_users"],
            max_executions_daily=updated.data["max_executions_daily"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan limits: {str(e)}"
        )


@router.patch("/plan-configurations/retention/{plan_name}", response_model=PlanRetentionDefaultsResponse)
async def update_plan_retention(
    plan_name: str,
    update: PlanRetentionDefaultsUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update plan retention defaults."""
    try:
        update_data = {}
        if update.drift_checks is not None:
            update_data["drift_checks"] = update.drift_checks
        if update.closed_incidents is not None:
            update_data["closed_incidents"] = update.closed_incidents
        if update.reconciliation_artifacts is not None:
            update_data["reconciliation_artifacts"] = update.reconciliation_artifacts
        if update.approvals is not None:
            update_data["approvals"] = update.approvals
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            db_service.client.table("plan_retention_defaults").update(update_data).eq("plan_name", plan_name.lower()).execute()
        
        # Fetch updated retention
        updated = db_service.client.table("plan_retention_defaults").select("*").eq("plan_name", plan_name.lower()).single().execute()
        
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan retention defaults not found")
        
        return PlanRetentionDefaultsResponse(
            plan_name=updated.data["plan_name"],
            drift_checks=updated.data["drift_checks"],
            closed_incidents=updated.data["closed_incidents"],
            reconciliation_artifacts=updated.data["reconciliation_artifacts"],
            approvals=updated.data["approvals"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan retention defaults: {str(e)}"
        )


@router.patch("/plan-configurations/feature-requirements/{feature_name}", response_model=PlanFeatureRequirementResponse)
async def update_plan_feature_requirement(
    feature_name: str,
    update: PlanFeatureRequirementUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update plan feature requirement."""
    try:
        update_data = {}
        if update.required_plan is not None:
            update_data["required_plan"] = update.required_plan.lower() if update.required_plan else None
        
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            db_service.client.table("plan_feature_requirements").update(update_data).eq("feature_name", feature_name).execute()
        
        # Fetch updated requirement
        updated = db_service.client.table("plan_feature_requirements").select("*").eq("feature_name", feature_name).single().execute()
        
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature requirement not found")
        
        return PlanFeatureRequirementResponse(
            feature_name=updated.data["feature_name"],
            required_plan=updated.data.get("required_plan"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feature requirement: {str(e)}"
        )


# =============================================================================
# Workflow Policy Matrix Management
# =============================================================================

@router.get("/workflow-policy-matrix", response_model=List[Dict[str, Any]])
async def get_workflow_policy_matrix(_: dict = Depends(require_platform_admin())):
    """Get workflow policy matrix for all environment classes."""
    try:
        response = db_service.client.table("workflow_policy_matrix").select("*").execute()
        return response.data or []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch workflow policy matrix: {str(e)}"
        )


@router.patch("/workflow-policy-matrix/{environment_class}", response_model=Dict[str, Any])
async def update_workflow_policy_matrix(
    environment_class: str,
    update: Dict[str, Any],
    user_info: dict = Depends(require_platform_admin()),
):
    """Update workflow policy matrix for an environment class."""
    try:
        update_data = {k: v for k, v in update.items() if v is not None}
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            db_service.client.table("workflow_policy_matrix").update(update_data).eq(
                "environment_class", environment_class.lower()
            ).execute()
        
        updated = db_service.client.table("workflow_policy_matrix").select("*").eq(
            "environment_class", environment_class.lower()
        ).single().execute()
        
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy matrix not found")
        
        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow policy matrix: {str(e)}"
        )


@router.get("/plan-policy-overrides", response_model=List[Dict[str, Any]])
async def get_plan_policy_overrides(_: dict = Depends(require_platform_admin())):
    """Get all plan-based policy overrides."""
    try:
        response = db_service.client.table("plan_policy_overrides").select("*").execute()
        return response.data or []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan policy overrides: {str(e)}"
        )


@router.patch("/plan-policy-overrides/{plan_name}/{environment_class}", response_model=Dict[str, Any])
async def update_plan_policy_override(
    plan_name: str,
    environment_class: str,
    update: Dict[str, Any],
    user_info: dict = Depends(require_platform_admin()),
):
    """Update or create plan-based policy override."""
    try:
        update_data = {k: v for k, v in update.items() if v is not None}
        if update_data:
            update_data["updated_at"] = datetime.utcnow().isoformat()
            # Try to update first
            existing = db_service.client.table("plan_policy_overrides").select("id").eq(
                "plan_name", plan_name.lower()
            ).eq("environment_class", environment_class.lower()).execute()
            
            if existing.data:
                db_service.client.table("plan_policy_overrides").update(update_data).eq(
                    "id", existing.data[0]["id"]
                ).execute()
            else:
                # Create new
                db_service.client.table("plan_policy_overrides").insert({
                    "plan_name": plan_name.lower(),
                    "environment_class": environment_class.lower(),
                    **update_data,
                }).execute()
        
        updated = db_service.client.table("plan_policy_overrides").select("*").eq(
            "plan_name", plan_name.lower()
        ).eq("environment_class", environment_class.lower()).single().execute()
        
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy override not found")
        
        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan policy override: {str(e)}"
        )