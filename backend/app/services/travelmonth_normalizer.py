from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime


REGION_ALIASES = {
    "서울특별시": "서울",
    "서울시": "서울",
    "서울": "서울",
    "부산광역시": "부산",
    "부산시": "부산",
    "부산": "부산",
    "대구광역시": "대구",
    "대구시": "대구",
    "대구": "대구",
    "인천광역시": "인천",
    "인천시": "인천",
    "인천": "인천",
    "광주광역시": "광주",
    "광주시": "광주",
    "광주": "광주",
    "대전광역시": "대전",
    "대전시": "대전",
    "대전": "대전",
    "울산광역시": "울산",
    "울산시": "울산",
    "울산": "울산",
    "세종특별자치시": "세종",
    "세종시": "세종",
    "세종": "세종",
    "경기도": "경기",
    "경기": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "강원": "강원",
    "충청북도": "충북",
    "충북": "충북",
    "충청남도": "충남",
    "충남": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전북": "전북",
    "전라남도": "전남",
    "전남": "전남",
    "경상북도": "경북",
    "경북": "경북",
    "경상남도": "경남",
    "경남": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
    "제주": "제주",
}

REGION_FALLBACK_ALIASES = {
    alias: region
    for alias, region in REGION_ALIASES.items()
    if alias.endswith(("특별시", "광역시", "특별자치시", "특별자치도", "도"))
    or alias
    in {
        "서울시",
        "부산시",
        "대구시",
        "인천시",
        "광주시",
        "대전시",
        "울산시",
        "세종시",
        "제주도",
    }
}

NATIONWIDE_ORGANIZERS = {"한국관광공사", "문화체육관광부"}

STYLE_KEYWORDS = {
    "휴식": ("휴식", "스파", "온천", "힐링", "숙박", "리조트", "호텔"),
    "맛집": ("맛집", "식음료", "카페", "전통주", "로컬푸드", "식사"),
    "체험": ("체험", "투어", "박물관", "과학관", "테마파크", "공예", "관람"),
    "자연": ("자연", "숲", "바다", "해변", "해수욕장", "둘레길", "정원", "DMZ"),
    "사진": ("사진", "전망대", "풍경", "포토", "스팟", "야경"),
}

STYLE_ORDER = ("휴식", "맛집", "체험", "자연", "사진")


@dataclass(frozen=True)
class RegionResult:
    region: str | None
    city: str | None
    is_nationwide: bool


@dataclass(frozen=True)
class BenefitValue:
    value_text: str | None
    amount_krw: int | None
    discount_percent: int | None
    value_type: str


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def stable_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()[:32]


def normalize_region(
    organizer_text: str,
    title: str = "",
    benefit_text: str = "",
) -> RegionResult:
    parts = [normalize_text(part) for part in re.split(r"[,/]", organizer_text) if normalize_text(part)]

    for index, part in enumerate(parts):
        region = REGION_ALIASES.get(part)
        if region is not None:
            city = parts[index + 1] if index + 1 < len(parts) else None
            return RegionResult(region=region, city=city, is_nationwide=False)

    searchable = normalize_text(f"{title} {benefit_text}")
    for alias, region in REGION_FALLBACK_ALIASES.items():
        if alias in searchable:
            return RegionResult(region=region, city=None, is_nationwide=False)

    is_nationwide = len(parts) == 1 and parts[0] in NATIONWIDE_ORGANIZERS
    return RegionResult(region=None, city=None, is_nationwide=is_nationwide)


def parse_period(period_text: str) -> tuple[date | None, date | None]:
    matches = re.findall(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}", period_text)
    if len(matches) < 2:
        return None, None

    return _parse_date(matches[0]), _parse_date(matches[1])


def normalize_status(
    status_text: str | None,
    start_date: date | None,
    end_date: date | None,
    today: date,
) -> str:
    cleaned = normalize_text(status_text)
    if "진행중" in cleaned or "진행 중" in cleaned:
        return "active"
    if "종료" in cleaned or "마감" in cleaned:
        return "ended"
    if "예정" in cleaned:
        return "scheduled"
    if start_date is None or end_date is None:
        return "unknown"
    if today < start_date:
        return "scheduled"
    if today > end_date:
        return "ended"
    return "active"


def extract_benefit_value(benefit_text: str, *, title: str | None = None) -> BenefitValue:
    text = normalize_text(" ".join(value for value in [title, benefit_text] if value))
    amount_matches = _extract_amounts(text)
    percent_matches = [int(value) for value in re.findall(r"(\d{1,3})\s*%", text)]

    amount = max((match[0] for match in amount_matches), default=None)
    percent = max(percent_matches) if percent_matches else None

    if amount is not None and percent is not None:
        return BenefitValue(_amount_value_text(amount_matches, amount), amount, percent, "mixed")
    if amount is not None:
        return BenefitValue(_amount_value_text(amount_matches, amount), amount, None, "amount")
    if percent is not None:
        return BenefitValue(f"최대 {percent}%", None, percent, "percent")
    if "무료" in text:
        return BenefitValue("무료", None, None, "free")
    return BenefitValue(None, None, None, "unknown")


def infer_travel_styles(*, title: str, benefit_text: str, tags: list[str]) -> list[str]:
    searchable = normalize_text(" ".join([title, benefit_text, *tags]))
    styles: list[str] = []
    for style in STYLE_ORDER:
        if any(keyword in searchable for keyword in STYLE_KEYWORDS[style]):
            styles.append(style)
    return styles


def calculate_field_completeness(values: dict[str, object | None]) -> int:
    if not values:
        return 0

    filled = 0
    for value in values.values():
        if value is None:
            continue
        if isinstance(value, str) and not normalize_text(value):
            continue
        if isinstance(value, (list, tuple, set, dict)) and not value:
            continue
        filled += 1
    return round(filled / len(values) * 100)


def _parse_date(value: str) -> date:
    normalized = value.replace(".", "-")
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def _extract_amounts(text: str) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    for match in re.finditer(r"(?<![\d,])(\d+(?:,\d{3})*)\s*(만원|천원|원)", text):
        number = int(match.group(1).replace(",", ""))
        unit = match.group(2)
        multiplier = {"만원": 10000, "천원": 1000, "원": 1}[unit]
        matches.append((number * multiplier, f"{number}{unit}"))
    for match in re.finditer(r"(?<![\d,])(\d+(?:,\d{3})*)\s*(만\s*원|천\s*원)", text):
        number = int(match.group(1).replace(",", ""))
        unit = match.group(2).replace(" ", "")
        amount = number * 10000 if unit == "만원" else number * 1000
        matches.append((amount, f"{number}{unit}"))
    return matches


def _amount_value_text(matches: list[tuple[int, str]], amount: int) -> str:
    for candidate_amount, candidate_text in matches:
        if candidate_amount == amount:
            return f"최대 {candidate_text}"
    return f"최대 {amount:,}원"
