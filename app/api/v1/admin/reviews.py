"""FEAT-3: guest-review moderation. Lists reviews and sets them published / hidden / pending.

Note: nothing in the customer site creates reviews yet (the old guest-review model was
removed), so this list stays empty until a submission flow is built.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.config.database import get_db
from app.models.enum import ReviewStatus, UserRole
from app.models.listing import Listing
from app.models.review import Review
from app.models.user import User

router = APIRouter(
    prefix="/reviews",
    tags=["admin-reviews"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))],
)


class ReviewStatusBody(BaseModel):
    status: ReviewStatus


def _row(review: Review, listing_title: str | None, user_email: str | None) -> dict:
    return {
        "id": str(review.id),
        "listing_id": str(review.listing_id),
        "listing_title": listing_title,
        "user_email": user_email,
        "rating": review.rating,
        "title": review.title,
        "status": review.status.value if hasattr(review.status, "value") else str(review.status),
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


@router.get("")
def list_reviews(
    status_filter: ReviewStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Review, Listing.title, User.email)
        .join(Listing, Listing.id == Review.listing_id)
        .join(User, User.id == Review.user_id)
    )
    if status_filter:
        query = query.filter(Review.status == status_filter)
    total = query.count()
    rows = query.order_by(Review.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": [_row(r, title, email) for r, title, email in rows], "total": total, "page": page, "per_page": per_page}


@router.patch("/{review_id}/status")
def set_review_status(review_id: UUID, body: ReviewStatusBody, db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    review.status = body.status
    db.commit()
    db.refresh(review)
    listing = db.get(Listing, review.listing_id)
    user = db.get(User, review.user_id)
    return _row(review, listing.title if listing else None, user.email if user else None)
