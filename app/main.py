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

# Create tables on startup
Base.metadata.create_all(bind=engine)

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
