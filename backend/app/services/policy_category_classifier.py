from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models import ExternalSourceRecord


POLICY_CATEGORY_PRIORITY = ("교통", "숙박", "여행상품", "이벤트", "지역할인", "기타")

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "교통": (
        "기차",
        "열차",
        "철도",
        "ktx",
        "srt",
        "항공",
        "항공권",
        "렌터카",
        "렌트카",
        "버스",
        "셔틀",
        "승선",
        "여객선",
        "크루즈",
        "운임",
        "교통",
        "투어패스",
    ),
    "숙박": (
        "숙박",
        "호텔",
        "리조트",
        "펜션",
        "글램핑",
        "캠핑",
        "스테이",
        "객실",
        "야영장",
        "숙소",
    ),
    "여행상품": (
        "패키지",
        "여행상품",
        "관광상품",
        "체험상품",
        "투어",
        "코스",
        "1박 2일",
        "2박 3일",
        "원정 경기",
        "체류여행",
    ),
    "이벤트": (
        "이벤트",
        "프로모션",
        "추첨",
        "경품",
        "챌린지",
        "인증 이벤트",
    ),
    "지역할인": (
        "캐시백",
        "환급",
        "지역",
        "입장료",
        "할인권",
        "방문객",
        "관광지",
    ),
}

SOURCE_CATEGORY_BOOSTS: dict[str, tuple[tuple[str, int, str], ...]] = {
    "traffic_benefit": (("교통", 5, "source_category:traffic_benefit"),),
    "local_half_trip": (
        ("지역할인", 2, "source_category:local_half_trip"),
        ("여행상품", 1, "source_category:local_half_trip"),
    ),
    "regional_benefit": (("지역할인", 1, "source_category:regional_benefit"),),
    "stay_discount": (("숙박", 15, "source_category:stay_discount"),),
}

URL_CATEGORY_BOOSTS: dict[str, tuple[str, int]] = {
    "benefits/traffic.do": ("교통", 8),
    "benefits/stay.do": ("숙박", 8),
    "benefits/special.do": ("여행상품", 8),
    "travelmonth/event.do": ("이벤트", 8),
    "travel-info.do": ("기타", 8),
}


@dataclass(frozen=True)
class PolicyCategoryDecision:
    category: str
    scores: dict[str, int]
    matched_keywords: dict[str, list[str]]


@dataclass(frozen=True)
class _WeightedText:
    text: str
    weight: int
    label: str


def classify_external_policy_category(record: ExternalSourceRecord) -> PolicyCategoryDecision:
    scores = {category: 0 for category in POLICY_CATEGORY_PRIORITY}
    matched_keywords = {category: [] for category in POLICY_CATEGORY_PRIORITY}

    for bucket in _weighted_texts(record):
        searchable = bucket.text.lower()
        if not searchable:
            continue
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in searchable:
                    scores[category] += bucket.weight
                    _append_unique(matched_keywords[category], f"{bucket.label}:{keyword}")

    for category, boost, reason in SOURCE_CATEGORY_BOOSTS.get(record.source_category or "", ()):
        scores[category] += boost
        _append_unique(matched_keywords[category], reason)

    for category, boost, reason in _url_boosts(record):
        scores[category] += boost
        _append_unique(matched_keywords[category], reason)

    category = _choose_category(scores)
    return PolicyCategoryDecision(
        category=category,
        scores=scores,
        matched_keywords={
            category_name: matches
            for category_name, matches in matched_keywords.items()
            if matches
        },
    )


def _weighted_texts(record: ExternalSourceRecord) -> Iterable[_WeightedText]:
    yield _WeightedText(record.title or "", 4, "title")
    yield _WeightedText(record.benefit_text or "", 3, "benefit_text")
    yield _WeightedText(record.raw_detail_text or "", 2, "raw_detail_text")
    yield _WeightedText(" ".join(_string_values(record.tags)), 1, "tags")
    yield _WeightedText(record.organizer_text or "", 1, "organizer_text")
    yield _WeightedText(record.detail_url or "", 1, "detail_url")
    yield _WeightedText(record.collected_page_url or "", 1, "collected_page_url")


def _url_boosts(record: ExternalSourceRecord) -> Iterable[tuple[str, int, str]]:
    source_text = " ".join(
        part
        for part in [record.detail_url, record.collected_page_url, record.source_url]
        if part
    ).lower()
    for marker, (category, boost) in URL_CATEGORY_BOOSTS.items():
        if marker in source_text:
            yield category, boost, f"url:{marker}"


def _choose_category(scores: dict[str, int]) -> str:
    best_score = max(scores.values())
    if best_score <= 0:
        return "기타"
    for category in POLICY_CATEGORY_PRIORITY:
        if scores[category] == best_score:
            return category
    return "기타"


def _string_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
