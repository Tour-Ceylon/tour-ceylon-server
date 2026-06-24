from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.notification import ClientNotification, NotificationType
from app.models.user import User
from app.schemas.notification_schema import CreateNotificationRequest


class NotificationRepository:
    """Repository class for ClientNotification model database operations"""

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        """Base query for client notifications"""
        return self.db.query(ClientNotification)

    def create_notification(self, notification_data: CreateNotificationRequest) -> ClientNotification:
        """Create a new client notification"""
        # Normalize email to lowercase
        recipient_email = notification_data.recipient_email.lower().strip()
        
        from app.core.logging import logger
        logger.info(f"Creating notification in database", extra={
            "recipient_email": recipient_email,
            "type": notification_data.type,
            "title": notification_data.title,
            "booking_inquiry_id": str(notification_data.booking_inquiry_id),
            "reference": notification_data.reference
        })
        
        db_notification = ClientNotification(
            user_id=notification_data.user_id,
            recipient_email=recipient_email,
            type=notification_data.type,
            title=notification_data.title,
            message=notification_data.message,
            booking_inquiry_id=notification_data.booking_inquiry_id,
            reference=notification_data.reference,
            payload=notification_data.payload or {},
            is_read=False
        )
        
        self.db.add(db_notification)
        self.db.commit()
        self.db.refresh(db_notification)
        
        logger.info(f"Successfully created notification id={db_notification.id} in database")
        return db_notification

    def get_by_id(self, notification_id: UUID) -> Optional[ClientNotification]:
        """Get a notification by ID"""
        return self._base_query().filter(ClientNotification.id == notification_id).first()

    def list_user_notifications(
        self,
        user: User,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[List[ClientNotification], int, int]:
        """List notifications for a user with pagination and counts"""
        # User can access notifications by user_id OR by matching email
        user_email = user.email.lower().strip() if user.email else ""
        
        base_filter = or_(
            ClientNotification.user_id == user.id,
            func.lower(ClientNotification.recipient_email) == user_email
        )
        
        # Get total count
        total_count = self._base_query().filter(base_filter).count()
        
        # Get unread count
        unread_count = self._base_query().filter(
            base_filter,
            ClientNotification.is_read == False
        ).count()
        
        # Get paginated notifications
        notifications = (
            self._base_query()
            .filter(base_filter)
            .order_by(ClientNotification.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        return notifications, total_count, unread_count

    def mark_notification_read(self, notification_id: UUID, user: User) -> Optional[ClientNotification]:
        """Mark a notification as read if the user owns it"""
        user_email = user.email.lower().strip() if user.email else ""
        
        notification = (
            self._base_query()
            .filter(
                ClientNotification.id == notification_id,
                or_(
                    ClientNotification.user_id == user.id,
                    func.lower(ClientNotification.recipient_email) == user_email
                )
            )
            .first()
        )
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(notification)
        
        return notification

    def mark_all_notifications_read(self, user: User) -> int:
        """Mark all notifications as read for a user"""
        user_email = user.email.lower().strip() if user.email else ""
        
        updated_count = (
            self.db.query(ClientNotification)
            .filter(
                or_(
                    ClientNotification.user_id == user.id,
                    func.lower(ClientNotification.recipient_email) == user_email
                ),
                ClientNotification.is_read == False
            )
            .update({
                "is_read": True,
                "read_at": datetime.utcnow()
            })
        )
        
        self.db.commit()
        return updated_count

    def get_notification_for_user(self, notification_id: UUID, user: User) -> Optional[ClientNotification]:
        """Get a notification if the user owns it"""
        user_email = user.email.lower().strip() if user.email else ""
        
        return (
            self._base_query()
            .filter(
                ClientNotification.id == notification_id,
                or_(
                    ClientNotification.user_id == user.id,
                    func.lower(ClientNotification.recipient_email) == user_email
                )
            )
            .first()
        )

    def check_duplicate_notification(
        self,
        booking_inquiry_id: UUID,
        notification_type: NotificationType
    ) -> bool:
        """Check if a notification of this type already exists for this booking inquiry"""
        existing = (
            self._base_query()
            .filter(
                ClientNotification.booking_inquiry_id == booking_inquiry_id,
                ClientNotification.type == notification_type
            )
            .first()
        )
        
        return existing is not None