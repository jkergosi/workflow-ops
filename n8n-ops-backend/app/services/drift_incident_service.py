"""Drift Incident Service with full lifecycle management.

Supports retention and soft-delete:
- Incidents are never hard-deleted, only payloads are purged
- is_deleted flag for soft-delete (future use)
- payload_purged_at tracks when payload was removed
- payload_available computed field for UI convenience
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status

from app.services.database import db_service
from app.services.feature_service import feature_service
from app.schemas.drift_incident import (
    DriftIncidentStatus,
    DriftSeverity,
    ResolutionType,
    AffectedWorkflow,
)


# Valid status transitions
VALID_TRANSITIONS = {
    DriftIncidentStatus.detected: [DriftIncidentStatus.acknowledged, DriftIncidentStatus.closed],
    DriftIncidentStatus.acknowledged: [DriftIncidentStatus.stabilized, DriftIncidentStatus.reconciled, DriftIncidentStatus.closed],
    DriftIncidentStatus.stabilized: [DriftIncidentStatus.reconciled, DriftIncidentStatus.closed],
    DriftIncidentStatus.reconciled: [DriftIncidentStatus.closed],
    DriftIncidentStatus.closed: [],  # Terminal state
}


class DriftIncidentService:
    """Service for managing drift incident lifecycle."""

    def _enrich_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich incident data with computed fields.
        - payload_available: False if payload_purged_at is set
        """
        if not incident:
            return incident

        # Add payload_available based on whether payload was purged
        incident["payload_available"] = incident.get("payload_purged_at") is None

        # Ensure is_deleted has a default
        if "is_deleted" not in incident:
            incident["is_deleted"] = False

        return incident

    def _enrich_incidents(self, incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich multiple incidents."""
        return [self._enrich_incident(inc) for inc in incidents]

    async def get_incidents(
        self,
        tenant_id: str,
        environment_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get drift incidents with pagination."""
        try:
            query = db_service.client.table("drift_incidents").select(
                "*", count="exact"
            ).eq("tenant_id", tenant_id)

            # Exclude soft-deleted incidents by default
            if not include_deleted:
                query = query.eq("is_deleted", False)

            if environment_id:
                query = query.eq("environment_id", environment_id)
            if status_filter:
                query = query.eq("status", status_filter)

            response = query.order(
                "detected_at", desc=True
            ).range(offset, offset + limit - 1).execute()

            return {
                "items": self._enrich_incidents(response.data or []),
                "total": response.count or 0,
                "has_more": (response.count or 0) > offset + limit,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch incidents: {str(e)}",
            )

    async def get_incident(
        self, tenant_id: str, incident_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single drift incident."""
        try:
            response = db_service.client.table("drift_incidents").select(
                "*"
            ).eq("tenant_id", tenant_id).eq("id", incident_id).single().execute()
            return self._enrich_incident(response.data)
        except Exception:
            return None

    async def get_active_incident_for_environment(
        self, tenant_id: str, environment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the active (non-closed) drift incident for an environment."""
        try:
            response = db_service.client.table("drift_incidents").select(
                "*"
            ).eq("tenant_id", tenant_id).eq(
                "environment_id", environment_id
            ).eq("is_deleted", False).neq("status", "closed").order(
                "detected_at", desc=True
            ).limit(1).execute()

            return self._enrich_incident(response.data[0]) if response.data else None
        except Exception:
            return None

    async def _check_duplicate_incident(
        self,
        tenant_id: str,
        environment_id: str,
        affected_workflows: Optional[List[AffectedWorkflow]] = None,
        drift_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Check if a duplicate incident exists based on content similarity.

        Returns the duplicate incident if found, None otherwise.

        Duplicate detection strategy:
        1. First check for active incidents (highest priority - prevent duplicates)
        2. Then check recent incidents (last 24 hours) with matching affected workflows
        3. Compare drift snapshots if available for exact match detection
        """
        # Check for active incident (non-closed)
        active_incident = await self.get_active_incident_for_environment(tenant_id, environment_id)
        if active_incident:
            return active_incident

        # If no affected workflows provided, skip detailed duplicate check
        if not affected_workflows:
            return None

        # Check for recent incidents (last 24 hours) with matching affected workflows
        try:
            # Get recent incidents from the last 24 hours
            cutoff_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()

            response = db_service.client.table("drift_incidents").select(
                "*"
            ).eq("tenant_id", tenant_id).eq(
                "environment_id", environment_id
            ).eq("is_deleted", False).gte(
                "detected_at", cutoff_time
            ).order("detected_at", desc=True).execute()

            if not response.data:
                return None

            # Extract workflow IDs from incoming request
            incoming_workflow_ids = {w.workflow_id for w in affected_workflows}

            # Check each recent incident for matching workflows
            for incident in response.data:
                existing_workflows = incident.get("affected_workflows", [])
                existing_workflow_ids = {
                    w.get("workflow_id") for w in existing_workflows if w.get("workflow_id")
                }

                # If the workflow sets match exactly, this is likely a duplicate
                if incoming_workflow_ids == existing_workflow_ids and len(incoming_workflow_ids) > 0:
                    # If drift snapshots are available, compare them for exact match
                    if drift_snapshot and incident.get("drift_snapshot"):
                        # For exact duplicate detection, compare snapshot structure
                        # This is a simplified comparison - in production might need deep comparison
                        if drift_snapshot == incident.get("drift_snapshot"):
                            return incident
                    else:
                        # If no snapshots, matching workflows is sufficient
                        return incident

            return None

        except Exception:
            # If duplicate check fails, don't block incident creation
            return None

    async def create_incident(
        self,
        tenant_id: str,
        environment_id: str,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        affected_workflows: Optional[List[AffectedWorkflow]] = None,
        drift_snapshot: Optional[Dict[str, Any]] = None,
        severity: Optional[DriftSeverity] = None,
    ) -> Dict[str, Any]:
        """Create a new drift incident with duplicate detection."""
        # Check for duplicate incidents (active or recent with same workflows)
        existing = await self._check_duplicate_incident(
            tenant_id, environment_id, affected_workflows, drift_snapshot
        )
        if existing:
            # Determine error type based on incident status
            is_active = existing["status"] != "closed"
            error_type = "active_incident_exists" if is_active else "duplicate_incident_exists"

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": error_type,
                    "incident_id": existing["id"],
                    "incident_status": existing["status"],
                    "detected_at": existing["detected_at"],
                    "message": (
                        "An active drift incident already exists for this environment"
                        if is_active
                        else "A duplicate drift incident was recently created (within last 24 hours) with the same affected workflows"
                    ),
                },
            )

        now = datetime.utcnow().isoformat()

        payload = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "status": DriftIncidentStatus.detected.value,
            "detected_at": now,
            "created_by": user_id,
            "affected_workflows": [w.model_dump() for w in affected_workflows] if affected_workflows else [],
            "drift_snapshot": drift_snapshot,
        }

        if title:
            payload["title"] = title
        if severity:
            payload["severity"] = severity.value

        try:
            response = db_service.client.table("drift_incidents").insert(
                payload
            ).execute()
            incident = response.data[0] if response.data else None

            if not incident:
                raise Exception("Failed to insert incident")

            # Update environment to point to this incident
            db_service.client.table("environments").update({
                "drift_status": "DRIFT_DETECTED",
                "active_drift_incident_id": incident["id"],
                "last_drift_detected_at": now,
            }).eq("id", environment_id).eq("tenant_id", tenant_id).execute()

            return incident
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create incident: {str(e)}",
            )

    async def update_incident(
        self,
        tenant_id: str,
        incident_id: str,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        reason: Optional[str] = None,
        ticket_ref: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        severity: Optional[DriftSeverity] = None,
        drift_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update incident fields (not status transitions).

        Note: drift_snapshot is immutable and cannot be updated after creation.
        """
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        # Reject any attempt to modify drift_snapshot after creation
        if drift_snapshot is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="drift_snapshot is immutable and cannot be modified after incident creation",
            )

        update_data = {"updated_at": datetime.utcnow().isoformat()}

        if title is not None:
            update_data["title"] = title
        if owner_user_id is not None:
            update_data["owner_user_id"] = owner_user_id
        if reason is not None:
            update_data["reason"] = reason
        if ticket_ref is not None:
            update_data["ticket_ref"] = ticket_ref
        if expires_at is not None:
            # Check if tenant has TTL feature
            features = await feature_service.get_tenant_features(tenant_id)
            if features.get("drift_ttl_sla"):
                update_data["expires_at"] = expires_at.isoformat()
        if severity is not None:
            update_data["severity"] = severity.value

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update incident: {str(e)}",
            )

    def _validate_transition(
        self, current_status: str, new_status: DriftIncidentStatus, admin_override: bool = False
    ) -> bool:
        """Check if a status transition is valid.

        Args:
            current_status: Current incident status
            new_status: Desired new status
            admin_override: If True, allows any transition (admin bypass)

        Returns:
            True if transition is valid or admin override is enabled
        """
        # Admin override allows any transition except FROM closed state
        if admin_override:
            current = DriftIncidentStatus(current_status)
            # Still enforce that closed is terminal even for admins
            if current == DriftIncidentStatus.closed:
                return False
            return True

        current = DriftIncidentStatus(current_status)
        return new_status in VALID_TRANSITIONS.get(current, [])

    async def acknowledge_incident(
        self,
        tenant_id: str,
        incident_id: str,
        user_id: str,
        reason: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        ticket_ref: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        admin_override: bool = False,
    ) -> Dict[str, Any]:
        """Acknowledge a drift incident."""
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        if not self._validate_transition(
            incident["status"], DriftIncidentStatus.acknowledged, admin_override
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge incident in '{incident['status']}' status. Valid transitions: {[s.value for s in VALID_TRANSITIONS.get(DriftIncidentStatus(incident['status']), [])]}",
            )

        now = datetime.utcnow().isoformat()
        update_data = {
            "status": DriftIncidentStatus.acknowledged.value,
            "acknowledged_at": now,
            "acknowledged_by": user_id,
            "updated_at": now,
        }

        if reason:
            update_data["reason"] = reason
        if owner_user_id:
            update_data["owner_user_id"] = owner_user_id
        if ticket_ref:
            update_data["ticket_ref"] = ticket_ref
        if expires_at:
            features = await feature_service.get_tenant_features(tenant_id)
            if features.get("drift_ttl_sla"):
                update_data["expires_at"] = expires_at.isoformat()

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to acknowledge incident: {str(e)}",
            )

    async def stabilize_incident(
        self,
        tenant_id: str,
        incident_id: str,
        user_id: str,
        reason: Optional[str] = None,
        admin_override: bool = False,
    ) -> Dict[str, Any]:
        """Mark incident as stabilized (no new drift changes)."""
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        if not self._validate_transition(
            incident["status"], DriftIncidentStatus.stabilized, admin_override
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot stabilize incident in '{incident['status']}' status. Valid transitions: {[s.value for s in VALID_TRANSITIONS.get(DriftIncidentStatus(incident['status']), [])]}",
            )

        now = datetime.utcnow().isoformat()
        update_data = {
            "status": DriftIncidentStatus.stabilized.value,
            "stabilized_at": now,
            "stabilized_by": user_id,
            "updated_at": now,
        }

        if reason:
            update_data["reason"] = reason

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stabilize incident: {str(e)}",
            )

    async def reconcile_incident(
        self,
        tenant_id: str,
        incident_id: str,
        user_id: str,
        resolution_type: ResolutionType,
        reason: Optional[str] = None,
        resolution_details: Optional[Dict[str, Any]] = None,
        admin_override: bool = False,
    ) -> Dict[str, Any]:
        """Mark incident as reconciled with resolution tracking."""
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        if not self._validate_transition(
            incident["status"], DriftIncidentStatus.reconciled, admin_override
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reconcile incident in '{incident['status']}' status. Valid transitions: {[s.value for s in VALID_TRANSITIONS.get(DriftIncidentStatus(incident['status']), [])]}",
            )

        now = datetime.utcnow().isoformat()
        update_data = {
            "status": DriftIncidentStatus.reconciled.value,
            "reconciled_at": now,
            "reconciled_by": user_id,
            "resolution_type": resolution_type.value,
            "updated_at": now,
        }

        if reason:
            update_data["reason"] = reason
        if resolution_details:
            update_data["resolution_details"] = resolution_details

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reconcile incident: {str(e)}",
            )

    async def close_incident(
        self,
        tenant_id: str,
        incident_id: str,
        user_id: str,
        reason: Optional[str] = None,
        resolution_type: Optional[ResolutionType] = None,
        admin_override: bool = False,
    ) -> Dict[str, Any]:
        """Close a drift incident.

        Validation rules:
        - If closing from detected/acknowledged/stabilized (without reconciliation):
          Requires resolution_type and reason to explain why it's being closed
        - If closing from reconciled status:
          Requires reason (resolution notes)
        """
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        if not self._validate_transition(
            incident["status"], DriftIncidentStatus.closed, admin_override
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot close incident in '{incident['status']}' status. Valid transitions: {[s.value for s in VALID_TRANSITIONS.get(DriftIncidentStatus(incident['status']), [])]}",
            )

        # Validate closure requirements based on current status
        current_status = DriftIncidentStatus(incident["status"])

        # If closing from pre-reconciliation states, require resolution_type and reason
        if current_status in [
            DriftIncidentStatus.detected,
            DriftIncidentStatus.acknowledged,
            DriftIncidentStatus.stabilized
        ]:
            if not resolution_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Closing incident from '{current_status.value}' status requires resolution_type to explain how the incident was resolved",
                )
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Closing incident from '{current_status.value}' status requires reason to explain why it's being closed without full reconciliation",
                )

        # If closing from reconciled status, require resolution notes (reason)
        if current_status == DriftIncidentStatus.reconciled:
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Closing reconciled incident requires reason (resolution notes)",
                )

        now = datetime.utcnow().isoformat()
        update_data = {
            "status": DriftIncidentStatus.closed.value,
            "closed_at": now,
            "closed_by": user_id,
            "updated_at": now,
        }

        if reason:
            update_data["reason"] = reason
        if resolution_type:
            update_data["resolution_type"] = resolution_type.value

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            # Clear environment's active incident reference
            db_service.client.table("environments").update({
                "active_drift_incident_id": None,
                "drift_status": "IN_SYNC",
            }).eq(
                "id", incident["environment_id"]
            ).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to close incident: {str(e)}",
            )

    async def refresh_incident_drift(
        self,
        tenant_id: str,
        incident_id: str,
        affected_workflows: List[AffectedWorkflow],
        drift_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update incident with latest drift data.

        Note: drift_snapshot is immutable after creation and cannot be updated.
        """
        incident = await self.get_incident(tenant_id, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        if incident["status"] == DriftIncidentStatus.closed.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update closed incident",
            )

        # Reject any attempt to modify drift_snapshot after creation
        if drift_snapshot is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="drift_snapshot is immutable and cannot be modified after incident creation",
            )

        update_data = {
            "affected_workflows": [w.model_dump() for w in affected_workflows],
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            response = db_service.client.table("drift_incidents").update(
                update_data
            ).eq("id", incident_id).eq("tenant_id", tenant_id).execute()

            return response.data[0] if response.data else incident
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to refresh incident drift: {str(e)}",
            )

    async def get_incident_stats(
        self, tenant_id: str, environment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get incident statistics."""
        try:
            base_query = db_service.client.table("drift_incidents").select(
                "status", count="exact"
            ).eq("tenant_id", tenant_id)

            if environment_id:
                base_query = base_query.eq("environment_id", environment_id)

            # Get counts by status
            stats = {"total": 0, "by_status": {}}

            for status_val in DriftIncidentStatus:
                response = base_query.eq(
                    "status", status_val.value
                ).execute()
                count = response.count or 0
                stats["by_status"][status_val.value] = count
                stats["total"] += count

            # Get open incidents count
            stats["open"] = (
                stats["by_status"].get("detected", 0) +
                stats["by_status"].get("acknowledged", 0) +
                stats["by_status"].get("stabilized", 0)
            )

            return stats
        except Exception:
            return {"total": 0, "open": 0, "by_status": {}}


# Singleton instance
drift_incident_service = DriftIncidentService()
