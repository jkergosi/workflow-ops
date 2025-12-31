"""
Drift mode definitions and plan-based enforcement.

Drift modes determine how drift is handled in the system:
- PASSIVE: Drift is detected but not actively managed
- MANAGED: Drift incidents can be created and managed
- ENFORCED: Drift blocks deployments and requires resolution
"""
from enum import Enum
from typing import Dict


class DriftMode(str, Enum):
    """
    Drift handling modes for environments.
    
    - PASSIVE: Drift is detected but not actively managed. No incidents can be created.
    - MANAGED: Drift incidents can be created and managed manually.
    - ENFORCED: Drift blocks deployments and requires resolution before proceeding.
    """
    PASSIVE = "passive"
    MANAGED = "managed"
    ENFORCED = "enforced"


# Plan-based drift mode mapping
PLAN_DRIFT_MODE: Dict[str, DriftMode] = {
    "free": DriftMode.PASSIVE,
    "pro": DriftMode.PASSIVE,
    "agency": DriftMode.MANAGED,
    "enterprise": DriftMode.ENFORCED,
}


def get_drift_mode_for_plan(plan_name: str) -> DriftMode:
    """
    Get the drift mode for a given plan name.
    
    Args:
        plan_name: The plan name (free, pro, agency, enterprise)
        
    Returns:
        The drift mode for the plan
    """
    plan_lower = plan_name.lower() if plan_name else "free"
    return PLAN_DRIFT_MODE.get(plan_lower, DriftMode.PASSIVE)


def can_create_drift_incident(drift_mode: DriftMode) -> bool:
    """
    Check if drift incidents can be created in the given drift mode.
    
    Args:
        drift_mode: The drift mode to check
        
    Returns:
        True if incidents can be created, False otherwise
    """
    return drift_mode in (DriftMode.MANAGED, DriftMode.ENFORCED)

