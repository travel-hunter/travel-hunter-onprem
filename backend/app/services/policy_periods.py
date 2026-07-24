from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from app.services.travelmonth_normalizer import normalize_text


PeriodType = str

APPLICATION = "application"
ISSUE = "issue"
USAGE = "usage"
UNKNOWN = "unknown"

_PRIORITY: dict[PeriodType, int] = {
    APPLICATION: 1,
    ISSUE: 2,
    USAGE: 3,
    UNKNOWN: 9,
}
_TYPE_TITLES: dict[PeriodType, str] = {
    APPLICATION: "신청 기간",
    ISSUE: "쿠폰 발급 기간",
    USAGE: "사용 기간",
    UNKNOWN: "기간",
}
_BUDGET_PATTERN = re.compile(r"예산\s*소진|소진\s*시|조기\s*종료|조기종료")
_FULL_DATE_PATTERN = re.compile(r"(20\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})")
_KOREAN_DATE_PATTERN = re.compile(r"(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일?")
_PARTIAL_DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})(?!\s*[./]?\d)")
_MONTH_RANGE_PATTERN = re.compile(r"(\d{1,2})\s*~\s*(\d{1,2})\s*월")


@dataclass(frozen=True)
class PeriodEvidence:
    period_type: PeriodType
    label: str
    original_text: str
    start_date: date | None = None
    end_date: date | None = None
    source: str | None = None
    caveat: str | None = None
    is_default_like: bool = False
    diagnostics: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.period_type,
            "label": self.label,
            "text": self.original_text,
        }
        if self.start_date is not None:
            payload["startDate"] = self.start_date.isoformat()
        if self.end_date is not None:
            payload["endDate"] = self.end_date.isoformat()
        if self.source:
            payload["source"] = self.source
        if self.caveat:
            payload["caveat"] = self.caveat
        if self.is_default_like:
            payload["defaultLike"] = True
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        return payload


@dataclass(frozen=True)
class RepresentativeDeadlineDecision:
    deadline: date | None
    start_date: date | None
    period_type: PeriodType | None
    safe: bool
    diagnostics: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "safe": self.safe,
            "deadline": self.deadline.isoformat() if self.deadline is not None else "",
        }
        if self.start_date is not None:
            payload["startDate"] = self.start_date.isoformat()
        if self.period_type:
            payload["type"] = self.period_type
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        if self.caveats:
            payload["caveats"] = list(self.caveats)
        return payload


def evidence_from_labeled_text(
    label: str,
    text: object,
    *,
    default_year: int,
    source: str | None = None,
    default_type: PeriodType | None = None,
) -> PeriodEvidence | None:
    original_text = normalize_text(str(text or ""))
    clean_label = normalize_text(label)
    if not original_text:
        return None

    caveat = _budget_caveat(original_text)
    start_date, end_date, parse_diagnostics = _parse_dates(original_text, default_year=default_year)
    period_type = default_type or classify_period_label(clean_label)
    diagnostics = list(parse_diagnostics)
    if start_date is None and end_date is None and caveat:
        diagnostics.append("budget-caveat-not-date")
    elif start_date is None and end_date is None:
        diagnostics.append("no-date-found")
    if period_type == UNKNOWN and (start_date is not None or end_date is not None):
        diagnostics.append("unclassified-period")

    return PeriodEvidence(
        period_type=period_type,
        label=clean_label,
        original_text=original_text,
        start_date=start_date,
        end_date=end_date,
        source=source,
        caveat=caveat,
        is_default_like=_is_default_like(end_date, period_type),
        diagnostics=tuple(diagnostics),
    )


def classify_period_label(label: str) -> PeriodType:
    compact = normalize_text(label).replace(" ", "")
    if any(token in compact for token in ("신청기간", "신청접수", "접수기간", "접수마감", "모집기간")):
        return APPLICATION
    if any(token in compact for token in ("쿠폰발급", "발급기간", "쿠폰기간", "할인권발급", "판매기간")):
        return ISSUE
    if any(token in compact for token in ("여행기간", "여행일정", "사용기간", "이용기간", "입실기간", "숙박기간", "투숙기간", "운영기간")):
        return USAGE
    return UNKNOWN


