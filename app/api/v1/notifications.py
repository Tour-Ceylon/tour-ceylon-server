from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.logging import logger
from app.models.user import User
from app.schemas.notification_schema import (
    ClientNotificationListResponse,
    ClientNotificationResponse,
    BookingConfirmationPreviewResponse
)
from app.services.notification_service import get_notification_service

router = APIRouter()


@router.get("/", response_model=ClientNotificationListResponse)
def list_my_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List notifications for the authenticated user.
    
    Returns notifications accessible by the user's ID or email address.
    Includes unread count and total count for UI badge display.
    """
    try:
        logger.info(f"API: GET /notifications - user {current_user.id} ({current_user.email})")
        
        service = get_notification_service(db)
        result = service.list_my_notifications(
            current_user=current_user,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"API: Returning {len(result.items)} notifications (unread: {result.unread_count}, total: {result.total})")
        return result
        
    except Exception as e:
        logger.error(f"Error listing notifications for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications"
        )


@router.patch("/{notification_id}/read", response_model=ClientNotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    
    Only works if the current user owns the notification by user_id or email.
    """
    try:
        service = get_notification_service(db)
        notification = service.mark_notification_read(notification_id, current_user)
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or access denied"
            )
        
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all notifications as read for the authenticated user.
    
    Returns the count of notifications that were marked as read.
    """
    try:
        service = get_notification_service(db)
        updated_count = service.mark_all_notifications_read(current_user)
        
        return {
            "message": "All notifications marked as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read"
        )


@router.get("/{notification_id}/confirmation-preview", response_model=BookingConfirmationPreviewResponse)
def get_confirmation_preview(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get booking confirmation preview for a notification.
    
    Only works for booking_confirmed notifications that the user owns.
    Returns detailed confirmation data that can be used for modal display.
    """
    try:
        service = get_notification_service(db)
        preview = service.get_confirmation_preview(notification_id, current_user)
        
        if not preview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Confirmation preview not found or access denied"
            )
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting confirmation preview for notification {notification_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve confirmation preview"
        )