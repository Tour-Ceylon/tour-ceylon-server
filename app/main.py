import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.api.errors import AdminAPIError, admin_api_error_handler

from app.config.database import engine
import app.models
from app.models.base import Base


logger = logging.getLogger(__name__)


# Create tables on startup for the configured PostgreSQL database.
try:
    from app.config.database import DATABASE_URL

    if DATABASE_URL.startswith("sqlite"):
        raise ValueError("SQLite is disabled for this app. Use the pre-production PostgreSQL DATABASE_URL.")

    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
except Exception as e:
    print(f"Database table creation skipped: {e}")
    print("Application will continue but some features may be limited")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Travel Ready Tours")

# Enhanced validation error handler for debugging 422 errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Enhanced validation error handler with detailed logging"""
    logger.error(f"Validation error on {request.method} {request.url}")
    logger.error(f"Request headers: {dict(request.headers)}")
    
    # Get request body for logging
    try:
        body = await request.body()
        logger.error(f"Request body length: {len(body)} bytes")
        if len(body) < 10000:  # Only log small bodies to avoid spam
            logger.error(f"Request body: {body.decode('utf-8')[:1000]}...")
    except Exception as e:
        logger.error(f"Could not read request body: {str(e)}")
    
    # Format validation errors
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        }
        if "input" in error:
            error_detail["received_value"] = str(error["input"])[:100]  # Limit length
        errors.append(error_detail)
        
        # Log each error individually
        logger.error(f"Validation error: {error_detail}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors,
            "message": "Request validation failed. Check the server logs for detailed information."
        }
    )

app.add_exception_handler(AdminAPIError, admin_api_error_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Add CORS middleware (permissive for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
