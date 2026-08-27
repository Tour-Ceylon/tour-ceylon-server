import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.api.errors import AdminAPIError, admin_api_error_handler

from app.config.database import engine
import app.models
from app.models.base import Base

# Note: Database tables should be created via Alembic migrations
# Base.metadata.create_all(bind=engine) # Removed for serverless deployment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Travel Ready Tours")
app.add_exception_handler(AdminAPIError, admin_api_error_handler)


from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error("Unhandled server exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": origin if origin else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )

# Add CORS middleware
import os
allowed_origins = [
    # Local development
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:5173",
    # Production domains
    "https://tour-ceylon-admin-portal-v2.vercel.app",
    "https://tour-ceylon-client.vercel.app",
    "https://tour-ceylon-server.vercel.app",
]

# Allow additional origins from environment variable
additional_origins = os.getenv("ADDITIONAL_CORS_ORIGINS", "")
if additional_origins:
    allowed_origins.extend([origin.strip() for origin in additional_origins.split(",")])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
