from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser

from app.schemas.external_sources import ExternalBenefitSource
from app.services.policy_card_quality import evaluate_card_copy
from app.services.policy_periods import period_payload
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

# 페이지가 제목 앞에 붙였다 뗐다 하는 캠페인 문구. 정책의 정체는 그 뒤의 핵심 명칭이다.
_CAMPAIGN_PREFIXES = (
    "대한민국 구석구석",
    "비행기타고 떠나는",
    "지구를 지키는 친환경여행",
    "’네이버 항공권‘에서 국내선 이용 시",
    "'네이버 항공권'에서 국내선 이용 시",
)
_QUOTE_CHARS = "’‘'\"“”"


def core_traffic_title(title: str) -> str:
    """캠페인 접두·따옴표를 뗀 핵심 명칭. canonical_key 의 재료다."""
    text = normalize_text(title)
    changed = True
    while changed:
        changed = False
        for prefix in _CAMPAIGN_PREFIXES:
            if text.startswith(prefix):
                text = normalize_text(text[len(prefix):])
                changed = True
    return normalize_text(text.translate({ord(c): None for c in _QUOTE_CHARS}))


def traffic_canonical_key(title: str) -> str:
    """정책의 정체는 제목이다. 혜택 원문·기간은 다듬어지거나 갱신되므로 key 에 넣지 않는다 -
    넣으면(예전 방식) 재수집마다 다른 정책으로 인식돼 카드가 복제되고 사용자 링크가 옛 행에 남는다."""
    return stable_hash(f"{SOURCE_CATEGORY}|{core_traffic_title(title)}")


class _TrafficBenefitHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None
        self._capture: str | None = None
        self._last_dt: str | None = None
        self._ignored_depth = 0
        self._in_anchor = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer", "aside"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        attr_map = {key: value for key, value in attrs}
        if tag == "h4":
            self._finish_current()
            self._current = {"raw": ""}
            self._capture = "title"
            return
        if self._current is None:
            return
        if tag in {"p", "li", "dt", "dd", "td", "th"}:
            self._capture = "td" if tag in {"td", "th"} else tag
        if tag == "a":
            # 링크 글자("할인혜택 보러가기")는 혜택이 아니다 - 주소만 받고 글자는 원문에 넣지 않는다
            self._in_anchor = True
            if attr_map.get("href") and not self._current.get("detail_url"):
                self._current["detail_url"] = attr_map["href"]

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "aside"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "a":
            self._in_anchor = False
        if tag == "article":
            # 카드 목록이 끝났다. 마지막 카드가 그 뒤(검색어 순위·푸터·주소)까지 끌고 가지 않게 여기서 닫는다.
            self._finish_current()
            return
        if tag in {"h4", "p", "li", "dt", "dd", "td", "th"}:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = normalize_text(data)
        if not text or self._in_anchor:
            return
        if self._current is not None:
            self._current["raw"] = normalize_text(f"{self._current.get('raw', '')} {text}")
        if self._current is None or self._capture is None:
            return
        if self._capture == "title":
            self._current["title"] = normalize_text(
                f"{self._current.get('title', '')} {text}"
            )
        elif self._capture in {"p", "li", "td"}:
            self._current["benefit"] = normalize_text(f"{self._current.get('benefit', '')} {text}")
            if self._capture == "td":
                self._current["table"] = normalize_text(f"{self._current.get('table', '')} {text}")
        elif self._capture == "dt":
            self._last_dt = text
        elif self._capture == "dd":
            period_label = normalize_text(self._last_dt or "").replace(" ", "")
            if period_label in {"판매기간", "예약기간", "발급및예약기간"}:
                self._current["issue_period"] = text
            elif period_label in {"탑승및이용기간", "이용기간", "사용기간"}:
                self._current["usage_period"] = text
            elif "기간" in period_label:
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
    page_context = " ".join(
        normalize_text(f"{raw.get('title', '')} {raw.get('benefit', '')}")
        for raw in parser.records
    )
    for raw_record in _deduplicate_records(parser.records):
        title = str(raw_record.get("title", ""))
        benefit_text = str(raw_record.get("benefit", ""))
        issue_period = str(raw_record.get("issue_period", ""))
        usage_period = str(raw_record.get("usage_period", ""))
        period_text = issue_period or usage_period or str(raw_record.get("period", ""))
        contact_text = str(raw_record.get("contact", "")) or None
        detail_url = str(raw_record.get("detail_url", "")) or None
        raw_text = str(raw_record.get("raw", ""))
        if not title or not benefit_text:
            continue

        start_date, end_date = _parse_period_with_year(period_text, fetched_at.year)
        status = normalize_status(None, start_date, end_date, today)
        benefit_value = _traffic_benefit_value(benefit_text)
        card_summary, card_issues = _traffic_card_summary(
            benefit_text,
            benefit_value,
            title=title,
            table_text=str(raw_record.get("table", "")),
            context_text=page_context,
        )
        card_copy = evaluate_card_copy(
            summary=card_summary,
            evidence=benefit_text,
            issues=card_issues,
        )
        _, _, period_evidence_payload = period_payload(
            [
                ("예약 기간", issue_period),
                ("탑승 및 이용 기간", usage_period),
            ],
            default_year=fetched_at.year,
            source="travelmonth-traffic",
        )
        canonical_key = traffic_canonical_key(title)
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
                external_id=canonical_key,
                canonical_key=canonical_key,
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
                raw_payload={
                    **period_evidence_payload,
                    "periodText": period_text,
                    "issuePeriod": issue_period or None,
                    "usagePeriod": usage_period or None,
                    "cardCopy": card_copy.to_payload(),
                },
                last_fetched_at=fetched_at,
                last_verified_at=fetched_at if confidence >= 85 else None,
                freshness_status="fresh" if status == "active" else "unknown",
            )
        )
    return records


