import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
import httpx
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User
from app.services.email_service import send_verification_otp, verify_otp_code
from app.services.auth_service import verify_username as verify_username_service
from app.api.deps import get_current_user
from app.schemas.user_schema import UserResponse


logger = logging.getLogger("app.auth")
router = APIRouter()


class VerifyUsernameRequest(BaseModel):
    email: EmailStr


class SendVerificationRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    user_exists: bool = None


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


async def _send_clerk_verification(email: str) -> bool:
    """Send verification email through Clerk"""
    secret_key = _get_clerk_secret()
    # Use the correct Clerk API endpoint for creating email verification
    verify_url = f"{_clerk_backend_api_url()}/email_addresses"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # First, create an email address for verification
            create_response = await client.post(
                verify_url,
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "email_address": email,
                    "verified": False
                }
            )
            
            if create_response.status_code not in [200, 201, 422]:  # 422 might mean already exists
                logger.error("Failed to create email address: %s", create_response.text)
                return False
                
            # Extract email address ID from response or handle existing email
            if create_response.status_code == 422:
                # Email might already exist, try to find it
                search_response = await client.get(
                    f"{_clerk_backend_api_url()}/email_addresses",
                    headers={"Authorization": f"Bearer {secret_key}"},
                    params={"email_address": email}
                )
                if search_response.status_code != 200:
                    return False
                emails = search_response.json()
                if not emails:
                    return False
                email_id = emails[0]["id"]
            else:
                email_data = create_response.json()
                email_id = email_data["id"]
            
            # Now prepare verification for this email
            verification_response = await client.post(
                f"{verify_url}/{email_id}/prepare_verification",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "strategy": "email_code"
                }
            )
            
            if verification_response.status_code in [200, 201]:
                logger.info("Verification email sent successfully to %s", email)
                return True
            else:
                logger.error("Verification preparation failed: %s", verification_response.text)
                return False
                
    except httpx.HTTPError as exc:
        logger.error("Failed to send Clerk verification: %s", str(exc))
        return False
    except Exception as exc:
        logger.error("Unexpected error in verification: %s", str(exc))
        return False


async def _verify_clerk_code(email: str, code: str) -> bool:
    """Verify OTP code through Clerk"""
    secret_key = _get_clerk_secret()
    verify_url = f"{_clerk_backend_api_url()}/email_addresses"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{verify_url}/attempt_verification",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "email_address": email,
                    "code": code,
                    "strategy": "email_code"
                }
            )
    except httpx.HTTPError as exc:
        logger.error("Failed to verify Clerk code: %s", str(exc))
        return False
    
    if response.status_code == 200:
        logger.info("Code verified successfully for %s", email)
        return True
    
    logger.error("Clerk code verification failed: %s", response.text)
    return False


@router.post("/verify-username", response_model=AuthResponse)
async def verify_username(
    request: VerifyUsernameRequest,
    db: Session = Depends(get_db)
):
    """Step 1: Check if user exists in Clerk and local DB"""
    try:
        result = await verify_username_service(db, request.email)
        return AuthResponse(**result)
    except Exception as e:
        logger.error("Error verifying username: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify username"
        )


@router.post("/send-verification", response_model=AuthResponse)
async def send_verification_code(request: SendVerificationRequest, db: Session = Depends(get_db)):
    """Step 2: Send OTP verification code via custom service"""
    try:
        result = await send_verification_otp(db, request.email)
        return AuthResponse(**result)
    except Exception as e:
        logger.error("Error sending verification: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code"
        )


@router.post("/verify-code", response_model=AuthResponse)
async def verify_code(request: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Step 3: Verify the OTP code"""
    try:
        result = await verify_otp_code(db, request.email, request.code)
        if result["success"]:
            return AuthResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["message"]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error verifying code: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify code"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get the authenticated local user resolved from Clerk auth."""
    return current_user


@router.get("/health")
async def auth_health():
    """Health check for auth service"""
    return {"status": "healthy", "service": "auth"}