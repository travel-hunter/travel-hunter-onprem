from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
from sqlalchemy.orm import Session

from app.services.travelmonth_collection import (
    TRAVELMONTH_REGIONAL_BENEFIT_URL,
    CollectionResult,
    collect_regional_benefits_from_html,
)


DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_HEADERS = {
    "User-Agent": "Travel Hunter official-source collector/0.1",
}


class TravelMonthLiveFetchError(RuntimeError):
    """Raised when the official TravelMonth source cannot be fetched."""


def collect_regional_benefits_from_live_source(
    db: Session,
    *,
    fetched_at: datetime | None = None,
    today: date | None = None,
    url: str = TRAVELMONTH_REGIONAL_BENEFIT_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CollectionResult:
    fetched_at = fetched_at or datetime.now(UTC)
    today = today or fetched_at.date()
    html = fetch_travelmonth_regional_benefit_html(url=url, timeout=timeout)
    return collect_regional_benefits_from_html(
        db,
        html,
        fetched_at=fetched_at,
        today=today,
    )


def fetch_travelmonth_regional_benefit_html(
    *,
    url: str = TRAVELMONTH_REGIONAL_BENEFIT_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise TravelMonthLiveFetchError(
            f"Failed to fetch TravelMonth regional benefits from {url}: {exc}"
        ) from exc
    return response.text
