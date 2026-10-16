"""Driver profile photos that an admin must approve before they are shown anywhere.

A driver uploads a photo (taken with the camera or picked from the gallery). It is stored in Cloudinary and recorded
in `driver_avatar_submissions` as "pending". Only a photo an admin has approved is ever returned as the driver's
`avatar_url`; the driver and admins can also see the newest submission so they can review or fix it.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.integrations.cloudinary import CloudinaryIntegrationError, delete_image, upload_image
from app.models.driver import Driver, DriverAvatarSubmission
from app.models.user import User
from app.repositories.driver_repository import DriverRepository

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024
EDITABLE_DRIVER_STATUSES = {"pending_review", "approved"}

_NOT_READY = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Profile photos are not available yet. Please try again later.",
)


def _looks_like_image(data: bytes) -> bool:
    """Check the bytes, not just the declared type: JPEG, PNG or WebP."""
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


class DriverAvatarService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DriverRepository(db)

    # ── lookups (never fail an existing endpoint if the table is missing) ───────

    def latest_for_driver(self, driver_id: UUID) -> Optional[DriverAvatarSubmission]:
        try:
            with self.db.begin_nested():
                return (
                    self.db.query(DriverAvatarSubmission)
                    .filter(DriverAvatarSubmission.driver_id == driver_id)
                    .order_by(DriverAvatarSubmission.created_at.desc())
                    .first()
                )
        except (ProgrammingError, OperationalError) as exc:
            logger.warning("driver_avatar.table_unavailable error=%s", str(exc).splitlines()[0])
            return None

    def approved_url_for_driver(self, driver_id: UUID) -> Optional[str]:
        """The photo to display: the most recently approved one, or None."""
        try:
            with self.db.begin_nested():
                row = (
                    self.db.query(DriverAvatarSubmission)
                    .filter(DriverAvatarSubmission.driver_id == driver_id, DriverAvatarSubmission.status == APPROVED)
                    .order_by(DriverAvatarSubmission.reviewed_at.desc().nullslast(), DriverAvatarSubmission.created_at.desc())
                    .first()
                )
                return row.image_url if row else None
        except (ProgrammingError, OperationalError):
            return None

    def approved_urls_for_drivers(self, driver_ids: List[UUID]) -> Dict[UUID, str]:
        """Batch version for lists. Returns {driver_id: url} for drivers that have an approved photo."""
        if not driver_ids:
            return {}
        try:
            with self.db.begin_nested():
                rows = (
                    self.db.query(DriverAvatarSubmission)
                    .filter(DriverAvatarSubmission.driver_id.in_(driver_ids), DriverAvatarSubmission.status == APPROVED)
                    .order_by(DriverAvatarSubmission.reviewed_at.asc().nullsfirst(), DriverAvatarSubmission.created_at.asc())
                    .all()
                )
        except (ProgrammingError, OperationalError):
            return {}
        urls: Dict[UUID, str] = {}
        for row in rows:  # ascending, so the newest approval wins
            urls[row.driver_id] = row.image_url
        return urls

    def _pending(self, driver_id: UUID) -> Optional[DriverAvatarSubmission]:
        latest = self.latest_for_driver(driver_id)
        return latest if latest and latest.status == PENDING else None

    def _driver_for_user(self, user_id: UUID) -> Driver:
        driver = self.repo.get_driver_by_user_id(user_id)
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found.")
        return driver

    # ── driver actions ──────────────────────────────────────────────────────────

    def submit(self, user_id: UUID, data: bytes, content_type: Optional[str]) -> DriverAvatarSubmission:
        driver = self._driver_for_user(user_id)
        if driver.status not in EDITABLE_DRIVER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your driver account is not active, so your photo cannot be changed. Please contact support.",
            )

        declared = (content_type or "").split(";")[0].strip().lower()
        if declared not in ALLOWED_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Please use a JPEG, PNG or WebP photo.")
        if not data:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The photo is empty. Please choose another.")
        if len(data) > MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The photo is larger than 5 MB. Please choose a smaller one.")
        if not _looks_like_image(data):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That file is not a valid photo.")

        previous = self._pending_or_503(driver.id)

        try:
            uploaded = upload_image(data, folder=f"driver_avatars/{driver.id}")
        except CloudinaryIntegrationError as exc:
            logger.error("driver_avatar.upload_failed driver_id=%s error=%s", driver.id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="We couldn't upload your photo right now. Please try again in a moment.",
            )

        try:
            if previous:
                # Sending a new photo replaces the one waiting for review.
                previous.status = WITHDRAWN
            submission = DriverAvatarSubmission(
                driver_id=driver.id,
                image_url=uploaded["secure_url"],
                cloudinary_public_id=uploaded.get("public_id"),
                status=PENDING,
            )
            self.db.add(submission)
            self.db.commit()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            self._discard_asset(uploaded.get("public_id"))
            raise _NOT_READY

        if previous and previous.cloudinary_public_id:
            self._discard_asset(previous.cloudinary_public_id)
        self.db.refresh(submission)
        return submission

    def withdraw(self, user_id: UUID) -> DriverAvatarSubmission:
        driver = self._driver_for_user(user_id)
        pending = self._pending_or_503(driver.id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="There is no photo waiting for review.")
        pending.status = WITHDRAWN
        self.db.commit()
        self._discard_asset(pending.cloudinary_public_id)
        self.db.refresh(pending)
        return pending

    # ── admin actions ───────────────────────────────────────────────────────────

    def approve(self, driver_id: UUID, admin: User) -> DriverAvatarSubmission:
        if not self.repo.get_driver_by_id(driver_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")
        pending = self._pending_or_503(driver_id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This driver has no photo waiting for review.")
        pending.status = APPROVED
        pending.reviewed_by_user_id = admin.id
        pending.reviewed_at = datetime.now(timezone.utc)
        pending.rejection_reason = None
        self.db.commit()
        self.db.refresh(pending)
        logger.info("driver_avatar.approved driver_id=%s submission_id=%s admin_id=%s", driver_id, pending.id, admin.id)
        return pending

    def reject(self, driver_id: UUID, admin: User, reason: str) -> DriverAvatarSubmission:
        pending = self._pending_or_503(driver_id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This driver has no photo waiting for review.")
        pending.status = REJECTED
        pending.rejection_reason = reason.strip()
        pending.reviewed_by_user_id = admin.id
        pending.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(pending)
        logger.info("driver_avatar.rejected driver_id=%s submission_id=%s admin_id=%s", driver_id, pending.id, admin.id)
        return pending

    # ── helpers ─────────────────────────────────────────────────────────────────

    def _pending_or_503(self, driver_id: UUID) -> Optional[DriverAvatarSubmission]:
        try:
            with self.db.begin_nested():
                latest = (
                    self.db.query(DriverAvatarSubmission)
                    .filter(DriverAvatarSubmission.driver_id == driver_id)
                    .order_by(DriverAvatarSubmission.created_at.desc())
                    .first()
                )
        except (ProgrammingError, OperationalError):
            raise _NOT_READY
        return latest if latest and latest.status == PENDING else None

    @staticmethod
    def _discard_asset(public_id: Optional[str]) -> None:
        if not public_id:
            return
        try:
            delete_image(public_id)
        except CloudinaryIntegrationError as exc:
            logger.warning("driver_avatar.cleanup_failed public_id=%s error=%s", public_id, exc)
