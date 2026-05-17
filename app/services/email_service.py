from sqlalchemy.orm import Session
from typing import Dict, Any

from app.integrations.email_provider import email_provider
from app.repositories.otp_repo import get_otp_repository
from app.core.logging import logger
from starlette.concurrency import run_in_threadpool


async def send_verification_otp(
    db: Session,
    email: str
) -> Dict[str, Any]:
    """Generate OTP, save to DB, send email"""
    try:
        otp_repo = get_otp_repository(db)
        otp = otp_repo.create(email)

        success = await run_in_threadpool(email_provider.send_otp_email, email, otp.code)

        if success:
            logger.info("Verification OTP sent to %s", email)
            return {"success": True, "message": "OTP sent"}
        else:
            # Rollback on send failure
            otp_repo.delete_old_by_email(email)
            logger.error("Email send failed for %s", email)
            raise ValueError("Failed to send verification email")

    except Exception as e:
        logger.error("Error sending OTP to %s: %s", email, str(e))
        raise


async def verify_otp_code(
    db: Session,
    email: str,
    code: str
) -> Dict[str, Any]:
    """Verify OTP code against DB"""
    try:
        otp_repo = get_otp_repository(db)
        is_valid = otp_repo.verify_and_increment(email, code)

        if is_valid:
            logger.info("OTP verified for %s", email)
            return {"success": True, "message": "Code verified"}
        else:
            logger.warning("Invalid OTP attempt for %s", email)
            return {"success": False, "message": "Invalid or expired code"}

    except Exception as e:
        logger.error("Error verifying OTP for %s: %s", email, str(e))
        raise