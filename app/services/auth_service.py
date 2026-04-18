import os
import httpx
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.email_service import send_verification_otp, verify_otp_code
from app.repositories.user_repo import get_user_repository
from app.config.database import get_db
from app.core.logging import logger


def _clerk_backend_api_url() -> str:
    base_url = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1")
    return base_url.rstrip("/")


def _get_clerk_secret() -> str:
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk configuration is missing"
        )
    return secret_key


async def _check_clerk_user_exists(email: str) -> Dict[str, Any]:
    """Check if user exists in Clerk by email"""
    secret_key = _get_clerk_secret()
    lookup_url = f"{_clerk_backend_api_url()}/users"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                lookup_url,
                headers={"Authorization": f"Bearer {secret_key}"},
                params={"email_address": email}
            )
    except httpx.HTTPError as exc:
        logger.error("Failed to check Clerk user: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
    
    if response.status_code == 200:
        users = response.json()
        return {"exists": len(users) > 0, "users": users}
    
    logger.error("Clerk API error: %s", response.text)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication service error"
    )


async def verify_username(
    db: Session,
    email: str
) -> Dict[str, Any]:
    """Check if user exists in Clerk or local DB"""
    try:
        # Check Clerk
        clerk_result = await _check_clerk_user_exists(email)
        clerk_exists = clerk_result["exists"]
        
        # Check local DB
        user_repo = get_user_repository(db)
        local_user = user_repo.get_by_email(email)
        
        if clerk_exists or local_user:
            return {
                "success": True,
                "message": "User found. Ready to send verification code.",
                "user_exists": True
            }
        else:
            return {
                "success": False,
                "message": "User not found with this email.",
                "user_exists": False
            }
    except Exception as e:
        logger.error("Error verifying username %s: %s", email, str(e))
        raise


# Re-export for convenience
async def send_verification_otp_service(db: Session, email: str):
    return await send_verification_otp(db, email)


async def verify_otp_code_service(db: Session, email: str, code: str):
    return await verify_otp_code(db, email, code)