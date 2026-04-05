import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config.database import Base, engine
from app.config.settings import get_settings

# Import concrete models so SQLAlchemy metadata is complete before create_all.
<<<<<<< Updated upstream
from app.models import admin_addon, admin_package, admin_setting, booking, guestReview, listing, reviewMetric, room, user  # noqa: F401
=======
from app.models import booking, listing, review, user  # noqa: F401
>>>>>>> Stashed changes

logger = logging.getLogger(__name__)

app = FastAPI(title="Travel Ready Tours")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
<<<<<<< Updated upstream
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
    except Exception:
        logger.exception("Failed to initialize database tables during startup")
        raise
=======
	settings = get_settings()
	if not settings.auto_create_tables:
		logger.info("Database table auto-creation is disabled. Use AUTO_CREATE_TABLES=true to enable.")
		return
	
	try:
		Base.metadata.create_all(bind=engine)
		logger.info("Database tables initialized")
	except Exception:
		logger.exception("Failed to initialize database tables during startup")
		raise
>>>>>>> Stashed changes


app.include_router(api_router, prefix="/api/v1")
