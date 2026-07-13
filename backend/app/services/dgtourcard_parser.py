from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.schemas.external_sources import ExternalBenefitSource
from app.services.local_half_trip_display import title_with_city_prefix
from app.services.travelmonth_normalizer import normalize_text, parse_period, stable_hash


SOURCE_NAME = "대한민국 반값여행"
SOURCE_URL = "https://korean.visitkorea.or.kr/dgtourcard/tour50.do"
SOURCE_CATEGORY = "local_half_trip"
DEFAULT_BENEFIT_TEXT = (
    "숙박, 식사, 체험 등 여행 중 사용한 금액의 50%를 환급받을 수 있으며 "
    "1명 최대 10만원, 2명 이상 최대 20만원까지 지원됩니다."
)

CITY_REGION = {
    "밀양": "경남",
    "평창": "강원",
    "하동": "경남",
    "거창": "경남",
    "영월": "강원",
    "제천": "충북",
    "강진": "전남",
    "영광": "전남",
    "합천": "경남",
    "해남": "전남",
    "남해": "경남",
    "영암": "전남",
    "고흥": "전남",
    "횡성": "강원",
    "완도": "전남",
    "고창": "전북",
}

_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class _DgTourCardHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.data_records: list[dict[str, object]] = []
        self.section_records: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._capture_heading = False
        self._capture_paragraph = False
        self._current_data: dict[str, object] | None = None
        self._data_depth = 0
        self._data_field: str | None = None
        self._data_buffer: list[str] = []
        self._data_label: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs if key}
        if tag == "aside" and attr_map.get("data-trvid") and attr_map.get("data-sttsnm"):
            self._finish_current()
            self._current_data = dict(attr_map)
            self._current_data["raw"] = ""
            self._current_data["field_values"] = {}
            self._data_depth = 1
            self._data_field = None
            self._data_buffer = []
            self._data_label = None
            return

        if self._current_data is not None:
            if tag not in _VOID_TAGS:
                self._data_depth += 1
            if tag in {"dt", "dd"}:
                self._data_field = tag
                self._data_buffer = []
            return

        if tag == "a" and attr_map.get("data-trvid") and (
            attr_map.get("data-town")
            or attr_map.get("data-trvnm")
            or attr_map.get("data-sttsnm")
        ):
            self.data_records.append(dict(attr_map))
            return

        if tag in {"h2", "h3"}:
            self._finish_current()
            self._current = {"raw": ""}
            self._capture_heading = True
            return

        if self._current is None:
            return
        if tag == "p":
            self._capture_paragraph = True
        elif tag == "a" and attr_map.get("href") and not self._current.get("detail_url"):
            self._current["detail_url"] = attr_map["href"]

    def handle_endtag(self, tag: str) -> None:
        if self._current_data is not None:
            if tag == "dt" and self._data_field == "dt":
                self._data_label = _clean_label(" ".join(self._data_buffer))
                self._data_field = None
                self._data_buffer = []
            elif tag == "dd" and self._data_field == "dd":
                value = normalize_text(" ".join(self._data_buffer))
                if self._data_label and value:
                    field_values = self._current_data.setdefault("field_values", {})
                    if isinstance(field_values, dict):
                        existing = normalize_text(str(field_values.get(self._data_label) or ""))
                        field_values[self._data_label] = normalize_text(f"{existing} {value}")
                self._data_field = None
                self._data_buffer = []

            if tag not in _VOID_TAGS:
                self._data_depth -= 1
            if self._data_depth <= 0:
                self.data_records.append(self._current_data)
                self._current_data = None
                self._data_depth = 0
                self._data_field = None
                self._data_buffer = []
                self._data_label = None
            return

        if tag in {"h2", "h3"}:
            self._capture_heading = False
        elif tag == "p":
            self._capture_paragraph = False

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return
        if self._current_data is not None:
            self._current_data["raw"] = normalize_text(f"{self._current_data.get('raw', '')} {text}")
            if self._data_field in {"dt", "dd"}:
                self._data_buffer.append(text)
            return
        if self._current is None:
            return
        self._current["raw"] = normalize_text(f"{self._current.get('raw', '')} {text}")
        if self._capture_heading:
            self._current["heading"] = text
        elif self._capture_paragraph:
            paragraphs = self._current.setdefault("paragraphs", [])
            if isinstance(paragraphs, list):
                paragraphs.append(text)

    def close(self) -> None:
        super().close()
        if self._current_data is not None:
            self.data_records.append(self._current_data)
            self._current_data = None
        self._finish_current()

    def _finish_current(self) -> None:
        if self._current and self._current.get("heading"):
            self.section_records.append(self._current)
        self._current = None


