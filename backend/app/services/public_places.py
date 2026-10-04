"""우리 장소 기반(카카오 운영정책 2단계) - 공공데이터 장소를 받아 두고, 고른 카카오 장소와 서버 안에서 맞춰 본다.

설계: docs/superpowers/specs/2026-10-03-public-place-storage-design.md. 카카오 값(장소명 · 주소 · 좌표)은 맞춰 볼 때 메모리에서만
견주고 버린다 - 저장하거나 로그에 남기지 않고, 외부(공공 API 포함)로 보내지 않는다. 공공데이터는 TourAPI 6개 유형(주 1회 동기화)과
소상공인 상가정보의 음식 · 숙박 · 예술·스포츠(분기 파일)다. 이름 비교 · 반경은 2026-10-03 실측(366곳)과 같은 기준이다.
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
import zipfile
from collections.abc import Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import PublicPlace
from app.repositories.public_places import (
    count_public_places_by,
    get_sync_state,
    prune_public_places,
    public_places_in_box,
    record_sync_state,
    upsert_public_places,
)
from app.services.place_search import resolve_city, resolve_region
from app.services.tour_api import TourApiConfigurationError, TourApiPage

logger = logging.getLogger(__name__)

TOURAPI = "tourapi"
SANGGA = "sangga"
# TourAPI contentTypeId → 우리 분류. 25(여행코스)는 장소가 아니라 받지 않는다
TOURAPI_CONTENT_TYPES = {"12": "sight", "14": "culture", "28": "leisure", "32": "stay", "38": "shopping", "39": "food"}
TOURAPI_CAFE_CAT3 = "A05020900"   # 음식점 > 카페/전통찻집
# 상가정보 대분류 음식 · 숙박 · 예술·스포츠만 - 소매 · 교육 · 부동산 등은 넣지 않는다
SANGGA_MAJOR_CATEGORIES = {"I2": "food", "I1": "stay", "R1": "leisure"}
SANGGA_MIDDLE_CATEGORIES = {"I212": "cafe", "R102": "culture"}   # 비알코올(카페) · 도서관·사적지
_NAME_NOISE = re.compile(r"[\s\-·・()\[\]{}<>.,'\"/&+_~!?:;|]+")


def name_key(name: str | None) -> str:
    """비교용 이름 - 소문자로 바꾸고 띄어쓰기 · 기호를 뺀다(실측과 같은 규칙)."""

    return _NAME_NOISE.sub("", (name or "").lower())


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 점 사이 거리(m) - 수 km 안에서 쓰는 평면 근사(실측과 같다)."""

    rad = math.pi / 180
    x = (lng2 - lng1) * rad * math.cos((lat1 + lat2) / 2 * rad)
    y = (lat2 - lat1) * rad
    return 6_371_000 * math.hypot(x, y)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _in_korea(latitude: float, longitude: float) -> bool:
    return 33.0 <= latitude <= 39.0 and 124.0 <= longitude <= 132.0


def _float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _region_city(first: str, second: str) -> tuple[str | None, str | None]:
    """주소 첫 · 둘째 낱말 → 지도 도 · 시군(통합 검색과 같은 규칙). 104만 행이라 같은 쌍은 한 번만 푼다."""

    return resolve_region(first, second), (resolve_city(second) if second else None)


def tourapi_row(entry: dict[str, Any], synced_at: datetime) -> dict[str, object] | None:
    """TourAPI 목록 항목 하나 → public_places 행. 장소가 아니거나 ID · 좌표가 없으면 None."""

    content_id = str(entry.get("contentid") or "").strip()
    category = TOURAPI_CONTENT_TYPES.get(str(entry.get("contenttypeid") or "").strip())
    title = str(entry.get("title") or "").strip()
    latitude, longitude = _float(entry.get("mapy")), _float(entry.get("mapx"))
    if not content_id or not category or not title or latitude is None or longitude is None:
        return None
    if not _in_korea(latitude, longitude):
        return None
    if category == "food" and entry.get("cat3") == TOURAPI_CAFE_CAT3:
        category = "cafe"
    address = str(entry.get("addr1") or "").strip() or None
    words = (address or "").split()
    sido, city = _region_city(*(words + ["", ""])[:2])
    photo = str(entry.get("firstimage") or "").strip() or None
    return {
        "source": TOURAPI,
        "source_id": content_id,
        "name": title[:200],
        "name_key": name_key(title)[:200],
        "address": address[:300] if address else None,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "sido": sido,
        "city": city,
        "photo_url": photo[:500] if photo else None,
        "photo_license": (str(entry.get("cpyrhtDivCd") or "").strip() or None) if photo else None,
        "synced_at": synced_at,
    }


