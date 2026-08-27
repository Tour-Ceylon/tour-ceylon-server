from typing import Any, Dict, Iterable, Optional

from fastapi import Depends, HTTPException, status

from app.core.auth.dependencies import get_auth_claims
from app.models.enum import UserRole


def _normalize_role(role: Optional[str]) -> Optional[str]:
    if role is None:
        return None
    return str(role).strip().lower()


def get_role_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    """
    Extract role from Clerk token claims as a fallback.

    Recommended architecture:
    - Source of truth should be your DB user.role
    - This function is a fallback helper for early integration or token-based checks

    Supported claim locations:
    - claims["role"]
    - claims["metadata"]["role"]
    - claims["public_metadata"]["role"]
    """
    direct_role = claims.get("role")
    if direct_role:
        return _normalize_role(direct_role)

    metadata = claims.get("metadata") or {}
    metadata_role = metadata.get("role")
    if metadata_role:
        return _normalize_role(metadata_role)

    public_metadata = claims.get("public_metadata") or {}
    public_role = public_metadata.get("role")
    if public_role:
        return _normalize_role(public_role)

    return None


def require_authenticated(
    claims: Dict[str, Any] = Depends(get_auth_claims),
) -> Dict[str, Any]:
    """
    Basic authenticated dependency.
    """
    return claims


def require_any_role(
    allowed_roles: Iterable[UserRole | str],
):
    """
    Factory dependency for role-based token checks.

    Example:
        @router.get("/admin")
        def admin_route(claims=Depends(require_any_role([UserRole.ADMIN]))):
            ...

    Note:
    For production authorization, prefer checking your local DB user's role
    after syncing Clerk user -> DB user.
    """
    normalized_allowed = {_normalize_role(r.value if isinstance(r, UserRole) else r) for r in allowed_roles}

    def dependency(
        claims: Dict[str, Any] = Depends(get_auth_claims),
    ) -> Dict[str, Any]:
        current_role = get_role_from_claims(claims)

        if current_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not found",
            )

        if current_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return claims

    return dependency


def require_admin(
    claims: Dict[str, Any] = Depends(require_any_role([UserRole.ADMIN])),
) -> Dict[str, Any]:
    return claims


def require_support_or_admin(
    claims: Dict[str, Any] = Depends(
        require_any_role([UserRole.ADMIN])
    ),
) -> Dict[str, Any]:
    return claims


def require_vendor_or_admin(
    claims: Dict[str, Any] = Depends(
        require_any_role([UserRole.VENDOR, UserRole.ADMIN])
    ),
) -> Dict[str, Any]:
    return claims


def require_tourist_or_admin(
    claims: Dict[str, Any] = Depends(
        require_any_role([UserRole.TOURIST, UserRole.ADMIN])
    ),
) -> Dict[str, Any]:
    return claims