def _deduplicate_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    deduplicated: dict[str, dict[str, object]] = {}
    without_url: list[dict[str, object]] = []
    for record in records:
        detail_url = normalize_text(str(record.get("detail_url", "")))
        if not detail_url:
            without_url.append(record)
            continue
        current = deduplicated.get(detail_url)
        if current is None or _record_score(record) > _record_score(current):
            deduplicated[detail_url] = record
    return [*deduplicated.values(), *without_url]


def _record_score(record: dict[str, object]) -> tuple[int, int]:
    typed_periods = int(bool(record.get("issue_period"))) + int(
        bool(record.get("usage_period"))
    )
    return typed_periods, len(str(record.get("raw", "")))


# 카드 문구에 앞세울 대상(수단·매체). 앞에 있는 것이 우선 - "카모아 렌터카" 처럼 상호가 붙으면 그것까지.
_TARGET_PATTERNS = (
    r"카모아\s*렌터카", r"렌터카", r"내일로패스", r"테마열차", r"KTX", r"철도", r"승차권",
    r"국내선", r"항공권", r"티맵", r"온누리상품권",
)
_TARGET_LABEL = {"승차권": "철도", "항공권": "국내선", "KTX": "철도"}
_POINT_ONLY_TARGETS = {"국내선", "티맵"}


def _largest_amount(text: str) -> tuple[str, int, str] | None:
    """본문에서 가장 큰 금액 하나 - (숫자 문구, 원 단위 비교값, 단위). "10,000원" 은 "1만" 으로 접는다."""
    best: tuple[str, int, str] | None = None
    for match in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(만|천)?\s*(원|포인트)", text):
        number = float(match.group(1).replace(",", ""))
        scale = match.group(2) or ""
        krw = int(number * (10000 if scale == "만" else 1000 if scale == "천" else 1))
        if scale:
            label = f"{match.group(1)}{scale}"
        elif krw >= 10000 and krw % 10000 == 0:
            label = f"{krw // 10000}만"
        elif krw >= 1000 and krw % 1000 == 0:
            label = f"{krw // 1000}천"
        else:
            label = f"{int(number):,}"
        if best is None or krw > best[1]:
            best = (label, krw, match.group(3))
    return best


def _pick_target(text: str, title: str) -> str | None:
    """본문에서 가장 먼저 나오는 대상 낱말. 본문에 없으면 제목에서. 상호가 붙은 것("카모아 렌터카")은 그대로."""
    for source in (text, title):
        first: tuple[int, str] | None = None
        for pattern in _TARGET_PATTERNS:
            found = re.search(pattern, source)
            if found and (first is None or found.start() < first[0]):
                first = (found.start(), normalize_text(found.group(0)))
        if first:
            return _TARGET_LABEL.get(first[1], first[1])
    return None


