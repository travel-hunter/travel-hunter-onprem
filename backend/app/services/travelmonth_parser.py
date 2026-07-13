from __future__ import annotations

from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

from app.schemas.external_sources import TravelMonthRegionalBenefitSource
from app.services.travelmonth_normalizer import (
    calculate_field_completeness,
    extract_benefit_value,
    infer_travel_styles,
    normalize_region,
    normalize_status,
    normalize_text,
    parse_period,
    stable_hash,
)


_VACATION_BENEFIT_AREAS: tuple[tuple[str, str, str], ...] = (
    ("강원특별자치도", "영월군", "영월"),
    ("강원특별자치도", "횡성군", "횡성"),
    ("강원특별자치도", "평창군", "평창"),
    ("경상남도", "밀양시", "밀양"),
    ("경상남도", "하동군", "하동"),
    ("경상남도", "거창군", "거창"),
    ("경상남도", "합천군", "합천"),
    ("경상남도", "남해군", "남해"),
    ("충청북도", "제천시", "제천"),
    ("전라남도", "강진군", "강진"),
    ("전라남도", "영광군", "영광"),
    ("전라남도", "해남군", "해남"),
    ("전라남도", "영암군", "영암"),
    ("전라남도", "고흥군", "고흥"),
    ("전라남도", "완도군", "완도"),
    ("전북특별자치도", "고창군", "고창"),
)


class _PageSummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = {key: value for key, value in attrs}
        href = normalize_text(attr_map.get("href"))
        if href:
            self.links.append(href)

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if text:
            self.text_parts.append(text)

    @property
    def text(self) -> str:
        return normalize_text(" ".join(self.text_parts))


_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _BenefitHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._field_stack: list[str] = []
        self._tag_items: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        if tag == "section" and "data-benefit-item" in attr_map:
            self._current = {"raw": "", "tags": []}
            self._field_stack.clear()
            self._tag_items = []
            return

        if self._current is None:
            return

        class_names = set((attr_map.get("class") or "").split())
        if tag == "h3":
            self._field_stack.append("title")
        elif tag == "p" and class_names.intersection({"organizer", "period", "status", "contact"}):
            self._field_stack.append(next(iter(class_names.intersection({"organizer", "period", "status", "contact"}))))
        elif tag == "div" and "benefit" in class_names:
            self._field_stack.append("benefit")
        elif tag == "li":
            self._field_stack.append("tag")
        elif tag == "a" and "detail" in class_names:
            self._current["detail_url"] = attr_map.get("href")

    def handle_endtag(self, tag: str) -> None:
        if self._current is not None and tag == "section":
            self._current["tags"] = list(self._tag_items)
            self.records.append(self._current)
            self._current = None
            self._field_stack.clear()
            self._tag_items = []
            return

        if self._field_stack and tag in {"h3", "p", "div", "li"}:
            self._field_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return

        text = normalize_text(data)
        if not text:
            return

        self._current["raw"] = normalize_text(f"{self._current.get('raw', '')} {text}")
        if not self._field_stack:
            return

        field = self._field_stack[-1]
        if field == "tag":
            self._tag_items.append(text.lstrip("#"))
            return

        self._current[field] = normalize_text(f"{self._current.get(field, '')} {text}")


