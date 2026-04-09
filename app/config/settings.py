# Placeholder
# Placeholderfrom functools import lru_cache
from typing import List, Optional
from functools import lru_cache
from pydantic import AnyHttpUrl, Field, field_validator
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    """
    Central configuration for the application.

    Loads from:
    - .env file
    - environment variables
    """

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        case_sensitive=True,
        extra="ignore"
    )

    # ---------------------------------------------------
    # APP CONFIG
    # ---------------------------------------------------
    APP_NAME: str = "Tour Ceylon API"
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"

    # ---------------------------------------------------
    # SERVER
    # ---------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---------------------------------------------------
    # DATABASE
    # ---------------------------------------------------
    DATABASE_URL: Optional[str] = None

    # ---------------------------------------------------
    # CLERK AUTH CONFIG
    # ---------------------------------------------------
    CLERK_SECRET_KEY: Optional[str] = None
    CLERK_PUBLISHABLE_KEY: Optional[str] = None

    # REQUIRED for backend verification
    CLERK_JWT_PUBLIC_KEY: Optional[str] = None
    CLERK_ISSUER: Optional[str] = None

    # optional (usually not required unless configured in Clerk)
    CLERK_AUDIENCE: Optional[str] = None

    # ---------------------------------------------------
    # FRONTEND URLS (CORS)
    # ---------------------------------------------------
    CLIENT_APP_URL: AnyHttpUrl = "http://localhost:3000"
    ADMIN_APP_URL: AnyHttpUrl = "http://localhost:3001"

    ADDITIONAL_CORS_ORIGINS: List[AnyHttpUrl] = Field(default_factory=list)

    # ---------------------------------------------------
    # PAYMENT CONFIG
    # ---------------------------------------------------
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_SECRET: Optional[str] = None

    # ---------------------------------------------------
    # EMAIL / NOTIFICATIONS
    # ---------------------------------------------------
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    EMAIL_FROM: Optional[str] = None

    # ---------------------------------------------------
    # FILE STORAGE (Cloudinary or future)
    # ---------------------------------------------------
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    CLOUDINARY_FOLDER: Optional[str] = "tour-ceylon"

    # ---------------------------------------------------
    # SECURITY
    # ---------------------------------------------------
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # fallback if needed

    # ---------------------------------------------------
    # LOGGING
    # ---------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # ---------------------------------------------------
    # UTILS
    # ---------------------------------------------------
    def get_cors_origins(self) -> List[str]:
        """
        Build final CORS origin list.
        """
        origins = [
            str(self.CLIENT_APP_URL),
            str(self.ADMIN_APP_URL),
        ]

        origins.extend([str(o) for o in self.ADDITIONAL_CORS_ORIGINS])

        return list(set(origins))
    
    @property
    def clerk_public_key(self) -> Optional[str]:
        if self.CLERK_JWT_PUBLIC_KEY:
            return self.CLERK_JWT_PUBLIC_KEY.replace("\\n", "\n")
        return None

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production"}:
                return False
        return value


# ---------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
