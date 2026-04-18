from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timezone

from app.models.otp import OtpCode


class OtpRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, email: str) -> OtpCode:
        """Create new OTP for email (deletes old ones first)"""
        # Delete old OTPs for this email
        self.delete_old_by_email(email)
        
        otp = OtpCode.create_new(self.db, email)
        return otp

    def get_latest_by_email(self, email: str) -> Optional[OtpCode]:
        """Get most recent valid OTP for email"""
        return self.db.query(OtpCode).filter(
            OtpCode.email == email,
            OtpCode.expires_at > datetime.now(timezone.utc)
        ).order_by(OtpCode.created_at.desc()).first()

    def verify_and_increment(self, email: str, code: str) -> bool:
        """Verify code and increment attempts, return True if valid"""
        otp = self.get_latest_by_email(email)
        if not otp or not otp.is_valid(code):
            if otp:
                otp.attempts += 1
                self.db.commit()
            return False
        otp.attempts += 1
        self.db.commit()
        return True

    def delete_old_by_email(self, email: str):
        """Delete expired/invalid OTPs for email"""
        self.db.query(OtpCode).filter(
            and_(
                OtpCode.email == email,
                OtpCode.expires_at < datetime.now(timezone.utc)
            )
        ).delete()
        self.db.commit()

    def cleanup_expired(self):
        """Global cleanup of expired OTPs (call periodically)"""
        self.db.query(OtpCode).filter(
            OtpCode.expires_at < datetime.now(timezone.utc)
        ).delete()
        self.db.commit()


def get_otp_repository(db: Session = None):
    if db is None:
        from app.config.database import SessionLocal
        db = SessionLocal()
    return OtpRepository(db)
