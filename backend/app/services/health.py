from app.core.config import settings
from app.db.session import check_database_connection


def get_health_payload() -> dict[str, str]:
    database_status = check_database_connection()

    return {
        "status": "ok",
        "service": "travel-hunter-backend",
        "environment": settings.app_env,
        "database": database_status,
    }
