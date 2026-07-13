from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser

from app.schemas.external_sources import ExternalBenefitSource
from app.services.travelmonth_normalizer import (
    BenefitValue,
    calculate_field_completeness,
    extract_benefit_value,
    normalize_status,
    normalize_text,
    parse_period,
    stable_hash,
)

SOURCE_NAME = "여행가는 달"
SOURCE_URL = "https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do"
SOURCE_CATEGORY = "traffic_benefit"
NATIONWIDE_REGION = "전국"


class _TrafficBenefitHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._capture: str | None = None
        self._last_dt: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        if tag == "h4":
            self._finish_current()
            self._current = {"raw": ""}
            self._capture = "title"
            return
        if self._current is None:
            return
        if tag in {"p", "dt", "dd"}:
            self._capture = tag
        if tag == "a" and attr_map.get("href") and not self._current.get("detail_url"):
            self._current["detail_url"] = attr_map["href"]

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h4", "p", "dt", "dd"}:
            self._capture = None

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return
        if self._current is not None:
            self._current["raw"] = normalize_text(f"{self._current.get('raw', '')} {text}")
        if self._current is None or self._capture is None:
            return
        if self._capture == "title":
            self._current["title"] = text
        elif self._capture == "p":
            self._current["benefit"] = normalize_text(f"{self._current.get('benefit', '')} {text}")
        elif self._capture == "dt":
            self._last_dt = text
        elif self._capture == "dd":
            if self._last_dt == "판매 기간":
                self._current["period"] = text
            elif self._last_dt == "문의처":
                self._current["contact"] = text
            self._last_dt = None

    def close(self) -> None:
        super().close()
        self._finish_current()

    def _finish_current(self) -> None:
        if self._current and self._current.get("title"):
            self.records.append(self._current)
        self._current = None


def parse_traffic_benefits(
    html: str,
    *,
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> list[ExternalBenefitSource]:
    parser = _TrafficBenefitHtmlParser()
    parser.feed(html)
    parser.close()

    records: list[ExternalBenefitSource] = []
    for raw_record in parser.records:
        title = str(raw_record.get("title", ""))
        benefit_text = str(raw_record.get("benefit", ""))
        period_text = str(raw_record.get("period", ""))
        contact_text = str(raw_record.get("contact", "")) or None
        detail_url = str(raw_record.get("detail_url", "")) or None
        raw_text = str(raw_record.get("raw", ""))
        if not title or not benefit_text:
            continue

        start_date, end_date = _parse_period_with_year(period_text, fetched_at.year)
        status = normalize_status(None, start_date, end_date, today)
        benefit_value = _traffic_benefit_value(benefit_text)
        canonical_text = "|".join([SOURCE_CATEGORY, title, period_text, benefit_text])
        field_completeness = calculate_field_completeness(
            {
                "title": title,
                "benefit_text": benefit_text,
                "period_text": period_text,
                "detail_url": detail_url,
                "contact_text": contact_text,
            }
        )
        confidence = 90 if field_completeness >= 75 else 70
        organizer = _organizer_for(title, benefit_text, contact_text)
        records.append(
            ExternalBenefitSource(
                source_name=SOURCE_NAME,
                source_type="official_campaign",
                source_url=SOURCE_URL,
                source_category=SOURCE_CATEGORY,
                external_id=stable_hash(canonical_text),
                canonical_key=stable_hash(canonical_text),
                detail_url=detail_url,
                collected_page_url=collected_page_url,
                title=title,
                organizer_text=organizer,
                organizers=[organizer],
                region=NATIONWIDE_REGION,
                city=None,
                is_nationwide=True,
                status_text=period_text or None,
                status=status,
                start_date=start_date,
                end_date=end_date,
                benefit_text=benefit_text,
                benefit_value_text=benefit_value.value_text,
                extracted_amount_krw=benefit_value.amount_krw,
                extracted_discount_percent=benefit_value.discount_percent,
                benefit_value_type=benefit_value.value_type,
                tags=["교통", _traffic_tag(title, benefit_text)],
                contact_text=contact_text,
                inferred_travel_styles=[],
                confidence=confidence,
                field_completeness=field_completeness,
                raw_list_text=raw_text,
                raw_detail_text=raw_text,
                raw_payload={"periodText": period_text},
                last_fetched_at=fetched_at,
                last_verified_at=fetched_at if confidence >= 85 else None,
                freshness_status="fresh" if status == "active" else "unknown",
            )
        )
    return records


def _parse_period_with_year(period_text: str, year: int) -> tuple[date | None, date | None]:
    try:
        parsed_start, parsed_end = parse_period(period_text)
        if parsed_start is not None and parsed_end is not None:
            return parsed_start, parsed_end
    except ValueError:
        pass
    normalized = normalize_text(period_text)
    matches = re.findall(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", normalized)
    if len(matches) < 2:
        return None, None
    return (
        date(year, int(matches[0][0]), int(matches[0][1])),
        date(year, int(matches[1][0]), int(matches[1][1])),
    )


def _traffic_benefit_value(benefit_text: str):
    text = normalize_text(benefit_text)
    point_matches = [
        int(value) * 10000 for value in re.findall(r"(\d+)\s*만\s*포인트", text)
    ]
    if point_matches:
        amount = max(point_matches)
        return BenefitValue(
            value_text=f"최대 {amount // 10000}만 포인트",
            amount_krw=amount,
            discount_percent=None,
            value_type="amount",
        )
    return extract_benefit_value(text)


def _organizer_for(title: str, benefit_text: str, contact_text: str | None) -> str:
    text = " ".join(part for part in [title, benefit_text, contact_text] if part)
    if "네이버" in text or "항공권" in text:
        return "네이버 항공권"
    if "철도" in text or "열차" in text or "내일로" in text:
        return "한국철도공사"
    return "한국관광공사"


def _traffic_tag(title: str, benefit_text: str) -> str:
    text = f"{title} {benefit_text}"
    if "항공" in text or "비행" in text:
        return "항공"
    if "철도" in text or "열차" in text or "내일로" in text:
        return "철도"
    return "교통"
