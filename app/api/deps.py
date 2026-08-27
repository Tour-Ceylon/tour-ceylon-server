import os
import time
import logging
from dataclasses import dataclass
from datetime import timezone, datetime
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.models.user import User
from app.models.enum import UserRole
from app.integrations.supabase_client import build_supabase_access_token


logger = logging.getLogger("app.auth")


bearer_scheme = HTTPBearer(auto_error=False)
_jwks_cache: dict | None = None
_jwks_cached_at = 0.0
_jwks_ttl_seconds = 300
_clerk_profile_cache: dict[str, tuple[float, dict]] = {}


def _clerk_backend_api_url() -> str:
    base_url = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1")
    return base_url.rstrip("/")


def _clerk_jwks_url() -> str:
    explicit_url = os.getenv("CLERK_JWKS_URL")
    if explicit_url:
        return explicit_url

    issuer = os.getenv("CLERK_ISSUER")
    if issuer:
        return f"{issuer.rstrip('/')}/.well-known/jwks.json"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Clerk JWKS configuration is missing. Set CLERK_ISSUER or CLERK_JWKS_URL.",
    )


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_cached_at

    if _jwks_cache and (time.time() - _jwks_cached_at) < _jwks_ttl_seconds:
        logger.debug(
            "auth.jwks_cache_hit url=%s age_seconds=%.2f ttl_seconds=%s",
            _clerk_jwks_url(),
            time.time() - _jwks_cached_at,
            _jwks_ttl_seconds,
        )
        return _jwks_cache

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(_clerk_jwks_url())
            response.raise_for_status()
            jwks_payload = response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch Clerk JWKS. Please verify Clerk issuer/JWKS configuration.",
        ) from exc

    if not isinstance(jwks_payload, dict) or not isinstance(jwks_payload.get("keys"), list):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid Clerk JWKS response format.",
        )

    _jwks_cache = jwks_payload
    _jwks_cached_at = time.time()
    logger.debug(
        "auth.jwks_refreshed url=%s key_count=%s kids=%s",
        _clerk_jwks_url(),
        len(_jwks_cache.get("keys", [])),
        [key.get("kid") for key in _jwks_cache.get("keys", [])],
    )
    return _jwks_cache


def _decode_and_verify_clerk_token(token: str) -> dict:
    logger.debug(
        "auth.token_received length=%s has_dots=%s",
        len(token),
        token.count(".") == 2,
    )
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    kid = unverified_header.get("kid")
    logger.debug("auth.token_unverified_header kid=%s alg=%s", kid, unverified_header.get("alg"))
    jwks = _get_jwks()
    jwks_kids = [key.get("kid") for key in jwks.get("keys", [])]
    matching_key = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)

    if not matching_key:
        logger.warning(
            "auth.token_kid_not_found token_kid=%s jwks_kids=%s jwks_url=%s",
            kid,
            jwks_kids,
            _clerk_jwks_url(),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify authentication token",
        )

    audience = os.getenv("CLERK_AUDIENCE")
    issuer = os.getenv("CLERK_ISSUER")
    options = {
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
        "leeway": 300,
    }
    logger.debug(
        "auth.token_verification_config issuer=%s audience=%s verify_iss=%s verify_aud=%s",
        issuer,
        audience,
        options["verify_iss"],
        options["verify_aud"],
    )

    try:
        claims = jwt.decode(
            token,
            matching_key,
            algorithms=["RS256"],
            audience=audience if audience else None,
            issuer=issuer if issuer else None,
            options=options,
        )
    except jwt.ExpiredSignatureError as exc:
        logger.warning(
            "auth.token_expired issuer=%s audience=%s error=%s",
            issuer,
            audience,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        ) from exc
    except JWTError as exc:
        logger.warning(
            "auth.token_decode_failed issuer=%s audience=%s error=%s",
            issuer,
            audience,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token verification failed",
        ) from exc

    exp = claims.get("exp")
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        )

    return claims


