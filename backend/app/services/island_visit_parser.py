from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin
from html.parser import HTMLParser

from app.schemas.external_sources import ExternalBenefitSource
from app.services.travelmonth_normalizer import extract_benefit_value, normalize_status, normalize_text

SOURCE_CATEGORY = "island_visit"
SOURCE_NAME = "2026 Island Visit Year"
SOURCE_URL = "https://www.visitisland.kr/promotion2"
CANONICAL_KEY = "2026-island-visit-support"


class IslandVisitParserChangedError(ValueError):
    pass


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if text := normalize_text(data):
            self.parts.append(text)


def parse_island_visit_support(html: str, *, fetched_at: datetime, today: date) -> list[ExternalBenefitSource]:
    parser = _TextParser()
    parser.feed(html)
    text = "\n".join(parser.parts)
    application = _line_after(text, "신청 기간")
    travel = _travel_period_line(text)
    benefit = _line_after(text, "지원 내용")
    if not application or not travel or not benefit:
        raise IslandVisitParserChangedError("missing required Island Visit campaign fields")
    period = _parse_period(travel, fallback_year=fetched_at.year)
    if period is None:
        raise IslandVisitParserChangedError("unreadable Island Visit travel period")
    start, end = period
    amount = extract_benefit_value(benefit)
    eligible_islands_url = _eligible_islands_url(html)
    return [ExternalBenefitSource(source_name=SOURCE_NAME, source_type="official_campaign", source_url=SOURCE_URL, source_category=SOURCE_CATEGORY, external_id=CANONICAL_KEY, canonical_key=CANONICAL_KEY, logical_key=CANONICAL_KEY, collected_page_url=SOURCE_URL, title="2026 섬 여행비 지원", organizer_text="섬 방문의 해 추진위원회", organizers=["섬 방문의 해 추진위원회"], region="전국", is_nationwide=True, status_text=travel, status=normalize_status(None, start, end, today), start_date=start, end_date=end, benefit_text=benefit, benefit_value_text=amount.value_text, extracted_amount_krw=amount.amount_krw, extracted_discount_percent=amount.discount_percent, benefit_value_type=amount.value_type, tags=["섬여행", "여행비지원"], inferred_travel_styles=[], confidence=95, field_completeness=90, raw_list_text=text, raw_detail_text=text, raw_payload={"applicationPeriod": application, "eligibleIslandsUrl": eligible_islands_url}, last_fetched_at=fetched_at, last_verified_at=fetched_at, freshness_status="fresh")]


def _line_after(text: str, label: str) -> str | None:
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    for index, line in enumerate(lines):
        if label in line:
            suffix = normalize_text(line.split(label, 1)[1].strip(" :|"))
            if suffix and re.search(r"\d", suffix):
                return suffix
            if index + 1 < len(lines):
                return normalize_text(f"{suffix} {lines[index + 1]}")
            return suffix or line
    return None


def _travel_period_line(text: str) -> str | None:
    for line in (normalize_text(line) for line in text.splitlines()):
        if "여행" in line and _parse_period(line, fallback_year=2000) is not None:
            return line
    return None


def _parse_period(value: str, *, fallback_year: int) -> tuple[date, date] | None:
    match = re.search(
        r"(?:(20\d{2})\s*년?\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일?"
        r"\s*(?:~|부터|[-–])\s*"
        r"(?:(20\d{2})\s*년?\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일?",
        value,
    )
    if match is None:
        return None
    start_year = int(match.group(1) or fallback_year)
    end_year = int(match.group(4) or start_year)
    try:
        return (
            date(start_year, int(match.group(2)), int(match.group(3))),
            date(end_year, int(match.group(5)), int(match.group(6))),
        )
    except ValueError:
        return None


def _eligible_islands_url(html: str) -> str | None:
    match = re.search(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[^<]*(?:\uB300\uC0C1\s*\uC12C|eligible\s+island)',
        html,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return urljoin(SOURCE_URL, match.group(1))