def sangga_row(row: dict[str, str], synced_at: datetime) -> dict[str, object] | None:
    """상가정보 CSV 한 줄 → public_places 행. 여행 업종이 아니거나 번호 · 좌표가 없으면 None."""

    category = SANGGA_MAJOR_CATEGORIES.get((row.get("상권업종대분류코드") or "").strip())
    store_id = (row.get("상가업소번호") or "").strip()
    name = (row.get("상호명") or "").strip()
    latitude, longitude = _float(row.get("위도")), _float(row.get("경도"))
    if not category or not store_id or not name or latitude is None or longitude is None:
        return None
    if not _in_korea(latitude, longitude):
        return None
    category = SANGGA_MIDDLE_CATEGORIES.get((row.get("상권업종중분류코드") or "").strip(), category)
    branch = (row.get("지점명") or "").strip()
    full = f"{name} {branch}" if branch else name
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    sido, city = _region_city((row.get("시도명") or "").strip(), (row.get("시군구명") or "").strip())
    return {
        "source": SANGGA,
        "source_id": store_id,
        "name": full[:200],
        "name_key": name_key(full)[:200],
        "address": address[:300] if address else None,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "sido": sido,
        "city": city,
        "photo_url": None,
        "photo_license": None,
        "synced_at": synced_at,
    }


TOURAPI_PAGE_ROWS = 1000
TOURAPI_TIMEOUT_SECONDS = 60.0   # 1,000건 한 페이지는 기본 5초를 넘길 때가 있다
TOURAPI_SYNC_DAYS = 7   # 마지막 성공 날짜(KST)에서 이만큼 지나면 다시 받는다
# TourAPI 유형 → 그 유형이 만드는 분류(유형별로 지울 때 쓴다 - 카페는 음식점 유형에서만 나온다)
TOURAPI_TYPE_CATEGORIES = {
    "12": ("sight",), "14": ("culture",), "28": ("leisure",), "32": ("stay",), "38": ("shopping",), "39": ("food", "cafe"),
}
KST_OFFSET = timedelta(hours=9)   # 자동 동기화의 '오늘'과 RUN_AT 은 KST 로 본다
UPSERT_BATCH = 1000
# 단위(TourAPI 유형 · 상가정보 시도)의 이번 고유 행이 기존의 80% 미만이면 그 단위는 지우지 않는다
PRUNE_MIN_RATIO = 0.8


class TourApiPageSource(Protocol):
    def list_area_based_page(
        self, *, content_type_id: str, page: int, rows: int, timeout: float | None = None
    ) -> TourApiPage: ...


@dataclass(frozen=True)
class PublicPlacesLoadResult:
    source: str
    received_count: int   # 받은 원본 항목(TourAPI 항목 · 상가정보 줄)
    parsed_count: int     # 이번 실행에서 넣거나 고친 고유 행
    skipped_count: int    # 넣지 않은 항목 - ID · 좌표 없음, 다른 업종
    pruned_count: int     # 지운 오래된 행
    outcome: str          # success · partial(못 지운 단위가 있음) · skipped(때가 아님 · 꺼짐) · error
    # 지우지 못한 단위와 까닭 - 운영자가 보는 한 줄. '39:10000->7000'(끝까지 받았지만 80% 미만 - 확인되면 --accept-shrink 39),
    # '39:incomplete'(끝까지 못 받음), '세종:missing'(판에 그 시도 파일이 없음)
    kept: tuple[str, ...] = ()


