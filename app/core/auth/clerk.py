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
def create_clerk_user(
    email: str,
    password: Optional[str] = None,
    full_name: Optional[str] = None,
    role: str = "VENDOR",
    vendor_status: Optional[str] = None,
    approved_categories: Optional[list] = None,
    company_name: Optional[str] = None,
) -> Optional[str]:
    """
    Creates a user in Clerk via the Clerk Backend API with verified email and returns the clerk_user_id.
    If the user already exists in Clerk, retrieves their clerk_user_id and syncs metadata.
    """
    secret_key = settings.CLERK_SECRET_KEY or os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        logger.warning("Clerk secret key is not set; skipping Clerk user creation.")
        return None

    base_url = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1").rstrip("/")
    url = f"{base_url}/users"

    # Derive first name and last name
    first_name = None
    last_name = None
    if full_name:
        parts = full_name.strip().split(" ", 1)
        first_name = parts[0]
        if len(parts) > 1:
            last_name = parts[1]

    # Derive valid alphanumeric username
    clean_prefix = "".join(c for c in email.split("@")[0] if c.isalnum() or c == "_")
    if len(clean_prefix) < 4:
        clean_prefix = f"user_{clean_prefix}"
    username = clean_prefix[:30]

    public_metadata: Dict[str, Any] = {
        "role": role,
    }
    if vendor_status is not None:
        public_metadata["vendorStatus"] = vendor_status
    if approved_categories is not None:
        public_metadata["approvedCategories"] = approved_categories
    if company_name is not None:
        public_metadata["company"] = company_name

    payload: Dict[str, Any] = {
        "email_address": [email],
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "skip_password_checks": True,
        "public_metadata": public_metadata,
    }
    if password:
        payload["password"] = password
    else:
        payload["skip_password_requirement"] = True

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {secret_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            # Handle username collision by appending random suffix and retrying
            if response.status_code == 422:
                err_data = response.json()
                err_str = str(err_data)
                if "username" in err_str and "taken" in err_str:
                    import random
                    payload["username"] = f"{username[:24]}_{random.randint(1000, 9999)}"
                    response = client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {secret_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

            if response.status_code in (200, 201):
                data = response.json()
                clerk_id = data.get("id")
                logger.info("Successfully created Clerk user: %s for %s", clerk_id, email)
                return clerk_id

            # If user already exists, lookup by email
            logger.warning("Clerk user creation response %s: %s", response.status_code, response.text)
            lookup_res = client.get(
                f"{base_url}/users",
                headers={"Authorization": f"Bearer {secret_key}"},
                params={"email_address": [email]},
            )
            if lookup_res.status_code == 200:
                users_list = lookup_res.json()
                if users_list and len(users_list) > 0:
                    clerk_id = users_list[0]["id"]
                    sync_user_metadata_to_clerk(
                        clerk_user_id=clerk_id,
                        role=role,
                        vendor_status=vendor_status,
                        approved_categories=approved_categories,
                        company_name=company_name,
                    )
                    return clerk_id

    except Exception as exc:
        logger.error("Failed to create Clerk user for %s: %s", email, str(exc))

    return None
