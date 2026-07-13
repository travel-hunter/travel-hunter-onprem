from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.repositories import external_sources as external_source_repository
from app.services import policy_normalization
from app.services.travelmonth_parser import parse_regional_benefits


TRAVELMONTH_REGIONAL_BENEFIT_URL = "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"


@dataclass(frozen=True)
class CollectionResult:
    source_name: str
    source_category: str
    parsed_count: int
    created_or_updated_count: int


def collect_regional_benefits_from_html(
    db: Session,
    html: str,
    *,
    fetched_at: datetime,
    today: date,
) -> CollectionResult:
    sources = parse_regional_benefits(
        html,
        collected_page_url=TRAVELMONTH_REGIONAL_BENEFIT_URL,
        fetched_at=fetched_at,
        today=today,
    )
    rows = external_source_repository.upsert_external_source_records(db, sources)
    if rows:
        policy_normalization.promote_external_benefits_to_policies(db)
    db.commit()
    return CollectionResult(
        source_name="여행가는 달",
        source_category="regional_benefit",
        parsed_count=len(sources),
        created_or_updated_count=len(rows),
    )
