from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EnvironmentTypeBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, description="Stored in environments.n8n_type")
    label: str = Field(..., min_length=1, max_length=100, description="Display name")
    sort_order: int = Field(0, description="Lower comes first")
    is_active: bool = True


class EnvironmentTypeCreate(EnvironmentTypeBase):
    pass


class EnvironmentTypeUpdate(BaseModel):
    key: Optional[str] = Field(None, min_length=1, max_length=50)
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class EnvironmentTypeResponse(EnvironmentTypeBase):
    id: str
    tenant_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EnvironmentTypeReorderRequest(BaseModel):
    ordered_ids: List[str] = Field(..., description="Environment type IDs in desired order")

