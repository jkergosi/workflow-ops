"""
Lifecycle stage definitions for Workflow Ops.

The canonical lifecycle represents the journey of a workflow through
the Workflow Ops platform, from authoring in n8n to observability.
"""
from enum import Enum


class LifecycleStage(str, Enum):
    """
    Canonical lifecycle stages for workflows in Workflow Ops.
    
    The lifecycle flow:
    1. AUTHORING - Workflow is created/edited in n8n (outside Workflow Ops)
    2. INGEST - Workflow is synced into Workflow Ops
    3. SNAPSHOT - Workflow is committed to Git (source of truth)
    4. PROMOTION - Promotion intent is created
    5. DEPLOYMENT - Workflow is deployed to target environment
    6. DRIFT_DETECTION - System detects differences from Git source
    7. DRIFT_HANDLING - Drift is handled based on mode (passive/managed/enforced)
    8. RECONCILIATION - Drift is reconciled (promote to Git, revert, or replace)
    9. OBSERVABILITY - Workflow execution and health monitoring
    """
    AUTHORING = "authoring"
    INGEST = "ingest"
    SNAPSHOT = "snapshot"
    PROMOTION = "promotion"
    DEPLOYMENT = "deployment"
    DRIFT_DETECTION = "drift_detection"
    DRIFT_HANDLING = "drift_handling"
    RECONCILIATION = "reconciliation"
    OBSERVABILITY = "observability"

