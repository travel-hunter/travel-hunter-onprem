import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


load_env_file(Path(__file__).resolve().parents[2] / ".env")


def split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


LOCAL_URL_MARKERS = ("127.0.0.1", "localhost")
PROTECTED_APP_ENVS = {"staging", "production", "prod"}
DEV_AUTH_SECRET_KEY = "dev-only-change-me-secret-key-32-bytes"


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local")
    database_url: str = os.getenv("DATABASE_URL", "")
    auth_secret_key: str = os.getenv(
        "AUTH_SECRET_KEY", "dev-only-change-me-secret-key-32-bytes"
    )
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
    refresh_cookie_name: str = os.getenv(
        "REFRESH_COOKIE_NAME", "travel_hunter_refresh"
    )
    refresh_cookie_secure: bool = os.getenv(
        "REFRESH_COOKIE_SECURE", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    cors_origins: tuple[str, ...] = split_csv(
        os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
        )
    )
    notification_scheduler_enabled: bool = os.getenv(
        "NOTIFICATION_SCHEDULER_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    notification_run_at: str = os.getenv("NOTIFICATION_RUN_AT", "09:00")
    notification_poll_seconds: int = int(
        os.getenv("NOTIFICATION_POLL_SECONDS", "60")
    )
    notification_retry_enabled: bool = os.getenv(
        "NOTIFICATION_RETRY_ENABLED", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    notification_retry_max_attempts: int = int(
        os.getenv("NOTIFICATION_RETRY_MAX_ATTEMPTS", "3")
    )
    notification_retry_delay_seconds: int = int(
        os.getenv("NOTIFICATION_RETRY_DELAY_SECONDS", "600")
    )
    external_collection_scheduler_enabled: bool = os.getenv(
        "EXTERNAL_COLLECTION_SCHEDULER_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    external_collection_run_at: str = os.getenv("EXTERNAL_COLLECTION_RUN_AT", "03:00")
    external_collection_poll_seconds: int = int(
        os.getenv("EXTERNAL_COLLECTION_POLL_SECONDS", "60")
    )
    external_collection_min_parsed_count: int = int(
        os.getenv("EXTERNAL_COLLECTION_MIN_PARSED_COUNT", "1")
    )
    travel_hunter_public_base_url: str = os.getenv(
        "TRAVEL_HUNTER_PUBLIC_BASE_URL", ""
    )
    password_reset_expire_minutes: int = int(
        os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30")
    )
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    kakao_client_id: str = os.getenv("KAKAO_CLIENT_ID", "")
    kakao_client_secret: str = os.getenv("KAKAO_CLIENT_SECRET", "")
    kakao_redirect_uri: str = os.getenv("KAKAO_REDIRECT_URI", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")
    kakao_local_enabled: bool = os.getenv(
        "KAKAO_LOCAL_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    kakao_local_rest_api_key: str = os.getenv("KAKAO_LOCAL_REST_API_KEY", "")
    kakao_local_timeout_seconds: float = float(os.getenv("KAKAO_LOCAL_TIMEOUT_SECONDS", "5"))
    oauth_state_cookie_name: str = os.getenv(
        "OAUTH_STATE_COOKIE_NAME", "travel_hunter_oauth_state"
    )

    @property
    def is_protected_env(self) -> bool:
        return self.app_env.strip().lower() in PROTECTED_APP_ENVS

    def frontend_base_url(self) -> str:
        return self.travel_hunter_public_base_url.rstrip("/") or "http://127.0.0.1:5173"

    def validate_runtime(self) -> None:
        if not self.is_protected_env:
            return

        problems: list[str] = []
        if self.auth_secret_key == DEV_AUTH_SECRET_KEY:
            problems.append("AUTH_SECRET_KEY must not use the development default")
        if not self.travel_hunter_public_base_url:
            problems.append("TRAVEL_HUNTER_PUBLIC_BASE_URL is required")
        elif any(marker in self.travel_hunter_public_base_url for marker in LOCAL_URL_MARKERS):
            problems.append("TRAVEL_HUNTER_PUBLIC_BASE_URL must not point to localhost")
        if any(any(marker in origin for marker in LOCAL_URL_MARKERS) for origin in self.cors_origins):
            problems.append("CORS_ORIGINS must not include localhost origins")
        if not self.refresh_cookie_secure:
            problems.append("REFRESH_COOKIE_SECURE=true is required")

        if problems:
            raise RuntimeError("Invalid protected runtime configuration: " + "; ".join(problems))


settings = Settings()
