"""
Canonical Workflow Service - Core service for canonical workflow identity management
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from app.services.database import db_service
from app.services.promotion_service import normalize_workflow_for_comparison

logger = logging.getLogger(__name__)


def compute_workflow_hash(workflow: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of normalized workflow content.
    
    Uses normalize_workflow_for_comparison() as the single source of truth
    for normalization, then hashes the sorted JSON representation.
    
    Returns hex digest (no prefix).
    """
    normalized = normalize_workflow_for_comparison(workflow)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


class CanonicalWorkflowService:
    """Service for managing canonical workflow identity"""
    
    @staticmethod
    async def create_canonical_workflow(
        tenant_id: str,
        canonical_id: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new canonical workflow.
        
        Args:
            tenant_id: Tenant ID
            canonical_id: Optional canonical ID (generates UUID if not provided)
            created_by_user_id: User who created the workflow
            display_name: Optional display name cache
            
        Returns:
            Created canonical workflow record
        """
        if not canonical_id:
            canonical_id = str(uuid4())
        
        workflow_data = {
            "tenant_id": tenant_id,
            "canonical_id": canonical_id,
            "created_at": datetime.utcnow().isoformat(),
            "created_by_user_id": created_by_user_id,
            "display_name": display_name
        }
        
        try:
            response = db_service.client.table("canonical_workflows").insert(workflow_data).execute()
            if response.data:
                logger.info(f"Created canonical workflow {canonical_id} for tenant {tenant_id}")
                return response.data[0]
            raise Exception("Failed to create canonical workflow")
        except Exception as e:
            logger.error(f"Error creating canonical workflow: {str(e)}")
            raise
    
    @staticmethod
    async def get_canonical_workflow(
        tenant_id: str,
        canonical_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a canonical workflow by ID"""
        try:
            response = (
                db_service.client.table("canonical_workflows")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("canonical_id", canonical_id)
                .is_("deleted_at", "null")
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"Error fetching canonical workflow {canonical_id}: {str(e)}")
            return None
    
    @staticmethod
    async def list_canonical_workflows(
        tenant_id: str,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """List all canonical workflows for a tenant"""
        try:
            query = (
                db_service.client.table("canonical_workflows")
                .select("*")
                .eq("tenant_id", tenant_id)
            )
            
            if not include_deleted:
                query = query.is_("deleted_at", "null")
            
            response = query.order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error listing canonical workflows: {str(e)}")
            return []
    
    @staticmethod
    async def update_canonical_workflow(
        tenant_id: str,
        canonical_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a canonical workflow"""
        try:
            response = (
                db_service.client.table("canonical_workflows")
                .update(updates)
                .eq("tenant_id", tenant_id)
                .eq("canonical_id", canonical_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating canonical workflow {canonical_id}: {str(e)}")
            return None
    
    @staticmethod
    async def mark_canonical_workflow_deleted(
        tenant_id: str,
        canonical_id: str
    ) -> bool:
        """
        Mark a canonical workflow as deleted (soft delete).
        
        Does not actually delete the row - sets deleted_at timestamp.
        """
        try:
            await CanonicalWorkflowService.update_canonical_workflow(
                tenant_id,
                canonical_id,
                {"deleted_at": datetime.utcnow().isoformat()}
            )
            logger.info(f"Marked canonical workflow {canonical_id} as deleted")
            return True
        except Exception as e:
            logger.error(f"Error marking canonical workflow as deleted: {str(e)}")
            return False
    
    @staticmethod
    async def get_canonical_workflow_git_state(
        tenant_id: str,
        environment_id: str,
        canonical_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get Git state for a canonical workflow in a specific environment"""
        try:
            response = (
                db_service.client.table("canonical_workflow_git_state")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("canonical_id", canonical_id)
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"Error fetching Git state: {str(e)}")
            return None
    
    @staticmethod
    async def upsert_canonical_workflow_git_state(
        tenant_id: str,
        environment_id: str,
        canonical_id: str,
        git_path: str,
        git_content_hash: str,
        git_commit_sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update Git state for a canonical workflow"""
        git_state_data = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "canonical_id": canonical_id,
            "git_path": git_path,
            "git_content_hash": git_content_hash,
            "git_commit_sha": git_commit_sha,
            "last_repo_sync_at": datetime.utcnow().isoformat()
        }
        
        try:
            response = (
                db_service.client.table("canonical_workflow_git_state")
                .upsert(git_state_data, on_conflict="tenant_id,environment_id,canonical_id")
                .execute()
            )
            return response.data[0] if response.data else git_state_data
        except Exception as e:
            logger.error(f"Error upserting Git state: {str(e)}")
            raise