def _write(db: Session, rows: Sequence[dict[str, object]]) -> None:
    """묶음마다 확정한다 - 도중에 실패해도 넣은 묶음은 남는다. 지우기는 끝까지 받은 뒤에만 한다."""

    for start in range(0, len(rows), UPSERT_BATCH):
        upsert_public_places(db, rows[start:start + UPSERT_BATCH])
        db.commit()


def _written_since(db: Session, *, source: str, since: datetime) -> int:
    return sum(count_public_places_by(db, source=source, column="category", since=since).values())


def _unit_passes(before: int, touched: int) -> bool:
    """단위(TourAPI 유형 · 상가정보 시도)의 이번 고유 행이 기존의 80% 이상인가 - 기존이 없으면 통과."""

    return not before or touched >= before * PRUNE_MIN_RATIO


def _failure_reason(exc: Exception) -> str:
    """상태 표에 남길 짧은 이유 - TourAPI 오류 문구는 키를 빼고 만들어져 있다. 그 밖은 예외 이름만(값이 섞이지 않게)."""

    return str(exc)[:300] if isinstance(exc, TourApiConfigurationError) else type(exc).__name__


def _start_run(db: Session, *, source: str, started: datetime) -> None:
    """첫 호출 · 첫 줄 전에 시도를 남기고 확정한다 - 도중에 죽거나 앱을 다시 띄워도 그날은 다시 하지 않게."""

    record_sync_state(db, source=source, attempted_at=started, outcome="running")
    db.commit()


