from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models import PendingSocialSignup
from app.models import User as UserModel
from app.repositories import pending_social_signups as pending_social_signup_repository
from app.repositories import users as user_repository
from app.schemas.user import CompleteSocialSignupRequest
from app.services import auth as auth_service


class OAuthServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class OAuthStartResult:
    authorization_url: str
    state: str
    redirect: str


@dataclass(frozen=True)
class OAuthCallbackResult:
    auth: auth_service.AuthResult | None
    frontend_redirect_url: str


@dataclass(frozen=True)
class PendingSocialSignupResult:
    provider: str
    email: str
    nickname: str | None
    expires_at: str
    redirect_path: str


@dataclass(frozen=True)
class OAuthProviderConfig:
    provider: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


@dataclass(frozen=True)
class OAuthProfile:
    provider_id: str
    email: str | None
    email_verified: bool
    nickname: str | None


def safe_redirect_path(redirect: str | None) -> str:
    if not redirect or not redirect.startswith("/") or redirect.startswith("//"):
        return "/home"
    return redirect


def _frontend_base_url() -> str:
    return settings.frontend_base_url()


def _provider_config(provider: str) -> OAuthProviderConfig:
    if provider == "kakao":
        return OAuthProviderConfig(
            provider="kakao",
            client_id=settings.kakao_client_id,
            client_secret=settings.kakao_client_secret,
            redirect_uri=settings.kakao_redirect_uri,
            authorize_url="https://kauth.kakao.com/oauth/authorize",
            token_url="https://kauth.kakao.com/oauth/token",
            userinfo_url="https://kapi.kakao.com/v2/user/me",
            scope="account_email",
        )
    if provider == "google":
        return OAuthProviderConfig(
            provider="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scope="openid email profile",
        )
    raise OAuthServiceError(404, "OAuth provider not found")


def _require_config(config: OAuthProviderConfig) -> None:
    if not config.client_id or not config.client_secret or not config.redirect_uri:
        raise OAuthServiceError(503, "OAuth provider is not configured")


def callback_error_redirect_url(error_code: str, redirect: str | None = None) -> str:
    query = urlencode(
        {
            "error": error_code,
            "redirect": safe_redirect_path(redirect),
        }
    )
    return f"{_frontend_base_url()}/oauth/callback?{query}"


def callback_error_code(error: OAuthServiceError) -> str:
    if error.detail == "invalid_state" or (
        error.status_code == 400 and "state" in error.detail.lower()
    ):
        return "invalid_state"
    if error.status_code == 404:
        return "provider_unavailable"
    if error.status_code == 503 or "token exchange" in error.detail.lower():
        return "provider_unavailable"
    if "profile" in error.detail.lower():
        return "profile_unavailable"
    if "email policy" in error.detail.lower():
        return "email_policy"
    return "provider_unavailable"


def provider_callback_error_code(provider_error: str, state_is_valid: bool) -> str:
    if not state_is_valid:
        return "invalid_state"
    if provider_error == "access_denied":
        return "access_denied"
    return "provider_unavailable"


def callback_success_redirect_url(redirect: str | None) -> str:
    return f"{_frontend_base_url()}/oauth/callback?redirect={quote(safe_redirect_path(redirect), safe='')}"


def social_signup_redirect_url(*, token: str, redirect: str | None) -> str:
    query = urlencode(
        {
            "token": token,
            "redirect": safe_redirect_path(redirect),
        }
    )
    return f"{_frontend_base_url()}/signup/social-agreement?{query}"


def state_matches_cookie(state: str | None, state_cookie: str | None) -> bool:
    return bool(state and state_cookie and state == state_cookie)


def redirect_from_state(state: str | None) -> str:
    if not state or ":" not in state:
        return "/home"
    _, redirect = state.split(":", 1)
    return safe_redirect_path(redirect)


def build_authorization_redirect(provider: str, redirect: str | None) -> OAuthStartResult:
    config = _provider_config(provider)
    _require_config(config)
    state = secrets.token_urlsafe(32)
    safe_redirect = safe_redirect_path(redirect)
    state_payload = f"{state}:{safe_redirect}"
    query = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "state": state_payload,
    }
    if config.scope:
        query["scope"] = config.scope
    if provider == "google":
        query["access_type"] = "offline"
        query["prompt"] = "consent"
    return OAuthStartResult(
        authorization_url=f"{config.authorize_url}?{urlencode(query)}",
        state=state_payload,
        redirect=safe_redirect,
    )