def _extract_clerk_email(clerk_user: dict) -> str | None:
    primary_email_address_id = clerk_user.get("primary_email_address_id")
    email_addresses = clerk_user.get("email_addresses") or []

    if not isinstance(email_addresses, list):
        return None

    for email_address in email_addresses:
        if not isinstance(email_address, dict):
            continue
        if email_address.get("id") == primary_email_address_id:
            return email_address.get("email_address")

    for email_address in email_addresses:
        if isinstance(email_address, dict) and email_address.get("email_address"):
            return email_address.get("email_address")

    return None


def _extract_clerk_name(clerk_user: dict) -> str | None:
    full_name = clerk_user.get("full_name")
    if isinstance(full_name, str) and full_name.strip():
        return full_name.strip()

    first_name = clerk_user.get("first_name")
    last_name = clerk_user.get("last_name")
    combined = " ".join(part.strip() for part in [first_name, last_name] if isinstance(part, str) and part.strip())
    if combined:
        return combined

    username = clerk_user.get("username")
    return username.strip() if isinstance(username, str) and username.strip() else None


def _fetch_clerk_user(subject: str) -> dict | None:
    if not settings.AUTH_ENABLE_CLERK_FALLBACK_SYNC:
        logger.debug("auth.clerk_user_lookup_disabled sub=%s", subject)
        return None

    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        logger.warning("auth.clerk_secret_missing_for_user_lookup sub=%s", subject)
        return None

    cached_entry = _clerk_profile_cache.get(subject)
    if cached_entry:
        cached_at, payload = cached_entry
        cache_age = time.time() - cached_at
        if cache_age < settings.AUTH_CLERK_PROFILE_CACHE_TTL_SECONDS:
            logger.debug(
                "auth.clerk_user_lookup_cache_hit sub=%s age_seconds=%.2f ttl_seconds=%s",
                subject,
                cache_age,
                settings.AUTH_CLERK_PROFILE_CACHE_TTL_SECONDS,
            )
            return payload
        logger.debug(
            "auth.clerk_user_lookup_cache_stale sub=%s age_seconds=%.2f ttl_seconds=%s",
            subject,
            cache_age,
            settings.AUTH_CLERK_PROFILE_CACHE_TTL_SECONDS,
        )

    lookup_url = f"{_clerk_backend_api_url()}/users/{subject}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                lookup_url,
                headers={"Authorization": f"Bearer {secret_key}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("auth.clerk_user_lookup_failed sub=%s error=%s", subject, str(exc))
        return None

    if response.status_code == status.HTTP_404_NOT_FOUND:
        logger.warning("auth.clerk_user_not_found sub=%s", subject)
        return None

    try:
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("auth.clerk_user_lookup_invalid_response sub=%s error=%s", subject, str(exc))
        return None

    if not isinstance(payload, dict):
        logger.warning("auth.clerk_user_lookup_unexpected_payload sub=%s", subject)
        return None

    _clerk_profile_cache[subject] = (time.time(), payload)
    logger.info("auth.clerk_user_lookup_succeeded sub=%s", subject)
    return payload


def _find_local_user(db: Session, subject: str, email: str | None) -> User | None:
    user = db.query(User).filter(User.clerk_user_id == subject).first()

    if email and user is None:
        user = db.query(User).filter(User.email == email).first()

    if user is None:
        try:
            subject_as_uuid = UUID(subject)
            user = db.query(User).filter(User.id == subject_as_uuid).first()
        except ValueError:
            user = None

    return user


def _apply_user_updates(db: Session, user: User, subject: str, email: str | None, full_name: str | None) -> tuple[User, str]:
    sync_action = "unchanged"
    did_update_user = False

    if subject and user.clerk_user_id != subject:
        user.clerk_user_id = subject
        did_update_user = True
        sync_action = "updated"

    if email and user.email != email:
        existing_email_owner = db.query(User).filter(User.email == email, User.id != user.id).first()
        if existing_email_owner:
            sync_action = "conflict"
            logger.warning(
                "auth.email_sync_conflict clerk_user_id=%s email=%s existing_user_id=%s",
                subject,
                email,
                existing_email_owner.id,
            )
        else:
            user.email = email
            did_update_user = True
            sync_action = "updated"

    if full_name and user.full_name != full_name:
        user.full_name = full_name
        did_update_user = True
        sync_action = "updated"

    if did_update_user:
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception as err:
            db.rollback()
            logger.warning("auth.apply_user_updates_rollback user_id=%s error=%s", user.id, str(err))

    return user, sync_action


def _resolve_local_user(db: Session, claims: dict, *, force_clerk_sync: bool = False) -> User:
    email = claims.get("email") or claims.get("email_address")
    subject = claims.get("sub")
    full_name = claims.get("name")

    if not subject:
        logger.warning("auth.token_missing_subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing the required subject claim",
        )

    user = _find_local_user(db, subject, email)
    should_sync_from_clerk = force_clerk_sync

    if user is not None:
        has_minimal_profile = bool(user.email) and bool(user.full_name)
        if not settings.AUTH_SYNC_ON_MISSING_LOCAL_USER_ONLY and not has_minimal_profile:
            should_sync_from_clerk = True

        if not should_sync_from_clerk:
            user, sync_action = _apply_user_updates(db, user, subject, email, full_name)
            logger.debug("auth.local_user_fast_path_hit sub=%s user_id=%s", subject, user.id)
            logger.debug(
                "auth.user_sync_result action=%s user_id=%s clerk_user_id=%s email=%s",
                sync_action,
                user.id,
                user.clerk_user_id,
                user.email,
            )
            return user

    if not email and not os.getenv("CLERK_SECRET_KEY") and settings.AUTH_ENABLE_CLERK_FALLBACK_SYNC:
        logger.error("auth.clerk_secret_missing_for_profile_enrichment sub=%s", subject)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server auth configuration is incomplete. Set CLERK_SECRET_KEY.",
        )

    sync_action = "unchanged"
    clerk_user = _fetch_clerk_user(subject)
    if clerk_user:
        clerk_email = _extract_clerk_email(clerk_user)
        if clerk_email:
            email = clerk_email

        full_name = full_name or _extract_clerk_name(clerk_user)
        logger.info(
            "auth.user_lookup_enriched_from_clerk sub=%s email_found=%s",
            subject,
            bool(email),
        )
        if user is None:
            user = _find_local_user(db, subject, email)

    if user is not None:
        user, sync_action = _apply_user_updates(db, user, subject, email, full_name)

    if user is None and email:
        user = User(clerk_user_id=subject, email=email, full_name=full_name, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        sync_action = "created"
        logger.info(
            "auth.user_auto_provisioned clerk_user_id=%s email=%s user_id=%s",
            subject,
            email,
            user.id,
        )

    if user is None:
        logger.warning("auth.user_not_linked sub=%s email=%s", subject, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user is not linked to a local user record",
        )

    log_method = logger.debug if sync_action == "unchanged" else logger.info
    log_method(
        "auth.user_sync_result action=%s user_id=%s clerk_user_id=%s email=%s",
        sync_action,
        user.id,
        user.clerk_user_id,
        user.email,
    )
    return user


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UUID:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    verify_started_at = time.perf_counter()
    claims = _decode_and_verify_clerk_token(credentials.credentials)
    verify_elapsed_ms = (time.perf_counter() - verify_started_at) * 1000
    logger.info(
        "auth.verify_timing route=get_current_user_id sub=%s elapsed_ms=%.2f",
        claims.get("sub"),
        verify_elapsed_ms,
    )

    resolve_started_at = time.perf_counter()
    user = _resolve_local_user(db=db, claims=claims)
    resolve_elapsed_ms = (time.perf_counter() - resolve_started_at) * 1000
    logger.info(
        "auth.resolve_local_user_timing route=get_current_user_id sub=%s user_id=%s elapsed_ms=%.2f",
        claims.get("sub"),
        user.id,
        resolve_elapsed_ms,
    )
    return user.id


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    verify_started_at = time.perf_counter()
    claims = _decode_and_verify_clerk_token(credentials.credentials)
    verify_elapsed_ms = (time.perf_counter() - verify_started_at) * 1000
    logger.info(
        "auth.verify_timing route=get_current_user sub=%s elapsed_ms=%.2f",
        claims.get("sub"),
        verify_elapsed_ms,
    )

    resolve_started_at = time.perf_counter()
    user = _resolve_local_user(db=db, claims=claims)
    resolve_elapsed_ms = (time.perf_counter() - resolve_started_at) * 1000
    logger.info(
        "auth.resolve_local_user_timing route=get_current_user sub=%s user_id=%s elapsed_ms=%.2f",
        claims.get("sub"),
        user.id,
        resolve_elapsed_ms,
    )
    return user


def get_current_user_with_sync(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    verify_started_at = time.perf_counter()
    claims = _decode_and_verify_clerk_token(credentials.credentials)
    verify_elapsed_ms = (time.perf_counter() - verify_started_at) * 1000
    logger.info(
        "auth.verify_timing route=get_current_user_with_sync sub=%s elapsed_ms=%.2f",
        claims.get("sub"),
        verify_elapsed_ms,
    )
    logger.info("auth.explicit_user_sync_requested sub=%s", claims.get("sub"))
    resolve_started_at = time.perf_counter()
    user = _resolve_local_user(db=db, claims=claims, force_clerk_sync=True)
    resolve_elapsed_ms = (time.perf_counter() - resolve_started_at) * 1000
    logger.info(
        "auth.resolve_local_user_timing route=get_current_user_with_sync sub=%s user_id=%s elapsed_ms=%.2f",
        claims.get("sub"),
        user.id,
        resolve_elapsed_ms,
    )
    return user


@dataclass
class AuthContext:
    user_id: UUID
    supabase_access_token: str
    clerk_claims: dict


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    logger.debug("auth.authorization_header_present=%s", bool(credentials))
    if not credentials:
        logger.warning("auth.missing_authorization_header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    claims = _decode_and_verify_clerk_token(credentials.credentials)
    user = _resolve_local_user(db=db, claims=claims)
    user_id = user.id
    try:
        supabase_access_token = build_supabase_access_token(str(user_id))
    except ValueError as exc:
        logger.error("auth.supabase_token_generation_failed user_id=%s error=%s", user_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWT configuration is missing for RLS access",
        ) from exc

    logger.info("auth.context_created user_id=%s", user_id)
    return AuthContext(
        user_id=user_id,
        supabase_access_token=supabase_access_token,
        clerk_claims=claims,
    )


# Reusable database-backed guards

def require_role(allowed_roles: list[UserRole] | list[str]):
    """
    Dependency factory to enforce user role using the DB user as the source of truth.
    Supports TOURIST/CUSTOMER/CLIENT aliases.
    """
    normalized_allowed = set()
    for role in allowed_roles:
        val = role.value if isinstance(role, UserRole) else str(role)
        val = val.strip().lower()
        normalized_allowed.add(val)
        # Add aliases
        if val in ("tourist", "customer", "client"):
            normalized_allowed.update(["tourist", "customer", "client"])

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
        user_role = user_role.strip().lower()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: User role not authorized",
            )
        return current_user

    return dependency


def require_vendor_status(required_status: str):
    """
    Dependency factory to enforce a specific vendor status for Vendor users.
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != UserRole.VENDOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: User is not a vendor",
            )
        if current_user.vendor_status != required_status:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Vendor status is '{current_user.vendor_status}', but '{required_status}' is required",
            )
        return current_user

    return dependency


# Aliases matching camelCase and pythonic naming
requireAuth = get_current_user
requireRole = require_role
requireVendorStatus = require_vendor_status
