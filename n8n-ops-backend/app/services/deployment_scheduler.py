"""
Deployment Scheduler Service

Polls for scheduled deployments and executes them when their scheduled_at time arrives.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from app.services.database import db_service
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobStatus,
    BackgroundJobType
)
from app.schemas.deployment import DeploymentStatus
from app.schemas.promotion import PromotionStatus
from app.api.endpoints.promotions import _execute_promotion_background

logger = logging.getLogger(__name__)

# Global flag to control scheduler
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None


async def _process_scheduled_deployments():
    """
    Poll for scheduled deployments that are ready to execute and start them.
    Runs every 30 seconds.
    """
    global _scheduler_running
    
    while _scheduler_running:
        try:
            # Get all scheduled deployments where scheduled_at <= now()
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            
            # Query for scheduled deployments ready to execute
            # Using Supabase client directly for complex query
            response = (
                db_service.client.table("deployments")
                .select("*")
                .eq("status", DeploymentStatus.SCHEDULED.value)
                .not_.is_("scheduled_at", "null")
                .lte("scheduled_at", now_iso)
                .execute()
            )
            
            scheduled_deployments = response.data or []
            
            if scheduled_deployments:
                logger.info(f"Found {len(scheduled_deployments)} scheduled deployment(s) ready to execute")
            
            for deployment in scheduled_deployments:
                deployment_id = deployment.get("id")
                scheduled_at_str = deployment.get("scheduled_at")
                
                try:
                    # Parse scheduled_at to ensure it's really time to execute
                    scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                    if scheduled_at.tzinfo is None:
                        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
                    
                    # Double-check it's time to execute (with 5 second buffer for clock skew)
                    if (now - scheduled_at).total_seconds() < -5:
                        continue  # Not quite time yet
                    
                    logger.info(f"Executing scheduled deployment {deployment_id} (scheduled for {scheduled_at})")
                    
                    # Get the promotion associated with this deployment
                    # We need to find the promotion by matching source/target environments
                    source_env_id = deployment.get("source_environment_id")
                    target_env_id = deployment.get("target_environment_id")
                    pipeline_id = deployment.get("pipeline_id")
                    tenant_id = deployment.get("tenant_id")
                    
                    # Find promotion with matching environments and pipeline
                    promotions_response = (
                        db_service.client.table("promotions")
                        .select("*")
                        .eq("tenant_id", tenant_id)
                        .eq("source_environment_id", source_env_id)
                        .eq("target_environment_id", target_env_id)
                        .eq("pipeline_id", pipeline_id)
                        .in_("status", ["pending", "approved"])
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    
                    promotion = promotions_response.data[0] if promotions_response.data else None
                    
                    if not promotion:
                        logger.error(f"Could not find promotion for scheduled deployment {deployment_id}")
                        # Mark deployment as failed
                        await db_service.update_deployment(deployment_id, {
                            "status": DeploymentStatus.FAILED.value,
                            "finished_at": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    promotion_id = promotion.get("id")
                    
                    # Get source and target environments
                    source_env = await db_service.get_environment(source_env_id, tenant_id)
                    target_env = await db_service.get_environment(target_env_id, tenant_id)
                    
                    if not source_env or not target_env:
                        logger.error(f"Could not find environments for scheduled deployment {deployment_id}")
                        await db_service.update_deployment(deployment_id, {
                            "status": DeploymentStatus.FAILED.value,
                            "finished_at": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Get selected workflows from promotion
                    workflow_selections = promotion.get("workflow_selections", [])
                    selected_workflows = [ws for ws in workflow_selections if ws.get("selected")]
                    
                    if not selected_workflows:
                        logger.error(f"No workflows selected for scheduled deployment {deployment_id}")
                        await db_service.update_deployment(deployment_id, {
                            "status": DeploymentStatus.FAILED.value,
                            "finished_at": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Create background job
                    job = await background_job_service.create_job(
                        tenant_id=tenant_id,
                        job_type=BackgroundJobType.PROMOTION_EXECUTE,
                        resource_id=promotion_id,
                        resource_type="promotion",
                        created_by=promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
                        initial_progress={
                            "current": 0,
                            "total": len(selected_workflows),
                            "percentage": 0,
                            "message": "Executing scheduled deployment"
                        }
                    )
                    job_id = job["id"]
                    
                    # Update deployment status to running
                    await db_service.update_deployment(deployment_id, {
                        "status": DeploymentStatus.RUNNING.value,
                        "started_at": datetime.utcnow().isoformat()
                    })
                    
                    # Update promotion status to running
                    await db_service.update_promotion(promotion_id, tenant_id, {
                        "status": PromotionStatus.RUNNING.value
                    })
                    
                    # Update job with deployment_id
                    await background_job_service.update_job_status(
                        job_id=job_id,
                        status=BackgroundJobStatus.PENDING,
                        result={"deployment_id": deployment_id}
                    )
                    
                    # Start background execution
                    # Use asyncio.create_task to run in background
                    asyncio.create_task(
                        _execute_promotion_background(
                            job_id=job_id,
                            promotion_id=promotion_id,
                            deployment_id=deployment_id,
                            promotion=promotion,
                            source_env=source_env,
                            target_env=target_env,
                            selected_workflows=selected_workflows
                        )
                    )
                    
                    logger.info(f"Scheduled deployment {deployment_id} execution started (job {job_id})")
                    
                except Exception as e:
                    logger.error(f"Failed to execute scheduled deployment {deployment_id}: {str(e)}", exc_info=True)
                    # Mark deployment as failed
                    try:
                        await db_service.update_deployment(deployment_id, {
                            "status": DeploymentStatus.FAILED.value,
                            "finished_at": datetime.utcnow().isoformat()
                        })
                    except:
                        pass
            
            # Wait 30 seconds before next poll
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in deployment scheduler: {str(e)}", exc_info=True)
            # Wait 30 seconds before retrying
            await asyncio.sleep(30)


async def start_scheduler():
    """Start the deployment scheduler background task."""
    global _scheduler_running, _scheduler_task
    
    if _scheduler_running:
        logger.warning("Deployment scheduler is already running")
        return
    
    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_process_scheduled_deployments())
    logger.info("Deployment scheduler started")


async def stop_scheduler():
    """Stop the deployment scheduler background task."""
    global _scheduler_running, _scheduler_task
    
    if not _scheduler_running:
        return
    
    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    logger.info("Deployment scheduler stopped")