def _exchange_code(config: OAuthProviderConfig, code: str) -> str:
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
        "code": code,
    }
    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(config.token_url, data=payload)
            response.raise_for_status()
            token_payload = response.json()
    except Exception as error:
        raise OAuthServiceError(502, "OAuth token exchange failed") from error
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthServiceError(502, "OAuth token exchange failed")
    return access_token


def _fetch_userinfo(config: OAuthProviderConfig, access_token: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8) as client:
            response = client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
    except Exception as error:
        raise OAuthServiceError(502, "OAuth user profile fetch failed") from error


def _extract_profile(provider: str, payload: dict[str, Any]) -> OAuthProfile:
    if provider == "kakao":
        provider_id = str(payload.get("id") or "")
        account = payload.get("kakao_account") if isinstance(payload.get("kakao_account"), dict) else {}
        profile = account.get("profile") if isinstance(account.get("profile"), dict) else {}
        email = account.get("email") if isinstance(account.get("email"), str) else None
        email_verified = account.get("is_email_verified") is True and account.get("is_email_valid") is not False
        nickname = profile.get("nickname") if isinstance(profile.get("nickname"), str) else None
    else:
        provider_id = str(payload.get("sub") or "")
        email = payload.get("email") if isinstance(payload.get("email"), str) else None
        email_verified = payload.get("email_verified") is True
        nickname = payload.get("name") if isinstance(payload.get("name"), str) else None

    if not provider_id:
        raise OAuthServiceError(502, "OAuth user profile is missing provider id")
    return OAuthProfile(
        provider_id=provider_id,
        email=email,
        email_verified=email_verified,
        nickname=nickname,
    )


def _kakao_placeholder_email(provider_id: str) -> str:
    return f"kakao_{provider_id}@oauth.local"


def _maybe_upgrade_kakao_placeholder_email(
    db: Session,
    user: UserModel,
    *,
    profile: OAuthProfile,
) -> UserModel:
    if not profile.email or not profile.email_verified:
        return user

    current_email = auth_service.normalize_email(user.email)
    placeholder_email = _kakao_placeholder_email(profile.provider_id)
    if current_email != placeholder_email:
        return user

    target_email = auth_service.normalize_email(profile.email)
    if target_email == current_email:
        return user

    existing_user = user_repository.get_active_user_by_email(db, target_email)
    if existing_user is not None and existing_user.id != user.id:
        return user

    return user_repository.update_user_email(db, user, email=target_email)


def _candidate_email_or_error(provider: str, profile: OAuthProfile) -> str:
    if provider == "google" and (not profile.email or not profile.email_verified):
        raise OAuthServiceError(400, "OAuth email policy requires a verified Google email")

    if profile.email and profile.email_verified:
        return auth_service.normalize_email(profile.email)
    if provider == "kakao":
        return _kakao_placeholder_email(profile.provider_id)
    raise OAuthServiceError(400, "OAuth email policy requires a verified email")


def _find_existing_oauth_user(
    db: Session,
    *,
    provider: str,
    profile: OAuthProfile,
) -> UserModel | None:
    social_account = user_repository.get_active_social_account(
        db,
        provider=provider,
        provider_id=profile.provider_id,
    )
    if social_account is not None:
        user = social_account.user
        if provider == "kakao":
            user = _maybe_upgrade_kakao_placeholder_email(db, user, profile=profile)
        return user

    if profile.email and profile.email_verified:
        user = user_repository.get_active_user_by_email(
            db,
            auth_service.normalize_email(profile.email),
        )
        if user is not None:
            user_repository.create_social_account(
                db,
                user=user,
                provider=provider,
                provider_id=profile.provider_id,
                provider_nickname=profile.nickname,
            )
            return user
    return None


