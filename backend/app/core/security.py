from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Response
from jwt import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    return utc_now().replace(tzinfo=None)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(user_id: int | str) -> str:
    expires_at = utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expires_at,
        "typ": "access",
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[ALGORITHM])
    except (ExpiredSignatureError, InvalidTokenError):
        return None

    if payload.get("typ") != "access":
        return None
    subject = payload.get("sub")
    return str(subject) if subject is not None else None


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_urlsafe_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_refresh_token(token: str) -> str:
    return hash_token(token)


def hmac_sha256_hex(value: str, *, secret: str | None = None) -> str:
    """Return a deterministic keyed SHA-256 digest for non-secret lookups.

    This is for stable fingerprints such as withdrawn email lookup. It is
    intentionally HMAC-based so the stored value is not a plain SHA/email hash.
    """

    key = (secret or settings.auth_secret_key).encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def refresh_token_expires_at() -> datetime:
    return utc_now_naive() + timedelta(days=settings.refresh_token_expire_days)


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path="/",
    )
