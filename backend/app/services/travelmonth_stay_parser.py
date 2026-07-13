from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.schemas.external_sources import ExternalBenefitSource
from app.services.travelmonth_normalizer import (
    calculate_field_completeness,
    extract_benefit_value,
    infer_travel_styles,
    normalize_text,
    stable_hash,
)


SOURCE_NAME = "대한민국 숙박세일 페스타"
SOURCE_URL = "https://ktostay.visitkorea.or.kr/"
SOURCE_CATEGORY = "stay_discount"
DEFAULT_TITLE = "2026 대한민국 숙박세일 페스타 숙박 할인"


class _StayHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._field_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs if key}
        class_names = set((attr_map.get("class") or "").split())
        if tag in {"section", "article", "div"} and (
            "data-stay-discount" in attr_map
            or "data-stay-item" in attr_map
            or class_names.intersection({"stay-discount", "stay-benefit", "benefit-stay"})
        ):
            self._finish_current()
            self._current = {"raw": "", "tags": []}
            return

        if self._current is None:
            return
        if tag in {"h2", "h3", "strong"}:
            self._field_stack.append("title")
        elif tag in {"p", "li", "dd"}:
            self._field_stack.append("text")
        elif tag == "a" and attr_map.get("href") and not self._current.get("detail_url"):
            self._current["detail_url"] = attr_map["href"]

    def handle_endtag(self, tag: str) -> None:
        if self._field_stack and tag in {"h2", "h3", "strong", "p", "li", "dd"}:
            self._field_stack.pop()
        if tag in {"section", "article", "div"} and self._current is not None:
            self._finish_current()

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return
        if self._current is None:
            return
        self._current["raw"] = normalize_text(f"{self._current.get('raw', '')} {text}")
        if not self._field_stack:
            return
        if self._field_stack[-1] == "title" and not self._current.get("title"):
            self._current["title"] = text

    def close(self) -> None:
        super().close()
        self._finish_current()

    def _finish_current(self) -> None:
        if self._current and normalize_text(str(self._current.get("raw", ""))):
            self.records.append(self._current)
        self._current = None
        self._field_stack.clear()


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if text:
            self.parts.append(text)


class _KtostayPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.raw_parts: list[str] = []
        self.population_groups: list[dict[str, object]] = []
        self.issue_period: str | None = None
        self.stay_period: str | None = None
        self.usage_area: str | None = None
        self.usage_place: str | None = None
        self.usage_method: str | None = None
        self.discount_tiers: list[str] = []
        self._current_label: str | None = None
        self._current_parts: list[str] = []
        self._in_population_group = False
        self._population_current_sido: str | None = None
        self._population_city_parts: list[str] = []
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        attr_map = {key: value for key, value in attrs if key}
        class_names = set((attr_map.get("class") or "").split())
        if "population-group" in class_names:
            self._in_population_group = True
            self._population_current_sido = None
            self._population_city_parts = []
        if class_names.intersection({"txt-title", "schedule-title"}):
            self._finish_label_section()
            self._current_label = ""
            self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._in_population_group:
            self._finish_population_group()
            self._in_population_group = False
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return
        self.raw_parts.append(text)
        if self._in_population_group:
            if self._tag_stack and self._tag_stack[-1] == "strong":
                self._finish_population_group()
                self._population_current_sido = text
                self._population_city_parts = []
            elif self._population_current_sido:
                self._population_city_parts.append(text)
        if self._current_label is not None:
            if self._current_label == "":
                self._current_label = text
            else:
                self._current_parts.append(text)
        elif self._looks_like_label(text):
            self._finish_label_section()
            self._current_label = text
            self._current_parts = []

    def close(self) -> None:
        super().close()
        self._finish_population_group()
        self._finish_label_section()

    def _finish_population_group(self) -> None:
        if not self._population_current_sido:
            return
        city_text = normalize_text(" ".join(self._population_city_parts)).replace("&nbsp;", " ")
        city_text = re.sub(r"\s+", " ", city_text)
        cities = [city.strip() for city in re.split(r"[,，]", city_text) if city.strip()]
        cities = [re.sub(r"\s+", " ", city).strip() for city in cities]
        if cities:
            self.population_groups.append({"sido": self._population_current_sido, "cities": cities})
        self._population_current_sido = None
        self._population_city_parts = []

    def _finish_label_section(self) -> None:
        label = normalize_text(self._current_label or "")
        if not label:
            self._current_label = None
            self._current_parts = []
            return
        value = normalize_text(" ".join(self._current_parts))
        if not value:
            self._current_label = None
            self._current_parts = []
            return
        compact_label = label.replace(" ", "")
        if "발급기간" in compact_label and not self.issue_period:
            self.issue_period = value
        elif "입실기간" in compact_label and not self.stay_period:
            self.stay_period = value
        elif "사용지역" in compact_label and not self.usage_area:
            self.usage_area = _trim_after(value, ("2026 여름맞이", "바른 여행문화"))
        elif "사용처" in compact_label and not self.usage_place:
            self.usage_place = value
        elif "사용방법" in compact_label and not self.usage_method:
            self.usage_method = value
        elif "할인혜택" in compact_label and not self.discount_tiers:
            self.discount_tiers = _discount_tiers_from_text(value)
        self._current_label = None
        self._current_parts = []

    @staticmethod
    def _looks_like_label(text: str) -> bool:
        compact = text.replace(" ", "")
        return compact in {"발급기간", "입실기간", "사용지역", "사용처", "사용방법", "할인혜택"}


