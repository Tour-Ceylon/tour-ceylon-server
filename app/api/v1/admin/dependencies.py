from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.config.database import get_db
from app.models.enum import UserRole
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.admin.dashboard_service import AdminDashboardService


def get_admin_service(db: Session = Depends(get_db)) -> AdminDashboardService:
    return AdminDashboardService(db)


def require_admin_user(
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = UserRepository(db).get_by_id(current_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found",
        )

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user

