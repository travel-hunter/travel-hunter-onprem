import os

import pytest

from app.core.config import Settings, load_env_file


def test_local_runtime_allows_development_defaults() -> None:
    Settings(app_env="local").validate_runtime()


def test_local_frontend_base_url_defaults_to_docker_frontend() -> None:
    settings = Settings(travel_hunter_public_base_url="")

    assert settings.frontend_base_url() == "http://127.0.0.1:4173"


def test_protected_runtime_rejects_localhost_and_dev_secret() -> None:
    settings = Settings(
        app_env="staging",
        auth_secret_key="dev-only-change-me-secret-key-32-bytes",
        travel_hunter_public_base_url="http://127.0.0.1:4173",
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


def test_load_env_file_allows_local_file_to_override_prior_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("TRAVEL_HUNTER_TEST_ENV", raising=False)
    defaults = tmp_path / ".env"
    local = tmp_path / ".env.local"
    defaults.write_text("TRAVEL_HUNTER_TEST_ENV=default\n", encoding="utf-8")
    local.write_text("TRAVEL_HUNTER_TEST_ENV=local\n", encoding="utf-8")

    load_env_file(defaults, protected_keys=frozenset())
    load_env_file(local, override=True, protected_keys=frozenset())

    assert os.environ["TRAVEL_HUNTER_TEST_ENV"] == "local"


def test_load_env_file_does_not_override_original_process_env(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("TRAVEL_HUNTER_TEST_ENV", "process")
    local = tmp_path / ".env.local"
    local.write_text("TRAVEL_HUNTER_TEST_ENV=local\n", encoding="utf-8")

    load_env_file(
        local,
        override=True,
        protected_keys=frozenset({"TRAVEL_HUNTER_TEST_ENV"}),
    )

    assert os.environ["TRAVEL_HUNTER_TEST_ENV"] == "process"
