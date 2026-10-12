from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.admin.packages import PackageResponse
from app.services.package_service import PackageService

router = APIRouter()


def get_package_service(db: Session = Depends(get_db)) -> PackageService:
    return PackageService(db)


@router.get("/", response_model=List[PackageResponse])
def get_packages(
    response: Response,
    package_service: PackageService = Depends(get_package_service),
):
    """Get all active packages for the client frontend."""
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return package_service.get_active_packages()


@router.get("/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: UUID,
    response: Response,
    package_service: PackageService = Depends(get_package_service),
):
    """Get a single active package for the client frontend."""
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return package_service.get_active_package(package_id)
