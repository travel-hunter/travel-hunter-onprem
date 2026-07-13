"""Create local-only auth links for UI verification without real SMTP/OAuth.

This helper intentionally refuses to run in protected environments. It writes the
same pending DB records that the normal signup/OAuth flows consume, then prints a
frontend URL that can be opened in a local browser.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

from app.core import security
from app.core.config import settings
from app.db.session import get_session_factory
from app.repositories import pending_signups, pending_social_signups, users
from app.services import auth as auth_service
from app.services import oauth as oauth_service

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_FILE = REPO_ROOT / ".omx/tmp/dev-auth-helper/latest-url.txt"


class DevAuthHelperError(RuntimeError):
    pass


def _guard_local_only() -> None:
    if settings.is_protected_env:
        raise DevAuthHelperError(
            "dev auth helper is disabled when APP_ENV is staging/production/prod"
        )


def _write_output_file(url: str, output_file: Path | None) -> None:
    if output_file is None:
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(url + "\n", encoding="utf-8")


def _print_result(*, label: str, url: str, output_file: Path | None) -> None:
    print(label)
    print(url)
    if output_file is not None:
        print(f"saved_to={output_file}")


def create_email_signup_link(
    *,
    email: str,
    minutes: int,
    output_file: Path | None,
) -> str:
    _guard_local_only()
    normalized_email = auth_service.normalize_email(email)
    raw_token = security.create_urlsafe_token()
    token_hash = security.hash_token(raw_token)
    now = security.utc_now_naive()
    expires_at = now + timedelta(minutes=minutes)

    with get_session_factory()() as db:
        if users.get_user_by_email(db, normalized_email) is not None:
            raise DevAuthHelperError(f"email is already registered: {normalized_email}")
        pending_signups.delete_pending_signup_by_email(db, normalized_email)
        pending_signups.create_pending_signup(
            db,
            email=normalized_email,
            token_hash=token_hash,
            expires_at=expires_at,
            terms_accepted=True,
            terms_accepted_at=now,
            terms_version=auth_service.CURRENT_TERMS_VERSION,
            privacy_accepted=True,
            privacy_accepted_at=now,
            privacy_version=auth_service.CURRENT_PRIVACY_VERSION,
        )
        db.commit()

    url = f"{settings.frontend_base_url()}/signup/verify?token={raw_token}"
    _write_output_file(url, output_file)
    return url


def create_social_signup_link(
    *,
    provider: str,
    email: str,
    provider_id: str,
    nickname: str | None,
    redirect: str,
    minutes: int,
    output_file: Path | None,
) -> str:
    _guard_local_only()
    provider = provider.strip().lower()
    if provider not in {"google", "kakao"}:
        raise DevAuthHelperError("provider must be one of: google, kakao")
    normalized_email = auth_service.normalize_email(email)
    safe_redirect = oauth_service.safe_redirect_path(redirect)
    raw_token = security.create_urlsafe_token()
    now = security.utc_now_naive()

    with get_session_factory()() as db:
        if users.get_user_by_email(db, normalized_email) is not None:
            raise DevAuthHelperError(
                f"email is already registered; use a fresh local test email: {normalized_email}"
            )
        if users.get_social_account(db, provider=provider, provider_id=provider_id) is not None:
            raise DevAuthHelperError(
                f"social account already exists: provider={provider} provider_id={provider_id}"
            )
        pending_social_signups.delete_pending_social_signup_by_provider(
            db,
            provider=provider,
            provider_id=provider_id,
        )
        pending_social_signups.create_pending_social_signup(
            db,
            token_hash=security.hash_token(raw_token),
            provider=provider,
            provider_id=provider_id,
            email=normalized_email,
            email_verified=True,
            nickname=nickname,
            redirect_path=safe_redirect,
            expires_at=now + timedelta(minutes=minutes),
        )
        db.commit()

    url = oauth_service.social_signup_redirect_url(token=raw_token, redirect=safe_redirect)
    _write_output_file(url, output_file)
    return url


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-file",
        action="store_true",
        help="Do not save the generated URL to .omx/tmp/dev-auth-helper/latest-url.txt.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Where to save the generated URL for copy/paste convenience.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create local-only email/social signup links without SMTP/OAuth.",
    )
    _add_output_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    email = subparsers.add_parser("email", help="Create an email signup verification URL.")
    _add_output_options(email)
    email.add_argument("--email", required=True, help="Fresh local test email.")
    email.add_argument(
        "--minutes",
        type=int,
        default=auth_service.SIGNUP_VERIFICATION_EXPIRE_MINUTES,
        help="Token lifetime in minutes.",
    )

    social = subparsers.add_parser("social", help="Create a social signup agreement URL.")
    _add_output_options(social)
    social.add_argument("--provider", choices=("google", "kakao"), default="google")
    social.add_argument("--email", required=True, help="Fresh local test email.")
    social.add_argument(
        "--provider-id",
        default="local-dev-social-user",
        help="Local fake provider subject/id. Change it when reusing the same provider.",
    )
    social.add_argument("--nickname", default="로컬 소셜", help="Displayed nickname metadata.")
    social.add_argument("--redirect", default="/home", help="Post-auth safe redirect path.")
    social.add_argument(
        "--minutes",
        type=int,
        default=auth_service.SIGNUP_VERIFICATION_EXPIRE_MINUTES,
        help="Token lifetime in minutes.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output_file = None if args.no_file else args.output_file
    try:
        if args.command == "email":
            url = create_email_signup_link(
                email=args.email,
                minutes=args.minutes,
                output_file=output_file,
            )
            _print_result(label="email_signup_url=", url=url, output_file=output_file)
            return 0
        if args.command == "social":
            url = create_social_signup_link(
                provider=args.provider,
                email=args.email,
                provider_id=args.provider_id,
                nickname=args.nickname,
                redirect=args.redirect,
                minutes=args.minutes,
                output_file=output_file,
            )
            _print_result(label="social_signup_url=", url=url, output_file=output_file)
            return 0
    except DevAuthHelperError as error:
        parser.error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
