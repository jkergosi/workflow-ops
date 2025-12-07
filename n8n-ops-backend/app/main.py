from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import environments, workflows, executions, tags, billing, teams, n8n_users, tenants, auth, restore, promotions

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)