def parse_dgtourcard_benefits(
    html: str,
    *,
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> list[ExternalBenefitSource]:
    parser = _DgTourCardHtmlParser()
    parser.feed(html)
    parser.close()

    if parser.data_records:
        unique_data_records: dict[str, dict[str, object]] = {}
        for raw_record in parser.data_records:
            key = str(raw_record.get("data-trvid") or raw_record.get("data-town") or "")
            if not key:
                continue
            existing = unique_data_records.get(key)
            if existing is None or (
                not existing.get("data-sttsnm") and raw_record.get("data-sttsnm")
            ) or (
                not existing.get("data-link") and raw_record.get("data-link")
            ):
                unique_data_records[key] = raw_record
        return [
            record
            for raw_record in unique_data_records.values()
            if (record := _record_from_data_attrs(raw_record, collected_page_url, fetched_at, today))
            is not None
        ]

    return [
        record
        for raw_record in parser.section_records
        if (record := _record_from_section(raw_record, collected_page_url, fetched_at, today))
        is not None
    ]


def _record_from_data_attrs(
    raw_record: dict[str, object],
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> ExternalBenefitSource | None:
    city = _city_from_data_attrs(raw_record)
    if city not in CITY_REGION:
        return None
    status_text = normalize_text(str(raw_record.get("data-sttsnm") or ""))
    field_values = raw_record.get("field_values")
    if not isinstance(field_values, dict):
        field_values = {}
    application_period = _period_from_dates(
        raw_record.get("data-evtbgndt"),
        raw_record.get("data-evtenddt"),
    )
    detailed_application_text = _field_value(field_values, "신청기간") or _field_value(
        field_values,
        "신청접수",
    )
    trip_period = _trip_period_from_text(detailed_application_text)
    local_currency = _field_value(field_values, "지역화폐")
    notes = _field_value(field_values, "특이사항")
    contact_text = _field_value(field_values, "문의전화")
    start_date, end_date = _parse_application_period(application_period)
    detail_url = _absolute_detail_url(raw_record.get("data-link"), collected_page_url)
    status = _status_from(status_text, application_period, start_date, end_date, today)
    raw_text = normalize_text(
        str(raw_record.get("raw") or " ".join(str(value or "") for value in raw_record.values()))
    )
    raw_payload = dict(raw_record)
    raw_payload.pop("raw", None)
    if detailed_application_text:
        raw_payload["applicationDetail"] = detailed_application_text
    if application_period:
        raw_payload["applicationPeriod"] = application_period
    if trip_period:
        raw_payload["tripPeriod"] = trip_period
    if local_currency:
        raw_payload["localCurrency"] = local_currency
    if notes:
        raw_payload["notes"] = notes
    if contact_text:
        raw_payload["contact"] = contact_text
    return _build_record(
        city=city,
        status_text=status_text,
        application_period=application_period,
        trip_period=trip_period,
        contact_text=contact_text,
        detail_url=detail_url,
        start_date=start_date,
        end_date=end_date,
        status=status,
        raw_text=raw_text,
        raw_payload=raw_payload,
        fetched_at=fetched_at,
    )


def _record_from_section(
    raw_record: dict[str, object],
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> ExternalBenefitSource | None:
    heading = str(raw_record.get("heading", ""))
    city, status_text = _split_heading(heading)
    if city not in CITY_REGION:
        return None
    paragraphs = [
        str(item) for item in raw_record.get("paragraphs", []) if str(item).strip()
    ]
    application_period = _value_after_label(paragraphs, "신청기간") or _value_after_label(paragraphs, "신청접수")
    trip_period = _value_after_label(paragraphs, "여행기간") or _value_after_label(
        paragraphs,
        "여행일정",
    )
    contact_text = _value_after_label(paragraphs, "문의전화")
    detail_url = _absolute_detail_url(raw_record.get("detail_url"), collected_page_url)
    start_date, end_date = _parse_application_period(application_period)
    status = _status_from(status_text, application_period, start_date, end_date, today)
    raw_payload: dict[str, object] = {
        "applicationPeriod": application_period,
        "tripPeriod": trip_period,
    }
    if detail_url:
        raw_payload["detailUrl"] = detail_url
    return _build_record(
        city=city,
        status_text=status_text,
        application_period=application_period,
        trip_period=trip_period,
        contact_text=contact_text,
        detail_url=detail_url,
        start_date=start_date,
        end_date=end_date,
        status=status,
        raw_text=str(raw_record.get("raw", "")),
        raw_payload=raw_payload,
        fetched_at=fetched_at,
    )


def _build_record(
    *,
    city: str,
    status_text: str | None,
    application_period: str | None,
    trip_period: str | None,
    contact_text: str | None,
    detail_url: str | None,
    start_date: date | None,
    end_date: date | None,
    status: str,
    raw_text: str,
    raw_payload: dict[str, object],
    fetched_at: datetime,
) -> ExternalBenefitSource:
    canonical_text = "|".join([SOURCE_CATEGORY, city, application_period or "", ""])
    return ExternalBenefitSource(
        source_name=SOURCE_NAME,
        source_type="official_campaign",
        source_url=SOURCE_URL,
        source_category=SOURCE_CATEGORY,
        external_id=stable_hash(canonical_text),
        canonical_key=stable_hash(canonical_text),
        detail_url=detail_url,
        collected_page_url=SOURCE_URL,
        title=title_with_city_prefix("대한민국 반값여행 지원", city),
        organizer_text=f"{city} 지자체",
        organizers=[f"{city} 지자체", "한국관광공사"],
        region=CITY_REGION[city],
        city=city,
        is_nationwide=False,
        status_text=status_text or application_period,
        status=status,
        start_date=start_date,
        end_date=end_date,
        benefit_text=DEFAULT_BENEFIT_TEXT,
        benefit_value_text="최대 20만원 환급",
        extracted_amount_krw=200000,
        extracted_discount_percent=50,
        benefit_value_type="mixed",
        tags=["지역할인", city, status_text or status],
        contact_text=contact_text,
        inferred_travel_styles=["체험"],
        confidence=90 if application_period or status_text else 70,
        field_completeness=90 if application_period or status_text else 70,
        raw_list_text=raw_text,
        raw_detail_text=raw_text,
        raw_payload=raw_payload,
        last_fetched_at=fetched_at,
        last_verified_at=fetched_at if status in {"active", "scheduled"} else None,
        freshness_status="fresh" if status == "active" else "unknown",
    )


def _city_from_data_attrs(raw_record: dict[str, object]) -> str:
    city = normalize_text(str(raw_record.get("data-town") or ""))
    if city:
        return city.removesuffix("시").removesuffix("군")
    district = normalize_text(str(raw_record.get("data-signgucdnm") or ""))
    if district:
        return district.removesuffix("시").removesuffix("군")
    title = normalize_text(str(raw_record.get("data-trvnm") or ""))
    for known_city in CITY_REGION:
        if known_city in title:
            return known_city
    return ""


def _clean_label(value: str) -> str:
    return normalize_text(value).rstrip(":：").strip()


def _field_value(values: dict[object, object], label: str) -> str | None:
    for key, value in values.items():
        if normalize_text(str(key)) == label:
            return normalize_text(str(value))
    return None


def _trip_period_from_text(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_text(value)
    label_match = re.search(r"(?:여행기간|여행일정)\s*[:：]?\s*(.+)", text)
    if label_match:
        candidate = label_match.group(1)
        candidate = re.split(
            r"\s+[-–]\s+|\s+[-–](?=\d|[가-힣])|●|\(",
            candidate,
            maxsplit=1,
        )[0]
        return normalize_text(candidate)
    return None


def _period_from_dates(start_value: object, end_value: object) -> str | None:
    start_text = normalize_text(str(start_value or ""))
    end_text = normalize_text(str(end_value or ""))
    if not start_text or not end_text:
        return None
    return f"{start_text}~{end_text}"


def _absolute_detail_url(value: object, collected_page_url: str) -> str | None:
    detail_url = normalize_text(str(value or ""))
    if not detail_url or detail_url.startswith(("javascript:", "#")):
        return None
    absolute_url = urljoin(collected_page_url, detail_url)
    scheme = urlparse(absolute_url).scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    return absolute_url


def _split_heading(value: str) -> tuple[str, str | None]:
    normalized = normalize_text(value)
    for status in ("신청접수중", "준비중", "예정", "마감"):
        if normalized.endswith(status):
            return normalize_text(normalized.removesuffix(status)), status
    parts = normalized.split()
    if not parts:
        return "", None
    return parts[0], " ".join(parts[1:]) or None


def _value_after_label(values: list[str], label: str) -> str | None:
    for value in values:
        if label not in value:
            continue
        if ":" in value:
            return normalize_text(value.split(":", 1)[-1])
        if "：" in value:
            return normalize_text(value.split("：", 1)[-1])
        return normalize_text(value.replace(label, "", 1))
    return None


def _parse_application_period(value: str | None) -> tuple[date | None, date | None]:
    if not value:
        return None, None
    text = normalize_text(value)
    if any(token in text for token in ("준비중", "미정")) or "월 중 예정" in text:
        return None, None
    parsed_period = _try_parse_standard_period(text)
    if parsed_period != (None, None):
        return parsed_period
    return _parse_partial_period(text, default_year=2026)


def _try_parse_standard_period(value: str) -> tuple[date | None, date | None]:
    try:
        return parse_period(value)
    except ValueError:
        return None, None


def _parse_partial_period(value: str, *, default_year: int) -> tuple[date | None, date | None]:
    korean_dates = re.findall(r"(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일?", value)
    if len(korean_dates) >= 2:
        return _date_from_korean(korean_dates[0], default_year), _date_from_korean(korean_dates[1], default_year)
    start_match = re.search(r"(?<!\d)(\d{1,2})\s*[.]\s*(\d{1,2})\s*(?=\d{1,2}시|부터|접수|오픈)", value)
    if start_match:
        return date(default_year, int(start_match.group(1)), int(start_match.group(2))), None
    dot_dates = re.findall(r"(?<!\d)(\d{1,2})\s*[.]\s*(\d{1,2})(?!\s*[.]?\d)", value)
    if len(dot_dates) >= 2:
        return date(default_year, int(dot_dates[0][0]), int(dot_dates[0][1])), date(default_year, int(dot_dates[1][0]), int(dot_dates[1][1]))
    if len(korean_dates) == 1:
        return _date_from_korean(korean_dates[0], default_year), None
    if len(dot_dates) == 1:
        return date(default_year, int(dot_dates[0][0]), int(dot_dates[0][1])), None
    return None, None


def _date_from_korean(parts: tuple[str, str, str], default_year: int) -> date:
    return date(int(parts[0] or default_year), int(parts[1]), int(parts[2]))


def _status_from(
    status_text: str | None,
    application_period: str | None,
    start_date: date | None,
    end_date: date | None,
    today: date,
) -> str:
    text = " ".join(part for part in [status_text, application_period] if part)
    if "마감" in text:
        return "ended"
    if "신청접수중" in text:
        return "active"
    if "준비중" in text or "예정" in text:
        return "scheduled"
    if start_date and today < start_date:
        return "scheduled"
    if start_date and end_date and today > end_date:
        return "ended"
    if start_date and (end_date is None or today <= end_date):
        return "active"
    return "unknown"
