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
    PROJECT_NAME: str = "N8N Ops"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Auth0 Configuration
    AUTH0_DOMAIN: str = ""
    AUTH0_API_AUDIENCE: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""

    # Stripe Configuration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID_MONTHLY: str = ""
    STRIPE_PRO_PRICE_ID_YEARLY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
