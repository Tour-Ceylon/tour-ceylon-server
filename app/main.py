from fastapi import FastAPI
from app.api.router import api_router

from app.config.database import engine
from app.models.user import Base

# Create tables on startup - with error handling
try:
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables created successfully")
except Exception as e:
    logging.warning(f"Failed to create database tables: {e}")
    logging.warning("Server will continue running without database functionality")

# Create tables on startup
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Travel Ready Tours")

app.include_router(api_router, prefix="/api/v1")