def select_representative_deadline(
    evidence: list[PeriodEvidence],
) -> RepresentativeDeadlineDecision:
    caveats = _unique_strings(item.caveat for item in evidence if item.caveat)
    dated = [item for item in evidence if item.end_date is not None]
    if not dated:
        diagnostics = ["no-safe-representative-deadline"]
        if caveats:
            diagnostics.append("budget-caveat-only")
        return RepresentativeDeadlineDecision(None, None, None, False, tuple(diagnostics), tuple(caveats))

    unknown_dated = [item for item in dated if item.period_type == UNKNOWN]
    unknown_default_like = [item for item in unknown_dated if item.is_default_like]
    diagnostics: list[str] = []
    if unknown_dated:
        diagnostics.append("unclassified-date-range")

    candidates = [item for item in dated if item.period_type in {APPLICATION, ISSUE, USAGE}]
    if not candidates:
        if unknown_default_like:
            diagnostics.append("default-like-only-unsafe")
        return RepresentativeDeadlineDecision(
            None,
            None,
            None,
            False,
            tuple([*diagnostics, "no-classified-date-range"]),
            tuple(caveats),
        )

    best_rank = min(_PRIORITY[item.period_type] for item in candidates)
    best_type = next(item.period_type for item in candidates if _PRIORITY[item.period_type] == best_rank)
    same_rank = [item for item in candidates if _PRIORITY[item.period_type] == best_rank]
    same_rank_end_dates = {item.end_date for item in same_rank}
    if len(same_rank_end_dates) > 1:
        return RepresentativeDeadlineDecision(
            None,
            None,
            best_type,
            False,
            tuple([*diagnostics, "same-rank-conflicting-deadlines"]),
            tuple(caveats),
        )

    selected = same_rank[0]
    if selected.is_default_like and len(candidates) == len(same_rank):
        return RepresentativeDeadlineDecision(
            None,
            None,
            selected.period_type,
            False,
            tuple([*diagnostics, "default-like-only-unsafe"]),
            tuple(caveats),
        )

    lower_default_like = [
        item
        for item in candidates
        if _PRIORITY[item.period_type] > best_rank and item.is_default_like
    ]
    if lower_default_like:
        diagnostics.append("lower-priority-default-like-ignored")
    if unknown_default_like:
        diagnostics.append("lower-priority-default-like-ignored")

    return RepresentativeDeadlineDecision(
        selected.end_date,
        selected.start_date,
        selected.period_type,
        True,
        tuple(diagnostics),
        tuple(caveats),
    )


def period_payload(
    entries: list[tuple[str, object]],
    *,
    default_year: int,
    source: str,
    default_type: PeriodType | None = None,
) -> tuple[list[PeriodEvidence], RepresentativeDeadlineDecision, dict[str, object]]:
    evidence = [
        item
        for label, value in entries
        if (
            item := evidence_from_labeled_text(
                label,
                value,
                default_year=default_year,
                source=source,
                default_type=default_type,
            )
        )
        is not None
    ]
    decision = select_representative_deadline(evidence)
    payload: dict[str, object] = {
        "periodEvidence": [item.to_payload() for item in evidence],
        "representativeDeadline": decision.to_payload(),
        "periodDiagnostics": list(decision.diagnostics),
    }
    return evidence, decision, payload


def evidence_from_payload(
    raw_payload: object,
    *,
    default_year: int,
    source: str = "raw_payload",
) -> list[PeriodEvidence]:
    if not isinstance(raw_payload, dict):
        return []
    existing = raw_payload.get("periodEvidence")
    if isinstance(existing, list):
        parsed = [_evidence_from_existing_payload(item) for item in existing]
        return [item for item in parsed if item is not None]

    entries: list[tuple[str, object]] = []
    for key, label in (
        ("applicationPeriod", "신청 기간"),
        ("issuePeriod", "쿠폰 발급 기간"),
        ("stayPeriod", "입실 기간"),
        ("tripPeriod", "여행 기간"),
        ("usagePeriod", "이용 기간"),
        ("periodText", "기간"),
    ):
        value = raw_payload.get(key)
        if value:
            entries.append((label, value))
    return [
        item
        for label, value in entries
        if (
            item := evidence_from_labeled_text(
                label,
                value,
                default_year=default_year,
                source=source,
            )
        )
        is not None
    ]


def representative_deadline_from_payload(
    raw_payload: object,
    *,
    default_year: int,
) -> RepresentativeDeadlineDecision:
    return select_representative_deadline(
        evidence_from_payload(raw_payload, default_year=default_year)
    )


