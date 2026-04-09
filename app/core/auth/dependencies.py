from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.auth.clerk import clerk_verifier


def extract_bearer_token(authorization: Optional[str]) -> str:
    """
    Extract raw bearer token from Authorization header.
    Expected format:
        Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )

    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    return token


def get_auth_claims(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Dependency that returns verified Clerk JWT claims.
    """
    token = extract_bearer_token(authorization)
    return clerk_verifier.verify_session_token(token)


def get_clerk_user_id(
    claims: Dict[str, Any] = Depends(get_auth_claims),
) -> str:
    """
    Dependency that returns the Clerk user id from verified claims.
    """
    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user identity",
        )
    return clerk_user_id


def get_auth_email(
    claims: Dict[str, Any] = Depends(get_auth_claims),
) -> Optional[str]:
    """
    Best-effort email extraction from token claims.
    Depending on Clerk token template, email may or may not be present.
    """
    return (
        claims.get("email")
        or claims.get("primary_email_address")
        or claims.get("email_address")
    )


def get_auth_full_name(
    claims: Dict[str, Any] = Depends(get_auth_claims),
) -> Optional[str]:
    """
    Best-effort full name extraction from token claims.
    """
    full_name = claims.get("full_name") or claims.get("name")
    if full_name:
        return full_name

    first_name = claims.get("given_name") or claims.get("first_name")
    last_name = claims.get("family_name") or claims.get("last_name")

    combined = " ".join(part for part in [first_name, last_name] if part)
    return combined or None