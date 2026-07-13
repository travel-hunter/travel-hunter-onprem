from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from sqlalchemy.orm import Session

from app.repositories import external_sources as external_source_repository
from app.services import policy_normalization
from app.services.dgtourcard_parser import parse_dgtourcard_benefits
from app.services.travelmonth_collection import (
    TRAVELMONTH_REGIONAL_BENEFIT_URL,
    CollectionResult,
)
from app.services.travelmonth_live_collector import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_SECONDS,
)
from app.services.travelmonth_parser import parse_regional_benefits
from app.services.travelmonth_stay_parser import (
    SOURCE_URL as TRAVELMONTH_STAY_DISCOUNT_URL,
)
from app.services.travelmonth_stay_parser import parse_stay_discount_benefits
from app.services.travelmonth_traffic_parser import (
    SOURCE_URL as TRAVELMONTH_TRAFFIC_BENEFIT_URL,
)
from app.services.travelmonth_traffic_parser import parse_traffic_benefits

DGTOURCARD_URL = "https://korean.visitkorea.or.kr/dgtourcard/tour50.do"


@dataclass(frozen=True)
class SourceDefinition:
    source_category: str
    url: str
    parser: Callable[[str, datetime, date], object]
    required: bool = True


@dataclass(frozen=True)
class SourceCollectionResult:
    source_category: str
    parsed_count: int
    created_or_updated_count: int
    outcome: str
    error: str | None = None


@dataclass(frozen=True)
class ExternalBenefitCollectionResult(CollectionResult):
    outcome: str
    sources: list[SourceCollectionResult]


Parser = Callable[[str, datetime, date], object]
_SOURCE_UNAVAILABLE_STATUSES = {404, 410}


def collect_external_benefits_from_html_sources(
    db: Session,
    *,
    html_sources: dict[str, str],
    fetched_at: datetime,
    today: date,
) -> ExternalBenefitCollectionResult:
    source_results: list[SourceCollectionResult] = []
    all_rows = []
    for source_category, html in html_sources.items():
        try:
            rows, result = _collect_source_records(
                db,
                source_category=source_category,
                parser=_parser_for(source_category),
                html=html,
                fetched_at=fetched_at,
                today=today,
            )
            all_rows.extend(rows)
            source_results.append(result)
        except Exception as exc:
            source_results.append(
                SourceCollectionResult(
                    source_category=source_category,
                    parsed_count=0,
                    created_or_updated_count=0,
                    outcome="error",
                    error=str(exc),
                )
            )
    if all_rows:
        policy_normalization.promote_external_benefits_to_policies(db)
    db.commit()
    return _build_result(source_results, len(all_rows))


def collect_external_benefits_from_live_sources(
    db: Session,
    *,
    fetched_at: datetime | None = None,
    today: date | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ExternalBenefitCollectionResult:
    fetched_at = fetched_at or datetime.now(UTC)
    today = today or fetched_at.date()
    source_results: list[SourceCollectionResult] = []
    all_rows = []
    for source in _source_registry():
        try:
            html = fetch_external_source_html(source.url, timeout=timeout)
            rows, result = _collect_source_records(
                db,
                source_category=source.source_category,
                parser=source.parser,
                html=html,
                fetched_at=fetched_at,
                today=today,
            )
            all_rows.extend(rows)
            source_results.append(result)
        except Exception as exc:
            source_results.append(_source_failure_result(source, exc))
    if all_rows:
        policy_normalization.promote_external_benefits_to_policies(db)
    db.commit()
    return _build_result(source_results, len(all_rows))


def fetch_external_source_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    )
    response.raise_for_status()
    return response.text


def _collect_source_records(
    db: Session,
    *,
    source_category: str,
    parser: Parser,
    html: str,
    fetched_at: datetime,
    today: date,
) -> tuple[list[object], SourceCollectionResult]:
    parsed = list(parser(html, fetched_at, today))
    rows = external_source_repository.upsert_external_source_records(db, parsed)
    return rows, SourceCollectionResult(
        source_category=source_category,
        parsed_count=len(parsed),
        created_or_updated_count=len(rows),
        outcome="success",
    )


def _parser_for(source_category: str) -> Parser:
    if source_category == "regional_benefit":
        return lambda html, fetched_at, today: parse_regional_benefits(
            html,
            collected_page_url=TRAVELMONTH_REGIONAL_BENEFIT_URL,
            fetched_at=fetched_at,
            today=today,
        )
    if source_category == "traffic_benefit":
        return lambda html, fetched_at, today: parse_traffic_benefits(
            html,
            collected_page_url=TRAVELMONTH_TRAFFIC_BENEFIT_URL,
            fetched_at=fetched_at,
            today=today,
        )
    if source_category == "local_half_trip":
        return lambda html, fetched_at, today: parse_dgtourcard_benefits(
            html,
            collected_page_url=DGTOURCARD_URL,
            fetched_at=fetched_at,
            today=today,
        )
    if source_category == "stay_discount":
        return lambda html, fetched_at, today: parse_stay_discount_benefits(
            html,
            collected_page_url=TRAVELMONTH_STAY_DISCOUNT_URL,
            fetched_at=fetched_at,
            today=today,
        )
    raise ValueError(f"Unsupported external source category: {source_category}")


def _source_registry() -> tuple[SourceDefinition, ...]:
    return (
        SourceDefinition(
            "regional_benefit",
            TRAVELMONTH_REGIONAL_BENEFIT_URL,
            _parser_for("regional_benefit"),
        ),
        SourceDefinition(
            "traffic_benefit",
            TRAVELMONTH_TRAFFIC_BENEFIT_URL,
            _parser_for("traffic_benefit"),
            required=False,
        ),
        SourceDefinition(
            "local_half_trip",
            DGTOURCARD_URL,
            _parser_for("local_half_trip"),
        ),
        SourceDefinition(
            "stay_discount",
            TRAVELMONTH_STAY_DISCOUNT_URL,
            _parser_for("stay_discount"),
        ),
    )


def _source_failure_result(source: SourceDefinition, exc: Exception) -> SourceCollectionResult:
    outcome = "source_unavailable" if _is_source_unavailable(exc) else "error"
    return SourceCollectionResult(
        source_category=source.source_category,
        parsed_count=0,
        created_or_updated_count=0,
        outcome=outcome,
        error=str(exc),
    )


def _is_source_unavailable(exc: Exception) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    return exc.response.status_code in _SOURCE_UNAVAILABLE_STATUSES


def _required_source_categories() -> set[str]:
    return {source.source_category for source in _source_registry() if source.required}


def _build_result(
    source_results: list[SourceCollectionResult],
    created_or_updated_count: int,
) -> ExternalBenefitCollectionResult:
    parsed_count = sum(item.parsed_count for item in source_results)
    required_sources = _required_source_categories()
    failed_count = sum(
        1
        for item in source_results
        if item.outcome == "error"
        or (item.outcome == "source_unavailable" and item.source_category in required_sources)
    )
    if failed_count == 0:
        outcome = "success"
    elif parsed_count > 0:
        outcome = "partial_success"
    else:
        outcome = "error"
    return ExternalBenefitCollectionResult(
        source_name="official external benefits",
        source_category="multiple",
        parsed_count=parsed_count,
        created_or_updated_count=created_or_updated_count,
        outcome=outcome,
        sources=source_results,
    )