class _LiveBenefitHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, object]] = []
        self.modals: dict[str, dict[str, object]] = {}
        self._anchor: dict[str, object] | None = None
        self._anchor_depth = 0
        self._anchor_p_depth = 0
        self._anchor_p_text = ""
        self._anchor_p_texts: list[str] = []
        self._modal: dict[str, object] | None = None
        self._modal_depth = 0
        self._modal_header_depth = 0
        self._modal_field_stack: list[str] = []
        self._modal_field_text = ""
        self._modal_current_label: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        class_names = set((attr_map.get("class") or "").split())

        if tag == "a" and attr_map.get("data-log-type") == "benefit" and attr_map.get("data-log-seq"):
            href = attr_map.get("href") or ""
            self._anchor = {
                "external_id": attr_map["data-log-seq"],
                "detail_anchor": href[1:] if href.startswith("#") else href,
                "title": attr_map.get("data-action-track-title") or "",
                "benefit": attr_map.get("data-action-track-recommend") or "",
                "raw": "",
                "tags": [],
            }
            self._anchor_depth = 1
            self._anchor_p_depth = 0
            self._anchor_p_texts = []
            return

        modal_id = attr_map.get("id") or ""
        if tag == "div" and modal_id.startswith("modal-benefit-") and "modal-benefit" in class_names:
            self._modal = {
                "external_id": modal_id.removeprefix("modal-benefit-"),
                "modal_id": modal_id,
                "raw": "",
                "tags": [],
            }
            self._modal_depth = 1
            self._modal_header_depth = 0
            self._modal_current_label = None
            self._modal_field_stack.clear()
            return

        if self._anchor is not None:
            if tag not in _VOID_TAGS:
                self._anchor_depth += 1
            if tag == "p":
                self._anchor_p_depth = 1
                self._anchor_p_text = ""
            elif self._anchor_p_depth and tag not in _VOID_TAGS:
                self._anchor_p_depth += 1

        if self._modal is None:
            return

        if tag not in _VOID_TAGS:
            self._modal_depth += 1
        if tag == "header":
            self._modal_header_depth = 1
        elif self._modal_header_depth and tag not in _VOID_TAGS:
            self._modal_header_depth += 1

        if tag == "h3":
            self._push_modal_field("title")
        elif tag == "p" and self._modal_header_depth:
            self._push_modal_field("organizer")
        elif tag == "li" and self._modal_header_depth:
            self._push_modal_field("tag")
        elif tag == "dt":
            self._push_modal_field("dt")
        elif tag == "dd":
            self._push_modal_field("dd")
        elif tag == "a" and attr_map.get("href") and not self._modal.get("detail_url"):
            self._modal["detail_url"] = attr_map["href"]

    def handle_endtag(self, tag: str) -> None:
        if self._anchor is not None:
            if tag == "p" and self._anchor_p_depth:
                text = normalize_text(self._anchor_p_text)
                if text:
                    self._anchor_p_texts.append(text)
                self._anchor_p_depth = 0
                self._anchor_p_text = ""
            elif self._anchor_p_depth and tag not in _VOID_TAGS:
                self._anchor_p_depth -= 1

            if tag not in _VOID_TAGS:
                self._anchor_depth -= 1
            if self._anchor_depth == 0:
                self._finalize_anchor()

        if self._modal is None:
            return

        if self._modal_field_stack and tag in {"h3", "p", "li", "dt", "dd"}:
            self._finalize_modal_field()

        if self._modal_header_depth and tag not in _VOID_TAGS:
            self._modal_header_depth -= 1

        if tag not in _VOID_TAGS:
            self._modal_depth -= 1
        if self._modal_depth == 0:
            modal_id = str(self._modal.get("modal_id", ""))
            if modal_id:
                self.modals[modal_id] = self._modal
            self._modal = None

    def handle_data(self, data: str) -> None:
        text = normalize_text(data)
        if not text:
            return

        if self._anchor is not None:
            self._anchor["raw"] = normalize_text(f"{self._anchor.get('raw', '')} {text}")
            if self._anchor_p_depth:
                self._anchor_p_text = normalize_text(f"{self._anchor_p_text} {text}")

        if self._modal is not None:
            self._modal["raw"] = normalize_text(f"{self._modal.get('raw', '')} {text}")
            if self._modal_field_stack:
                self._modal_field_text = normalize_text(f"{self._modal_field_text} {text}")

    def _push_modal_field(self, field: str) -> None:
        self._modal_field_stack.append(field)
        self._modal_field_text = ""

    def _finalize_modal_field(self) -> None:
        if self._modal is None:
            return
        field = self._modal_field_stack.pop()
        text = normalize_text(self._modal_field_text)
        self._modal_field_text = ""
        if not text:
            return
        if field == "tag":
            tags = self._modal.setdefault("tags", [])
            if isinstance(tags, list):
                tags.append(text.lstrip("#"))
            return
        if field == "dt":
            self._modal_current_label = text
            return
        if field == "dd":
            if self._modal_current_label == "기간":
                self._modal["period"] = text
            elif self._modal_current_label == "할인혜택":
                self._modal["benefit"] = text
            elif self._modal_current_label == "문의처":
                self._modal["contact"] = text
            self._modal_current_label = None
            return
        self._modal[field] = text

    def _finalize_anchor(self) -> None:
        if self._anchor is None:
            return
        p_texts = self._anchor_p_texts
        if len(p_texts) >= 2 and not self._anchor.get("title"):
            self._anchor["title"] = p_texts[1]
        if len(p_texts) >= 3:
            self._anchor["period"] = p_texts[2]
            self._anchor["status"] = _extract_bracket_status(p_texts[2])
        if len(p_texts) >= 4:
            self._anchor["organizer"] = p_texts[3]
        self.records.append(self._anchor)
        self._anchor = None
        self._anchor_depth = 0
        self._anchor_p_texts = []


