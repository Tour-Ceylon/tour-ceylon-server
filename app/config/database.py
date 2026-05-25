import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)

dotenv_values_map = dotenv_values(ENV_PATH)
database_url = os.getenv("DATABASE_URL")

# Keep explicit SQLite overrides for tests, but prefer the project .env for the app.
if not database_url or not database_url.startswith("sqlite"):
    database_url = dotenv_values_map.get("DATABASE_URL") or database_url
    if database_url:
        os.environ["DATABASE_URL"] = database_url

# Get database URL from environment variables
DATABASE_URL = database_url

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")


def _mask_database_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.netloc:
        return url

    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{username}:***@" if username else ""
    return urlunsplit((parsed.scheme, f"{auth}{hostname}{port}", parsed.path, parsed.query, parsed.fragment))


print(f"[database] DATABASE_URL resolved to: {_mask_database_url(DATABASE_URL)}")

engine_kwargs: dict[str, object] = {
    "pool_pre_ping": True,
    "echo": False,
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_recycle": 3600,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Create session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
