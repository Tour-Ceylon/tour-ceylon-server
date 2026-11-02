"""SEC-2 regression test: protected route groups must always require authentication.

Walks the FastAPI dependency tree of every route, so a route that loses its
auth dependency fails this test without needing a database or Clerk.
"""
from fastapi.routing import APIRoute

from app.api import deps
from app.main import app

AUTH_CALLS = {
    deps.get_current_user,
    deps.get_current_user_id,
    deps.get_current_user_with_sync,
    deps.get_auth_context,
}

# Whole prefixes that must be authenticated.
PROTECTED_PREFIXES = ("/api/v1/admin", "/api/v1/vendor/", "/api/v1/drivers/me")

# (method, path) pairs under otherwise-public routers that must be authenticated.
PROTECTED_ROUTES = {
    ("GET", "/api/v1/booking-inquiries/me"),
    ("GET", "/api/v1/transport/bookings/me"),
    ("GET", "/api/v1/booking-inquiries/"),
    ("GET", "/api/v1/booking-inquiries/{inquiry_id}"),
    ("GET", "/api/v1/booking-inquiries/email/{email}"),
    ("GET", "/api/v1/booking-inquiries/status/{status}"),
    ("GET", "/api/v1/booking-inquiries/admin/statistics"),
    ("PUT", "/api/v1/booking-inquiries/{inquiry_id}"),
    ("DELETE", "/api/v1/booking-inquiries/{inquiry_id}"),
    ("POST", "/api/v1/listings/"),
    ("PUT", "/api/v1/listings/{listing_id}"),
    ("DELETE", "/api/v1/listings/{listing_id}"),
    ("PATCH", "/api/v1/listings/{listing_id}/archive"),
    ("PATCH", "/api/v1/listings/{listing_id}/publish"),
    ("PATCH", "/api/v1/listings/{listing_id}/draft"),
    ("POST", "/api/v1/rooms/"),
    ("PUT", "/api/v1/rooms/{room_id}"),
    ("DELETE", "/api/v1/rooms/{room_id}"),
    ("POST", "/api/v1/listing-addons/"),
    ("DELETE", "/api/v1/listing-addons/listing/{listing_id}"),
    ("POST", "/api/v1/transfers/"),
}


def _requires_auth(dependant) -> bool:
    for sub in dependant.dependencies:
        call = sub.call
        if call in AUTH_CALLS or getattr(call, "__qualname__", "").startswith("require_"):
            return True
        if _requires_auth(sub):
            return True
    return False


def _routes():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, route.path, route


def test_protected_prefixes_require_auth():
    open_routes = [
        f"{m} {p}"
        for m, p, r in _routes()
        if p.startswith(PROTECTED_PREFIXES) and not _requires_auth(r.dependant)
    ]
    assert not open_routes, f"Unauthenticated routes in protected groups: {open_routes}"


def test_sensitive_public_router_routes_require_auth():
    found = {(m, p): _requires_auth(r.dependant) for m, p, r in _routes() if (m, p) in PROTECTED_ROUTES}
    missing = PROTECTED_ROUTES - set(found)
    assert not missing, f"Expected routes not found (renamed?): {sorted(missing)}"
    open_routes = sorted(k for k, ok in found.items() if not ok)
    assert not open_routes, f"Routes missing auth: {open_routes}"
