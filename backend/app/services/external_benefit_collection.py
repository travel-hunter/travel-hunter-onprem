from __future__ import annotations

from collections.abc import Callable
from math import ceil
import re
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord
from app.repositories import external_sources as external_source_repository
from app.repositories import policy_collection_sources
from app.services import digital_tourism_resident_card as dgtour_identity
from app.services import policy_candidate_review
from app.services.island_visit_parser import (
    SOURCE_CATEGORY as ISLAND_VISIT_SOURCE_CATEGORY,
    SOURCE_URL as ISLAND_VISIT_SOURCE_URL,
    parse_island_visit_support,
)
from app.services.dgtourcard_parser import (
    enrich_dgtourcard_benefits_with_detail_pages,
    parse_dgtourcard_benefits,
    parse_local_half_trip_detail_fields,
)
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
    _queue_review_candidates(db, all_rows, source_results=source_results)
    _record_source_results(db, source_results, collected_at=fetched_at)
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
    enabled_categories = _enabled_source_categories(db)
    for source in _source_registry():
        if source.source_category not in enabled_categories:
            continue
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
                    timeout=timeout,
                )
            all_rows.extend(rows)
            source_results.append(result)
        except Exception as exc:
            source_results.append(_source_failure_result(source, exc))
    if any(
        source.source_category == "local_half_trip" and source.outcome == "success"
        for source in source_results
    ):
        enrich_existing_local_half_trip_detail_fields(db, timeout=timeout)
    _queue_review_candidates(db, all_rows, source_results=source_results)
    _record_source_results(db, source_results, collected_at=fetched_at)
    db.commit()
    return _build_result(source_results, len(all_rows))





def _record_source_results(
    db: Session,
    source_results: list[SourceCollectionResult],
    *,
    collected_at: datetime,
) -> None:
    if not hasattr(db, "scalars"):
        return
    for result in source_results:
        source = policy_collection_sources.get_collection_source_by_key(
            db, key=result.source_category
        )
        if source is not None:
            policy_collection_sources.record_collection_source_run(
                db,
                source=source,
                outcome=result.outcome,
                collected_at=collected_at,
                error=result.error,
                parsed_count=result.parsed_count,
            )


def _enabled_source_categories(db: Session) -> set[str]:
    if not hasattr(db, "scalars"):
        return {source.source_category for source in _source_registry()}
    return policy_collection_sources.enabled_collection_source_categories(db)


