from dataclasses import dataclass
from datetime import datetime, timezone
<<<<<<< Updated upstream
=======
from typing import Callable
>>>>>>> Stashed changes
from uuid import UUID

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.enum import UserRole
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user_schema import UserCreate, UserUpdate


@dataclass(frozen=True)
class AuthIdentity:
	subject: str
	email: str | None
	full_name: str | None
	raw_claims: dict


_JWKS_CACHE: dict[str, object] = {"keys": [], "fetched_at": datetime.min.replace(tzinfo=timezone.utc)}
_JWKS_TTL_SECONDS = 300


def _unauthorized(detail: str) -> HTTPException:
	return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _extract_bearer_token(authorization: str | None) -> str:
	if not authorization:
		raise _unauthorized("Missing Authorization header")

	scheme, _, token = authorization.partition(" ")
	if scheme.lower() != "bearer" or not token:
		raise _unauthorized("Invalid Authorization header format")

	return token.strip()


def _get_jwks() -> list[dict]:
	now = datetime.now(timezone.utc)
	fetched_at = _JWKS_CACHE["fetched_at"]
	if isinstance(fetched_at, datetime):
		age_seconds = (now - fetched_at).total_seconds()
		if _JWKS_CACHE["keys"] and age_seconds < _JWKS_TTL_SECONDS:
			return _JWKS_CACHE["keys"]  # type: ignore[return-value]

	settings = get_settings()
	if not settings.clerk_jwks_url:
		raise _unauthorized("Server auth is not configured (missing CLERK_JWKS_URL or CLERK_ISSUER)")

	try:
		response = httpx.get(settings.clerk_jwks_url, timeout=8.0)
		response.raise_for_status()
		payload = response.json()
	except Exception as exc:
		raise _unauthorized("Unable to fetch token signing keys") from exc

	keys = payload.get("keys") if isinstance(payload, dict) else None
	if not isinstance(keys, list) or not keys:
		raise _unauthorized("Invalid token signing key configuration")

	_JWKS_CACHE["keys"] = keys
	_JWKS_CACHE["fetched_at"] = now
	return keys


def _decode_clerk_token(token: str) -> dict:
	settings = get_settings()
	try:
		unverified_header = jwt.get_unverified_header(token)
	except JWTError as exc:
		raise _unauthorized("Invalid token header") from exc

	kid = unverified_header.get("kid")
	jwks = _get_jwks()
	key = next((entry for entry in jwks if entry.get("kid") == kid), None)
	if key is None:
		raise _unauthorized("Token signing key not found")

	decode_kwargs = {
		"algorithms": ["RS256"],
		"issuer": settings.clerk_issuer,
		"options": {
			"verify_aud": bool(settings.clerk_audience),
			"verify_iss": bool(settings.clerk_issuer),
		},
	}
	if settings.clerk_audience:
		decode_kwargs["audience"] = settings.clerk_audience

	try:
		claims = jwt.decode(token, key, **decode_kwargs)
	except JWTError as exc:
		raise _unauthorized("Invalid or expired token") from exc

	if not isinstance(claims, dict):
		raise _unauthorized("Invalid token claims")

	return claims


def get_auth_identity(
	authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthIdentity:
	token = _extract_bearer_token(authorization)
	claims = _decode_clerk_token(token)

	subject = claims.get("sub")
	if not isinstance(subject, str) or not subject:
		raise _unauthorized("Token subject is missing")

	email = claims.get("email") or claims.get("email_address")
	if email is not None and not isinstance(email, str):
		email = None

	full_name = claims.get("name")
	if full_name is not None and not isinstance(full_name, str):
		full_name = None

	return AuthIdentity(subject=subject, email=email, full_name=full_name, raw_claims=claims)


def resolve_or_create_local_user(auth_identity: AuthIdentity, user_repo: UserRepository) -> User:
	user = user_repo.get_by_email(auth_identity.email) if auth_identity.email else None
	if user is None:
		try:
			subject_as_uuid = UUID(auth_identity.subject)
			user = user_repo.get_by_id(subject_as_uuid)
		except ValueError:
			user = None

	if user is None:
		if not auth_identity.email:
			raise _unauthorized("Authenticated token does not include an email claim")

		display_name = auth_identity.full_name or auth_identity.email.split("@")[0]
		return user_repo.create(
			UserCreate(
				email=auth_identity.email,
				full_name=display_name,
				country=None,
				role=UserRole.TOURIST,
				is_active=True,
			)
		)

	update_payload = {}
	if not user.full_name and auth_identity.full_name:
		update_payload["full_name"] = auth_identity.full_name

	if update_payload:
		user = user_repo.update(user.id, UserUpdate(**update_payload))

	return user


def get_current_user(
	auth_identity: AuthIdentity = Depends(get_auth_identity),
	db: Session = Depends(get_db),
) -> User:
	user_repo = UserRepository(db)
	return resolve_or_create_local_user(auth_identity, user_repo)


<<<<<<< Updated upstream
def get_current_user_id(current_user: User = Depends(get_current_user)) -> UUID:
	return current_user.id
=======
def get_current_local_user(
	auth_identity: AuthIdentity = Depends(get_auth_identity),
	db: Session = Depends(get_db),
) -> User:
	return get_current_user(auth_identity=auth_identity, db=db)


def get_current_user_id(current_user: User = Depends(get_current_user)) -> UUID:
	return current_user.id


def require_admin(current_user: User = Depends(get_current_user)) -> User:
	"""Dependency that enforces current user has admin role. Raises 403 if not."""
	if current_user.role != UserRole.ADMIN:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin role required"
		)
	return current_user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
	"""Factory to create a dependency that enforces one of the specified roles."""
	def check_role(current_user: User = Depends(get_current_user)) -> User:
		if current_user.role not in allowed_roles:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail=f"One of these roles required: {', '.join(r.value for r in allowed_roles)}"
			)
		return current_user
	return check_role
>>>>>>> Stashed changes
