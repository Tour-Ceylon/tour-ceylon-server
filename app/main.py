from fastapi import FastAPI
from app.api.router import api_router

from app.config.database import engine
from app.models.user import Base

# Create tables on startup
Base.metadata.create_all(bind=engine)

# Create tables on startup
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Travel Ready Tours")

app.include_router(api_router, prefix="/api/v1")
