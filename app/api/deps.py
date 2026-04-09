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
from app.models.user import User
from app.integrations.supabase_client import build_supabase_access_token


logger = logging.getLogger("app.auth")


bearer_scheme = HTTPBearer(auto_error=False)
_jwks_cache: dict | None = None
_jwks_cached_at = 0.0
_jwks_ttl_seconds = 300


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
    options = {"verify_aud": bool(audience), "verify_iss": bool(issuer)}
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
    secret_key = os.getenv("CLERK_SECRET_KEY")
    if not secret_key:
        logger.warning("auth.clerk_secret_missing_for_user_lookup sub=%s", subject)
        return None

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

    logger.info("auth.clerk_user_lookup_succeeded sub=%s", subject)
    return payload


def _resolve_local_user(db: Session, claims: dict) -> User:
    email = claims.get("email") or claims.get("email_address")
    subject = claims.get("sub")
    full_name = claims.get("name")

    if not email and subject:
        clerk_user = _fetch_clerk_user(subject)
        if clerk_user:
            email = _extract_clerk_email(clerk_user)
            full_name = full_name or _extract_clerk_name(clerk_user)
            logger.info(
                "auth.user_lookup_enriched_from_clerk sub=%s email_found=%s",
                subject,
                bool(email),
            )

    user = None
    if subject:
        user = db.query(User).filter(User.clerk_user_id == subject).first()

    if email:
        user = user or db.query(User).filter(User.email == email).first()

    if user is None and subject:
        try:
            subject_as_uuid = UUID(subject)
            user = db.query(User).filter(User.id == subject_as_uuid).first()
        except ValueError:
            user = None

    did_update_user = False
    if user is not None and subject and user.clerk_user_id != subject:
        user.clerk_user_id = subject
        did_update_user = True

    if user is not None and full_name and user.full_name != full_name:
        user.full_name = full_name
        did_update_user = True

    if did_update_user:
        db.add(user)
        db.commit()
        db.refresh(user)

    if user is None and email:
        user = User(clerk_user_id=subject, email=email, full_name=full_name, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
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

    logger.info("auth.user_resolved user_id=%s email=%s", user.id, user.email)
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

    claims = _decode_and_verify_clerk_token(credentials.credentials)
    user = _resolve_local_user(db=db, claims=claims)
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

    claims = _decode_and_verify_clerk_token(credentials.credentials)
    return _resolve_local_user(db=db, claims=claims)


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