def parse_regional_benefits(
    html: str,
    *,
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> list[TravelMonthRegionalBenefitSource]:
    parser = _BenefitHtmlParser()
    parser.feed(html)
    live_parser = _LiveBenefitHtmlParser()
    live_parser.feed(html)

    records: list[TravelMonthRegionalBenefitSource] = []
    for raw_record in [*parser.records, *_merge_live_records(live_parser)]:
        title = str(raw_record.get("title", ""))
        organizer_text = str(raw_record.get("organizer", ""))
        period_text = str(raw_record.get("period", ""))
        status_text = str(raw_record.get("status", "")) or None
        benefit_text = str(raw_record.get("benefit", ""))
        contact_text = str(raw_record.get("contact", "")) or None
        detail_url = str(raw_record.get("detail_url", "")) or None
        tags = [str(tag) for tag in raw_record.get("tags", [])]
        raw_text = str(raw_record.get("raw", ""))

        try:
            start_date, end_date = parse_period(period_text)
        except ValueError:
            continue

        if not _has_required_fields(
            title=title,
            organizer_text=organizer_text,
            benefit_text=benefit_text,
            collected_page_url=collected_page_url,
        ):
            continue

        status = normalize_status(status_text, start_date, end_date, today)
        region = normalize_region(organizer_text, title=title, benefit_text=benefit_text)
        benefit_value = extract_benefit_value(benefit_text, title=title)
        canonical_text = "|".join([title, organizer_text, period_text])
        external_id = str(raw_record.get("external_id", "")) or stable_hash(canonical_text)
        canonical_key = str(raw_record.get("canonical_key", "")) or stable_hash(canonical_text)
        confidence = _calculate_confidence(
            {
                "title": title,
                "organizer_text": organizer_text,
                "period_text": period_text,
                "status": status,
                "benefit_text": benefit_text,
                "detail_url": detail_url,
            }
        )

        records.append(
            TravelMonthRegionalBenefitSource(
                external_id=external_id,
                canonical_key=canonical_key,
                detail_url=detail_url,
                collected_page_url=collected_page_url,
                title=title,
                organizer_text=organizer_text,
                organizers=[part.strip() for part in organizer_text.split(",") if part.strip()],
                region=region.region,
                city=region.city,
                is_nationwide=region.is_nationwide,
                status_text=status_text,
                status=status,
                start_date=start_date,
                end_date=end_date,
                benefit_text=benefit_text,
                benefit_value_text=benefit_value.value_text,
                extracted_amount_krw=benefit_value.amount_krw,
                extracted_discount_percent=benefit_value.discount_percent,
                benefit_value_type=benefit_value.value_type,
                tags=tags,
                contact_text=contact_text,
                inferred_travel_styles=infer_travel_styles(title=title, benefit_text=benefit_text, tags=tags),
                confidence=confidence,
                field_completeness=calculate_field_completeness(
                    {
                        "title": title,
                        "organizer_text": organizer_text,
                        "period_text": period_text,
                        "status": status,
                        "benefit_text": benefit_text,
                        "detail_url": detail_url,
                        "contact_text": contact_text,
                    }
                ),
                raw_list_text=raw_text,
                raw_detail_text=raw_text,
                raw_payload={"periodText": period_text},
                last_fetched_at=fetched_at,
                last_verified_at=fetched_at if confidence >= 85 else None,
                freshness_status=_freshness_status(status),
            )
        )

    if not records:
        records.extend(
            _parse_vacation_benefit_summary(
                html,
                collected_page_url=collected_page_url,
                fetched_at=fetched_at,
                today=today,
            )
        )

    return records


def _parse_vacation_benefit_summary(
    html: str,
    *,
    collected_page_url: str,
    fetched_at: datetime,
    today: date,
) -> list[TravelMonthRegionalBenefitSource]:
    parser = _PageSummaryParser()
    parser.feed(html)
    page_text = parser.text
    if not ("지역사랑 휴가지원" in page_text and "50% 환급" in page_text):
        return []

    period_text = f"{fetched_at.year}-04-01 ~ {fetched_at.year}-08-31" if "4~8월" in page_text else ""
    try:
        start_date, end_date = parse_period(period_text)
    except ValueError:
        start_date, end_date = None, None
    status = normalize_status(None, start_date, end_date, today)
    detail_url = _find_vacation_benefit_detail_url(parser.links, collected_page_url)
    contact_text = "반값여행 운영사무국 02-6271-2016" if "02-6271-2016" in page_text else None
    benefit_text = (
        "농어촌 인구감소지역 방문 후 소비 인증 시 여행경비 50%를 모바일 지역화폐로 환급합니다. "
        "1인 10만원, 2인 이상 20만원, 청년 20% 가산, 가족 최대 50만원 한도가 적용됩니다."
    )
    benefit_value = extract_benefit_value(benefit_text, title="여행가는 달 지역사랑 휴가지원")
    records: list[TravelMonthRegionalBenefitSource] = []

    for province, city, city_keyword in _VACATION_BENEFIT_AREAS:
        if city_keyword not in page_text:
            continue
        title = f"여행가는 달 지역사랑 휴가지원 - {city_keyword}"
        organizer_text = f"{province}, {city}"
        region = normalize_region(organizer_text, title=title, benefit_text=benefit_text)
        tags = ["지역사랑", "반값여행", "인구감소지역", city_keyword]
        raw_text = normalize_text(
            f"여행가는 달 지역사랑 휴가지원 {organizer_text} {period_text} {benefit_text} {contact_text or ''}"
        )
        canonical_text = "|".join([title, organizer_text, period_text, collected_page_url])
        records.append(
            TravelMonthRegionalBenefitSource(
                external_id=f"vacation-benefit-{stable_hash(organizer_text)[:12]}",
                canonical_key=stable_hash(canonical_text),
                detail_url=detail_url,
                collected_page_url=collected_page_url,
                title=title,
                organizer_text=organizer_text,
                organizers=[province, city],
                region=region.region,
                city=region.city,
                is_nationwide=region.is_nationwide,
                status_text=None,
                status=status,
                start_date=start_date,
                end_date=end_date,
                benefit_text=benefit_text,
                benefit_value_text=benefit_value.value_text,
                extracted_amount_krw=benefit_value.amount_krw,
                extracted_discount_percent=benefit_value.discount_percent,
                benefit_value_type=benefit_value.value_type,
                tags=tags,
                contact_text=contact_text,
                inferred_travel_styles=infer_travel_styles(title=title, benefit_text=benefit_text, tags=tags),
                confidence=90,
                field_completeness=calculate_field_completeness(
                    {
                        "title": title,
                        "organizer_text": organizer_text,
                        "period_text": period_text,
                        "status": status,
                        "benefit_text": benefit_text,
                        "detail_url": detail_url,
                        "contact_text": contact_text,
                    }
                ),
                raw_list_text=raw_text,
                raw_detail_text=page_text,
                raw_payload={"periodText": period_text, "fallback": "vacation-benefit-summary"},
                last_fetched_at=fetched_at,
                last_verified_at=fetched_at,
                freshness_status=_freshness_status(status),
            )
        )

    return records


def _find_vacation_benefit_detail_url(links: list[str], collected_page_url: str) -> str | None:
    for link in links:
        if "dgtourcard/tour50.do" in link:
            return urljoin(collected_page_url, link)
    return collected_page_url


def _merge_live_records(parser: _LiveBenefitHtmlParser) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for record in parser.records:
        detail_anchor = str(record.get("detail_anchor", ""))
        modal = parser.modals.get(detail_anchor, {})
        merged = dict(record)
        for field in ("title", "organizer", "period", "benefit", "contact", "detail_url"):
            if modal.get(field):
                merged[field] = modal[field]
        if modal.get("tags"):
            merged["tags"] = modal["tags"]
        if modal.get("raw"):
            merged["raw"] = normalize_text(f"{record.get('raw', '')} {modal.get('raw', '')}")
            merged["raw_detail_text"] = modal["raw"]
        records.append(merged)
    return records


def _extract_bracket_status(value: str) -> str | None:
    start = value.find("[")
    end = value.find("]", start + 1)
    if start == -1 or end == -1:
        return None
    return value[start : end + 1]


def _has_required_fields(
    *,
    title: str,
    organizer_text: str,
    benefit_text: str,
    collected_page_url: str,
) -> bool:
    return all(
        [
            normalize_text(title),
            normalize_text(organizer_text),
            normalize_text(benefit_text),
            normalize_text(collected_page_url),
        ]
    )


def _calculate_confidence(values: dict[str, object | None]) -> int:
    completeness = calculate_field_completeness(values)
    return 90 if completeness >= 85 else 70


def _freshness_status(status: str) -> str:
    if status == "active":
        return "fresh"
    if status == "ended":
        return "expired"
    return "unknown"
