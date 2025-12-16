from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.endpoints import environments, workflows, executions, tags, billing, teams, n8n_users, tenants, auth, restore, promotions, dev, credentials, pipelines, deployments, snapshots, observability, notifications, admin_entitlements, admin_audit, admin_billing, admin_usage, admin_credentials, admin_providers, support, admin_support
import logging
import traceback

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

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
    dev.router,
    prefix=f"{settings.API_V1_PREFIX}/dev",
    tags=["dev"]
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
    admin_entitlements.router,
    prefix=f"{settings.API_V1_PREFIX}/admin/entitlements",
    tags=["admin-entitlements"]
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


@app.get("/")
async def root():
    return {
        "message": "N8N Ops API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch unhandled exceptions and emit system.error events.
    """
    # Skip HTTPExceptions as they are already handled
    if isinstance(exc, HTTPException):
        raise exc
    
    # Extract tenant_id from request if available (from headers, query params, or path)
    tenant_id = None
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
        # Fallback to system tenant if not found
        if not tenant_id:
            tenant_id = "00000000-0000-0000-0000-000000000000"  # MOCK_TENANT_ID
    except Exception:
        tenant_id = "00000000-0000-0000-0000-000000000000"
    
    # Emit system.error event
    try:
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
    uvicorn.run("main:app", host="0.0.0.0", port=3000)