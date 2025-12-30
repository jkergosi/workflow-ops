"""
Health check endpoint for service status monitoring.
Provides comprehensive health status for database, Supabase, and other services.
"""
import logging
logger = logging.getLogger(__name__)
logger.info("Loading health module")

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any
import logging

from app.services.database import db_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def health_check() -> JSONResponse:
    """
    Comprehensive health check endpoint.

    Returns:
        - status: "healthy", "degraded", or "unhealthy"
        - timestamp: Current UTC timestamp
        - services: Status of each service (database, supabase)

    Status codes:
        - 200: All services healthy
        - 503: One or more services unhealthy
    """
    checks: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check database/Supabase connection
    try:
        # Try a simple query to test database connectivity
        response = db_service.client.table("users").select("id").limit(1).execute()
        checks["services"]["database"] = {
            "status": "healthy",
            "latency_ms": None  # Could add timing if needed
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Database health check failed: {error_msg}")
        checks["services"]["database"] = {
            "status": "unhealthy",
            "error": error_msg
        }
        checks["status"] = "degraded"

    # Check Supabase service specifically (same as database for now, but could be separate)
    try:
        # Test Supabase by checking if we can access the environments table
        response = db_service.client.table("environments").select("id").limit(1).execute()
        checks["services"]["supabase"] = {
            "status": "healthy"
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Supabase health check failed: {error_msg}")
        checks["services"]["supabase"] = {
            "status": "unhealthy",
            "error": error_msg
        }
        checks["status"] = "degraded"

    # Check if all services are unhealthy
    all_unhealthy = all(
        svc.get("status") == "unhealthy"
        for svc in checks["services"].values()
    )
    if all_unhealthy and checks["services"]:
        checks["status"] = "unhealthy"

    # Return appropriate status code
    status_code = 200 if checks["status"] == "healthy" else 503

    return JSONResponse(content=checks, status_code=status_code)


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Kubernetes-style readiness probe.
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Quick database check
        db_service.client.table("users").select("id").limit(1).execute()
        return JSONResponse(
            content={"ready": True, "timestamp": datetime.utcnow().isoformat()},
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={"ready": False, "error": str(e), "timestamp": datetime.utcnow().isoformat()},
            status_code=503
        )


@router.get("/live")
async def liveness_check() -> JSONResponse:
    """
    Kubernetes-style liveness probe.
    Returns 200 if the service is running (not deadlocked).
    """
    return JSONResponse(
        content={"alive": True, "timestamp": datetime.utcnow().isoformat()},
        status_code=200
    )
