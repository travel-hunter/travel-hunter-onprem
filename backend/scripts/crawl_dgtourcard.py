"""
디지털관광주민증 정책 크롤링 스크립트.

실행:
    cd backend
    python scripts/crawl_dgtourcard.py

결과물: backend/app/data/dgtourcard_policies.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("httpx가 설치되어 있지 않습니다. pip install httpx", file=sys.stderr)
    sys.exit(1)

DEFAULT_BASE_URL = "https://korean.visitkorea.or.kr"
DEFAULT_TARGET_PATH = "/dgtourcard/tour50.do"
DEFAULT_TARGET_URL = f"{DEFAULT_BASE_URL}{DEFAULT_TARGET_PATH}"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "dgtourcard_policies.json"
DEFAULT_DEADLINE = "2026-12-31"
DEFAULT_EXISTING_SLUGS: tuple[str, ...] = ()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 지역명 → slug 접미사
REGION_CODE: dict[str, str] = {
    "서울": "seoul",
    "부산": "busan",
    "대구": "daegu",
    "인천": "incheon",
    "광주": "gwangju",
    "대전": "daejeon",
    "울산": "ulsan",
    "세종": "sejong",
    "경기": "gyeonggi",
    "강원": "gangwon",
    "충북": "chungbuk",
    "충남": "chungnam",
    "전북": "jeonbuk",
    "전남": "jeonnam",
    "경북": "gyeongbuk",
    "경남": "gyeongnam",
    "제주": "jeju",
    "전국": "nation",
}

# 카테고리 매핑 (허용값: "교통" | "숙박" | "여행상품" | "지역할인" | "이벤트" | "기타")
CATEGORY_MAP: dict[str, str] = {
    "할인": "지역할인",
    "숙박": "숙박",
    "캐시백": "지역할인",
    "환급": "지역할인",
    "체험": "여행상품",
    "식음": "여행상품",
    "교통": "교통",
    "관광": "여행상품",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def make_slug(region: str, title: str) -> str:
    region_code = REGION_CODE.get(region, slugify(region[:2]))
    title_slug = slugify(title)[:30].strip("-")
    return f"dgtour-{region_code}-{title_slug}"


def guess_category(text: str) -> str:
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in text:
            return cat
    return "지역할인"


class TableParser(HTMLParser):
    """간단한 테이블 파서. 텍스트 노드를 수집한다."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current: list[str] = []
        self._cell: list[str] = []
        self._in_cell = False
        self._in_table = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
        if self._in_table and tag in ("td", "th"):
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._current:
                self.rows.append(self._current)
            self._current = []
            self._in_table = False
        if self._in_table and tag in ("td", "th"):
            self._current.append(" ".join(self._cell).strip())
            self._in_cell = False
        if self._in_table and tag == "tr":
            if any(c.strip() for c in self._current):
                self.rows.append(self._current)
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            cleaned = data.strip()
            if cleaned:
                self._cell.append(cleaned)


_FUNC_DETAIL_RE = re.compile(r"func_go_detail\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)")

# data-signgucd 앞 2자리 → 시도 코드 (행정구역 표준 코드)
SIGNGU_PREFIX_PROVINCE: dict[str, str] = {
    "11": "서울",
    "26": "부산",
    "27": "대구",
    "28": "인천",
    "29": "광주",
    "30": "대전",
    "31": "울산",
    "36": "세종",
    "41": "경기",
    "43": "충북",
    "44": "충남",
    "46": "전남",
    "47": "경북",
    "48": "경남",
    "50": "제주",
    "51": "강원",
    "52": "전북",
}

# <a href="javascript:func_go_detail('도시','id')" ... data-signgucd='NNNNN' ...>도시<span>상태</span></a>
_MAP_ENTRY_RE = re.compile(
    r"func_go_detail\('([^']+)',\s*'(\d+)'\)[^>]*?data-signgucd='(\d{5})'",
    re.DOTALL,
)


def extract_map_entries(html: str) -> list[dict[str, str]]:
    """지도 기반 페이지에서 func_go_detail 링크와 행정구역 코드를 추출한다."""
    entries = []
    seen: set[str] = set()
    for m in _MAP_ENTRY_RE.finditer(html):
        city = m.group(1).strip()
        entry_id = m.group(2).strip()
        signgucd = m.group(3).strip()
        province = SIGNGU_PREFIX_PROVINCE.get(signgucd[:2], city)
        key = f"{city}:{entry_id}"
        if key not in seen:
            seen.add(key)
            entries.append({"city": city, "id": entry_id, "province": province})
    return entries


