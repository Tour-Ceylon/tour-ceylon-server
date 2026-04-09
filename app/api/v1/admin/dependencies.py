from fastapi import Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.services.admin.dashboard_service import AdminDashboardService
from app.api.deps import require_admin


def get_admin_service(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardService:
    """Dependency providing admin dashboard service to authenticated admin users only."""
    return AdminDashboardService(db)

