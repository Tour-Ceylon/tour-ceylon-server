from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.auth.roles import require_admin
from app.models.enum import ListingType
from app.services.admin.stay_approval_service import StayApprovalService
from app.services.admin.stay_archive_service import StayArchiveService
from app.schemas.stay_schema import StayPropertyListResponse, StayPropertyResponse


class ArchiveStayRequest(BaseModel):
    archive_reason: Optional[str] = None


class RestoreStayRequest(BaseModel):
    pass

router = APIRouter(prefix="/stays", tags=["admin-stays"])


def get_stay_approval_service(db: Session = Depends(get_db)) -> StayApprovalService:
    """Get stay approval service instance"""
    return StayApprovalService(db)


def get_stay_archive_service(db: Session = Depends(get_db)) -> StayArchiveService:
    """Get stay archive service instance"""
    return StayArchiveService(db)


@router.get("/", response_model=StayPropertyListResponse)
async def get_stays(
    status: Optional[str] = Query(None, description="Filter by status (submitted, approved, rejected)"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
    service: StayApprovalService = Depends(get_stay_approval_service),
):
    """Get stays filtered by status for admin review"""
    try:
        return service.list_stays(status)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve stays: {str(e)}"
        )


@router.post("/{property_id}/approve", response_model=dict)
async def approve_stay(
    property_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
    service: StayApprovalService = Depends(get_stay_approval_service),
):
    """Approve a submitted stay property and convert to marketplace listing"""
    try:
        result = service.approve_stay(property_id)
        return {
            "success": True,
            "message": "Stay property approved successfully",
            "listing_id": result["listing_id"],
            "stay_id": str(property_id)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve stay: {str(e)}"
        )


@router.post("/{property_id}/reject", response_model=dict)
async def reject_stay(
    property_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
    service: StayApprovalService = Depends(get_stay_approval_service),
):
    """Reject a submitted stay property"""
    try:
        service.reject_stay(property_id)
        return {
            "success": True,
            "message": "Stay property rejected",
            "stay_id": str(property_id)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject stay: {str(e)}"
        )


@router.get("/{property_id}/archive-impact", response_model=dict)
async def get_archive_impact_analysis(
    property_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
    archive_service: StayArchiveService = Depends(get_stay_archive_service),
):
    """Analyze the impact of archiving a stay property before performing the operation"""
    try:
        analysis = archive_service.get_archive_impact_analysis(property_id)
        return {
            "success": True,
            "analysis": analysis
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze archive impact: {str(e)}"
        )


@router.post("/{property_id}/archive", response_model=dict)
async def archive_stay(
    property_id: UUID,
    request: ArchiveStayRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
    archive_service: StayArchiveService = Depends(get_stay_archive_service),
):
    """Archive a stay property with cascade logic to linked marketplace listing"""
    try:
        archived_by_id = UUID(current_user["user_id"])
        result = archive_service.archive_stay(
            property_id=property_id,
            archived_by_id=archived_by_id,
            archive_reason=request.archive_reason
        )
        return {
            "success": True,
            "message": "Stay property archived successfully",
            **result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive stay: {str(e)}"
        )


@router.post("/{property_id}/restore", response_model=dict)
async def restore_stay(
    property_id: UUID,
    request: RestoreStayRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
    archive_service: StayArchiveService = Depends(get_stay_archive_service),
):
    """Restore an archived stay property"""
    try:
        restored_by_id = UUID(current_user["user_id"])
        result = archive_service.restore_stay(
            property_id=property_id,
            restored_by_id=restored_by_id
        )
        return {
            "success": True,
            "message": "Stay property restored successfully",
            **result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore stay: {str(e)}"
        )


@router.get("/archived", response_model=dict)
async def get_archived_stays(
    archived_by_id: Optional[UUID] = Query(None, description="Filter by who archived the stay"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
    archive_service: StayArchiveService = Depends(get_stay_archive_service),
):
    """Get list of archived stay properties with restore options"""
    try:
        archived_stays = archive_service.list_archived_stays(archived_by_id)
        return {
            "success": True,
            "archived_stays": archived_stays,
            "total": len(archived_stays)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve archived stays: {str(e)}"
        )