def structured_period_items(evidence: list[PeriodEvidence]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in evidence:
        if item.start_date is None and item.end_date is None:
            continue
        title = _period_title(item)
        description = item.original_text
        period_item: dict[str, str] = {"title": title, "description": description, "type": item.period_type}
        if item.start_date is not None:
            period_item["startDate"] = item.start_date.isoformat()
        if item.end_date is not None:
            period_item["endDate"] = item.end_date.isoformat()
        if period_item not in items:
            items.append(period_item)
    return items


def _period_title(item: PeriodEvidence) -> str:
    label = normalize_text(item.label)
    if item.period_type != UNKNOWN and label and label != "기간":
        return label
    return _TYPE_TITLES.get(item.period_type, label or "기간")


def budget_caveat_notices(evidence: list[PeriodEvidence]) -> list[dict[str, str]]:
    return [
        {"title": "비고", "description": caveat}
        for caveat in _unique_strings(item.caveat for item in evidence if item.caveat)
    ]


def _parse_dates(value: str, *, default_year: int) -> tuple[date | None, date | None, list[str]]:
    text = normalize_text(value)
    diagnostics: list[str] = []

    full_dates = _FULL_DATE_PATTERN.findall(text)
    if len(full_dates) >= 2:
        return _safe_date(full_dates[0]), _safe_date(full_dates[1]), diagnostics

    korean_dates = _KOREAN_DATE_PATTERN.findall(text)
    if len(korean_dates) >= 2:
        return (
            _safe_date(_with_default_year(korean_dates[0], default_year)),
            _safe_date(_with_default_year(korean_dates[1], default_year)),
            diagnostics,
        )
    if len(korean_dates) == 1:
        parsed = _safe_date(_with_default_year(korean_dates[0], default_year))
        return (None, parsed, diagnostics) if _looks_like_deadline(text) else (parsed, None, diagnostics)

    timed_start = re.search(r"(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})\s*(?=\d{1,2}\s*시|부터|접수|오픈)", text)
    if timed_start:
        return _safe_date((str(default_year), timed_start.group(1), timed_start.group(2))), None, diagnostics

    partial_dates = _PARTIAL_DATE_PATTERN.findall(text)
    if len(full_dates) == 1 and len(partial_dates) >= 2:
        return (
            _safe_date(full_dates[0]),
            _safe_date((str(default_year), partial_dates[-1][0], partial_dates[-1][1])),
            diagnostics,
        )
    if len(full_dates) == 1:
        parsed = _safe_date(full_dates[0])
        return (None, parsed, diagnostics) if _looks_like_deadline(text) else (parsed, None, diagnostics)

    if len(partial_dates) >= 2:
        return (
            _safe_date((str(default_year), partial_dates[0][0], partial_dates[0][1])),
            _safe_date((str(default_year), partial_dates[1][0], partial_dates[1][1])),
            diagnostics,
        )
    if len(partial_dates) == 1:
        parsed = _safe_date((str(default_year), partial_dates[0][0], partial_dates[0][1]))
        return (None, parsed, diagnostics) if _looks_like_deadline(text) else (parsed, None, diagnostics)

    month_range = _MONTH_RANGE_PATTERN.search(text)
    if month_range:
        start_month = int(month_range.group(1))
        end_month = int(month_range.group(2))
        return date(default_year, start_month, 1), _month_end(default_year, end_month), diagnostics

    return None, None, diagnostics


def _evidence_from_existing_payload(item: object) -> PeriodEvidence | None:
    if not isinstance(item, dict):
        return None
    start_date = _date_from_iso_text(item.get("startDate"))
    end_date = _date_from_iso_text(item.get("endDate"))
    period_type = str(item.get("type") or UNKNOWN)
    return PeriodEvidence(
        period_type=period_type if period_type in _PRIORITY else UNKNOWN,
        label=normalize_text(str(item.get("label") or "")),
        original_text=normalize_text(str(item.get("text") or item.get("description") or "")),
        start_date=start_date,
        end_date=end_date,
        source=normalize_text(str(item.get("source") or "")) or None,
        caveat=normalize_text(str(item.get("caveat") or "")) or None,
        is_default_like=bool(item.get("defaultLike")) or _is_default_like(end_date, period_type),
        diagnostics=tuple(str(value) for value in item.get("diagnostics", []) if value)
        if isinstance(item.get("diagnostics"), list)
        else (),
    )


def _budget_caveat(value: str) -> str | None:
    match = _BUDGET_PATTERN.search(value)
    if not match:
        return None
    return "예산 소진 시 조기 종료"


def _looks_like_deadline(value: str) -> bool:
    return any(token in value for token in ("까지", "마감", "종료", "기한"))


def _is_default_like(value: date | None, period_type: PeriodType) -> bool:
    return value is not None and value.month == 12 and value.day == 31 and period_type == UNKNOWN


def _with_default_year(parts: tuple[str, str, str], default_year: int) -> tuple[str, str, str]:
    return (parts[0] or str(default_year), parts[1], parts[2])


def _safe_date(parts: tuple[str, str, str]) -> date | None:
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _date_from_iso_text(value: object) -> date | None:
    text = normalize_text(str(value or ""))
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1).replace(day=1) - date.resolution


def _unique_strings(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        text = normalize_text(str(value or ""))
        if text and text not in result:
            result.append(text)
    return result
