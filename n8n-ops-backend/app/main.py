from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.endpoints import environments, workflows, executions, tags, billing, teams, n8n_users, tenants, auth, restore, promotions, credentials, pipelines, deployments, snapshots, observability, notifications, admin_entitlements, admin_audit, admin_billing, admin_usage, admin_credentials, admin_providers, support, admin_support, admin_environment_types, sse, providers, background_jobs, health, incidents, drift_policies, drift_approvals, workflow_policy, environment_capabilities, drift_reports, admin_retention, security, platform_admins, platform_impersonation, platform_console, platform_overview, admin_overview, canonical_workflows, github_webhooks
from app.services.background_job_service import background_job_service
from app.services.database import db_service
from app.api.endpoints.admin_audit import create_audit_log
from app.services.auth_service import supabase_auth_service
from datetime import datetime, timedelta
import logging
import traceback

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    redirect_slashes=False
)

@app.middleware("http")
async def impersonation_write_audit_middleware(request: Request, call_next):
    response = await call_next(request)

    try:
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response

        auth_header = request.headers.get("authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            return response

        token = auth_header.split(" ", 1)[1].strip()

        # Resolve actor user_id from Supabase JWT, then check for an active impersonation session.
        payload = await supabase_auth_service.verify_token(token)
        supabase_user_id = payload.get("sub")
        if not supabase_user_id:
            return response

        actor_resp = db_service.client.table("users").select("id").eq("supabase_auth_id", supabase_user_id).maybe_single().execute()
        actor = actor_resp.data or {}
        actor_user_id = actor.get("id")
        if not actor_user_id:
            return response

        sess_resp = (
            db_service.client.table("platform_impersonation_sessions")
            .select("id, actor_user_id, impersonated_user_id, impersonated_tenant_id, ended_at")
            .eq("actor_user_id", actor_user_id)
            .is_("ended_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        sessions = sess_resp.data or []
        if not sessions:
            return response
        session = sessions[0]
        session_id = session.get("id")

        await create_audit_log(
            action_type="impersonation.write",
            action=f"{request.method} {request.url.path}",
            actor_id=session.get("actor_user_id"),
            tenant_id=session.get("impersonated_tenant_id"),
            resource_type="http_request",
            resource_id=session_id,
            metadata={
                "impersonated_user_id": session.get("impersonated_user_id"),
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(response, "status_code", None),
            },
            ip_address=getattr(request.client, "host", None) if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass

    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    environments.router,
    prefix=f"{settings.API_V1_PREFIX}/environments",
    tags=["environments"]
)

app.include_router(
    workflows.router,
    prefix=f"{settings.API_V1_PREFIX}/workflows",
    tags=["workflows"]
)

app.include_router(
    workflow_policy.router,
    prefix=f"{settings.API_V1_PREFIX}/workflows",
    tags=["workflow-policy"]
)

app.include_router(
    environment_capabilities.router,
    prefix=f"{settings.API_V1_PREFIX}/environments",
    tags=["environment-capabilities"]
)

app.include_router(
    executions.router,
    prefix=f"{settings.API_V1_PREFIX}/executions",
    tags=["executions"]
)

app.include_router(
    tags.router,
    prefix=f"{settings.API_V1_PREFIX}/tags",
    tags=["tags"]
)

app.include_router(
    billing.router,
    prefix=f"{settings.API_V1_PREFIX}/billing",
    tags=["billing"]
)

app.include_router(
    teams.router,
    prefix=f"{settings.API_V1_PREFIX}/teams",
    tags=["teams"]
)

app.include_router(
    n8n_users.router,
    prefix=f"{settings.API_V1_PREFIX}/n8n-users",
    tags=["n8n-users"]
)

app.include_router(
    tenants.router,
    prefix=f"{settings.API_V1_PREFIX}/tenants",
    tags=["tenants"]
)

app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_PREFIX}/auth",
    tags=["auth"]
)

app.include_router(
    restore.router,
    prefix=f"{settings.API_V1_PREFIX}/restore",
    tags=["restore"]
)

app.include_router(
    promotions.router,
    prefix=f"{settings.API_V1_PREFIX}/promotions",
    tags=["promotions"]
)

app.include_router(
    pipelines.router,
    prefix=f"{settings.API_V1_PREFIX}/pipelines",
    tags=["pipelines"]
)

app.include_router(
    credentials.router,
    prefix=f"{settings.API_V1_PREFIX}/credentials",
    tags=["credentials"]
)

app.include_router(
    deployments.router,
    prefix=f"{settings.API_V1_PREFIX}/deployments",
    tags=["deployments"]
)

app.include_router(
    sse.router,
    prefix=f"{settings.API_V1_PREFIX}/sse",
    tags=["sse"]
)

app.include_router(
    background_jobs.router,
    prefix=f"{settings.API_V1_PREFIX}/background-jobs",
    tags=["background-jobs"]
)

app.include_router(
    snapshots.router,
    prefix=f"{settings.API_V1_PREFIX}/snapshots",
    tags=["snapshots"]
)

app.include_router(
    observability.router,
    prefix=f"{settings.API_V1_PREFIX}/observability",
    tags=["observability"]
)

app.include_router(
    notifications.router,
    prefix=f"{settings.API_V1_PREFIX}/notifications",
    tags=["notifications"]
)

app.include_router(
    security.router,
    prefix=f"{settings.API_V1_PREFIX}/security",
    tags=["security"]
)

app.include_router(
    admin_entitlements.router,
    prefix=f"{settings.API_V1_PREFIX}/platform/entitlements",
    tags=["platform-entitlements"]
)

app.include_router(
    admin_audit.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/audit-logs",
    tags=["admin-audit"]
)

app.include_router(
    admin_billing.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/billing",
    tags=["admin-billing"]
)

app.include_router(
    admin_usage.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/usage",
    tags=["admin-usage"]
)

app.include_router(
    admin_overview.router,
    prefix=f"{settings.API_V1_PREFIX}/admin",
    tags=["admin-overview"]
)

app.include_router(
    admin_credentials.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/credentials",
    tags=["admin-credentials"]
)

app.include_router(
    admin_providers.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/providers",
    tags=["admin-providers"]
)

app.include_router(
    support.router,
    prefix=f"{settings.API_V1_PREFIX}/support",
    tags=["support"]
)

app.include_router(
    admin_support.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/support",
    tags=["admin-support"]
)

app.include_router(
    admin_environment_types.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/environment-types",
    tags=["admin-environment-types"]
)

app.include_router(
    admin_retention.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/retention",
    tags=["admin-retention"]
)

app.include_router(
    platform_admins.router,
    prefix=f"{settings.API_V1_PREFIX}/platform/admins",
    tags=["platform-admins"]
)

app.include_router(
    platform_impersonation.router,
    prefix=f"{settings.API_V1_PREFIX}/platform",
    tags=["platform-impersonation"]
)

app.include_router(
    platform_console.router,
    prefix=f"{settings.API_V1_PREFIX}/platform",
    tags=["platform-console"]
)

app.include_router(
    platform_overview.router,
    prefix=f"{settings.API_V1_PREFIX}/platform",
    tags=["platform-overview"]
)

app.include_router(
    providers.router,
    prefix=f"{settings.API_V1_PREFIX}/providers",
    tags=["providers"]
)

app.include_router(
    health.router,
    prefix=f"{settings.API_V1_PREFIX}/health",
    tags=["health"]
)

app.include_router(
    incidents.router,
    prefix=f"{settings.API_V1_PREFIX}/incidents",
    tags=["incidents"]
)

app.include_router(
    drift_policies.router,
    prefix=f"{settings.API_V1_PREFIX}/drift-policies",
    tags=["drift-policies"]
)

app.include_router(
    drift_approvals.router,
    prefix=f"{settings.API_V1_PREFIX}/drift-approvals",
    tags=["drift-approvals"]
)

app.include_router(
    drift_reports.router,
    prefix=f"{settings.API_V1_PREFIX}/reports",
    tags=["drift-reports"]
)

app.include_router(
    canonical_workflows.router,
    prefix=f"{settings.API_V1_PREFIX}/canonical",
    tags=["canonical-workflows"]
)

app.include_router(
    github_webhooks.router,
    prefix=f"{settings.API_V1_PREFIX}",
    tags=["webhooks"]
)


@app.get("/")
async def root():
    return {
        "message": "WorkflowOps API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """
    Cleanup stale background jobs and deployments on startup.
    This handles cases where the server crashed or restarted while jobs were running.
    Also starts the deployment scheduler.
    """
    try:
        logger.info("Cleaning up stale background jobs on startup...")
        cleanup_result = await background_job_service.cleanup_stale_jobs(max_runtime_hours=24)
        logger.info(
            f"Startup cleanup complete: {cleanup_result['cleaned_count']} jobs cleaned "
            f"({cleanup_result['stale_running']} running, {cleanup_result['stale_pending']} pending)"
        )
        
        # Start deployment scheduler
        from app.services.deployment_scheduler import start_scheduler
        await start_scheduler()
        logger.info("Deployment scheduler started")

        # Start drift detection scheduler
        from app.services.drift_scheduler import start_all_drift_schedulers
        await start_all_drift_schedulers()
        logger.info("Drift detection scheduler started")
        
        # Start canonical workflow sync schedulers
        from app.services.canonical_sync_scheduler import start_canonical_sync_schedulers
        await start_canonical_sync_schedulers()
        logger.info("Canonical workflow sync schedulers started")
        
        # Also cleanup stale deployments directly (in case job cleanup didn't catch them)
        try:
            from app.services.database import db_service
            from app.schemas.deployment import DeploymentStatus
            from datetime import timedelta
            
            # Use 1 hour threshold instead of 24 hours - deployments shouldn't run that long
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            stale_deployments = (
                db_service.client.table("deployments")
                .select("*")
                .eq("tenant_id", "00000000-0000-0000-0000-000000000000")
                .eq("status", DeploymentStatus.RUNNING.value)
                .lt("started_at", cutoff_time.isoformat())
                .execute()
            )
            
            if stale_deployments.data:
                logger.info(f"Found {len(stale_deployments.data)} stale deployments to clean up")
                for dep in stale_deployments.data:
                    dep_id = dep.get("id")
                    try:
                        await db_service.update_deployment(dep_id, {
                            "status": "failed",
                            "finished_at": datetime.utcnow().isoformat(),
                            "summary_json": {
                                "error": "Deployment timed out after running for more than 1 hour. Background job may have crashed or server restarted.",
                                "timeout_hours": 1
                            }
                        })
                        logger.info(f"Marked stale deployment {dep_id} as failed")
                    except Exception as dep_error:
                        logger.error(f"Failed to mark stale deployment {dep_id} as failed: {str(dep_error)}")
        except Exception as dep_cleanup_error:
            logger.error(f"Failed to cleanup stale deployments: {str(dep_cleanup_error)}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Failed to cleanup stale jobs on startup: {str(e)}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop all schedulers on shutdown."""
    try:
        from app.services.deployment_scheduler import stop_scheduler
        await stop_scheduler()
        logger.info("Deployment scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping deployment scheduler: {str(e)}")

    try:
        from app.services.drift_scheduler import stop_all_drift_schedulers
        await stop_all_drift_schedulers()
        logger.info("Drift detection scheduler stopped")
        
        # Stop canonical workflow sync schedulers
        from app.services.canonical_sync_scheduler import stop_canonical_sync_schedulers
        await stop_canonical_sync_schedulers()
        logger.info("Canonical workflow sync schedulers stopped")
    except Exception as e:
        logger.error(f"Error stopping drift scheduler: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch unhandled exceptions and emit system.error events.
    """
    # Skip HTTPExceptions as they are already handled
    if isinstance(exc, HTTPException):
        raise exc
    
    tenant_id: str | None = None
    try:
        # Try to get tenant_id from various sources
        tenant_id = request.headers.get("x-tenant-id")
        if not tenant_id:
            # Try to extract from path if it's an environment-specific endpoint
            path_parts = request.url.path.split("/")
            if "environments" in path_parts:
                env_idx = path_parts.index("environments")
                if env_idx + 1 < len(path_parts):
                    # Could potentially look up tenant from environment_id
                    pass
    except Exception:
        tenant_id = None
    
    # Emit system.error event
    try:
        if tenant_id:
            from app.services.notification_service import notification_service
            await notification_service.emit_event(
                tenant_id=tenant_id,
                event_type="system.error",
                environment_id=None,
                metadata={
                    "path": str(request.url.path),
                    "method": request.method,
                    "error_message": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc()
                }
            )
    except Exception as event_error:
        logger.error(f"Failed to emit system.error event: {str(event_error)}")
    
    # Log the error
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Return 500 error
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=4000, reload=True)
