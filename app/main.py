import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.api.errors import AdminAPIError, admin_api_error_handler

from app.config.database import engine
from app.config.settings import settings
import app.models
from app.models.base import Base

# Validate settings at startup
settings.validate()

# Create tables on startup only if explicitly enabled (dev/local mode)
if settings.AUTO_CREATE_TABLES:
    Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Travel Ready Tours")
app.add_exception_handler(AdminAPIError, admin_api_error_handler)

# Add CORS middleware with centralized origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
