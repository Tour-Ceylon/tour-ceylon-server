from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.security import HTTPAuthorizationCredentials

from app.api import deps
from app.models.enum import UserRole
from app.models.user import User


def _build_user(**overrides):
    user = User(
        clerk_user_id=overrides.get("clerk_user_id", "user_123"),
        email=overrides.get("email", "user@example.com"),
        full_name=overrides.get("full_name", "Portal User"),
        is_active=overrides.get("is_active", True),
        role=overrides.get("role", UserRole.ADMIN),
    )
    user.id = overrides.get("id", uuid4())
    user.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    user.updated_at = overrides.get("updated_at", datetime.now(timezone.utc))
    return user


def test_resolve_local_user_uses_fast_path_without_clerk_lookup(monkeypatch):
    user = _build_user()
    calls = {"apply": 0}

    monkeypatch.setattr(deps.settings, "AUTH_SYNC_ON_MISSING_LOCAL_USER_ONLY", True)
    monkeypatch.setattr(deps, "_find_local_user", lambda db, subject, email: user)

    def fake_apply(db, db_user, subject, email, full_name):
        calls["apply"] += 1
        assert db_user is user
        assert subject == "user_123"
        assert email == "user@example.com"
        assert full_name == "Portal User"
        return db_user, "unchanged"

    monkeypatch.setattr(deps, "_apply_user_updates", fake_apply)

    def fail_fetch(subject):
        raise AssertionError(f"unexpected Clerk lookup for {subject}")

    monkeypatch.setattr(deps, "_fetch_clerk_user", fail_fetch)

    resolved = deps._resolve_local_user(
        db=object(),
        claims={"sub": "user_123", "email": "user@example.com", "name": "Portal User"},
    )

    assert resolved is user
    assert calls["apply"] == 1


def test_resolve_local_user_auto_provisions_from_clerk_when_missing(monkeypatch):
    find_calls = {"count": 0}

    class FakeDB:
        def __init__(self):
            self.added = []
            self.commits = 0
            self.refreshed = 0

        def add(self, value):
            self.added.append(value)

        def commit(self):
            self.commits += 1

        def refresh(self, value):
            self.refreshed += 1
            if getattr(value, "id", None) is None:
                value.id = uuid4()
            if getattr(value, "created_at", None) is None:
                value.created_at = datetime.now(timezone.utc)
            if getattr(value, "updated_at", None) is None:
                value.updated_at = datetime.now(timezone.utc)

    def fake_find_local_user(db, subject, email):
        find_calls["count"] += 1
        return None

    monkeypatch.setattr(deps.settings, "AUTH_SYNC_ON_MISSING_LOCAL_USER_ONLY", True)
    monkeypatch.setattr(deps.settings, "AUTH_ENABLE_CLERK_FALLBACK_SYNC", True)
    monkeypatch.setattr(deps, "_find_local_user", fake_find_local_user)
    monkeypatch.setattr(
        deps,
        "_fetch_clerk_user",
        lambda subject: {
            "primary_email_address_id": "primary",
            "email_addresses": [{"id": "primary", "email_address": "fresh@example.com"}],
            "full_name": "Fresh User",
        },
    )

    db = FakeDB()
    user = deps._resolve_local_user(db=db, claims={"sub": "user_new"})

    assert user.clerk_user_id == "user_new"
    assert user.email == "fresh@example.com"
    assert user.full_name == "Fresh User"
    assert db.commits == 1
    assert db.refreshed == 1
    assert len(db.added) == 1
    assert find_calls["count"] == 2


def test_get_current_user_with_sync_forces_clerk_refresh(monkeypatch):
    observed = {}
    resolved_user = _build_user()

    monkeypatch.setattr(deps, "_decode_and_verify_clerk_token", lambda token: {"sub": "user_123"})

    def fake_resolve(db, claims, *, force_clerk_sync=False):
        observed["db"] = db
        observed["claims"] = claims
        observed["force_clerk_sync"] = force_clerk_sync
        return resolved_user

    monkeypatch.setattr(deps, "_resolve_local_user", fake_resolve)

    result = deps.get_current_user_with_sync(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
        db=SimpleNamespace(name="db"),
    )

    assert result is resolved_user
    assert observed["claims"] == {"sub": "user_123"}
    assert observed["force_clerk_sync"] is True
