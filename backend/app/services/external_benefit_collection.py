from __future__ import annotations

from collections.abc import Callable
from math import ceil
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from sqlalchemy.orm import Session

from app.repositories import external_sources as external_source_repository
from app.services import digital_tourism_resident_card as dgtour_identity
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
DIGITAL_TOURISM_RESIDENT_CARD_URL = dgtour_identity.SOURCE_URL


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
            if source.source_category == dgtour_identity.SOURCE_CATEGORY:
                rows, result = _collect_digital_tourism_records(
                    db,
                    fetched_at=fetched_at,
                    today=today,
                    timeout=timeout,
                )
            else:
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



def fetch_digital_tourism_partner_benefits(
    *,
    city: str,
    mtpc_do_cd: str,
    signgu_cd: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
) -> list[dict[str, object]]:
    close_client = client is None
    http_client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS)
    try:
        rows: list[dict[str, object]] = []
        page_no = 1
        total_count: int | None = None
        while True:
            payload = {
                "mtpcDoCd": mtpc_do_cd,
                "signguCd": signgu_cd,
                "mbrbBnefClCd": "all",
                "pageNo": str(page_no),
                "tipPageNo": "1",
                "orderDiv": "DATE",
            }
            response = http_client.post(
                dgtour_identity.REGIONAL_MEMBER_BENEFIT_ENDPOINT,
                data=payload,
                headers={
                    **DEFAULT_HEADERS,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://korean.visitkorea.or.kr",
                    "Referer": dgtour_identity.official_url_for_city(city) or dgtour_identity.SOURCE_URL,
                },
                timeout=timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            result = response.json()
            page_rows = result.get("resultList") if isinstance(result, dict) else None
            if not isinstance(page_rows, list):
                break
            typed_page_rows = [row for row in page_rows if isinstance(row, dict)]
            rows.extend(typed_page_rows)
            if total_count is None:
                total_count = _digital_tourism_total_count(typed_page_rows)
            if not typed_page_rows:
                break
            if total_count is None:
                break
            if page_no >= max(1, ceil(total_count / dgtour_identity.REGIONAL_BENEFIT_PAGE_SIZE)):
                break
            page_no += 1
        return dgtour_identity.partner_benefits_from_api_rows(rows)
    finally:
        if close_client:
            http_client.close()


def _digital_tourism_total_count(rows: list[dict[str, object]]) -> int | None:
    if not rows:
        return 0
    total = rows[0].get("totCnt")
    return total if isinstance(total, int) else None


def collect_digital_tourism_partner_benefits_by_city(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, list[dict[str, object]]]:
    benefits_by_city: dict[str, list[dict[str, object]]] = {}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
        for city, _region, mtpc_do_cd, signgu_cd in dgtour_identity.data.REGIONAL_URL_CODE_ROWS:
            benefits_by_city[city] = fetch_digital_tourism_partner_benefits(
                city=city,
                mtpc_do_cd=mtpc_do_cd,
                signgu_cd=signgu_cd,
                timeout=timeout,
                client=client,
            )
    return benefits_by_city


def _collect_digital_tourism_records(
    db: Session,
    *,
    fetched_at: datetime,
    today: date,
    timeout: float,
) -> tuple[list[object], SourceCollectionResult]:
    materialized = dgtour_identity.materialize_participating_region_sources(
        fetched_at=fetched_at,
        today=today,
    )
    benefits_by_city = collect_digital_tourism_partner_benefits_by_city(timeout=timeout)
    enriched = dgtour_identity.apply_partner_benefit_enrichment_by_city(
        materialized,
        benefits_by_city,
    )
    rows = external_source_repository.upsert_external_source_records(db, enriched)
    return rows, SourceCollectionResult(
        source_category=dgtour_identity.SOURCE_CATEGORY,
        parsed_count=len(enriched),
        created_or_updated_count=len(rows),
        outcome="success",
    )

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
    if source_category == dgtour_identity.SOURCE_CATEGORY:
        parsed = dgtour_identity.merge_materialized_and_parsed_sources(
            dgtour_identity.materialize_participating_region_sources(
                fetched_at=fetched_at,
                today=today,
            ),
            parsed,
        )
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
    if source_category == dgtour_identity.SOURCE_CATEGORY:
        return lambda html, fetched_at, today: []
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
            dgtour_identity.SOURCE_CATEGORY,
            DIGITAL_TOURISM_RESIDENT_CARD_URL,
            _parser_for(dgtour_identity.SOURCE_CATEGORY),
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
