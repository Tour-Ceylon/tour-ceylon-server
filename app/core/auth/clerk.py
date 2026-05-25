import os
import logging
import httpx
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config.settings import settings

logger = logging.getLogger("app.auth")


class ClerkTokenVerifier:
    """
    Verifies Clerk-issued session JWTs using the Clerk JWT public key.

    Required settings:
    - settings.CLERK_JWT_PUBLIC_KEY
    - settings.CLERK_ISSUER

    Optional:
    - settings.CLERK_AUDIENCE
    """

    def __init__(self) -> None:
        self.public_key: str = settings.CLERK_JWT_PUBLIC_KEY
        self.issuer: str = settings.CLERK_ISSUER
        self.audience: Optional[str] = getattr(settings, "CLERK_AUDIENCE", None)

        if not self.public_key:
            raise ValueError("CLERK_JWT_PUBLIC_KEY is not configured")

        if not self.issuer:
            raise ValueError("CLERK_ISSUER is not configured")

    def verify_session_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Clerk session token and return decoded claims.
        """
        try:
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": bool(self.audience),
            }

            payload = jwt.decode(
                token=token,
                key=self.public_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience if self.audience else None,
                options=options,
            )

            # Clerk user id should be in "sub"
            if not payload.get("sub"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing subject claim",
                )

            return payload

        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            ) from exc


clerk_verifier = ClerkTokenVerifier()


def sync_user_metadata_to_clerk(
    clerk_user_id: str,
    role: str,
    vendor_status: Optional[str] = None,
    approved_categories: Optional[list] = None,
    company_name: Optional[str] = None,
) -> bool:
    """
    Sync user's role and vendor status back to Clerk's public_metadata.
    This serves as a fallback for frontends (since Clerk JWT holds these claims).
    """
    secret_key = settings.CLERK_SECRET_KEY or os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        logger.warning("Clerk secret key is not set; skipping metadata sync.")
        return False

    if not clerk_user_id:
        logger.warning("No clerk_user_id provided for metadata sync.")
        return False

    base_url = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1").rstrip("/")
    url = f"{base_url}/users/{clerk_user_id}/metadata"

    public_metadata = {
        "role": role,
    }
    if vendor_status is not None:
        public_metadata["vendorStatus"] = vendor_status
    if approved_categories is not None:
        public_metadata["approvedCategories"] = approved_categories
    if company_name is not None:
        public_metadata["company"] = company_name

    payload = {
        "public_metadata": public_metadata
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.patch(
                url,
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            logger.info("Successfully synced metadata to Clerk for user %s", clerk_user_id)
            return True
    except Exception as exc:
        logger.error("Failed to sync metadata to Clerk for user %s: %s", clerk_user_id, str(exc))
        return False