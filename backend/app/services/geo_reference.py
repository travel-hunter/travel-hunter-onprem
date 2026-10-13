"""건물 · 땅 지번(국토교통부 GIS건물통합정보 · 연속지적도) - 방식1 '주소 채움'의 공공데이터 규칙(순수 함수).

카카오 좌표 · 지도에서 찍은 좌표는 맞춰 보는 동안만 쓰고 버린다(데브톡 151505-1 · 151842). 일정에 담는 주소 · 좌표는 이 표의 값뿐이다.
계획: docs/superpowers/plans/2026-10-07-place-add-address-fill.md 0절.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

GeoKind = Literal["building", "parcel"]
TABLES = ("building", "parcel")
DATASET_OF = {"building": "D010", "parcel": "D002"}   # 브이월드 데이터셋 번호: 건물 D010 · 연속지적도 D002 - 파일 이름에 들어 있다
PARCEL_GATE_M = 30   # 땅 중심이 고른 자리에서 이만큼 안일 때만 핀까지 채운다(2026-10-07 사용자 결정, 248줄 실측 89%)
EXCLUDED_JIMOK = frozenset({"전", "답", "과", "목", "임"})   # 적재하지 않는 지목 - 농지 · 임야(10/7 결정, 땅 크기 49%, 자동 88%)
# 브이월드 전체데이터의 시도 코드(2026-09 판). 전남 · 광주는 2026-07 부터 통합 코드 12, 강원 51 · 전북 52. 바뀌면 여기와 운영 문서를 함께 고친다
EXPECTED_REGION_CODES = frozenset({"11", "12", "26", "27", "28", "30", "31", "36", "41", "43", "44", "47", "48", "50", "51", "52"})
# 판마다 행 수 범위(2026-09 판 전국 실측: 건물 14,392,125 · 땅 농지 · 임야 뺀 19,406,867 - 둘 다 약 ±15% 안)
ROW_BOUNDS = {"building": (12_000_000, 17_000_000), "parcel": (16_000_000, 23_000_000)}
MAX_DUP_RATIO = {"building": 0.02, "parcel": 0.01}   # 같은 feature_key 비율(전국 실측 건물 0.60% - 한 건물 여러 도형, 땅 0%)
MAX_MISSING_KEY_RATIO = 0.001   # 고유번호가 19자리 숫자가 아니거나 식별자(건물 A1)가 빈 줄 - 넣지 않고 센다(전국 실측 건물 1줄 · 땅 0줄)
MAX_UNKNOWN_JIMOK_RATIO = 0.01   # 지목을 읽지 못한 땅 - 넣되 센다(전국 실측 0.023%). 넘으면 농지 · 임야 거르기를 믿을 수 없다
MAX_UNNAMED_DONG_RATIO = 0.01   # 법정동코드가 두 데이터 어디에도 이름이 없는 줄(읽은 줄 대비) - 2026-09 전국 건물 45,515줄 = 0.32%. 그 자리는 땅 레이어가 현행 코드로 덮는다. 적재에서 빼고 센다
# 지목 약식 부호 28개와 정식 이름 - 땅 지번 칸은 대개 약식('203-24전')이지만 약 2,300줄은 정식 이름('12임야' · '5과수원')이다(전국 실측).
# 정식 이름도 부호로 바꿔야 농지 · 임야 거르기를 빠져나가지 않는다. 둘 다 아니면(겹친 글자 · 깨진 글자) 못 읽음으로 센다
JIMOK_CODES = frozenset("전답과목임광염대장학차주창도철제천구유양수공체원종사묘잡")
JIMOK_NAMES = {
    "과수원": "과", "과수": "과", "목장용지": "목", "목장용": "목", "목장": "목", "임야": "임", "광천지": "광", "염전": "염", "대지": "대",
    "공장용지": "장", "공장용": "장", "학교용지": "학", "주차장": "차", "주유소용지": "주", "창고용지": "창", "창고용": "창", "도로": "도",
    "철도용지": "철", "제방": "제", "하천": "천", "구거": "구", "유지": "유", "양어장": "양", "수도용지": "수", "수도용": "수", "공원": "공",
    "체육용지": "체", "유원지": "원", "종교용지": "종", "사적지": "사", "묘지": "묘", "잡종지": "잡",
}
GEO_SOURCE_NOTICE = "국토교통부 공공데이터"   # 화면 출처 표시(GIS건물통합정보 공공누리 1유형 · 연속지적도 CC BY)
_PNU = re.compile(r"[0-9]{19}")   # fullmatch - `^\d{19}$` 는 끝의 줄바꿈과 전각 · 다른 문자 체계의 숫자도 받는다
_JIMOK = re.compile(r"([가-힣]+)\s*$")
_SOURCE = re.compile(r"AL_(D0(?:10|02))_([0-9]{2})_([0-9]{8})(?:\(([0-9]+)\))?\.shp", re.ASCII | re.IGNORECASE)   # fullmatch
_MAX_KEY_LEN = 40   # geo.* feature_key varchar(40), 전국 실측 최대 28
_NOT_A_KEY = frozenset({"", "none", "nan", "null"})


def _require_table(table: str) -> None:
    if table not in TABLES:
        raise ValueError(f"unknown geo table: {table}")


def is_pnu(value: object) -> bool:
    return isinstance(value, str) and bool(_PNU.fullmatch(value))


def is_feature_key(value: object) -> bool:
    # 너무 긴 값은 식별자 없는 줄로 센다 - 열을 넘어 COPY 전체가 멈추지 않게
    return isinstance(value, str) and (key := value.strip()).lower() not in _NOT_A_KEY and len(key) <= _MAX_KEY_LEN


def jibun_address(dong_name: str, pnu: str) -> str:
    """법정동 이름 + 고유번호 → 지번 주소. PNU 19자리 = 법정동코드 10 · 산 여부 1(1 일반, 2 산) · 본번 4 · 부번 4."""

    if not is_pnu(pnu):
        raise ValueError("pnu must be 19 digits")
    main, sub = int(pnu[11:15]), int(pnu[15:19])
    lot = ("산" if pnu[10] == "2" else "") + (f"{main}-{sub}" if sub else str(main))
    # 법정동 이름이 없으면(적재 검사가 막지만) 번지만 - 결과를 버려 위치 찍기로 떨어뜨리지 않는다
    return " ".join(part for part in (" ".join(dong_name.split()), lot) if part)


def jimok_of(label: str | None) -> str | None:
    """연속지적도 지번 칸('203-24전', '930 공', '12임야')의 끝 한글이 지목이다 - 약식 부호 한 글자로 돌려준다. 모르는 낱말은 None(못 읽음)."""

    match = _JIMOK.search(label or "")
    if match is None:
        return None
    word = match.group(1)
    return word if word in JIMOK_CODES else JIMOK_NAMES.get(word)


def keep_parcel(jimok: str | None) -> bool:
    return jimok not in EXCLUDED_JIMOK


@dataclass(frozen=True)
class GeoHit:
    """고른 자리를 품은 건물 · 땅 하나. id 는 이 판의 행 번호(판이 바뀌면 사라진다), 주소와 대표점은 공공데이터 값,
    distance_m 은 고른 자리에서 대표점(도형 중심, 밖이면 도형 위 한 점)까지."""

    kind: GeoKind
    id: int
    pnu: str
    address: str
    latitude: float
    longitude: float
    distance_m: float


def within_gate(hit: GeoHit) -> bool:
    return hit.kind == "building" or hit.distance_m <= PARCEL_GATE_M


def fill_item(hit: GeoHit) -> dict[str, object]:
    return {
        "kind": hit.kind,
        "id": hit.id,
        "pnu": hit.pnu,
        "address": hit.address,
        "latitude": hit.latitude,
        "longitude": hit.longitude,
        "distanceMeters": round(hit.distance_m),
    }


def swap_statements(table: str) -> list[str]:
    """월 갱신 - 새 표(*_next)와 그 색인을 한 트랜잭션 안에서 이름 바꿔치기한다. 읽는 쪽은 옛 표나 새 표 하나만 본다."""

    _require_table(table)
    indexes = ("pkey", "geom_gix", "pnu_ix")
    return (
        [f"ALTER TABLE geo.{table} RENAME TO {table}_old"]
        + [f"ALTER INDEX geo.{table}_{index} RENAME TO {table}_old_{index}" for index in indexes]
        + [f"ALTER TABLE geo.{table}_next RENAME TO {table}"]
        + [f"ALTER INDEX geo.{table}_next_{index} RENAME TO {table}_{index}" for index in indexes]
        + [f"DROP TABLE geo.{table}_old"]
    )


@dataclass(frozen=True)
class SourceFile:
    path: str
    name: str
    code: str
    base_date: str
    dataset: str   # 'D010' 건물 · 'D002' 땅 - 파일 이름에서, 대문자
    part: int | None   # '(2)' 의 2, 없으면 None


def parse_source(path: str) -> SourceFile | None:
    name = PurePosixPath(path.replace("\\", "/")).name
    match = _SOURCE.fullmatch(name)
    if match is None:
        return None
    part = int(match.group(4)) if match.group(4) else None
    return SourceFile(path, name, match.group(2), match.group(3), match.group(1).upper(), part)


def manifest_problems(files: list[str], dataset: str) -> list[str]:
    """한 데이터셋(건물 D010 또는 땅 D002, `DATASET_OF`)의 파일 목록 구조 검사 - 하나라도 있으면 적재하지 않는다(넘길 수 없다, 첫 적재에도 걸린다).
    다른 데이터셋의 파일은 `wrong dataset` 으로 막고 지역 수에 넣지 않는다 - 건물 15개 + 땅 1개가 완전한 세트로 보이지 않게."""

    if dataset not in DATASET_OF.values():
        raise ValueError(f"unknown dataset: {dataset}")
    problems: list[str] = []
    parsed = []
    for path in files:
        source = parse_source(path)
        if source is None:
            problems.append(f"unknown file name: {PurePosixPath(path.replace(chr(92), '/')).name}")
        elif source.dataset != dataset:
            problems.append(f"wrong dataset: {source.name}")
        else:
            parsed.append(source)
    codes = {source.code for source in parsed}
    if missing := sorted(EXPECTED_REGION_CODES - codes):
        problems.append(f"missing region codes: {', '.join(missing)}")
    if unexpected := sorted(codes - EXPECTED_REGION_CODES):
        problems.append(f"unexpected region codes: {', '.join(unexpected)}")
    if len(dates := sorted({source.base_date for source in parsed})) > 1:
        problems.append(f"more than one base date: {', '.join(dates)}")
    seen: set[str] = set()
    for source in parsed:
        if source.name.lower() in seen:
            problems.append(f"duplicated file: {source.name}")
        seen.add(source.name.lower())
    # '(2)' 조각은 같은 지역 · 같은 기준일의 본 파일이 세트에 있어야 한다 - 본 파일 없이 조각만 있으면 반쪽이다
    bases = {(source.code, source.base_date) for source in parsed if source.part is None}
    problems += [
        f"part file without base file: {source.name}"
        for source in parsed
        if source.part is not None and (source.code, source.base_date) not in bases
    ]
    return problems


def content_duplicate_problems(digests: dict[str, str]) -> list[str]:
    """파일 이름 → .shp 내용 지문(sha256). 지문이 같은 파일이 둘 이상이면 같은 파일을 두 번 받은 것이다(넘길 수 없다)."""

    by_digest: dict[str, list[str]] = {}
    for name, digest in digests.items():
        by_digest.setdefault(digest, []).append(name)
    return [f"same content: {', '.join(sorted(names))}" for names in by_digest.values() if len(names) > 1]


def quality_problems(table: str, rows: int, distinct_keys: int, *, missing_keys: int, unknown_jimok: int) -> list[str]:
    """적재한 줄의 품질 검사(넘길 수 없다): 같은 식별자 비율 · 식별자 빈 줄 비율 · 지목을 못 읽은 땅 비율."""

    _require_table(table)
    problems: list[str] = []
    if rows <= 0:
        problems.append(f"{table}: no rows")
    if distinct_keys > rows:
        problems.append(f"{table}: more distinct keys than rows")
    dup = 1 - distinct_keys / rows if rows > 0 else 0.0
    if dup > MAX_DUP_RATIO[table]:
        problems.append(f"{table}: duplicate feature keys {dup * 100:.1f}% > {MAX_DUP_RATIO[table] * 100:.1f}%")
    read = rows + missing_keys
    if read and missing_keys / read > MAX_MISSING_KEY_RATIO:
        problems.append(f"{table}: rows without a feature key {missing_keys / read * 100:.2f}% > {MAX_MISSING_KEY_RATIO * 100:.2f}%")
    if rows and unknown_jimok / rows > MAX_UNKNOWN_JIMOK_RATIO:
        problems.append(f"{table}: unknown land category {unknown_jimok / rows * 100:.2f}% > {MAX_UNKNOWN_JIMOK_RATIO * 100:.2f}%")
    return problems


def unnamed_dong_problems(table: str, rows: int, unnamed: int) -> list[str]:
    """법정동 이름이 어디에도 없어 적재에서 뺀 줄(unnamed)이 읽은 줄(남긴 rows + 뺀 unnamed)의 `MAX_UNNAMED_DONG_RATIO` 를 넘으면 멈춘다(넘길 수 없다)."""

    _require_table(table)
    read = rows + unnamed
    if read and unnamed / read > MAX_UNNAMED_DONG_RATIO:
        return [f"{table}: rows with an unnamed legal-dong code {unnamed / read * 100:.2f}% > {MAX_UNNAMED_DONG_RATIO * 100:.2f}%"]
    return []


def row_count_problems(table: str, rows: int) -> list[str]:
    """행 수 범위 - 판이 실제로 커지거나 줄었을 수 있어 이것만 --accept-row-count-change 로 받아들일 수 있다."""

    _require_table(table)
    low, high = ROW_BOUNDS[table]
    return [] if low <= rows <= high else [f"{table}: {rows} rows is outside {low}..{high}"]
