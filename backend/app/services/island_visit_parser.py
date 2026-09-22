from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.schemas.external_sources import ExternalBenefitSource
from app.services.policy_card_quality import evaluate_card_copy
from app.services.travelmonth_normalizer import extract_benefit_value, normalize_status, normalize_text

SOURCE_CATEGORY = "island_visit"
SOURCE_NAME = "2026 Island Visit Year"
SOURCE_URL = "https://www.visitisland.kr/promotion2"
CANONICAL_KEY = "2026-island-visit-support"

# Official application forms live on Google Forms; nothing else is accepted as a form link.
_FORM_URL = re.compile(r"https://(?:forms\.gle/[A-Za-z0-9_-]+|docs\.google\.com/forms/[^\s\"'<>)]+)")
_LIST_LINK_HOSTS = {"buly.kr"}
_SECTION_HEADERS = {"지원 제외 기준", "문의사항", "필수 제출 증빙 자료", "신청 및 인정기준", "지원 프로세스"}


class IslandVisitParserChangedError(ValueError):
    pass


class _TextParser(HTMLParser):
    """Visible text nodes in order. Comments never reach handle_data; script/style text is skipped."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if text := normalize_text(data):
            self.parts.append(text)


def parse_island_visit_support(html: str, *, fetched_at: datetime, today: date) -> list[ExternalBenefitSource]:
    parser = _TextParser()
    parser.feed(html)
    lines = parser.parts
    text = "\n".join(lines)
    year = fetched_at.year

    procedure, apply_texts = _parse_procedure(html, lines, year=year)
    rounds = procedure["rounds"]
    representative = representative_round(rounds, today=today, document_deadline_days=procedure["documentDeadlineDaysAfterTrip"] or 0)
    application = (apply_texts.get(representative["key"]) if representative else None) or _value_after(lines, "신청 기간")
    travel = _travel_period_line(text)
    benefit = _value_after(lines, "지원 내용 및 금액", "지원 내용")
    if not application or not travel or not benefit:
        raise IslandVisitParserChangedError("missing required Island Visit campaign fields")
    period = _parse_period(travel, fallback_year=year)
    if period is None:
        raise IslandVisitParserChangedError("unreadable Island Visit travel period")
    if procedure["documentDeadlineDaysAfterTrip"] is None:
        raise IslandVisitParserChangedError("missing Island Visit document submission deadline")
    if not any(item["applyUntil"] and item["travelStart"] and item["travelEnd"] for item in rounds):
        raise IslandVisitParserChangedError("missing Island Visit round deadlines")
    start, end = period
    amount = extract_benefit_value(benefit)
    eligible_islands_url = _eligible_islands_url(html)
    card_copy = evaluate_card_copy(summary=amount.value_text, evidence=benefit)
    return [ExternalBenefitSource(source_name=SOURCE_NAME, source_type="official_campaign", source_url=SOURCE_URL, source_category=SOURCE_CATEGORY, external_id=CANONICAL_KEY, canonical_key=CANONICAL_KEY, logical_key=CANONICAL_KEY, collected_page_url=SOURCE_URL, title="2026 섬 여행비 지원", organizer_text="섬 방문의 해 추진위원회", organizers=["섬 방문의 해 추진위원회"], region="전국", is_nationwide=True, status_text=travel, status=normalize_status(None, start, end, today), start_date=start, end_date=end, benefit_text=benefit, benefit_value_text=amount.value_text, extracted_amount_krw=amount.amount_krw, extracted_discount_percent=amount.discount_percent, benefit_value_type=amount.value_type, tags=["섬여행", "여행비지원"], inferred_travel_styles=[], confidence=95, field_completeness=90, raw_list_text=text, raw_detail_text=text, raw_payload={"applicationPeriod": application, "eligibleIslandsUrl": eligible_islands_url, "procedure": procedure, "cardCopy": card_copy.to_payload()}, last_fetched_at=fetched_at, last_verified_at=fetched_at, freshness_status="fresh")]


# --- rounds ---------------------------------------------------------------------------------------


def round_status(round_: dict, *, today: date, document_deadline_days: int) -> str:
    """past once documents can no longer be submitted, upcoming before applications open, else current."""
    travel_end = round_.get("travelEnd")
    if travel_end and today > date.fromisoformat(travel_end) + timedelta(days=document_deadline_days):
        return "past"
    apply_start = round_.get("applyStart")
    if apply_start and today < date.fromisoformat(apply_start[:10]):
        return "upcoming"
    return "current"


def representative_round(rounds: list[dict], *, today: date, document_deadline_days: int) -> dict | None:
    """The round a user acts on now: still open for applications first, otherwise the latest non-past one."""
    if not rounds:
        return None
    active = [item for item in rounds if round_status(item, today=today, document_deadline_days=document_deadline_days) != "past"]
    open_for_apply = sorted(
        (item for item in active if item.get("applyUntil") and today <= date.fromisoformat(item["applyUntil"][:10])),
        key=lambda item: item["applyUntil"],
    )
    if open_for_apply:
        return open_for_apply[0]
    return (active or rounds)[-1]


def _empty_round(key: str) -> dict:
    return {"key": key, "applyStart": None, "applyUntil": None, "travelStart": None, "travelEnd": None, "applicationFormUrl": None, "documentFormUrl": None}


def _parse_procedure(html: str, lines: list[str], *, year: int) -> tuple[dict, dict[str, str]]:
    rounds: dict[str, dict] = {}
    apply_texts: dict[str, str] = {}

    for index, line in enumerate(lines):
        promotion = re.search(r"프로모션\s*(\d)\s*차", line)
        if promotion:
            key = promotion.group(1)
            round_ = rounds.setdefault(key, _empty_round(key))
            window = lines[index + 1 : index + 14]
            for offset, item in enumerate(window):
                months = re.search(r"(\d)\s*차\s*(\d{1,2})\s*~\s*(\d{1,2})\s*월", item)
                if months and months.group(1) == key and round_["travelStart"] is None:
                    first, last = int(months.group(2)), int(months.group(3))
                    round_["travelStart"] = date(year, first, 1).isoformat()
                    round_["travelEnd"] = date(year, last, calendar.monthrange(year, last)[1]).isoformat()
                if item == "신청 기간" and offset + 1 < len(window) and round_["applyUntil"] is None:
                    start, until = _parse_apply_range(window[offset + 1], year=year)
                    round_["applyStart"], round_["applyUntil"] = start, until
                    apply_texts.setdefault(key, window[offset + 1])
                if re.search(r"프로모션\s*\d\s*차", item):
                    break

        if line == "지원 프로세스":
            block = lines[index + 1 : index + 30]
            key_match = next((match for item in block if (match := re.search(r"(\d)\s*차", item))), None)
            if key_match is None:
                continue
            key = key_match.group(1)
            round_ = rounds.setdefault(key, _empty_round(key))
            for item in block:
                if round_["applyUntil"] is None and "까지" in item and ("신청" in item or "제출 기한" in item):
                    _, until = _parse_apply_range(item, year=year)
                    if until:
                        round_["applyUntil"] = until
                        apply_texts.setdefault(key, item)
                if round_["travelStart"] is None and "여행하기" in item:
                    period = _parse_period(item, fallback_year=year)
                    if period:
                        round_["travelStart"], round_["travelEnd"] = period[0].isoformat(), period[1].isoformat()

    if not rounds:
        # Single-round pages: fall back to the labelled application period and the travel line.
        application = _value_after(lines, "신청 기간")
        travel = _travel_period_line("\n".join(lines))
        period = _parse_period(travel, fallback_year=year) if travel else None
        if application and period:
            start, until = _parse_apply_range(application, year=year)
            rounds["1"] = {**_empty_round("1"), "applyStart": start, "applyUntil": until, "travelStart": period[0].isoformat(), "travelEnd": period[1].isoformat()}
            apply_texts["1"] = application

    _assign_forms(html, rounds)
    procedure = {
        "rounds": [rounds[key] for key in sorted(rounds)],
        "documentDeadlineDaysAfterTrip": _document_deadline_days(lines),
        "minNights": _first_int(lines, r"(\d+)\s*박\s*\d+\s*일\s*이상"),
        "minPaymentKrw": (lambda value: value * 10_000 if value is not None else None)(_first_int(lines, r"결제\s*금액\s*(\d+)\s*만\s*원\s*이상")),
        "requiredDocuments": _bullet_section(lines, "필수 제출 증빙 자료"),
        "photoRequirement": next((line.lstrip("※").strip() for line in lines if line.startswith("※") and "사진" in line), None),
        "exclusions": _bullet_section(lines, "지원 제외 기준"),
        "contacts": _contacts("\n".join(lines)),
    }
    return procedure, apply_texts


def _parse_apply_range(value: str, *, year: int) -> tuple[str | None, str | None]:
    left, _, right = value.partition("~")
    if not right:
        return None, _format_moment(value, year=year, end=True)
    return _format_moment(left, year=year, end=False), _format_moment(right, year=year, end=True)


def _format_moment(segment: str, *, year: int, end: bool) -> str | None:
    full = re.search(r"(20\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})", segment)
    korean = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", segment)
    if full:
        day = date(int(full.group(1)), int(full.group(2)), int(full.group(3)))
    elif korean:
        day = date(year, int(korean.group(1)), int(korean.group(2)))
    else:
        return None
    clock = re.search(r"(오전|오후)\s*(\d{1,2})\s*시", segment)
    if clock:
        hour = int(clock.group(2)) % 12 + (12 if clock.group(1) == "오후" else 0)
        return f"{day.isoformat()}T{hour:02d}:00"
    return f"{day.isoformat()}T{'23:59' if end else '00:00'}"


def _assign_forms(html: str, rounds: dict[str, dict]) -> None:
    """Attach live (uncommented) Google Form links to a round by the button label or alert text around them."""
    live = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for match in _FORM_URL.finditer(live):
        after = live[match.end() : match.end() + 300]
        label = _strip_tags(after.split("</button>")[0]) if "</button>" in after else ""
        context = label if re.search(r"\d\s*차", label) else _strip_tags(live[max(0, match.start() - 200) : match.start()])
        round_key = re.search(r"(\d)\s*차", context)
        if round_key is None or round_key.group(1) not in rounds:
            continue
        field = "documentFormUrl" if "서류" in context else "applicationFormUrl" if "신청" in context else None
        if field and rounds[round_key.group(1)][field] is None:
            rounds[round_key.group(1)][field] = match.group(0)


def _strip_tags(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


def _document_deadline_days(lines: list[str]) -> int | None:
    for line in lines:
        if "서류" in line or "제출" in line:
            weeks = re.search(r"(\d+)\s*주\s*이내", line)
            if weeks:
                return int(weeks.group(1)) * 7
    for line in lines:
        if ("서류" in line or "제출" in line) and "지급" not in line:
            days = re.search(r"(\d+)\s*일\s*이내", line)
            if days:
                return int(days.group(1))
    return None


def _first_int(lines: list[str], pattern: str) -> int | None:
    for line in lines:
        match = re.search(pattern, line)
        if match:
            return int(match.group(1))
    return None


def _bullet_section(lines: list[str], header: str) -> list[str]:
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []
    items: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            item = normalize_text(" ".join(current))
            if item and item not in items:
                items.append(item)
            current.clear()

    for line in lines[start:]:
        if line.startswith("※") or line in _SECTION_HEADERS:
            break
        if line in {"•", "·"}:
            flush()
            continue
        current.append(line.lstrip("•·").strip())
    flush()
    return items


def _contacts(text: str) -> dict:
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.]+", text)
    phones: list[str] = []
    for phone in re.findall(r"0\d{1,2}-\d{3,4}-\d{4}", text):
        if phone not in phones:
            phones.append(phone)
    return {"email": email.group(0) if email else None, "phones": phones}


# --- card fields ----------------------------------------------------------------------------------


def _value_after(lines: list[str], *labels: str) -> str | None:
    """Value of a label: the next text node when the label stands alone, or the text after 'label:' inline.

    Exact matching matters: '지원 내용' must not match the '지원 내용 및 금액' header and return '및 금액'.
    """
    for label in labels:
        for index, line in enumerate(lines):
            # The real page splits some headers across text nodes ('지원 내용' + '및 금액').
            if index + 2 < len(lines) and f"{line} {lines[index + 1]}" == label:
                return lines[index + 2]
            if line == label:
                following = lines[index + 1] if index + 1 < len(lines) else None
                if following is not None and any(f"{line} {following}" == longer for longer in labels if longer != label):
                    continue
                if following is not None:
                    return following
            elif line.startswith(label):
                remainder = line[len(label) :].strip()
                if remainder.startswith(":"):
                    value = remainder.lstrip(":").strip()
                    if value:
                        return value
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
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[^<]*(?:대상\s*섬|eligible\s+island)',
        html,
        flags=re.IGNORECASE,
    )
    if match is not None:
        return urljoin(SOURCE_URL, match.group(1))
    live = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for href in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', live, flags=re.IGNORECASE):
        absolute = urljoin(SOURCE_URL, href)
        if urlparse(absolute).netloc in _LIST_LINK_HOSTS or absolute.startswith("https://docs.google.com/spreadsheets/"):
            return absolute
    return None