def _queue_review_candidates(
    db: Session,
    rows: list[object],
    *,
    source_results: list[SourceCollectionResult] | None = None,
) -> None:
    results_by_category = {result.source_category: result for result in source_results or []}
    sources_by_category: dict[str, object] = {}
    for row in rows:
        if not (isinstance(row, ExternalSourceRecord) and row.id is not None):
            continue
        candidate = policy_candidate_review.classify_candidate(db, record=row)
        # Only freshly created candidates go through the gate; re-seen evidence keeps its verdict.
        if candidate.review_status != "pending" or candidate.review_reason is not None:
            continue
        category = row.source_category or ""
        if category not in sources_by_category:
            sources_by_category[category] = (
                policy_collection_sources.get_collection_source_by_key(db, key=category)
                if hasattr(db, "scalars")
                else None
            )
        policy_candidate_review.auto_publish_gate(
            db,
            candidate=candidate,
            record=row,
            source=sources_by_category[category],
            source_result=results_by_category.get(category),
        )

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
        for category_code, _category_name in dgtour_identity.PARTNER_BENEFIT_CATEGORY_ORDER:
            page_no = 1
            total_count: int | None = None
            while True:
                payload = {
                    "mtpcDoCd": mtpc_do_cd,
                    "signguCd": signgu_cd,
                    "mbrbBnefClCd": category_code,
                    "pageNo": str(page_no),
                    "tipPageNo": "1",
                    "orderDiv": "UTZT",
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



def fetch_local_half_trip_detail_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    html = fetch_external_source_html(url, timeout=timeout)
    ajax_url = _local_half_trip_ajax_content_url(url, html)
    if ajax_url is None:
        landing_url = _local_half_trip_landing_page_url(url, html)
        if landing_url is not None:
            try:
                landing_html = fetch_external_source_html(landing_url, timeout=timeout)
            except Exception:
                landing_html = html
            else:
                landing_ajax_url = _local_half_trip_ajax_content_url(landing_url, landing_html)
                if landing_ajax_url is not None:
                    ajax_url = landing_ajax_url
                else:
                    html = landing_html
        if ajax_url is None:
            return html
    try:
        return fetch_external_source_html(ajax_url, timeout=timeout)
    except Exception:
        return html


def enrich_existing_local_half_trip_detail_fields(
    db: Session,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> int:
    records = list(
        db.scalars(
            select(ExternalSourceRecord)
            .where(ExternalSourceRecord.source_category == "local_half_trip")
            .where(ExternalSourceRecord.detail_url.is_not(None))
            .where(ExternalSourceRecord.status.in_(("active", "scheduled")))
            .where(ExternalSourceRecord.freshness_status.in_(("fresh", "unknown")))
            .order_by(ExternalSourceRecord.id)
        ).all()
    )
    updated_count = 0
    for record in records:
        try:
            fields = parse_local_half_trip_detail_fields(
                fetch_local_half_trip_detail_html(str(record.detail_url), timeout=timeout)
            )
        except Exception:
            continue
        if not fields:
            continue
        payload = dict(record.raw_payload or {})
        changed = False
        for key, value in fields.items():
            if payload.get(key) != value:
                payload[key] = value
                changed = True
        if not changed:
            continue
        record.raw_payload = payload
        record.raw_detail_text = _merged_local_half_trip_detail_text(record.raw_detail_text, fields)
        record.field_completeness = min(100, max(record.field_completeness, 95))
        record.confidence = min(100, max(record.confidence, 95))
        updated_count += 1
    return updated_count


def _merged_local_half_trip_detail_text(
    raw_detail_text: str,
    fields: dict[str, object],
) -> str:
    values = [
        raw_detail_text,
        fields.get("participantTarget"),
        fields.get("supportDetail"),
        fields.get("requiredDocumentsDetail"),
        fields.get("detailNotes"),
    ]
    lines: list[str] = []
    for value in values:
        if not value:
            continue
        for line in re.split(r"[ \t]*\r?\n[ \t]*", str(value)):
            text = " ".join(line.split())
            if text and text not in lines:
                lines.append(text)
    return "\n".join(lines) if lines else raw_detail_text


def _local_half_trip_landing_page_url(url: str, html: str) -> str | None:
    for pattern in (
        r"<meta[^>]+http-equiv=['\"]?refresh['\"]?[^>]+content=['\"][^'\"]*url=([^'\"]+)['\"]",
        r"<meta[^>]+property=['\"]og:url['\"][^>]+content=['\"]([^'\"]+)['\"]",
        r"<meta[^>]+property=['\"]twitter:url['\"][^>]+content=['\"]([^'\"]+)['\"]",
    ):
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match is None:
            continue
        candidate = match.group(1).strip()
        if not candidate:
            continue
        absolute_url = urljoin(url, candidate)
        parsed = urlparse(absolute_url)
        if parsed.scheme in {"http", "https"} and absolute_url.rstrip("/") != url.rstrip("/"):
            return absolute_url
    return None


def _local_half_trip_ajax_content_url(url: str, html: str) -> str | None:
    match = re.search(
        r"DataLoad\(['\"]load_content['\"],\s*['\"][^'\"]*['\"],\s*['\"]([^'\"]+)['\"]",
        html,
    )
    if match is None:
        return None
    parsed = urlparse(url)
    ajax_path = match.group(1)
    if not ajax_path or parsed.scheme not in {"http", "https"}:
        return None
    return urljoin(url, ajax_path)

def _collect_source_records(
    db: Session,
    *,
    source_category: str,
    parser: Parser,
    html: str,
    fetched_at: datetime,
    today: date,
    timeout: float | None = None,
) -> tuple[list[object], SourceCollectionResult]:
    parsed = list(parser(html, fetched_at, today))
    if source_category == "local_half_trip" and timeout is not None:
        parsed = enrich_dgtourcard_benefits_with_detail_pages(
            parsed,
            fetch_detail_html=lambda detail_url: fetch_local_half_trip_detail_html(
                detail_url,
                timeout=timeout,
            ),
        )
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
    if source_category == ISLAND_VISIT_SOURCE_CATEGORY:
        return lambda html, fetched_at, today: parse_island_visit_support(
            html,
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
        SourceDefinition(
            ISLAND_VISIT_SOURCE_CATEGORY,
            ISLAND_VISIT_SOURCE_URL,
            _parser_for(ISLAND_VISIT_SOURCE_CATEGORY),
        ),
    )


def _source_failure_result(source: SourceDefinition, exc: Exception) -> SourceCollectionResult:
    outcome = (
        "parser_changed"
        if exc.__class__.__name__ == "IslandVisitParserChangedError"
        else "source_unavailable" if _is_source_unavailable(exc) else "error"
    )
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
        if item.outcome in {"error", "parser_changed"}
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
