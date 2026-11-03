from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class InquiryAssignment(Base, UUIDMixin, TimestampMixin):
    """FEAT-2: who delivers a tour, safari or experience booking.

    A request can have a driver (a registered, approved driver) and/or a guide. Guides have no
    accounts in the system yet, so a guide is a name and phone number the admin types in.
    Unassigning keeps the row with status 'cancelled' so there is a record of who was assigned.
    """

    __tablename__ = "inquiry_assignments"
    __table_args__ = (
        CheckConstraint("assignee_type IN ('guide', 'driver')", name="ck_inquiry_assignments_type"),
        CheckConstraint("status IN ('assigned', 'cancelled')", name="ck_inquiry_assignments_status"),
        CheckConstraint(
            "(assignee_type = 'driver' AND driver_id IS NOT NULL) OR (assignee_type = 'guide' AND guide_name IS NOT NULL)",
            name="ck_inquiry_assignments_assignee",
        ),
    )

    inquiry_id = Column(UUID(as_uuid=True), ForeignKey("booking_inquiries.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_type = Column(String(10), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True)
    guide_name = Column(String(150), nullable=True)
    guide_phone = Column(String(40), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(10), nullable=False, default="assigned", index=True)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
