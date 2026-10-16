"""Driver profile updates that need an admin's approval before they reach the driver's record.

A driver can propose changes to a small set of profile fields (languages, experience, base location and
payout details). The proposal is stored in `driver_profile_change_requests`; the live `drivers` row is only
written when an admin approves it. Identity, vehicle, documents, status, rating and earnings can never be
changed this way.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.driver import Driver, DriverProfileChangeRequest
from app.models.user import User
from app.repositories.driver_repository import DriverRepository
from app.schemas.driver_schema import DriverProfileChangeSubmit

# The only Driver columns a change request may touch.
EDITABLE_FIELDS = (
    "base_location",
    "languages_spoken",
    "years_experience",
    "bank_account_holder",
    "bank_name",
    "bank_account_number",
)
BANK_FIELDS = ("bank_account_holder", "bank_name", "bank_account_number")

# Drivers who are rejected or suspended cannot change their profile.
EDITABLE_DRIVER_STATUSES = {"pending_review", "approved"}

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"

_NOT_READY = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Profile updates are not available yet. Please try again later.",
)


def _comparable(field: str, value: Any) -> Any:
    if field == "languages_spoken":
        return list(value or [])
    return value


class DriverProfileChangeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DriverRepository(db)

    # ── lookups ────────────────────────────────────────────────────────────────

    def latest_for_driver(self, driver_id: UUID) -> Optional[DriverProfileChangeRequest]:
        """Newest request for a driver, or None. Returns None (rather than failing) when the table has not
        been created yet, so existing driver endpoints keep working until it exists."""
        try:
            with self.db.begin_nested():
                return (
                    self.db.query(DriverProfileChangeRequest)
                    .filter(DriverProfileChangeRequest.driver_id == driver_id)
                    .order_by(DriverProfileChangeRequest.created_at.desc())
                    .first()
                )
        except (ProgrammingError, OperationalError) as exc:
            logger.warning("driver_profile_change.table_unavailable error=%s", str(exc).splitlines()[0])
            return None

    def _pending_for_driver(self, driver_id: UUID) -> Optional[DriverProfileChangeRequest]:
        latest = self._latest_or_503(driver_id)
        return latest if latest and latest.status == PENDING else None

    def _latest_or_503(self, driver_id: UUID) -> Optional[DriverProfileChangeRequest]:
        try:
            with self.db.begin_nested():
                return (
                    self.db.query(DriverProfileChangeRequest)
                    .filter(DriverProfileChangeRequest.driver_id == driver_id)
                    .order_by(DriverProfileChangeRequest.created_at.desc())
                    .first()
                )
        except (ProgrammingError, OperationalError):
            raise _NOT_READY

    def _driver_for_user(self, user_id: UUID) -> Driver:
        driver = self.repo.get_driver_by_user_id(user_id)
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found.")
        return driver

    # ── driver actions ─────────────────────────────────────────────────────────

    def submit(self, user_id: UUID, data: DriverProfileChangeSubmit) -> DriverProfileChangeRequest:
        driver = self._driver_for_user(user_id)

        if driver.status not in EDITABLE_DRIVER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your driver account is not active, so its profile cannot be changed. Please contact support.",
            )

        requested: Dict[str, Any] = data.model_dump(exclude_none=True)
        # Keep only what actually differs from what is saved today.
        changes = {
            field: value
            for field, value in requested.items()
            if field in EDITABLE_FIELDS and _comparable(field, getattr(driver, field)) != value
        }
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nothing has changed. Update at least one detail before sending it for review.",
            )

        # Payout details only make sense as a complete set.
        merged_bank = {field: changes.get(field, getattr(driver, field)) for field in BANK_FIELDS}
        if any(merged_bank.values()) and not all(merged_bank.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter the account holder, bank name and account number together.",
            )

        pending = self._pending_for_driver(driver.id)
        try:
            if pending:
                # One open request at a time: sending again replaces what is waiting for review.
                pending.proposed = changes
                request = pending
            else:
                request = DriverProfileChangeRequest(driver_id=driver.id, status=PENDING, proposed=changes)
                self.db.add(request)
            self.db.commit()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            raise _NOT_READY
        self.db.refresh(request)
        return request

    def withdraw(self, user_id: UUID) -> DriverProfileChangeRequest:
        driver = self._driver_for_user(user_id)
        pending = self._pending_for_driver(driver.id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="There is no pending update to withdraw.")
        pending.status = WITHDRAWN
        self.db.commit()
        self.db.refresh(pending)
        return pending

    # ── admin actions ──────────────────────────────────────────────────────────

    def approve(self, driver_id: UUID, admin: User) -> DriverProfileChangeRequest:
        driver = self.repo.get_driver_by_id(driver_id)
        if not driver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")
        pending = self._pending_for_driver(driver_id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This driver has no update waiting for review.")

        # Re-check what is about to be saved, whatever is in the table.
        try:
            proposal = DriverProfileChangeSubmit.model_validate(pending.proposed or {})
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The stored update is not valid and cannot be approved: {exc}",
            )

        for field, value in proposal.model_dump(exclude_none=True).items():
            if field in EDITABLE_FIELDS:
                setattr(driver, field, value)

        pending.status = APPROVED
        pending.reviewed_by_user_id = admin.id
        pending.reviewed_at = datetime.now(timezone.utc)
        pending.rejection_reason = None
        self.db.commit()
        self.db.refresh(pending)
        logger.info("driver_profile_change.approved driver_id=%s request_id=%s admin_id=%s", driver_id, pending.id, admin.id)
        return pending

    def reject(self, driver_id: UUID, admin: User, reason: str) -> DriverProfileChangeRequest:
        pending = self._pending_for_driver(driver_id)
        if not pending:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This driver has no update waiting for review.")
        pending.status = REJECTED
        pending.rejection_reason = reason.strip()
        pending.reviewed_by_user_id = admin.id
        pending.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(pending)
        logger.info("driver_profile_change.rejected driver_id=%s request_id=%s admin_id=%s", driver_id, pending.id, admin.id)
        return pending
