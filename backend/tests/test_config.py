import pytest

from app.core.config import Settings


def test_local_runtime_allows_development_defaults() -> None:
    Settings(app_env="local").validate_runtime()


def test_protected_runtime_rejects_localhost_and_dev_secret() -> None:
    settings = Settings(
        app_env="staging",
        auth_secret_key="dev-only-change-me-secret-key-32-bytes",
        travel_hunter_public_base_url="http://127.0.0.1:5173",
        cors_origins=("http://localhost:5173",),
        refresh_cookie_secure=False,
    )

    with pytest.raises(RuntimeError, match="Invalid protected runtime configuration") as error:
        settings.validate_runtime()

    message = str(error.value)
    assert "AUTH_SECRET_KEY" in message
    assert "TRAVEL_HUNTER_PUBLIC_BASE_URL" in message
    assert "CORS_ORIGINS" in message
    assert "REFRESH_COOKIE_SECURE" in message


def test_protected_runtime_accepts_https_public_values() -> None:
    Settings(
        app_env="staging",
        auth_secret_key="not-the-default-secret-key",
        travel_hunter_public_base_url="https://staging.travel-hunter.example",
        cors_origins=("https://staging.travel-hunter.example",),
        refresh_cookie_secure=True,
    ).validate_runtime()