def _traffic_card_summary(
    benefit_text: str,
    benefit_value: BenefitValue,
    *,
    title: str = "",
    table_text: str = "",
    context_text: str = "",
) -> tuple[str | None, tuple[str, ...]]:
    """카드 문구 = 대상 + 혜택. 예: "카모아 렌터카 2만원 쿠폰", "국내선 최대 4만 포인트", "테마열차 운임 50% 할인".
    금액이 여럿이면 제목의 "최대 N"을 우선하고, 없으면 가장 큰 값을 쓴다(첫 문장을 집던 오류 수정).
    원과 포인트가 한 문장에 섞이면 어느 단위인지 정할 수 없어 보류한다 - 포인트만이면 그대로 통과."""
    text = normalize_text(benefit_text)
    context = normalize_text(context_text)
    core_title = core_traffic_title(title)
    target = _pick_target(text, title)

    # 공식 블록에서 조건과 혜택이 함께 확인되는 정책만 카드 문구를 구체화한다.
    if (
        "인구감소지역 자유여행상품 할인" in title
        and "방문 인증" in text
        and "운임" in text
        and "쿠폰" in text
    ):
        return "방문 인증 시 철도 운임 상당 할인쿠폰", ()
    if (
        "인구감소지역 자유여행상품 추가 혜택" in title
        and "선착순" in text
        and "1인당 2만원" in text
    ):
        return "1인 온누리상품권 2만원·선착순", ()
    if (
        core_title == "자유로운 기차여행"
        and "테마열차 할인" in context
        and "내일로패스 할인" in context
    ):
        return "철도 할인쿠폰·테마열차·내일로 혜택", ()
    if (
        "항공권" in text
        and "최대 4만 포인트" in text
        and "인당 1만 포인트" in context
        and "왕복 기준" in context
    ):
        return "대상 국내선 왕복 최대 4만 포인트(4인)", ()
    if (
        "인구감소지역 자동차 여행 할인" in title
        and "30km" in text
        and "스탬프" in text
        and "티맵 포인트" in text
    ):
        return "티맵 방문 스탬프 누적 최대 3만 포인트", ()
    prefix = f"{target} " if target else ""

    # "티맵 포인트(2천원)" 처럼 괄호 안 원 표기는 포인트의 환산 설명이지 다른 혜택이 아니다
    text_without_parenthetical = re.sub(r"\([^)]*\)", "", text)
    has_won = re.search(r"\d\s*(?:만|천)?\s*원", text_without_parenthetical) is not None
    has_point = "포인트" in text
    if has_won and has_point:
        return None, ("benefit_unit_ambiguous",)

    # 운임 100% 쿠폰은 금액이 아니라 비율이 혜택이다. 이 문구가 있으면 옆의 부가 혜택(상품권 등)보다 앞선다.
    if re.search(r"운임의?\s*100\s*%", text) and "쿠폰" in text:
        return f"{'철도' if target in (None, '내일로패스', '테마열차') else target} 운임 100% 할인쿠폰", ()

    # 금액·포인트: 제목의 최대값 우선, 없으면 본문 최대값
    # "최대 N" 이 명시돼 있으면 그것을 쓴다 - 제목이 먼저, 없으면 본문. 여럿이면(표) 가장 큰 값.
    # 명시가 없을 때만 본문의 모든 금액 중 최댓값.
    explicit = None
    # 금액이 표(지역×기간)로 오면 "최대" 표기 유무가 칸마다 달라 명시값을 믿을 수 없다 - 표 전체의 최댓값.
    sources = () if table_text else (title, text)
    for source in sources:
        stated = re.findall(r"최대\s*(\d[\d,]*(?:\.\d+)?)\s*(만|천)?\s*(원|포인트)", source)
        if stated:
            explicit = max(stated, key=lambda m: float(m[0].replace(",", "")) * (10000 if m[1] == "만" else 1000 if m[1] == "천" else 1))
            break
    if explicit:
        largest = _largest_amount(f"{explicit[0]}{explicit[1]}{explicit[2]}")
    else:
        largest = _largest_amount(text)
    amount, unit = (largest[0], largest[2]) if largest else (None, None)

    if (
        "연안지역" in title
        and "저공해 렌터카" in text
        and "할인쿠폰" in text
        and amount is not None
    ):
        return f"저공해 렌터카 최대 {amount}{unit} 할인쿠폰", ()
    if (
        core_title == "바다가는 달"
        and "카모아 렌터카" in text
        and "최대" in text
        and amount is not None
    ):
        return f"카모아 렌터카 최대 {amount}{unit} 쿠폰", ()

    if has_point:
        if amount is None:
            return None, ("benefit_missing",)
        return f"{prefix}최대 {amount} 포인트", ()

    # 할인율(금액 없이)
    percent = re.search(r"(\d{1,3})\s*%\s*할인", text)
    if percent and amount is None:
        return f"{prefix}운임 {percent.group(1)}% 할인", ()
    if amount is None:
        return None, ("benefit_missing",)

    won = f"{amount}{unit}"
    if "상품권" in text and target == "온누리상품권":
        return f"온누리상품권 {won}", ()
    if re.search(r"할인\s*쿠폰", text):
        return f"{prefix}할인쿠폰 최대 {won}", ()
    if "쿠폰" in text or re.search(r"\d\s*(?:만|천)?\s*원\s*권", text):
        return f"{prefix}{won} 쿠폰", ()
    if "할인" in text:
        return f"{prefix}{won} 할인", ()
    return f"{prefix}최대 {won}", ()


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
