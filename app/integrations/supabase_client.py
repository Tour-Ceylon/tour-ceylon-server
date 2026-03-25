import os
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

from jose import jwt


def _extract_project_ref_from_url(supabase_url: str) -> str | None:
    parsed = urlparse(supabase_url)
    hostname = parsed.hostname or ""
    if not hostname.endswith(".supabase.co"):
        return None
    return hostname.split(".")[0]


def _extract_project_ref_from_key(api_key: str) -> str | None:
    try:
        claims = jwt.get_unverified_claims(api_key)
    except Exception:
        return None
    ref = claims.get("ref")
    return str(ref) if ref else None


def _validate_project_ref_match(supabase_url: str, api_key: str, key_name: str) -> None:
    url_ref = _extract_project_ref_from_url(supabase_url)
    key_ref = _extract_project_ref_from_key(api_key)
    if url_ref and key_ref and url_ref != key_ref:
        raise ValueError(
            f"{key_name} project ref ({key_ref}) does not match SUPABASE_URL project ref ({url_ref})"
        )


def _create_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise ValueError("supabase package is not installed. Please install dependencies.") from exc

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_anon_key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_KEY) are required")
    _validate_project_ref_match(supabase_url, supabase_anon_key, "SUPABASE_ANON_KEY")

    return create_client(supabase_url, supabase_anon_key)


def build_supabase_access_token(user_id: str) -> str:
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        raise ValueError("SUPABASE_JWT_SECRET is required for RLS user-context access")

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=60)

    claims = {
        "sub": user_id,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    issuer = os.getenv("SUPABASE_JWT_ISS")
    if issuer:
        claims["iss"] = issuer

    return jwt.encode(claims, jwt_secret, algorithm="HS256")


def get_supabase_client(user_access_token: str | None = None):
    client = _create_client()
    if user_access_token:
        try:
            client.postgrest.auth(user_access_token)
        except Exception as exc:
            raise ValueError("Unable to bind user access token to Supabase client") from exc
    return client


def get_supabase_rls_client(user_id: str):
    token = build_supabase_access_token(user_id)
    return get_supabase_client(user_access_token=token)


def get_supabase_service_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise ValueError("supabase package is not installed. Please install dependencies.") from exc

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for service client")
    _validate_project_ref_match(supabase_url, service_key, "SUPABASE_SERVICE_KEY")
    return create_client(supabase_url, service_key)
