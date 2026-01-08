from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # N8N Configuration
    N8N_API_URL: str = "https://ns8i839t.rpcld.net"
    N8N_API_KEY: str = "123"

    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str

    # Database
    DATABASE_URL: str

    # GitHub Configuration
    GITHUB_TOKEN: str = ""
    GITHUB_REPO_OWNER: str = ""
    GITHUB_REPO_NAME: str = ""
    GITHUB_BRANCH: str = "main"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "WorkflowOps"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Bulk Operations Configuration
    MAX_BULK_WORKFLOWS: int = 50

    # Execution Retention Configuration
    EXECUTION_RETENTION_ENABLED: bool = True
    EXECUTION_RETENTION_DAYS: int = 90
    RETENTION_JOB_BATCH_SIZE: int = 1000
    RETENTION_JOB_SCHEDULE_CRON: str = "0 2 * * *"  # Daily at 2 AM

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Supabase Auth Configuration
    SUPABASE_JWT_SECRET: str = ""  # From Supabase Dashboard > Settings > API > JWT Secret

    # Stripe Configuration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID_MONTHLY: str = ""
    STRIPE_PRO_PRICE_ID_YEARLY: str = ""

    # Email Configuration (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@n8nops.com"
    SMTP_FROM_NAME: str = "WorkflowOps"
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
