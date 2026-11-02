"""FEAT-2: assign a driver and/or a guide to a tour, safari or experience request.

Rules:
  * only for approved requests (quoted or converted_to_booking), never a cancelled one;
  * a driver must be a registered, approved driver; a guide is a typed name and phone
    (guides have no accounts yet);
  * transfers are dispatched from Transfer Requests, not here;
  * unassigning keeps the row (status 'cancelled') as a record.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.config.database import get_db
from app.models.bookingInquiry import BookingInquiry
from app.models.driver import Driver
from app.models.enum import InquiryStatus, UserRole
from app.models.inquiryAssignment import InquiryAssignment
from app.models.user import User

router = APIRouter(
    prefix="/inquiries/{inquiry_id}/assignments",
    tags=["admin-assignments"],
)

ASSIGNABLE = (InquiryStatus.QUOTED, InquiryStatus.CONVERTED_TO_BOOKING)


class AssignmentCreate(BaseModel):
    assignee_type: str = Field(..., pattern="^(guide|driver)$")
    driver_id: UUID | None = None
    guide_name: str | None = Field(None, max_length=150)
    guide_phone: str | None = Field(None, max_length=40)
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        if self.assignee_type == "driver" and not self.driver_id:
            raise ValueError("Choose a driver")
        if self.assignee_type == "guide" and not (self.guide_name or "").strip():
            raise ValueError("Enter the guide's name")
        return self


def _inquiry_or_404(db: Session, inquiry_id: UUID) -> BookingInquiry:
    inquiry = db.get(BookingInquiry, inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking inquiry not found")
    return inquiry


def _is_transfer_only(inquiry: BookingInquiry) -> bool:
    items = inquiry.cart_items or []
    return bool(items) and all(
        str(i.get("listing_id") or i.get("listingId") or "").lower().startswith("transfer-") for i in items
    )


def _serialize(db: Session, row: InquiryAssignment) -> dict:
    driver = None
    if row.driver_id:
        record = db.get(Driver, row.driver_id)
        if record:
            profile = (record.user.business_profile or {}) if record.user else {}
            driver = {
                "id": str(record.id),
                "full_name": record.user.full_name if record.user else None,
                "phone": profile.get("phone") if isinstance(profile, dict) else None,
                "vehicle": f"{record.vehicle_make} {record.vehicle_model}".strip(),
                "plate": record.vehicle_plate_number,
            }
    return {
        "id": str(row.id),
        "inquiry_id": str(row.inquiry_id),
        "assignee_type": row.assignee_type,
        "driver": driver,
        "guide_name": row.guide_name,
        "guide_phone": row.guide_phone,
        "notes": row.notes,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
def list_assignments(
    inquiry_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    _inquiry_or_404(db, inquiry_id)
    rows = (
        db.query(InquiryAssignment)
        .filter(InquiryAssignment.inquiry_id == inquiry_id)
        .order_by(InquiryAssignment.created_at.desc())
        .all()
    )
    return [_serialize(db, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_assignment(
    inquiry_id: UUID,
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.ADMIN])),
):
    inquiry = _inquiry_or_404(db, inquiry_id)
    if inquiry.status not in ASSIGNABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the request first. A guide or driver can only be assigned to an approved request.",
        )
    if _is_transfer_only(inquiry):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfers are dispatched from Transfer Requests, not assigned here.",
        )

    if body.assignee_type == "driver":
        driver = db.get(Driver, body.driver_id)
        if driver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
        if driver.status != "approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved drivers can be assigned")
        already = (
            db.query(InquiryAssignment)
            .filter(
                InquiryAssignment.inquiry_id == inquiry_id,
                InquiryAssignment.driver_id == body.driver_id,
                InquiryAssignment.status == "assigned",
            )
            .first()
        )
        if already:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This driver is already assigned")

    row = InquiryAssignment(
        inquiry_id=inquiry_id,
        assignee_type=body.assignee_type,
        driver_id=body.driver_id if body.assignee_type == "driver" else None,
        guide_name=(body.guide_name or "").strip() or None if body.assignee_type == "guide" else None,
        guide_phone=(body.guide_phone or "").strip() or None if body.assignee_type == "guide" else None,
        notes=(body.notes or "").strip() or None,
        status="assigned",
        assigned_by=admin.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(db, row)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign(
    inquiry_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role([UserRole.ADMIN])),
):
    row = db.get(InquiryAssignment, assignment_id)
    if row is None or row.inquiry_id != inquiry_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    row.status = "cancelled"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
