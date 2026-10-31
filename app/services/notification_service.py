from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.bookingInquiry import BookingInquiry
from app.models.notification import ClientNotification, NotificationType
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification_schema import (
    CreateNotificationRequest,
    ClientNotificationResponse,
    ClientNotificationListResponse,
    BookingConfirmationPreviewResponse,
    BookingConfirmationCustomer,
    BookingConfirmationItem
)


class NotificationService:
    """Service class for handling client notification operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificationRepository(db)
    
    def create_booking_status_notification(
        self,
        inquiry: BookingInquiry,
        status: str
    ) -> Optional[ClientNotification]:
        """Create a notification for booking status changes"""
        
        logger.info(f"Processing notification creation for inquiry {inquiry.reference} with status '{status}'")
        
        # Determine notification type and content based on status
        if status == "converted_to_booking":
            notification_type = NotificationType.BOOKING_CONFIRMED
            title = "Booking request confirmed"
            message = f"Your booking request {inquiry.reference} has been confirmed. View your confirmation details."
            
        elif status == "cancelled":
            notification_type = NotificationType.BOOKING_CANCELLED
            title = "Booking request cancelled"
            message = f"Your booking request {inquiry.reference} was cancelled. Contact support if you need help."
            
        elif status == "quoted":
            notification_type = NotificationType.BOOKING_QUOTED
            title = "Quote ready"
            message = f"Your booking request {inquiry.reference} has a quote update."
            
        else:
            logger.info(f"No notification needed for status: {status}")
            return None
        
        logger.info(f"Determined notification type: {notification_type} for status: {status}")
        
        # Check for duplicates to avoid spam
        duplicate_exists = self.repository.check_duplicate_notification(inquiry.id, notification_type)
        logger.info(f"Duplicate check result for inquiry {inquiry.id} and type {notification_type}: {duplicate_exists}")
        
        if duplicate_exists:
            logger.info(f"Duplicate notification avoided for inquiry {inquiry.reference} with type {notification_type}")
            return None
        
        # Create payload with confirmation preview data
        payload = self._build_confirmation_payload(inquiry) if status == "converted_to_booking" else {}
        logger.info(f"Created payload for notification: {len(payload)} keys")
        
        # Create notification request
        notification_request = CreateNotificationRequest(
            user_id=None,  # Guest bookings don't have user_id yet
            recipient_email=inquiry.email,
            type=notification_type,
            title=title,
            message=message,
            booking_inquiry_id=inquiry.id,
            reference=inquiry.reference,
            payload=payload
        )
        
        logger.info(f"Creating notification with recipient_email={inquiry.email}, type={notification_type}")
        
        try:
            notification = self.repository.create_notification(notification_request)
            logger.info(f"Successfully created {notification_type} notification id={notification.id} for inquiry {inquiry.reference}")
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification for inquiry {inquiry.reference}: {str(e)}", exc_info=True)
            return None
    
    def list_my_notifications(
        self,
        current_user: User,
        limit: int = 20,
        offset: int = 0
    ) -> ClientNotificationListResponse:
        """List notifications for the current user"""
        
        logger.info(f"Listing notifications for user", extra={
            "user_id": str(current_user.id),
            "user_email": current_user.email,
            "limit": limit,
            "offset": offset
        })
        
        notifications, total_count, unread_count = self.repository.list_user_notifications(
            user=current_user,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Found {len(notifications)} notifications for user {current_user.email} (total: {total_count}, unread: {unread_count})")
        
        # Convert to response format
        notification_items = [
            self._convert_to_response(notification) for notification in notifications
        ]
        
        return ClientNotificationListResponse(
            items=notification_items,
            unreadCount=unread_count,  # Use the alias name
            total=total_count
        )
    
    def mark_notification_read(
        self,
        notification_id: UUID,
        current_user: User
    ) -> Optional[ClientNotificationResponse]:
        """Mark a notification as read"""
        
        notification = self.repository.mark_notification_read(notification_id, current_user)
        if notification:
            return self._convert_to_response(notification)
        return None
    
    def mark_all_notifications_read(self, current_user: User) -> int:
        """Mark all notifications as read for current user"""
        return self.repository.mark_all_notifications_read(current_user)
    
    def get_confirmation_preview(
        self,
        notification_id: UUID,
        current_user: User
    ) -> Optional[BookingConfirmationPreviewResponse]:
        """Get booking confirmation preview for a notification"""
        
        # Get notification and verify user access
        notification = self.repository.get_notification_for_user(notification_id, current_user)
        if not notification or not notification.booking_inquiry_id:
            return None
        
        # Get the booking inquiry
        from app.services.booking_inquiry_service import get_booking_inquiry_service
        inquiry_service = get_booking_inquiry_service(self.db)
        inquiry = inquiry_service.get_inquiry_by_id(notification.booking_inquiry_id)
        
        if not inquiry:
            return None
        
        return self._build_confirmation_preview(inquiry, notification)
    
    def _convert_to_response(self, notification: ClientNotification) -> ClientNotificationResponse:
        """Convert notification model to response format"""
        return ClientNotificationResponse(
            id=notification.id,
            type=notification.type.value,
            title=notification.title,
            message=notification.message,
            reference=notification.reference,
            bookingInquiryId=notification.booking_inquiry_id,
            isRead=notification.is_read,
            createdAt=notification.created_at,
            payload=notification.payload
        )
    
    def _build_confirmation_payload(self, inquiry: BookingInquiry) -> Dict[str, Any]:
        """Build confirmation preview payload for storage"""
        return {
            "subtotal": float(inquiry.subtotal),
            "total": float(inquiry.total),
            "currency": inquiry.currency.value,
            "travelers": inquiry.number_of_travelers,
            "customerName": f"{inquiry.first_name} {inquiry.last_name}",
            "customerEmail": inquiry.email
        }
    
    def _build_confirmation_preview(
        self,
        inquiry: BookingInquiry,
        notification: ClientNotification
    ) -> BookingConfirmationPreviewResponse:
        """Build full confirmation preview response"""
        
        # Customer information
        customer = BookingConfirmationCustomer(
            name=f"{inquiry.first_name} {inquiry.last_name}",
            email=inquiry.email,
            phone=inquiry.phone,
            nationality=inquiry.nationality
        )
        
        # Cart items
        items = []
        for cart_item in inquiry.cart_items:
            # Handle both dict and object formats
            item_data = cart_item if isinstance(cart_item, dict) else cart_item.__dict__
            
            # Safely extract listing_id and convert to UUID
            listing_id_raw = item_data.get("listing_id") or item_data.get("listingId")
            try:
                from uuid import UUID
                listing_id = UUID(str(listing_id_raw)) if listing_id_raw else UUID('00000000-0000-0000-0000-000000000000')
            except (ValueError, TypeError):
                logger.warning(f"Invalid listing_id in cart item: {listing_id_raw}")
                listing_id = UUID('00000000-0000-0000-0000-000000000000')
            
            # Safely extract travel date
            travel_date = item_data.get("travel_date") or item_data.get("travelDate")
            if isinstance(travel_date, datetime):
                travel_date = travel_date.isoformat()
            elif travel_date:
                travel_date = str(travel_date)
            
            confirmation_item = BookingConfirmationItem(
                title=item_data.get("title", "Travel Service"),
                listingId=listing_id,
                type=item_data.get("type", "service"),
                travelDate=travel_date,
                travelers=int(item_data.get("travelers", 1)),
                price=float(item_data.get("price", 0)),
                currency=inquiry.currency.value
            )
            items.append(confirmation_item)
        
        # Support information
        support = {
            "email": "support@travelreadytours.com",
            "phone": "+94 77 123 4567"
        }
        
        # Next steps
        next_steps = [
            "Our travel team will contact you with final pickup/details.",
            "Keep this reference number for support.",
            "Please check your email for future voucher updates."
        ]
        
        # Important notes
        important_notes = [
            "This confirmation is subject to availability.",
            "Final details will be provided 24-48 hours before travel.",
            "Please arrive at pickup location 15 minutes early."
        ]
        
        return BookingConfirmationPreviewResponse(
            reference=inquiry.reference,
            status="confirmed",
            customer=customer,
            items=items,
            subtotal=float(inquiry.subtotal),
            total=float(inquiry.total),
            currency=inquiry.currency.value,
            specialRequests=inquiry.special_requests,
            confirmedAt=notification.created_at,
            updatedAt=inquiry.updated_at,
            support=support,
            nextSteps=next_steps,
            importantNotes=important_notes
        )


def get_notification_service(db: Session) -> NotificationService:
    """Factory function to get notification service instance"""
    return NotificationService(db)