def _record_failure(db: Session, *, source: str, started: datetime, received: int, exc: Exception) -> None:
    try:
        record_sync_state(
            db, source=source, attempted_at=started, outcome="error", received=received,
            written=_written_since(db, source=source, since=started), error=_failure_reason(exc),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("public_places_sync_state_not_saved source=%s", source)


def _close_run(
    db: Session, *, source: str, started: datetime, received: int, skipped: int, pruned: int, outcome: str,
    kept: tuple[str, ...] = (),
) -> PublicPlacesLoadResult:
    written = _written_since(db, source=source, since=started)
    if outcome == "success" and written == 0:
        outcome = "partial"   # 한 건도 못 썼다 - 깨끗한 성공처럼 보이면 안 된다
    record_sync_state(
        db, source=source, attempted_at=started, outcome=outcome, received=received, written=written, pruned=pruned,
    )
    db.commit()
    return PublicPlacesLoadResult(source, received, written, skipped, pruned, outcome, kept)


def _judge_units(
    source: str, units: dict[str, tuple[int, int]], incomplete: Collection[str], accept_shrink: Collection[str]
) -> tuple[list[str], list[str]]:
    """단위마다 지워도 되는지 - (통과한 단위, 지우지 못한 단위와 까닭). 끝까지 받지 못한 단위는 받아들여도 지우지 않는다.
    80% 미만이어도 운영자가 원인을 확인해 받아들인 단위(accept_shrink)는 지운다. units 는 단위 → (기존 고유 행, 이번 고유 행)."""

    passed: list[str] = []
    kept: list[str] = []
    accepted: list[str] = []
    for unit, (unit_before, unit_now) in units.items():
        if unit in incomplete:
            kept.append(f"{unit}:incomplete")
        elif _unit_passes(unit_before, unit_now):
            passed.append(unit)
        elif unit in accept_shrink:
            passed.append(unit)
            accepted.append(f"{unit}:{unit_before}->{unit_now}")
        else:
            kept.append(f"{unit}:{unit_before}->{unit_now}")
    if accepted:
        logger.warning("public_places_shrink_accepted source=%s units=%s", source, ",".join(accepted))
    return passed, kept


def sync_tourapi_places(
    db: Session, client: TourApiPageSource, *, now: datetime, accept_shrink: Collection[str] = ()
) -> PublicPlacesLoadResult:
    """TourAPI 6개 유형 전국 목록을 다시 받는다(약 50회 호출). 유형마다 첫 페이지 totalCount 만큼 페이지를 받고, 그 유형을
    끝까지 받았는지(페이지마다 totalCount 가 같고, 받은 항목 · 고유 contentid 가 totalCount 와 정확히 같고, 이번 고유 행이 기존의
    80% 이상) 본 뒤 통과한 유형의 오래된 행만 지운다. 도중에 실패하면 상태를 error 로 남기고 예외를 올린다 - 지운 행은 없다.
    accept_shrink 는 운영자가 원인을 확인한 유형(contentTypeId) - 끝까지 받았으면 80% 기준 없이 지운다(손 스크립트만 쓴다)."""

    before = count_public_places_by(db, source=TOURAPI, column="category")
    _start_run(db, source=TOURAPI, started=now)
    received = skipped = 0
    complete_types: list[str] = []
    try:
        for content_type_id in TOURAPI_CONTENT_TYPES:
            first = client.list_area_based_page(
                content_type_id=content_type_id, page=1, rows=TOURAPI_PAGE_ROWS, timeout=TOURAPI_TIMEOUT_SECONDS
            )
            entries = 0
            ids: set[str] = set()
            consistent = True
            for number in range(1, max(1, math.ceil(first.total_count / TOURAPI_PAGE_ROWS)) + 1):
                page = first if number == 1 else client.list_area_based_page(
                    content_type_id=content_type_id, page=number, rows=TOURAPI_PAGE_ROWS, timeout=TOURAPI_TIMEOUT_SECONDS
                )
                consistent = consistent and page.total_count == first.total_count
                rows = [row for row in (tourapi_row(entry, now) for entry in page.items) if row is not None]
                entries += len(page.items)
                received += len(page.items)   # 페이지마다 누적 - 도중에 실패해도 받은 만큼 남는다
                skipped += len(page.items) - len(rows)
                ids.update(str(entry.get("contentid") or "").strip() for entry in page.items)
                _write(db, rows)
            ids.discard("")
            if consistent and entries == first.total_count and len(ids) == first.total_count:
                complete_types.append(content_type_id)
    except Exception as exc:
        db.rollback()
        _record_failure(db, source=TOURAPI, started=now, received=received, exc=exc)
        raise
    touched = count_public_places_by(db, source=TOURAPI, column="category", since=now)
    units = {
        content_type_id: (sum(before.get(c, 0) for c in categories), sum(touched.get(c, 0) for c in categories))
        for content_type_id, categories in TOURAPI_TYPE_CATEGORIES.items()
    }
    passed, kept = _judge_units(TOURAPI, units, set(TOURAPI_CONTENT_TYPES) - set(complete_types), accept_shrink)
    if kept:
        logger.warning("public_places_prune_limited source=tourapi kept=%s", ",".join(kept))
    pruned = prune_public_places(
        db, source=TOURAPI, synced_before=now,
        categories=[category for content_type_id in passed for category in TOURAPI_TYPE_CATEGORIES[content_type_id]],
    )
    outcome = "partial" if kept else "success"
    return _close_run(
        db, source=TOURAPI, started=now, received=received, skipped=skipped, pruned=pruned, outcome=outcome, kept=tuple(kept),
    )


def tourapi_sync_due(db: Session, *, now: datetime, run_at: time) -> bool:
    """자동 동기화를 지금 돌릴 때인가 - KST 로 RUN_AT 뒤이고, 오늘(KST) 아직 시도하지 않았고, 마지막 성공 날짜(KST)에서 7일이
    지났을 때(날짜로 세어 매주 같은 시각에 돈다). 상태가 DB 에 있어 앱을 다시 띄워도 판단이 같다. 손으로 돌리는 스크립트는 이것을 보지 않는다."""

    local = now + KST_OFFSET
    if local.time() < run_at:
        return False
    state = get_sync_state(db, source=TOURAPI)
    if state is None:
        return True
    if (state.last_attempt_at + KST_OFFSET).date() == local.date():
        return False
    if state.last_success_at is None:
        return True
    return (local.date() - (state.last_success_at + KST_OFFSET).date()).days >= TOURAPI_SYNC_DAYS


SANGGA_ENCODING = "utf-8-sig"   # 20260630판. 판이 바뀌어 cp949 면 읽다 멈춘다 - 넣은 묶음만 남고 지운 행은 없다


def iter_sangga_rows(paths: Sequence[Path], *, only: str | None = None) -> Iterator[dict[str, str]]:
    """분기 파일(zip 안의 시도별 CSV, 또는 CSV)을 한 줄씩 - 1.4GB 를 메모리에 올리지 않는다. only 는 파일 이름에 든 말(예: 세종)."""

    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if not info.filename.lower().endswith(".csv") or (only and only not in info.filename):
                        continue
                    with archive.open(info) as raw:
                        yield from csv.DictReader(io.TextIOWrapper(raw, encoding=SANGGA_ENCODING, newline=""))
        elif not only or only in path.name:
            with path.open(encoding=SANGGA_ENCODING, newline="") as handle:
                yield from csv.DictReader(handle)


def load_sangga_places(
    db: Session, rows: Iterable[dict[str, str]], *, now: datetime, prune: bool = True, accept_shrink: Collection[str] = (),
) -> PublicPlacesLoadResult:
    """상가정보 한 판을 넣는다(여행 업종만). 1,000줄씩 묶어 쓰고 묶음마다 확정한다. prune=True 면 끝까지 읽은 뒤 읽은 시도마다
    이번 고유 행이 기존의 80% 이상인 시도의 오래된 행만 지운다. 읽은 시도는 여행 업종이 아닌 줄까지 포함해 정한다(0건이 된 시도도
    알아보게). DB 에 있는데 이번에 읽지 않은 시도(파일이 빠진 판)는 남기고 partial 이다. prune=False(일부 시도만)면 지우지 않는다.
    accept_shrink 는 운영자가 원인을 확인한 시도(짧은 이름) - 이번 판에서 읽었으면 80% 기준 없이 지운다. 빠진 시도는 지우지 않는다."""

    before = count_public_places_by(db, source=SANGGA, column="sido")
    _start_run(db, source=SANGGA, started=now)
    received = skipped = 0
    read_sidos: set[str] = set()
    batch: list[dict[str, object]] = []
    try:
        for raw in rows:
            received += 1
            sido, _city = _region_city((raw.get("시도명") or "").strip(), (raw.get("시군구명") or "").strip())
            if sido:
                read_sidos.add(sido)
            row = sangga_row(raw, now)
            if row is None:
                skipped += 1
                continue
            batch.append(row)
            if len(batch) >= UPSERT_BATCH:
                _write(db, batch)
                batch = []
        _write(db, batch)
    except Exception as exc:
        db.rollback()
        _record_failure(db, source=SANGGA, started=now, received=received, exc=exc)
        raise
    if not prune:
        return _close_run(db, source=SANGGA, started=now, received=received, skipped=skipped, pruned=0, outcome="partial")
    touched = count_public_places_by(db, source=SANGGA, column="sido", since=now)
    units = {sido: (before.get(sido, 0), touched.get(sido, 0)) for sido in sorted(read_sidos)}
    passed, kept = _judge_units(SANGGA, units, (), accept_shrink)
    kept = [f"{sido}:missing" for sido in sorted(sido for sido in before if sido and sido not in read_sidos)] + kept
    if kept:
        logger.warning("public_places_prune_limited source=sangga kept=%s", ",".join(kept))
    pruned = prune_public_places(db, source=SANGGA, synced_before=now, sidos=passed)
    outcome = "partial" if kept else "success"
    return _close_run(
        db, source=SANGGA, started=now, received=received, skipped=skipped, pruned=pruned, outcome=outcome, kept=tuple(kept),
    )


# 맞춰 보기 반경(2026-10-03 실측과 같은 기준): 카카오 분류가 관광명소 · 문화시설이면 TourAPI 1km, 그 밖과 상가정보는 200m
WIDE_KAKAO_CATEGORIES = frozenset({"AT4", "CT1"})
WIDE_RADIUS_M = 1000
NEAR_RADIUS_M = 200
# 고른 카카오 분류와 맞는 공공데이터 분류. 분류가 없거나 이 다섯 코드가 아니면 맞는지 알 수 없으므로 바로 담지 않고 후보로 보인다
KAKAO_TO_PUBLIC_CATEGORIES = {
    "AT4": frozenset({"sight", "culture", "leisure", "shopping"}),
    "CT1": frozenset({"culture", "sight", "leisure"}),
    "FD6": frozenset({"food", "cafe"}),
    "CE7": frozenset({"cafe", "food"}),
    "AD5": frozenset({"stay"}),
}
MAX_CANDIDATES = 3
METERS_PER_DEGREE = 6_371_000 * math.pi / 180   # distance_m 과 같은 지구 반경(약 111,195m)
BOX_MARGIN = 1.01   # 상자가 반경 안쪽 끝을 놓치지 않게 조금 넓게


@dataclass(frozen=True)
class PlaceMatch:
    result: str   # match · candidates · none
    places: list[tuple[PublicPlace, float]]


def _fits(category_code: str | None, place: PublicPlace) -> bool:
    allowed = KAKAO_TO_PUBLIC_CATEGORIES.get(category_code or "")
    return allowed is not None and place.category in allowed


def match_place(
    db: Session, *, name: str, latitude: float, longitude: float, category_code: str | None
) -> PlaceMatch:
    """고른 카카오 장소의 이름 · 좌표를 우리 장소 기반과 견준다. 받은 값은 이 함수 안에서만 쓰고 버린다(저장 · 로그 금지).
    바로 담기는 이름이 같은 곳이 반경 안에 하나뿐이고 분류가 맞을 때만 - 두 출처에 같은 이름이 있으면 둘로 센다."""

    key = name_key(name)
    if not key:
        return PlaceMatch("none", [])
    tour_radius = WIDE_RADIUS_M if category_code in WIDE_KAKAO_CATEGORIES else NEAR_RADIUS_M
    dlat = max(tour_radius, NEAR_RADIUS_M) * BOX_MARGIN / METERS_PER_DEGREE
    dlng = dlat / math.cos(math.radians(latitude + dlat))   # 상자 북쪽 끝의 좁은 경도까지 덮는다
    near: list[tuple[PublicPlace, float]] = []
    for place in public_places_in_box(
        db, south=latitude - dlat, north=latitude + dlat, west=longitude - dlng, east=longitude + dlng
    ):
        distance = distance_m(latitude, longitude, place.latitude, place.longitude)
        if distance <= (tour_radius if place.source == TOURAPI else NEAR_RADIUS_M):
            near.append((place, distance))
    near.sort(key=lambda pair: pair[1])
    exact = [pair for pair in near if pair[0].name_key == key]
    if exact:
        if len(exact) == 1 and _fits(category_code, exact[0][0]):
            return PlaceMatch("match", exact)
        return PlaceMatch("candidates", exact[:MAX_CANDIDATES])
    if len(key) >= 2:
        loose = [pair for pair in near if len(pair[0].name_key) >= 2 and (key in pair[0].name_key or pair[0].name_key in key)]
        if loose:
            return PlaceMatch("candidates", loose[:MAX_CANDIDATES])
    return PlaceMatch("none", [])


def public_place_item(place: PublicPlace, distance: float) -> dict[str, object]:
    return {
        "source": place.source,
        "sourceId": place.source_id,
        "name": place.name,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "category": place.category,
        "sido": place.sido,
        "city": place.city,
        "photoUrl": place.photo_url,
        "photoLicense": place.photo_license,
        "distanceMeters": round(distance),
    }


def match_place_response(
    db: Session, *, name: str, latitude: float, longitude: float, category_code: str | None
) -> dict[str, object]:
    found = match_place(db, name=name, latitude=latitude, longitude=longitude, category_code=category_code)
    return {"result": found.result, "places": [public_place_item(place, distance) for place, distance in found.places]}
