
from app.schemas.driver_schema import DriverSignupRequest, DriverResponse
from app.services.driver_service import DriverService
import json
import os
import logging
import re as _re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Depends
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

# ---------------------------------------------------------------------------
# Allowed MIME types / max size for document uploads
# ---------------------------------------------------------------------------
_ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
_MAX_DOC_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_doc_file(upload: UploadFile, field_name: str) -> bytes:
    """Validate content-type and size; return raw bytes on success."""
    ct = (upload.content_type or "").split(";")[0].strip().lower()
    if ct not in _ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name}: unsupported file type '{ct}'. Allowed: JPEG, PNG, PDF.",
        )
    file_bytes = upload.file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name}: uploaded file is empty.",
        )
    if len(file_bytes) > _MAX_DOC_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name}: file exceeds 10 MB limit.",
        )
    return file_bytes


def _email_to_folder_slug(email: str) -> str:
    """Convert an email address to a safe Cloudinary folder component."""
    return _re.sub(r"[^a-zA-Z0-9_-]", "_", email.split("@")[0])[:40]


@router.post("/driver/signup", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def driver_signup(
    # ── Scalar fields (all come as Form(...) in multipart) ──────────────────
    full_name: str = Form(...),
    nic_number: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: Optional[str] = Form(None),
    clerk_user_id: Optional[str] = Form(None),
    country: Optional[str] = Form("Sri Lanka"),
    vehicle_model_preset_id: Optional[str] = Form(None),
    vehicle_make: str = Form(...),
    vehicle_model: str = Form(...),
    vehicle_plate_number: str = Form(...),
    seats: int = Form(4),
    luggage_capacities: str = Form("[]"),  # JSON-encoded list
    license_number: Optional[str] = Form(None),
    # ── URL fallbacks (for JSON-path clients / tests) ────────────────────────
    license_photo_url: Optional[str] = Form(None),
    nic_photo_url: Optional[str] = Form(None),
    vehicle_registration_doc_url: Optional[str] = Form(None),
    insurance_doc_url: Optional[str] = Form(None),
    police_clearance_doc_url: Optional[str] = Form(None),
    # ── File uploads (optional — if provided, take precedence over URL fields) ─
    license_photo: Optional[UploadFile] = File(None),
    nic_photo: Optional[UploadFile] = File(None),
    vehicle_registration_doc: Optional[UploadFile] = File(None),
    insurance_doc: Optional[UploadFile] = File(None),
    police_clearance_doc: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Phase 1 Driver Signup.

    Accepts **multipart/form-data**.  Each document field can be either:
    - An ``UploadFile`` (the actual file bytes — will be uploaded to Cloudinary),
    - Or a plain URL string via the ``*_url`` fallback fields (for test clients
      and API consumers that pre-host the document themselves).

    File uploads take precedence over URL fields when both are provided.
    """
    from app.integrations.cloudinary import upload_document, delete_document, CloudinaryIntegrationError
    from app.config.settings import settings
    import uuid as _uuid

    # Parse luggage capacities JSON
    try:
        raw_capacities = json.loads(luggage_capacities)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="luggage_capacities must be a valid JSON array.",
        )

    # ── Upload any provided files to Cloudinary ──────────────────────────────
    base_folder = (settings.CLOUDINARY_FOLDER or "tour-ceylon").strip("/")
    email_slug = _email_to_folder_slug(email)
    doc_folder = f"{base_folder}/drivers/{email_slug}"

    uploaded_public_ids: List[str] = []

    def _upload_one(upload: Optional[UploadFile], field_name: str, current_url: Optional[str]) -> Optional[str]:
        """Upload a file if provided, otherwise return the existing URL."""
        if upload is None or not getattr(upload, "filename", None):
            return current_url
        file_bytes = _validate_doc_file(upload, field_name)
        try:
            result = upload_document(file_bytes, folder=doc_folder)
            uploaded_public_ids.append(result["public_id"])
            return result["secure_url"]
        except CloudinaryIntegrationError as exc:
            # Clean up any already-uploaded assets before re-raising
            for pid in uploaded_public_ids:
                try:
                    delete_document(pid)
                except CloudinaryIntegrationError:
                    pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to upload {field_name} to Cloudinary: {exc}",
            ) from exc

    try:
        final_license_photo_url = _upload_one(license_photo, "license_photo", license_photo_url)
        final_nic_photo_url = _upload_one(nic_photo, "nic_photo", nic_photo_url)
        final_vehicle_reg_url = _upload_one(vehicle_registration_doc, "vehicle_registration_doc", vehicle_registration_doc_url)
        final_insurance_url = _upload_one(insurance_doc, "insurance_doc", insurance_doc_url)
        final_police_url = _upload_one(police_clearance_doc, "police_clearance_doc", police_clearance_doc_url)
    except HTTPException:
        raise

    # ── Build DriverSignupRequest and call service ────────────────────────────
    try:
        from uuid import UUID as _UUID
        preset_uuid = _UUID(vehicle_model_preset_id) if vehicle_model_preset_id else None
    except ValueError:
        preset_uuid = None

    from app.schemas.driver_schema import DriverLuggageCapacityItem
    try:
        capacities = [DriverLuggageCapacityItem(**item) for item in raw_capacities]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid luggage_capacities: {exc}",
        )

    payload = DriverSignupRequest(
        full_name=full_name,
        nic_number=nic_number,
        email=email,
        phone=phone,
        password=password,
        clerk_user_id=clerk_user_id,
        country=country or "Sri Lanka",
        vehicle_model_preset_id=preset_uuid,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_plate_number=vehicle_plate_number,
        seats=seats,
        luggage_capacities=capacities,
        license_number=license_number,
        license_photo_url=final_license_photo_url,
        nic_photo_url=final_nic_photo_url,
        vehicle_registration_doc_url=final_vehicle_reg_url,
        insurance_doc_url=final_insurance_url,
        police_clearance_doc_url=final_police_url,
    )

    service = DriverService(db)
    return service.signup_driver(payload)
