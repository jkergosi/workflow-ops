"""Entitlements schemas for plan-based feature access."""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum


class FeatureType(str, Enum):
    FLAG = "flag"
    LIMIT = "limit"


class FeatureStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    HIDDEN = "hidden"


class FeatureResponse(BaseModel):
    """Feature definition response."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    type: FeatureType
    default_value: Dict[str, Any]
    status: FeatureStatus

    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    """Plan definition response."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

    class Config:
        from_attributes = True


class PlanFeatureResponse(BaseModel):
    """Plan-feature mapping response."""
    feature_name: str
    feature_type: FeatureType
    value: Dict[str, Any]


class TenantPlanResponse(BaseModel):
    """Tenant's current plan assignment."""
    plan_id: str
    plan_name: str
    plan_display_name: str
    entitlements_version: int
    effective_from: datetime
    effective_until: Optional[datetime] = None


class EntitlementsResponse(BaseModel):
    """Full entitlements context for a tenant."""
    plan_id: Optional[str] = None
    plan_name: str
    entitlements_version: int
    features: Dict[str, Any]  # {feature_name: resolved_value}


class FeatureCheckResult(BaseModel):
    """Result of checking a specific feature."""
    feature_name: str
    allowed: bool
    value: Optional[Union[bool, int]] = None
    message: Optional[str] = None
    required_plan: Optional[str] = None


class LimitCheckResult(BaseModel):
    """Result of checking a limit feature."""
    feature_name: str
    allowed: bool
    current: int
    limit: int
    message: Optional[str] = None
