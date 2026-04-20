from sqlalchemy import Column, String, DateTime, Index, Integer
from sqlalchemy.orm import Session

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.core.utils import generate_otp
from datetime import datetime, timedelta, timezone


class OtpCode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "otp_codes"

    email = Column(String, nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_otp_codes_email_expires', 'email', 'expires_at'),
    )

    @classmethod
    def create_new(cls, db: Session, email: str) -> 'OtpCode':
        """Generate and save new OTP for email"""
        code = generate_otp()  # Implement in utils
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        otp = cls(
            email=email,
            code=code,
            expires_at=expires_at
        )
        db.add(otp)
        db.commit()
        db.refresh(otp)
        return otp

    def is_valid(self, provided_code: str) -> bool:
        if self.expires_at < datetime.now(timezone.utc):
            return False
        if self.attempts >= 3:
            return False
        return self.code == provided_code
