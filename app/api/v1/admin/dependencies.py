from fastapi import Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.services.admin.dashboard_service import AdminDashboardService
from app.services.media_service import MediaService


def get_admin_service(db: Session = Depends(get_db)) -> AdminDashboardService:
    return AdminDashboardService(db)


def get_media_service(db: Session = Depends(get_db)) -> MediaService:
    return MediaService(db)
