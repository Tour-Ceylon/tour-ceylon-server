import os
from typing import List


class Settings:
    """Centralized application settings from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Create tables on startup (dev/local only; production uses migrations)
    AUTO_CREATE_TABLES: bool = os.getenv("AUTO_CREATE_TABLES", "false").lower() in ("true", "1", "yes")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # Clerk Authentication
    CLERK_ISSUER: str = os.getenv("CLERK_ISSUER", "")
    CLERK_JWKS_URL: str = os.getenv("CLERK_JWKS_URL", "")
    CLERK_AUDIENCE: str = os.getenv("CLERK_AUDIENCE", "")
    CLERK_SECRET_KEY: str = os.getenv("CLERK_SECRET_KEY", "")
    CLERK_API_URL: str = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1")
    
    # Supabase
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    
    def validate(self) -> None:
        """Validate critical settings at startup."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
        if not self.CLERK_ISSUER and not self.CLERK_JWKS_URL:
            raise ValueError("Either CLERK_ISSUER or CLERK_JWKS_URL must be set")
        if not self.SUPABASE_JWT_SECRET:
            raise ValueError("SUPABASE_JWT_SECRET is required")


settings = Settings()