def fetch(url: str, client: httpx.Client) -> str:
    resp = client.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_policies_from_html(html: str, *, target_url: str = DEFAULT_TARGET_URL) -> list[dict[str, Any]]:
    """HTML에서 정책 목록을 추출한다. func_go_detail → 테이블 순으로 시도."""
    policies: list[dict[str, Any]] = []

    map_entries = extract_map_entries(html)

    if map_entries:
        print(f"  지도 링크 파싱: {len(map_entries)}개 항목 발견")
        for entry in map_entries:
            city = entry["city"]
            province = entry["province"]
            # 광역시도명이 REGION_CODE에 없으면 city 자체를 region으로 사용
            region = next(
                (r for r in REGION_CODE if r in province or province in r), province
            )
            title = f"{city} 디지털관광주민증 혜택"
            policy = _make_policy_dict(
                title=title,
                org="한국관광공사",
                region=region,
                amount="혜택 제공",
                summary=f"디지털관광주민증 소지자 대상 {city}({province}) 지역 방문 시 혜택을 제공합니다.",
                url=target_url,
            )
            policy["slug"] = f"dgtour-{slugify(city)}-{entry['id']}"
            policies.append(policy)
    else:
        table_parser = TableParser()
        table_parser.feed(html)
        print(f"  테이블 파싱: {len(table_parser.rows)}개 행 발견")
        for row in table_parser.rows:
            if len(row) < 2:
                continue
            title = row[0]
            if not title or len(title) < 2:
                continue
            region = next(
                (r for r in REGION_CODE if any(r in cell for cell in row)),
                "전국",
            )
            amount = next(
                (cell for cell in row if re.search(r"[\d%만원]", cell)),
                "혜택 제공",
            )
            policies.append(
                _make_policy_dict(
                    title=title,
                    org="한국관광공사",
                    region=region,
                    amount=amount,
                    summary=" ".join(row[:3])[:100],
                    url=target_url,
                )
            )

    return policies


def _make_policy_dict(
    *,
    title: str,
    org: str,
    region: str,
    amount: str,
    summary: str,
    url: str,
) -> dict[str, Any]:
    slug = make_slug(region, title)
    category = guess_category(amount + summary)
    return {
        "slug": slug,
        "title": title,
        "org": org,
        "region": region,
        "deadline": DEFAULT_DEADLINE,
        "amount": amount,
        "summary": summary,
        "match": 75,
        "category": category,
        "requirements": ["디지털관광주민증 발급자", f"{region} 방문"],
        "documents": ["디지털관광주민증"],
        "officialUrl": url or DEFAULT_TARGET_URL,
        "applyUrl": None,
    }


