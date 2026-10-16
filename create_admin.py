"""Create an admin account, or promote an existing user to admin.

An admin needs two things:
  1. a login in Clerk, and
  2. a row in the `users` table with role ADMIN (the database is the source of truth for roles).

This script does step 2 and, if you ask, step 1. It talks to the database directly, so it needs no
open HTTP endpoint. It only ever promotes; it never demotes or deletes anyone.

Examples (run from this folder with the project's virtualenv):

  # Database row only. The person then signs up / signs in to Clerk with the SAME email and is linked automatically.
  python create_admin.py --email new.admin@example.com --name "New Admin"

  # Also create the Clerk login now (you will be asked for a password; needs CLERK_SECRET_KEY in .env).
  python create_admin.py --email new.admin@example.com --name "New Admin" --create-clerk-user

  # Promote someone who already has an account.
  python create_admin.py --email existing.user@example.com

  # See what would happen without changing anything.
  python create_admin.py --email new.admin@example.com --dry-run

Add --yes to skip the confirmation question.
"""
import argparse
import getpass
import os
import re
import sys
from urllib.parse import urlparse

import httpx
from sqlalchemy import func

from app.config.database import SessionLocal, engine
from app.models.enum import UserRole
from app.models.user import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CLERK_API = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1").rstrip("/")


def clerk_secret() -> str | None:
    try:
        from app.config.settings import settings

        return settings.CLERK_SECRET_KEY or os.getenv("CLERK_SECRET_KEY")
    except Exception:
        return os.getenv("CLERK_SECRET_KEY")


def create_clerk_user(email: str, name: str | None, password: str, username: str | None = None) -> str:
    """Create the login in Clerk and return its user id. If the email already exists there, reuse that login."""
    secret = clerk_secret()
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    first, _, last = (name or "").strip().partition(" ")

    body = {"email_address": [email], "password": password}
    if username:
        body["username"] = username
    if first:
        body["first_name"] = first
    if last:
        body["last_name"] = last

    with httpx.Client(timeout=20.0) as client:
        response = client.post(f"{CLERK_API}/users", headers=headers, json=body)
        if response.status_code in (200, 201):
            return response.json()["id"]

        errors = response.json().get("errors", []) if response.headers.get("content-type", "").startswith("application/json") else []
        if any(e.get("code") == "form_identifier_exists" for e in errors):
            lookup = client.get(f"{CLERK_API}/users", headers=headers, params={"email_address": email})
            lookup.raise_for_status()
            found = lookup.json()
            if found:
                print("  Clerk already has a login for this email; using it (its password is unchanged).")
                return found[0]["id"]

        detail = "; ".join(e.get("long_message") or e.get("message", "") for e in errors) or response.text[:200]
        sys.exit(f"Clerk refused to create the login: {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin account or promote an existing user to admin.")
    parser.add_argument("--email", required=True, help="Email address of the admin")
    parser.add_argument("--name", help="Full name (used for a new account, or to fill a missing name)")
    parser.add_argument("--create-clerk-user", action="store_true", help="Also create the Clerk login (asks for a password)")
    parser.add_argument("--username", help="Clerk username, for instances that have usernames turned on")
    parser.add_argument(
        "--password-env",
        metavar="VAR",
        help="Read the Clerk password from this environment variable instead of asking (keeps it out of the command line)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen and change nothing")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        sys.exit(f"'{args.email}' does not look like an email address.")
    if args.create_clerk_user and not clerk_secret():
        sys.exit("--create-clerk-user needs CLERK_SECRET_KEY in the server .env file.")

    host = urlparse(str(engine.url)).hostname
    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        current_role = getattr(user.role, "value", user.role) if user else None

        print(f"\nDatabase host : {host}")
        print(f"Email         : {email}")
        if user is None:
            print("Plan          : create a NEW user with role ADMIN")
        elif current_role == UserRole.ADMIN.value and user.is_active:
            print("Plan          : nothing to change in the database, this user is already an active ADMIN")
        else:
            print(f"Plan          : promote the existing user (currently {current_role}, active={user.is_active}) to ADMIN")
        if args.create_clerk_user:
            print("Clerk         : create the login" + (f" with username '{args.username}'" if args.username else "") + " (or reuse it if the email already exists there)")
        else:
            print("Clerk         : not touched. The person must sign in to Clerk with this same email.")

        if args.dry_run:
            print("\nDry run: nothing was changed.")
            return

        if not args.yes and input("\nType 'yes' to continue: ").strip().lower() != "yes":
            print("Cancelled. Nothing was changed.")
            return

        clerk_id = None
        if args.create_clerk_user:
            if args.password_env:
                password = os.getenv(args.password_env, "")
                if not password:
                    sys.exit(f"Environment variable {args.password_env} is empty or not set. Nothing was changed.")
            else:
                password = getpass.getpass("Password for the new login: ")
                if password != getpass.getpass("Repeat the password: "):
                    sys.exit("The passwords do not match. Nothing was changed.")
            if len(password) < 8:
                sys.exit("Use a password of at least 8 characters. Nothing was changed.")
            clerk_id = create_clerk_user(email, args.name, password, args.username)
            print(f"  Clerk user id: {clerk_id}")

        if user is None:
            user = User(
                email=email,
                full_name=args.name,
                clerk_user_id=clerk_id,
                role=UserRole.ADMIN,
                is_active=True,
                approved_categories=[],
                business_profile={},
            )
            db.add(user)
        else:
            if clerk_id and user.clerk_user_id and user.clerk_user_id != clerk_id:
                sys.exit(
                    f"This user is already linked to a different Clerk login ({user.clerk_user_id}). "
                    "Nothing was changed; sort that out before promoting."
                )
            user.role = UserRole.ADMIN
            user.is_active = True
            if clerk_id and not user.clerk_user_id:
                user.clerk_user_id = clerk_id
            if args.name and not user.full_name:
                user.full_name = args.name

        db.commit()
        db.refresh(user)
        print(f"\nDone. {email} is now an ADMIN (user id {user.id}).")

        # Keep Clerk's copy of the role in step with the database, the same way the app does.
        if user.clerk_user_id and clerk_secret():
            from app.core.auth.clerk import sync_user_metadata_to_clerk

            synced = sync_user_metadata_to_clerk(clerk_user_id=user.clerk_user_id, role=UserRole.ADMIN.value)
            print("Clerk metadata :", "updated" if synced else "could not be updated (the database role is still correct)")

        if not user.clerk_user_id:
            print("Next: have them sign in to the admin portal with this exact email. The first sign-in links the Clerk login to this account.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
