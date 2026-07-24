from __future__ import annotations

from dataclasses import dataclass


SOURCE_CATEGORY = "digital_tourism_resident_card"
SOURCE_NAME = "디지털관광주민증"
SOURCE_URL = "https://korean.visitkorea.or.kr/dgtourcard/"
TITLE_SUFFIX = "디지털관광주민증 혜택"
OFFICIAL_PARTICIPATING_REGIONS_SOURCE_URL = SOURCE_URL
OFFICIAL_PARTICIPATING_REGIONS_VERIFIED_ON = "2026-07-24"
HAENAM_REGIONAL_URL = (
    "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?"
    "mtpcDoCd=12&signguCd=12790"
)
VISITKOREA_DGTOURCARD_HOST = "korean.visitkorea.or.kr"
VISITKOREA_DGTOURCARD_PATH_PREFIX = "/dgtourcard/"


@dataclass(frozen=True)
class ParticipatingRegion:
    city: str
    region: str
    official_url: str = SOURCE_URL


PARTICIPATING_REGIONS: tuple[ParticipatingRegion, ...] = (
    ParticipatingRegion("철원", "강원"),
    ParticipatingRegion("양양", "강원"),
    ParticipatingRegion("정선", "강원"),
    ParticipatingRegion("삼척", "강원"),
    ParticipatingRegion("태백", "강원"),
    ParticipatingRegion("홍천", "강원"),
    ParticipatingRegion("평창", "강원"),
    ParticipatingRegion("영월", "강원"),
    ParticipatingRegion("연천", "경기"),
    ParticipatingRegion("가평", "경기"),
    ParticipatingRegion("강화", "인천"),
    ParticipatingRegion("태안", "충남"),
    ParticipatingRegion("예산", "충남"),
    ParticipatingRegion("보령", "충남"),
    ParticipatingRegion("제천", "충북"),
    ParticipatingRegion("단양", "충북"),
    ParticipatingRegion("괴산", "충북"),
    ParticipatingRegion("옥천", "충북"),
    ParticipatingRegion("영동", "충북"),
    ParticipatingRegion("보은", "충북"),
    ParticipatingRegion("김제", "전북"),
    ParticipatingRegion("무주", "전북"),
    ParticipatingRegion("고창", "전북"),
    ParticipatingRegion("임실", "전북"),
    ParticipatingRegion("남원", "전북"),
    ParticipatingRegion("순창", "전북"),
    ParticipatingRegion("영광", "전남"),
    ParticipatingRegion("함평", "전남"),
    ParticipatingRegion("곡성", "전남"),
    ParticipatingRegion("신안", "전남"),
    ParticipatingRegion("해남", "전남", HAENAM_REGIONAL_URL),
    ParticipatingRegion("장흥", "전남"),
    ParticipatingRegion("구례", "전남"),
    ParticipatingRegion("담양", "전남"),
    ParticipatingRegion("고흥", "전남"),
    ParticipatingRegion("완도", "전남"),
    ParticipatingRegion("영주", "경북"),
    ParticipatingRegion("안동", "경북"),
    ParticipatingRegion("영덕", "경북"),
    ParticipatingRegion("청도", "경북"),
    ParticipatingRegion("고령", "경북"),
    ParticipatingRegion("의성", "경북"),
    ParticipatingRegion("울진", "경북"),
    ParticipatingRegion("밀양", "경남"),
    ParticipatingRegion("하동", "경남"),
    ParticipatingRegion("합천", "경남"),
    ParticipatingRegion("거창", "경남"),
    ParticipatingRegion("함양", "경남"),
    ParticipatingRegion("산청", "경남"),
    ParticipatingRegion("부산동구", "부산"),
    ParticipatingRegion("부산영도", "부산"),
    ParticipatingRegion("부산서구", "부산"),
)

PARTICIPATING_CITY_REGIONS: dict[str, str] = {
    item.city: item.region for item in PARTICIPATING_REGIONS
}
PARTICIPATING_CITIES = frozenset(PARTICIPATING_CITY_REGIONS)
REGIONAL_URLS: dict[str, str] = {
    item.city: item.official_url
    for item in PARTICIPATING_REGIONS
    if item.official_url != SOURCE_URL
}
CITY_ALIASES: dict[str, str] = {
    "부산동": "부산동구",
    "부산동구": "부산동구",
    "부산 동구": "부산동구",
    "부산광역시동구": "부산동구",
    "부산영도": "부산영도",
    "부산영도구": "부산영도",
    "부산 영도": "부산영도",
    "부산광역시영도구": "부산영도",
    "부산서": "부산서구",
    "부산서구": "부산서구",
    "부산 서구": "부산서구",
    "부산광역시서구": "부산서구",
}
