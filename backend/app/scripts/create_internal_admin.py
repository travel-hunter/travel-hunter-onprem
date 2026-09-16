from __future__ import annotations

import argparse
import getpass
import sys

from app.core import security
from app.core.internal_accounts import is_internal_admin_identifier
from app.db.session import get_session_factory
from app.repositories import users as user_repository
from app.services import auth as auth_service

def main() -> int:
    parser = argparse.ArgumentParser(description="Create one internal administrator account.")
    parser.add_argument("--email", required=True, help="Internal login identifier (for example admin-name@travel-hunter.invalid).")
    parser.add_argument("--nickname", required=True, help="Display name for audit records.")
    args = parser.parse_args()

    email = auth_service.normalize_email(args.email)
    if not is_internal_admin_identifier(email):
        parser.error("--email must use a non-deliverable .invalid internal identifier")
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm administrator password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if len(password) < 16:
        print("Administrator password must be at least 16 characters.", file=sys.stderr)
        return 2

    with get_session_factory()() as db:
        if user_repository.get_user_by_email(db, email) is not None:
            print("Administrator identifier already exists.", file=sys.stderr)
            return 1
        now = security.utc_now_naive()
        user = user_repository.create_user(
            db,
            email=email,
            nickname=args.nickname.strip(),
            password_hash=security.hash_password(password),
            nickname_setup_completed=True,
            profile_setup_skipped=True,
            terms_accepted=True,
            terms_accepted_at=now,
            terms_version="internal-admin-bootstrap",
            privacy_accepted=True,
            privacy_accepted_at=now,
            privacy_version="internal-admin-bootstrap",
        )
        user.role = "admin"
        user.onboarding_completed = True
        db.commit()

    print("Administrator account created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