def _create_pending_social_signup(
    db: Session,
    *,
    provider: str,
    profile: OAuthProfile,
    redirect: str,
) -> str:
    email = _candidate_email_or_error(provider, profile)
    raw_token = security.create_urlsafe_token()
    pending_social_signup_repository.delete_pending_social_signup_by_provider(
        db,
        provider=provider,
        provider_id=profile.provider_id,
    )
    pending_social_signup_repository.create_pending_social_signup(
        db,
        token_hash=security.hash_token(raw_token),
        provider=provider,
        provider_id=profile.provider_id,
        email=email,
        email_verified=profile.email_verified,
        nickname=profile.nickname,
        redirect_path=safe_redirect_path(redirect),
        expires_at=security.utc_now_naive() + timedelta(minutes=auth_service.SIGNUP_VERIFICATION_EXPIRE_MINUTES),
    )
    return raw_token


def complete_oauth_callback(
    db: Session,
    *,
    provider: str,
    code: str | None,
    state: str | None,
    state_cookie: str | None,
) -> OAuthCallbackResult:
    if not code or not state or not state_cookie or state != state_cookie:
        raise OAuthServiceError(400, "invalid_state")

    config = _provider_config(provider)
    _require_config(config)
    access_token = _exchange_code(config, code)
    profile_payload = _fetch_userinfo(config, access_token)
    profile = _extract_profile(provider, profile_payload)
    user = _find_existing_oauth_user(
        db,
        provider=provider,
        profile=profile,
    )
    redirect = redirect_from_state(state)
    if user is None:
        pending_token = _create_pending_social_signup(
            db,
            provider=provider,
            profile=profile,
            redirect=redirect,
        )
        db.commit()
        return OAuthCallbackResult(
            auth=None,
            frontend_redirect_url=social_signup_redirect_url(token=pending_token, redirect=redirect),
        )

    result = auth_service._issue_tokens(db, user)
    db.commit()

    frontend_redirect_url = callback_success_redirect_url(redirect)
    return OAuthCallbackResult(auth=result, frontend_redirect_url=frontend_redirect_url)


def _get_active_pending_social_signup(db: Session, token: str) -> PendingSocialSignup:
    pending = pending_social_signup_repository.get_active_pending_social_signup_by_token(
        db,
        token_hash=security.hash_token(token),
        now=security.utc_now_naive(),
    )
    if pending is None:
        raise OAuthServiceError(400, "Invalid or expired social signup token")
    return pending


def get_pending_social_signup(db: Session, token: str) -> PendingSocialSignupResult:
    pending = _get_active_pending_social_signup(db, token)
    return PendingSocialSignupResult(
        provider=pending.provider,
        email=pending.email,
        nickname=pending.nickname,
        expires_at=pending.expires_at.isoformat(),
        redirect_path=safe_redirect_path(pending.redirect_path),
    )


def complete_pending_social_signup(
    db: Session,
    request: CompleteSocialSignupRequest,
) -> auth_service.AuthResult:
    pending = _get_active_pending_social_signup(db, request.token)
    accepted_at = auth_service.validate_required_agreements(request.agreements)

    social_account = user_repository.get_active_social_account(
        db,
        provider=pending.provider,
        provider_id=pending.provider_id,
    )
    if social_account is not None:
        pending_social_signup_repository.delete_pending_social_signup(db, pending)
        result = auth_service._issue_tokens(db, social_account.user)
        db.commit()
        return result

    existing_user = user_repository.get_active_user_by_email(db, pending.email)
    if existing_user is None:
        user = user_repository.create_user(
            db,
            email=pending.email,
            nickname=pending.nickname or f"{pending.provider} 사용자",
            password_hash=None,
            nickname_setup_completed=False,
            terms_accepted=True,
            terms_accepted_at=accepted_at,
            terms_version=request.agreements.termsVersion,
            privacy_accepted=True,
            privacy_accepted_at=accepted_at,
            privacy_version=request.agreements.privacyVersion,
        )
    else:
        user = existing_user

    user_repository.create_social_account(
        db,
        user=user,
        provider=pending.provider,
        provider_id=pending.provider_id,
        provider_nickname=pending.nickname,
    )
    pending_social_signup_repository.delete_pending_social_signup(db, pending)
    result = auth_service._issue_tokens(db, user)
    db.commit()
    return result
