from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["official_campaign"]
SourceCategory = Literal["regional_benefit", "traffic_benefit", "local_half_trip", "stay_discount"]
SourceStatus = Literal["active", "ended", "scheduled", "unknown"]
BenefitValueType = Literal["amount", "percent", "free", "upgrade", "mixed", "unknown"]
FreshnessStatus = Literal["fresh", "stale", "expired", "unknown"]
TravelStyle = Literal["휴식", "맛집", "체험", "자연", "사진"]


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


class ExternalBenefitSource(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel_case,
        populate_by_name=True,
    )

    source_name: str
    source_type: SourceType
    source_url: str
    source_category: SourceCategory
    external_id: str
    canonical_key: str
    detail_url: str | None = None
    collected_page_url: str
    title: str
    organizer_text: str
    organizers: list[str]
    region: str | None = None
    city: str | None = None
    is_nationwide: bool = False
    status_text: str | None = None
    status: SourceStatus
    start_date: date | None = None
    end_date: date | None = None
    benefit_text: str
    benefit_value_text: str | None = None
    extracted_amount_krw: int | None = None
    extracted_discount_percent: int | None = None
    benefit_value_type: BenefitValueType = "unknown"
    tags: list[str] = Field(default_factory=list)
    contact_text: str | None = None
    inferred_travel_styles: list[TravelStyle] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    field_completeness: int = Field(ge=0, le=100)
    raw_list_text: str
    raw_detail_text: str
    raw_payload: dict[str, object] = Field(default_factory=dict)
    last_fetched_at: datetime
    last_verified_at: datetime | None = None
    freshness_status: FreshnessStatus


class TravelMonthRegionalBenefitSource(ExternalBenefitSource):
    source_name: Literal["여행가는 달"] = "여행가는 달"
    source_type: SourceType = "official_campaign"
    source_url: str = "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    source_category: Literal["regional_benefit"] = "regional_benefit"


class ExternalSourceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    source_type: str
    source_category: str
    external_id: str
    canonical_key: str
    title: str
    region: str | None
    city: str | None
    status: str
    benefit_value_type: str
    extracted_amount_krw: int | None
    extracted_discount_percent: int | None
    last_fetched_at: datetime
    last_verified_at: datetime | None
    freshness_status: str