def parse_stay_discount_benefits(
    html: str,
    *,
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> list[ExternalBenefitSource]:
    ktostay_record = _ktostay_page_record(html)
    if ktostay_record is not None:
        return [_build_record(ktostay_record, collected_page_url, fetched_at, today)]

    parser = _StayHtmlParser()
    parser.feed(html)
    parser.close()
    records = parser.records or [_page_text_record(html)]
    return [
        _build_record(raw_record, collected_page_url, fetched_at, today)
        for raw_record in records
        if _looks_like_stay_discount(str(raw_record.get("raw", "")))
    ]


def _ktostay_page_record(html: str) -> dict[str, object] | None:
    if "population-group" not in html or "숙박세일 페스타" not in html:
        return None
    parser = _KtostayPageParser()
    parser.feed(html)
    parser.close()
    area_count = sum(len(group.get("cities", [])) for group in parser.population_groups)
    raw_text = normalize_text(" ".join(parser.raw_parts))
    if area_count == 0 or not _looks_like_stay_discount(raw_text):
        return None
    discount_tiers = parser.discount_tiers or _discount_tiers_from_text(raw_text)
    return {
        "raw": raw_text,
        "title": DEFAULT_TITLE,
        "detail_url": SOURCE_URL,
        "issue_period": parser.issue_period,
        "stay_period": parser.stay_period,
        "usage_area": parser.usage_area,
        "usage_place": parser.usage_place,
        "usage_method": parser.usage_method,
        "discount_tiers": discount_tiers,
        "eligible_areas": parser.population_groups,
        "eligible_area_count": area_count,
    }


def _page_text_record(html: str) -> dict[str, object]:
    collector = _TextCollector()
    collector.feed(html)
    return {"raw": normalize_text(" ".join(collector.parts)), "title": DEFAULT_TITLE}


def _looks_like_stay_discount(text: str) -> bool:
    normalized = normalize_text(text)
    return any(token in normalized for token in ("숙박세일", "숙박 할인", "숙박할인", "입실기간", "쿠폰"))


def _build_record(
    raw_record: dict[str, object],
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> ExternalBenefitSource:
    raw_text = normalize_text(str(raw_record.get("raw", "")))
    title = normalize_text(str(raw_record.get("title") or "")) or DEFAULT_TITLE
    issue_period_text = normalize_text(str(raw_record.get("issue_period") or "")) or _label_value(raw_text, ("쿠폰 발급기간", "발급기간", "쿠폰기간", "쿠폰 발급"))
    stay_period_text = normalize_text(str(raw_record.get("stay_period") or "")) or _label_value(raw_text, ("입실기간", "숙박기간", "투숙기간", "사용기간"))
    selected_period_text = stay_period_text or issue_period_text or raw_text
    start_date, end_date = _parse_korean_period(selected_period_text, default_year=today.year)
    issue_start, issue_end = _parse_korean_period(issue_period_text or "", default_year=today.year)
    discount_tiers = _string_list(raw_record.get("discount_tiers"))
    benefit_text = _benefit_text(raw_text, discount_tiers=discount_tiers)
    benefit_value = extract_benefit_value(_expanded_amount_text(benefit_text), title=title)
    discount_amount_krw = _max_discount_amount_krw(discount_tiers)
    status_text = "진행중" if raw_record.get("eligible_areas") else _status_text(raw_text)
    status = _status_from(status_text, start_date, end_date, today)
    detail_url = _absolute_url(raw_record.get("detail_url"), collected_page_url)
    is_nationwide = not any(token in raw_text for token in ("비수도권", "인구감소", "지역특별"))
    region = "전국" if is_nationwide else "비수도권·인구감소지역"
    tags = _unique(["숙박", "숙박세일", "여행가는 달", *_conditional_tags(raw_text)])
    canonical_text = "|".join([SOURCE_CATEGORY, title, issue_period_text or "", stay_period_text or benefit_text])
    eligible_areas = _eligible_areas(raw_record.get("eligible_areas"))
    raw_payload: dict[str, object] = {
        "issuePeriod": issue_period_text,
        "stayPeriod": stay_period_text,
        "issueStartDate": issue_start.isoformat() if issue_start else None,
        "issueEndDate": issue_end.isoformat() if issue_end else None,
        "usageArea": normalize_text(str(raw_record.get("usage_area") or "")) or None,
        "usagePlace": normalize_text(str(raw_record.get("usage_place") or "")) or None,
        "usageMethod": normalize_text(str(raw_record.get("usage_method") or "")) or None,
        "discountTiers": discount_tiers,
        "eligibleAreas": eligible_areas,
        "eligibleAreaCount": sum(len(group["cities"]) for group in eligible_areas),
        "earlyCloseWarning": any(token in raw_text for token in ("예산 소진", "조기 종료", "조기종료", "소진 시")),
    }
    contact_text = _truncate_text(_contact_text(raw_payload), 200)
    return ExternalBenefitSource(
        source_name=SOURCE_NAME,
        source_type="official_campaign",
        source_url=SOURCE_URL,
        source_category=SOURCE_CATEGORY,
        external_id=stable_hash(canonical_text),
        canonical_key=stable_hash(canonical_text),
        detail_url=detail_url,
        collected_page_url=collected_page_url,
        title=title if "숙박" in title else f"{title} 숙박 할인",
        organizer_text="문화체육관광부, 한국관광공사",
        organizers=["문화체육관광부", "한국관광공사"],
        region=region,
        city=None,
        is_nationwide=is_nationwide,
        status_text=status_text or "상태 확인 필요",
        status=status,
        start_date=start_date,
        end_date=end_date,
        benefit_text=_truncate_text(benefit_text, 200),
        benefit_value_text=_benefit_value_text(raw_text, benefit_value.value_text, discount_tiers=discount_tiers),
        extracted_amount_krw=discount_amount_krw or benefit_value.amount_krw,
        extracted_discount_percent=benefit_value.discount_percent,
        benefit_value_type=benefit_value.value_type,
        tags=tags,
        contact_text=contact_text,
        inferred_travel_styles=infer_travel_styles(title=title, benefit_text=benefit_text, tags=tags),
        confidence=90 if start_date and end_date and benefit_value.value_text else 75,
        field_completeness=calculate_field_completeness(
            {
                "title": title,
                "period": selected_period_text,
                "benefit": benefit_text,
                "amount": benefit_value.value_text,
                "raw": raw_text,
            }
        ),
        raw_list_text=raw_text,
        raw_detail_text=raw_text,
        raw_payload=raw_payload,
        last_fetched_at=fetched_at,
        last_verified_at=fetched_at if status == "active" else None,
        freshness_status="fresh" if status == "active" else "unknown",
    )


def _label_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]?\s*([^|]+?)(?=(?:쿠폰 발급기간|발급기간|입실기간|숙박기간|투숙기간|사용기간|할인혜택|혜택|지원내용)\s*[:：]|$)"
        match = re.search(pattern, text)
        if match:
            value = normalize_text(match.group(1))
            if value:
                return value
    return None


def _truncate_text(value: str | None, max_length: int) -> str | None:
    if value is None or len(value) <= max_length:
        return value
    return f"{value[: max_length - 1].rstrip()}…"


def _benefit_text(text: str, *, discount_tiers: list[str] | None = None) -> str:
    if discount_tiers:
        return " / ".join(discount_tiers)
    labeled = _label_value(text, ("할인혜택", "혜택", "지원내용", "할인금액"))
    if labeled:
        return labeled
    amount_tokens = re.findall(r"\d+(?:/\d+)*\s*만원|\d+\s*만\s*원|\d{1,3}%", text)
    if amount_tokens:
        return f"숙박 할인권 {'/'.join(amount_tokens)} 지원"
    return "숙박 할인권 지원"


def _benefit_value_text(text: str, fallback: str | None, *, discount_tiers: list[str] | None = None) -> str | None:
    if discount_tiers and _max_discount_amount_krw(discount_tiers):
        return "2/3/5/7만원 할인권"
    slash_match = re.search(r"((?:\d+/)+\d+)\s*만원", text)
    if slash_match:
        return f"{slash_match.group(1)}만원 할인권"
    amount_matches = re.findall(r"\d+\s*만\s*원|\d+만원", text)
    if amount_matches:
        return "/".join(token.replace(" ", "") for token in _unique(amount_matches)) + " 할인권"
    return fallback


def _expanded_amount_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return " ".join(f"{part}만원" for part in match.group(1).split("/"))

    return re.sub(r"((?:\d+/)+\d+)\s*만원", replace, text)


def _conditional_tags(text: str) -> list[str]:
    tags: list[str] = []
    if "인구감소" in text:
        tags.append("인구감소지역")
    if "비수도권" in text:
        tags.append("비수도권")
    if "조기" in text or "예산 소진" in text:
        tags.append("예산소진주의")
    return tags


def _status_text(text: str) -> str | None:
    for token in ("진행중", "진행 중", "마감", "종료", "예정", "준비중"):
        if token == "종료" and any(phrase in text for phrase in ("조기 종료", "조기종료", "자동 종료", "자동종료", "소진 시")):
            continue
        if token in text:
            return token
    return None


def _status_from(status_text: str | None, start_date: date | None, end_date: date | None, today: date) -> str:
    if status_text and any(token in status_text for token in ("마감", "종료")):
        return "ended"
    if status_text and any(token in status_text for token in ("예정", "준비")):
        return "scheduled"
    if start_date and today < start_date:
        return "scheduled"
    if end_date and today > end_date:
        return "ended"
    if start_date or end_date or (status_text and "진행" in status_text):
        return "active"
    return "unknown"


def _parse_korean_period(value: str, *, default_year: int) -> tuple[date | None, date | None]:
    normalized = normalize_text(value)
    if not normalized:
        return None, None
    full_dates = re.findall(r"(20\d{2})[-.]\s*(\d{1,2})[-.]\s*(\d{1,2})", normalized)
    if len(full_dates) >= 2:
        return _date_from_parts(full_dates[0]), _date_from_parts(full_dates[1])
    korean_dates = re.findall(r"(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일?", normalized)
    if len(korean_dates) >= 2:
        return _date_from_parts(_with_year(korean_dates[0], default_year)), _date_from_parts(_with_year(korean_dates[1], default_year))
    dot_dates = re.findall(r"(?<!\d)(\d{1,2})\s*[.]\s*(\d{1,2})(?!\d)", normalized)
    if len(dot_dates) >= 2:
        return date(default_year, int(dot_dates[0][0]), int(dot_dates[0][1])), date(default_year, int(dot_dates[1][0]), int(dot_dates[1][1]))
    if len(korean_dates) == 1:
        single = _date_from_parts(_with_year(korean_dates[0], default_year))
        return single, None
    if len(dot_dates) == 1:
        return date(default_year, int(dot_dates[0][0]), int(dot_dates[0][1])), None
    return None, None


def _with_year(parts: tuple[str, str, str], default_year: int) -> tuple[str, str, str]:
    return (parts[0] or str(default_year), parts[1], parts[2])


def _date_from_parts(parts: tuple[str, str, str]) -> date:
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _absolute_url(value: object, collected_page_url: str) -> str | None:
    raw_url = normalize_text(str(value or ""))
    if not raw_url or raw_url.startswith(("javascript:", "#")):
        return None
    absolute = urljoin(collected_page_url, raw_url)
    if urlparse(absolute).scheme.lower() not in {"http", "https"}:
        return None
    return absolute


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = normalize_text(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _discount_tiers_from_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    tiers: list[str] = []
    patterns = (
        r"7만원\s*미만[^0-9]+2만원\s*할인[^/]*?1박\s*이상",
        r"7만원\s*이상[^0-9]+3만원\s*할인[^/]*?1박\s*이상",
        r"14만원\s*미만[^0-9]+5만원\s*할인[^/]*?연박\s*이상",
        r"14만원\s*이상[^0-9]+7만원\s*할인[^/]*?연박\s*이상",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            tiers.append(match.group(0))
    if tiers:
        return tiers
    if all(token in normalized for token in ("2만원", "3만원", "5만원", "7만원")):
        return [
            "7만원 미만 국내 숙박상품 예약 시 2만원 할인(1박 이상)",
            "7만원 이상 국내 숙박상품 예약 시 3만원 할인(1박 이상)",
            "14만원 미만 국내 숙박상품 예약 시 5만원 할인(연박 이상)",
            "14만원 이상 국내 숙박상품 예약 시 7만원 할인(연박 이상)",
        ]
    return []


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(str(item)) for item in value if normalize_text(str(item))]


def _eligible_areas(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    groups: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sido = normalize_text(str(item.get("sido") or ""))
        raw_cities = item.get("cities")
        if not sido or not isinstance(raw_cities, list):
            continue
        cities = [normalize_text(str(city)) for city in raw_cities if normalize_text(str(city))]
        if cities:
            groups.append({"sido": sido, "cities": cities})
    return groups


def _contact_text(raw_payload: dict[str, object]) -> str | None:
    parts = []
    discount_tiers = raw_payload.get("discountTiers")
    if isinstance(discount_tiers, list) and discount_tiers:
        parts.append("할인혜택: " + " / ".join(str(item) for item in discount_tiers))
    for key, label in (
        ("issuePeriod", "발급기간"),
        ("stayPeriod", "입실기간"),
        ("usageArea", "사용지역"),
        ("usagePlace", "사용처"),
        ("usageMethod", "사용방법"),
    ):
        value = raw_payload.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts) if parts else None


def _max_discount_amount_krw(discount_tiers: list[str] | None) -> int | None:
    if not discount_tiers:
        return None
    discounts = [int(value) * 10_000 for value in re.findall(r"(\d+)만원\s*할인", " ".join(discount_tiers))]
    return max(discounts) if discounts else None


def _trim_after(value: str, markers: tuple[str, ...]) -> str:
    trimmed = value
    for marker in markers:
        if marker in trimmed:
            trimmed = trimmed.split(marker, 1)[0]
    return normalize_text(trimmed)
