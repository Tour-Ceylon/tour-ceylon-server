from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config.settings import settings


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