def deduplicate(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for p in policies:
        slug = p["slug"]
        if slug in seen:
            i = 2
            while f"{slug}-{i}" in seen:
                i += 1
            slug = f"{slug}-{i}"
            p["slug"] = slug
        seen.add(slug)
        result.append(p)
    return result


def _fallback_policies(*, target_url: str = DEFAULT_TARGET_URL) -> list[dict[str, Any]]:
    """
    JavaScript 렌더링이나 파싱 실패 시 반환할 기본 정책 목록.
    디지털관광주민증 프로그램의 대표적인 지역 혜택 기준으로 작성.
    실제 사이트 확인 후 내용을 보완해야 한다.
    """
    base = [
        {
            "region": "제주",
            "title": "제주 디지털관광주민증 혜택",
            "amount": "숙박·교통·체험 최대 30% 할인",
            "summary": "디지털관광주민증 소지자 대상 제주 방문 시 숙박, 교통, 체험 시설 할인 혜택을 제공합니다.",
        },
        {
            "region": "강원",
            "title": "강원 디지털관광주민증 혜택",
            "amount": "강원 관광지 입장료 할인",
            "summary": "디지털관광주민증 소지자 대상 강원 주요 관광지 입장료 및 체험 프로그램 할인 혜택을 제공합니다.",
        },
        {
            "region": "경북",
            "title": "경북 디지털관광주민증 혜택",
            "amount": "경북 숙박·식음 할인",
            "summary": "디지털관광주민증 소지자 대상 경북 지역 숙박 및 식음료 업소 할인 혜택을 제공합니다.",
        },
        {
            "region": "전남",
            "title": "전남 디지털관광주민증 혜택",
            "amount": "전남 관광 패키지 할인",
            "summary": "디지털관광주민증 소지자 대상 전남 권역 관광 패키지 및 체험 프로그램 할인 혜택을 제공합니다.",
        },
        {
            "region": "경남",
            "title": "경남 디지털관광주민증 혜택",
            "amount": "경남 숙박 할인",
            "summary": "디지털관광주민증 소지자 대상 경남 지역 숙박 시설 할인 혜택을 제공합니다.",
        },
        {
            "region": "충남",
            "title": "충남 디지털관광주민증 혜택",
            "amount": "충남 관광지 무료 입장",
            "summary": "디지털관광주민증 소지자 대상 충남 주요 관광지 무료 또는 할인 입장 혜택을 제공합니다.",
        },
        {
            "region": "전북",
            "title": "전북 디지털관광주민증 혜택",
            "amount": "전북 체험·숙박 할인",
            "summary": "디지털관광주민증 소지자 대상 전북 지역 체험 프로그램 및 숙박 시설 할인 혜택을 제공합니다.",
        },
        {
            "region": "부산",
            "title": "부산 디지털관광주민증 혜택",
            "amount": "부산 관광 할인권 제공",
            "summary": "디지털관광주민증 소지자 대상 부산 지역 관광 명소 및 체험 시설 할인 혜택을 제공합니다.",
        },
    ]
    policies: list[dict[str, Any]] = []
    for item in base:
        policies.append(
            _make_policy_dict(
                title=item["title"],
                org="한국관광공사",
                region=item["region"],
                amount=item["amount"],
                summary=item["summary"],
                url=target_url,
            )
        )
    return deduplicate(policies)


def crawl(*, target_url: str = DEFAULT_TARGET_URL) -> list[dict[str, Any]]:
    print(f"대상 URL: {target_url}")
    with httpx.Client() as client:
        print("페이지 요청 중...")
        try:
            html = fetch(target_url, client)
        except httpx.HTTPError as e:
            print(f"HTTP 오류: {e}", file=sys.stderr)
            print("폴백 정책 데이터를 사용합니다.", file=sys.stderr)
            return _fallback_policies(target_url=target_url)

        print(f"  응답 수신: {len(html):,} 바이트")

        # JavaScript-only 페이지 감지
        if len(html) < 3000 or html.count("<") < 30:
            print(
                "  경고: 페이지 내용이 너무 적습니다. JavaScript 렌더링이 필요할 수 있습니다.",
                file=sys.stderr,
            )
            print("  폴백 정책 데이터를 사용합니다.", file=sys.stderr)
            return _fallback_policies(target_url=target_url)

        print("HTML 파싱 중...")
        policies = parse_policies_from_html(html, target_url=target_url)

        if not policies:
            print(
                "  경고: 자동 파싱으로 정책을 찾지 못했습니다. 폴백 데이터를 사용합니다.",
                file=sys.stderr,
            )
            return _fallback_policies(target_url=target_url)

        return deduplicate(policies)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="디지털관광주민증 정책 데이터를 수집합니다.")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="수집할 한국관광공사 페이지 URL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="정책 JSON 저장 경로")
    parser.add_argument("--existing-slug", action="append", default=list(DEFAULT_EXISTING_SLUGS), help="충돌을 확인할 기존 seed slug. 여러 번 지정할 수 있습니다.")
    parser.add_argument("--debug", action="store_true", help="첫 번째 정책 미리보기를 출력합니다.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    policies = crawl(target_url=str(args.target_url))
    print(f"\n총 {len(policies)}개 정책 수집됨.")

    if args.debug:
        print("\n--- 첫 번째 정책 미리보기 ---")
        if policies:
            print(json.dumps(policies[0], ensure_ascii=False, indent=2))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {args.output}")

    # slug 중복 확인
    slugs = [p["slug"] for p in policies]
    if len(slugs) != len(set(slugs)):
        print("경고: slug 중복이 있습니다!", file=sys.stderr)

    # 기존 seed slug와 충돌 확인
    existing_slugs = set(args.existing_slug)
    conflicts = existing_slugs & set(slugs)
    if conflicts:
        print(f"경고: 기존 seed slug와 충돌: {conflicts}", file=sys.stderr)

    print("\n다음 단계:")
    print("  python -m app.db.seed   # DB에 반영")
    print("  python -m pytest tests/test_policy_db_service.py -v")


if __name__ == "__main__":
    main()
