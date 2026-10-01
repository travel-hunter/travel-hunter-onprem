"""사진 검토(0047): 수집은 대상마다 후보만 넣고, 관리자가 한 장을 확정해야 앱 사진 줄(active)이 된다.

대상은 시군(도 전체 포함, region)과 정책(policy). 응답 쪽 해석 순서(region_photos.py: 정책 사진 → 시군 사진 →
혜택 그림)는 그대로라, 정책은 고르지 않으면 시군 사진을 물려받는다(2026-10-01 사용자 결정).

후보 줄: 그 시군(시군 코드)의 관광지 · 쇼핑 · 축제를 조회순(arrange P)으로 받아 번갈아 섞고, 수집 기준
(photo_criteria.py)을 통과한 것만. 이미 다른 대상의 후보인 사진은 건너뛴다 - 시군을 먼저 채우고 그 시군 정책을
채우므로 정책은 시군 후보 다음 사진을 받는다. '이름으로 찾기'는 관광공사 키워드 검색(분류 무관, 음식점 · 숙박 제외).
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from itertools import zip_longest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.travel_areas import normalize_municipality_name
from app.models import ExternalSourceRecord, PhotoReviewCandidate, PhotoReviewTarget, Policy, User
from app.repositories import photo_review as repository
from app.repositories.policies import list_active_policies_for_photo_backfill
from app.repositories.policy_photos import upsert_policy_photo
from app.repositories.region_photos import upsert_region_photo
from app.services.photo_criteria import ImageProbeError, attribution_for, metadata_rejections, size_rejections
from app.services.policies import _normalize_policy_category
from app.services.tour_api import TourApiAreaCode, TourApiPhotoProvider, TourApiSpot

PROVIDER = "tour_api"
WANT = 6
LIST_ROWS = 40
MORE_PAGES = 3
SEARCH_ROWS = 30
COLLECT_TYPES = ("12", "38", "15")   # 관광지 · 쇼핑(시장·거리) · 축제를 번갈아
SEARCH_EXCLUDED_TYPES = frozenset({"32", "39"})   # 숙박 · 음식점
CONTENT_TYPE_LABELS = {
    "12": "관광지", "14": "문화시설", "15": "축제", "25": "여행코스", "28": "레포츠", "38": "시장·거리",
}
# 전국 정책은 시도가 없어 지역코드로 못 찾는다 - 나라 전체를 대표하는 사진을 키워드로 찾는다
NATIONWIDE_SIDO = "전국"
NATIONWIDE_KEYWORD = "대한민국 여행"
SIDO_LEVEL_CITY = ""

# policies.region 축약형 → TourAPI 지역코드 정식명 · 주소 앞머리 후보. 강원 · 전북 개칭 때문에 단순 일치는 0장이 된다.
# 2026-10-01 실측: 전남 · 광주 관광지 주소는 모두 '전남광주통합특별시'로 시작한다 - 둘 다 받아들이고 도 구분은 지역코드로.
# 지역코드 이름 맞추기에 걸리지 않게 맨 뒤에 둔다. DB 에는 축약형만 저장한다.
_TOUR_API_SIDO_CANDIDATES: dict[str, tuple[str, ...]] = {
    "서울": ("서울특별시", "서울"),
    "부산": ("부산광역시", "부산"),
    "대구": ("대구광역시", "대구"),
    "인천": ("인천광역시", "인천"),
    "광주": ("광주광역시", "광주", "전남광주통합특별시"),
    "대전": ("대전광역시", "대전"),
    "울산": ("울산광역시", "울산"),
    "세종": ("세종특별자치시", "세종"),
    "경기": ("경기도", "경기"),
    "강원": ("강원특별자치도", "강원도", "강원"),
    "충북": ("충청북도", "충북"),
    "충남": ("충청남도", "충남"),
    "전북": ("전북특별자치도", "전라북도", "전북"),
    "전남": ("전라남도", "전남", "전남광주통합특별시"),
    "경북": ("경상북도", "경북"),
    "경남": ("경상남도", "경남"),
    "제주": ("제주특별자치도", "제주도", "제주"),
}
_TITLE_CITY_MARKER = re.compile(r"^\[([^\]]+)\]")

SizeOf = Callable[[str], "tuple[int, int] | None"]
logger = logging.getLogger(__name__)


class PhotoReviewError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---------- 지역 ----------


def resolve_area_code_for_sido(sido: str, area_codes: Sequence[TourApiAreaCode]) -> str | None:
    for candidate in _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,)):
        for area in area_codes:
            if area.name == candidate or area.name.startswith(candidate):
                return area.code
    return None


def resolve_sigungu_code(
    city: str, sigungu_codes: Sequence[TourApiAreaCode], sido: str | None = None
) -> str | None:
    """'영광' ↔ '영광군', 정책 표기 '부산동구' ↔ '동구'. 이름이 같은 시군 코드."""

    names = {city, city.removeprefix(sido or "")}
    for area in sigungu_codes:
        if names & {area.name, normalize_municipality_name(area.name), area.name[:-1]}:
            return area.code
    return None


def addr_matches_sido(addr1: str | None, sido: str) -> bool:
    if not addr1:
        return False
    return any(addr1.startswith(candidate) for candidate in _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,)))


def policy_city_hint(policy: Policy) -> str | None:
    """정규화된 시군 먼저, 없으면 제목의 [시군] 표기."""

    region = str(policy.region or "").strip()
    city = str(policy.city).strip() if policy.city else ""
    if city and city != region:
        return city
    marker = _TITLE_CITY_MARKER.match(str(policy.title).strip())
    if marker:
        city = marker.group(1).strip()
        if city and city != region:
            return city
    return None


def _norm_city(city: str | None) -> str:
    return (normalize_municipality_name(city) or city or "") if city else ""


def region_key(sido: str, city: str) -> str:
    return f"region:{sido}|{city}"


def policy_key(policy_id: int) -> str:
    return f"policy:{policy_id}"


# ---------- 후보 줄 ----------


@dataclass
class PlaceSpots:
    """한 곳(도 · 시군)의 후보 줄. 관광지 · 쇼핑 · 축제 목록을 쪽 단위로 받아 번갈아 섞는다(한 번 받은 쪽은 다시 받지 않는다)."""

    provider: TourApiPhotoProvider
    sido: str
    city: str
    area_code: str | None
    sigungu_code: str | None
    pages: list[list[TourApiSpot]] = field(default_factory=list)

    def _fetch(self, page: int) -> list[TourApiSpot]:
        if self.sido == NATIONWIDE_SIDO and not self.city:
            if page > 1:
                return []
            return self.provider.search_spots_by_keyword(keyword=NATIONWIDE_KEYWORD, rows=LIST_ROWS)
        if not self.area_code or (self.city and not self.sigungu_code):
            return []   # 시군 코드를 못 찾은 시군은 도 전체 앞쪽을 주소로 고르지 않는다 - 엉뚱한 사진이 된다
        lists = [
            self.provider.list_area_spots(
                area_code=self.area_code,
                sigungu_code=self.sigungu_code,
                rows=LIST_ROWS,
                content_type_id=type_id,
                page=page,
            )
            for type_id in COLLECT_TYPES
        ]
        return [spot for group in zip_longest(*lists) for spot in group if spot is not None]

    def spots(self, max_pages: int = 1) -> Iterator[TourApiSpot]:
        for page in range(1, max_pages + 1):
            if len(self.pages) < page:
                self.pages.append(self._fetch(page))
            if not self.pages[page - 1]:
                return
            yield from self.pages[page - 1]


class PlaceResolver:
    """도 · 시군 → 관광공사 지역코드. 한 번 물은 것은 다시 묻지 않는다."""

    def __init__(self, provider: TourApiPhotoProvider) -> None:
        self.provider = provider
        self._areas: list[TourApiAreaCode] | None = None
        self._sigungu: dict[str, list[TourApiAreaCode]] = {}
        self._places: dict[tuple[str, str], PlaceSpots] = {}

    def place(self, sido: str, city: str) -> PlaceSpots:
        key = (sido, city)
        if key not in self._places:
            area_code = sigungu_code = None
            if sido != NATIONWIDE_SIDO:
                if self._areas is None:
                    self._areas = self.provider.list_area_codes()
                area_code = resolve_area_code_for_sido(sido, self._areas)
                if area_code and city:
                    if area_code not in self._sigungu:
                        self._sigungu[area_code] = self.provider.list_area_codes(area_code=area_code)
                    sigungu_code = resolve_sigungu_code(city, self._sigungu[area_code], sido)
            self._places[key] = PlaceSpots(self.provider, sido, city, area_code, sigungu_code)
        return self._places[key]


def spot_rejections(spot: TourApiSpot, *, sido: str, size_of: SizeOf | None) -> list[str]:
    """수집 기준 + 도 일치. 앞의 것이 다 통과할 때만 사진을 받아 크기를 잰다(ImageProbeError 는 부른 쪽이 처리)."""

    reasons = metadata_rejections(title=spot.title, image_url=spot.first_image, copyright_type=spot.copyright_type)
    if sido != NATIONWIDE_SIDO and not addr_matches_sido(spot.addr1, sido):
        reasons.append("other-sido")
    if not reasons and size_of is not None and spot.first_image:
        reasons = size_rejections(size_of(spot.first_image))
    return reasons


def _candidate_fields(spot: TourApiSpot, *, size: tuple[int, int] | None, source: str, keyword: str | None = None) -> dict:
    return {
        "provider": PROVIDER,
        "provider_content_id": spot.content_id,
        "title": spot.title[:200],
        "content_type_id": spot.content_type_id,
        "image_url": spot.first_image,
        "thumbnail_url": spot.first_image2,
        "copyright_type": spot.copyright_type,
        "image_width": size[0] if size else None,
        "image_height": size[1] if size else None,
        "address": (spot.addr1 or "")[:200] or None,
        "source": source,
        "search_keyword": keyword,
    }


@dataclass
class _Probe:
    """크기를 재고 결과를 기억한다. 사진 서버에 닿지 못한 것(ImageProbeError)은 기억하지 않고 실패로 센다."""

    size_of: SizeOf | None
    sizes: dict[str, tuple[int, int] | None] = field(default_factory=dict)
    rejected: set[str] = field(default_factory=set)
    failures: int = 0

    def passes(self, spot: TourApiSpot, sido: str) -> tuple[bool, tuple[int, int] | None]:
        url = spot.first_image
        if not url or url in self.rejected:
            return False, None
        try:
            reasons = spot_rejections(spot, sido=sido, size_of=self._remember if self.size_of else None)
        except ImageProbeError:
            self.failures += 1
            return False, None
        if reasons:
            self.rejected.add(url)
            return False, None
        return True, self.sizes.get(url)

    def _remember(self, url: str) -> tuple[int, int] | None:
        if url not in self.sizes:
            self.sizes[url] = self.size_of(url)
        return self.sizes[url]


def _fill(
    db: Session,
    target: PhotoReviewTarget,
    spots: Iterable[TourApiSpot],
    *,
    want: int,
    used: set[str],
    probe: _Probe,
) -> int:
    added = 0
    for spot in spots:
        if added >= want:
            break
        if not spot.first_image or spot.first_image in used:
            continue
        ok, size = probe.passes(spot, target.sido)
        if not ok:
            continue
        repository.add_candidate(db, target, **_candidate_fields(spot, size=size, source="collect"))
        used.add(spot.first_image)
        added += 1
    return added


# ---------- 수집 ----------


def build_region_keys(pairs: Iterable[tuple[str | None, str | None]]) -> list[tuple[str, str]]:
    """(도, 시군) 쌍 → 대상 키. 시군은 이름을 맞추고, 도마다 도 전체 줄을 하나 붙인다."""

    keys: list[tuple[str, str]] = []
    sidos: list[str] = []
    for sido, city in pairs:
        if not sido:
            continue
        if sido not in sidos:
            sidos.append(sido)
        normalized = _norm_city(city)
        if normalized and (sido, normalized) not in keys:
            keys.append((sido, normalized))
    keys += [(sido, SIDO_LEVEL_CITY) for sido in sidos if (sido, SIDO_LEVEL_CITY) not in keys]
    return keys


def ensure_targets(db: Session, *, today: date | None = None) -> int:
    """활성 정책 · 수집 기록의 (도, 시군)과 공개 정책 하나하나를 검토 대상으로 둔다. 새로 만든 수."""

    by_key = {target.target_key: target for target in repository.list_all_targets(db)}
    existing = set(by_key)
    created = 0
    policy_pairs = db.execute(select(Policy.region, Policy.city).where(Policy.status == "active")).all()
    record_pairs = db.execute(select(ExternalSourceRecord.region, ExternalSourceRecord.city)).all()
    for sido, city in build_region_keys([*policy_pairs, *record_pairs]):
        key = region_key(sido, city)
        if key not in existing:
            repository.add_target(db, target_key=key, target_type="region", sido=sido, city=city, status="pending")
            existing.add(key)
            created += 1
    for policy in list_active_policies_for_photo_backfill(db, today=today):
        key = policy_key(int(policy.id))
        city = _norm_city(policy_city_hint(policy))
        if key in by_key:
            # 0047 은 policies.city 만 옮겼다 - 숙박세일처럼 시군 칸이 비고 제목에만 [시군]이 있는 정책은 그 시군 줄에서 후보를 받는다
            if by_key[key].status == "pending" and by_key[key].city != city:
                by_key[key].city = city
            continue
        if key in existing or not policy.region:
            continue
        repository.add_target(
            db,
            target_key=key,
            target_type="policy",
            sido=str(policy.region),
            city=city,
            policy_id=int(policy.id),
            status="pending",
        )
        existing.add(key)
        created += 1
    return created


@dataclass
class CollectSummary:
    targets_created: int = 0
    targets_total: int = 0   # 채울 대상(검토 대기 · 후보 6장 미만)
    targets_done: int = 0
    targets_filled: int = 0
    targets_empty: int = 0   # 다 돌고도 후보가 0장 - 관광공사 목록에 없는 곳(이름으로 찾기)
    candidates_added: int = 0
    decided_skipped: int = 0
    probe_failures: int = 0


Progress = Callable[[CollectSummary], None]


def collect_candidates(
    db: Session,
    provider: TourApiPhotoProvider,
    *,
    size_of: SizeOf | None,
    only_sido: str | None = None,
    today: date | None = None,
    commit: bool = False,
    progress: Progress | None = None,
) -> CollectSummary:
    """검토 대기 대상마다 ('이름으로 찾기'를 뺀) 후보가 6장이 되게 채운다. 결정된 대상은 건드리지 않는다.

    commit=True 면 대상 하나를 채울 때마다 저장한다 - 몇 분 걸리는 첫 수집 동안 관리자의 확정이 그 대상 잠금을 기다리지 않고,
    중간에 끊겨도 받은 만큼은 남는다(관리자 '후보 채우기' · 스크립트). progress 는 시작(0곳)과 대상 하나마다 불린다.
    """

    summary = CollectSummary(targets_created=ensure_targets(db, today=today))
    if commit:
        db.commit()
    used = repository.all_candidate_image_urls(db)
    probe = _Probe(size_of)
    places = PlaceResolver(provider)
    visible = _visible(db, today=today)
    todo: list[PhotoReviewTarget] = []
    for target in repository.list_all_targets(db):
        if not visible.shows(target) or (only_sido and target.sido != only_sido):
            continue
        if target.status != "pending":
            summary.decided_skipped += 1
        elif _collected(target) < WANT:
            todo.append(target)
    # 시군 → 그 시군 정책 → 도 전체 줄 순서. 도 전체 목록 앞쪽에 시군 대표 장소가 섞여 있어 도 줄이 먼저 가져가면 안 된다
    todo.sort(key=lambda t: (t.sido, t.city == SIDO_LEVEL_CITY, t.city, t.target_type != "region", t.policy_id or 0))
    summary.targets_total = len(todo)
    if progress:
        progress(summary)
    for target in todo:
        added = _fill(
            db, target, places.place(target.sido, target.city).spots(), want=WANT - _collected(target), used=used, probe=probe
        )
        if commit:
            db.commit()
        summary.candidates_added += added
        summary.targets_filled += 1 if added else 0
        summary.targets_empty += 0 if target.candidates else 1
        summary.targets_done += 1
        summary.probe_failures = probe.failures
        if progress:
            progress(summary)
    return summary


def _collected(target: PhotoReviewTarget) -> int:
    return sum(1 for c in target.candidates if c.source != "search")


# ---------- 관리자 '후보 채우기'(v52) - 수집을 뒤에서 돌리고 화면은 진행을 묻는다 ----------


@dataclass
class CollectJob:
    running: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: CollectSummary = field(default_factory=CollectSummary)
    error: str | None = None


# ponytail: 한 프로세스 안에서만 겹침을 막는다(uvicorn 하나로 뜬다). 워커를 늘리면 Postgres advisory lock 으로 바꾼다
_job = CollectJob()
_job_lock = threading.Lock()


def _spawn(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="photo-review-collect", daemon=True).start()


def start_collect_job(
    admin: User,
    provider: TourApiPhotoProvider,
    *,
    size_of: SizeOf | None,
    session_factory: Callable[[], Session],
    spawn: Callable[[Callable[[], None]], None] = _spawn,
) -> CollectJob:
    """'후보 채우기': 수집을 뒤에서 돌린다. 이미 돌고 있으면 409. 끝나면 변경 이력(photo_review.collect)에 남긴다."""

    global _job
    with _job_lock:
        if _job.running:
            raise PhotoReviewError(409, "Photo candidate collection is already running")
        _job = job = CollectJob(running=True, started_at=_now())
    admin_id = int(admin.id)

    def work() -> None:
        try:
            with session_factory() as db:
                def report(summary: CollectSummary) -> None:
                    job.summary = replace(summary)

                summary = collect_candidates(db, provider, size_of=size_of, commit=True, progress=report)
                from app.repositories.admin import add_audit_log

                add_audit_log(
                    db,
                    admin_user_id=admin_id,
                    action="photo_review.collect",
                    target_type="photo_review",
                    target_id="collect",
                    summary=f"후보 채우기: 후보 {summary.candidates_added}장 · 새 대상 {summary.targets_created}곳",
                    before_json=None,
                    after_json={
                        "finishedAt": _utc_iso(_now()),
                        "candidatesAdded": summary.candidates_added,
                        "targetsCreated": summary.targets_created,
                        "targetsEmpty": summary.targets_empty,
                        "probeFailures": summary.probe_failures,
                    },
                )
                db.commit()
                job.summary = replace(summary)
        except Exception as error:   # 관광공사 오류 문구에는 키가 없다(TourApiConfigurationError 는 주소를 떼고 올린다)
            logger.exception("Photo candidate collection failed.")
            job.error = str(error)[:300] or type(error).__name__
        finally:
            job.finished_at = _now()
            job.running = False

    spawn(work)
    return job


def collect_status(db: Session) -> dict[str, object]:
    from app.repositories.admin import list_audit_logs

    job = _job
    last, _total = list_audit_logs(db, action="photo_review.collect", limit=1)
    last_run = None
    if last:
        after = last[0].after_json or {}
        last_run = {"at": after.get("finishedAt") or last[0].created_at.isoformat(), "candidatesAdded": int(after.get("candidatesAdded", 0))}
    return {
        "running": job.running,
        "startedAt": _utc_iso(job.started_at),
        "finishedAt": _utc_iso(job.finished_at),
        "done": job.summary.targets_done,
        "total": job.summary.targets_total,
        "candidatesAdded": job.summary.candidates_added,
        "targetsCreated": job.summary.targets_created,
        "targetsEmpty": job.summary.targets_empty,
        "error": job.error,
        "lastRun": last_run,
    }


# ---------- 관리자 결정 ----------


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_iso(value: datetime | None) -> str | None:
    """UTC 로 저장한 시각을 Z 를 붙여 내보낸다 - DB 기본값(now())은 DB 시간대라 섞이면 화면 시각이 어긋난다."""

    return value.isoformat(timespec="seconds") + "Z" if value else None


def _require_target(db: Session, target_id: str, *, lock: bool = False) -> PhotoReviewTarget:
    try:
        numeric_id = int(target_id)
    except ValueError:
        raise PhotoReviewError(404, "Photo review target not found") from None
    target = repository.get_target(db, numeric_id, lock=lock)
    if target is None:
        raise PhotoReviewError(404, "Photo review target not found")
    return target


def _hide_published(db: Session, target: PhotoReviewTarget) -> None:
    if target.target_type == "region":
        repository.hide_region_photos(db, sido=target.sido, city=target.city)
    elif target.policy_id is not None:
        repository.hide_policy_photo(db, policy_id=target.policy_id)


def _publish(db: Session, target: PhotoReviewTarget, candidate: PhotoReviewCandidate) -> None:
    common = {
        "provider_content_id": candidate.provider_content_id,
        "copyright_type": candidate.copyright_type,
        "image_width": candidate.image_width,
        "image_height": candidate.image_height,
        "attribution_text": attribution_for(candidate.copyright_type),
        "status": "active",
        "fetched_at": _now(),
    }
    _hide_published(db, target)   # 다른 제공처의 옛 줄이 남아 있어도 이 줄 하나만 보이게
    if target.target_type == "region":
        upsert_region_photo(
            db,
            provider=PROVIDER,
            sido=target.sido,
            city=target.city,
            content_title=candidate.title,
            hero_image_url=candidate.image_url,
            thumb_image_url=candidate.thumbnail_url,
            provider_image_url=candidate.image_url,
            selection_reason="admin",
            **common,
        )
    else:
        upsert_policy_photo(
            db,
            policy_id=int(target.policy_id),
            provider=PROVIDER,
            image_url=candidate.image_url,
            thumbnail_url=candidate.thumbnail_url,
            alt_text=candidate.title[:200],
            relevance_score=0,
            assignment_reason="admin",
            **common,
        )


def _snapshot(target: PhotoReviewTarget) -> dict[str, object]:
    return {"status": target.status, "approvedCandidateId": target.approved_candidate_id}


def _decide(
    db: Session,
    target: PhotoReviewTarget,
    admin: User,
    *,
    action: str,
    status: str,
    summary: str,
    candidate: PhotoReviewCandidate | None = None,
) -> PhotoReviewTarget:
    from app.repositories.admin import add_audit_log

    before = _snapshot(target)
    if candidate is not None:
        _publish(db, target, candidate)
    else:
        _hide_published(db, target)
    target.status = status
    target.approved_candidate_id = candidate.id if candidate is not None else None
    target.decided_at = _now() if status != "pending" else None
    target.decided_by_user_id = int(admin.id) if status != "pending" else None
    after = _snapshot(target)
    if candidate is not None:
        after["imageUrl"] = candidate.image_url
    add_audit_log(
        db,
        admin_user_id=int(admin.id),
        action=action,
        target_type="photo_review_target",
        target_id=target.target_key,
        summary=summary,
        before_json=before,
        after_json=after,
    )
    db.flush()
    return target


def approve(db: Session, target_id: str, candidate_id: str, admin: User) -> PhotoReviewTarget:
    target = _require_target(db, target_id, lock=True)
    candidate = next((c for c in target.candidates if str(c.id) == str(candidate_id)), None)
    if candidate is None:
        raise PhotoReviewError(404, "Photo review candidate not found")
    return _decide(
        db, target, admin, action="photo_review.approve", status="approved",
        summary=f"사진 확정: {candidate.title}", candidate=candidate,
    )


def mark_none(db: Session, target_id: str, admin: User) -> PhotoReviewTarget:
    target = _require_target(db, target_id, lock=True)
    summary = "혜택 그림으로 둠" if target.target_type == "region" else "시군 사진 그대로 둠"
    return _decide(db, target, admin, action="photo_review.none", status="none", summary=summary)


def reopen(db: Session, target_id: str, admin: User) -> PhotoReviewTarget:
    target = _require_target(db, target_id, lock=True)
    return _decide(db, target, admin, action="photo_review.reopen", status="pending", summary="다시 고르기")


def _require_pending(target: PhotoReviewTarget) -> None:
    if target.status != "pending":
        raise PhotoReviewError(409, "Decided target: reopen it first")


def fetch_more(
    db: Session, target_id: str, provider: TourApiPhotoProvider, *, size_of: SizeOf | None
) -> PhotoReviewTarget:
    """같은 줄에서 아직 아무 대상의 후보도 아닌 다음 6장(필요하면 다음 쪽까지)."""

    target = _require_target(db, target_id, lock=True)
    _require_pending(target)
    place = PlaceResolver(provider).place(target.sido, target.city)
    _fill(
        db, target, place.spots(max_pages=MORE_PAGES), want=WANT,
        used=repository.all_candidate_image_urls(db), probe=_Probe(size_of),
    )
    return target


def search(
    db: Session, target_id: str, keyword: str, provider: TourApiPhotoProvider, *, size_of: SizeOf | None
) -> PhotoReviewTarget:
    """이름으로 찾아 후보에 더한다(최대 6장). 같은 도 · 수집 기준 통과 · 음식점 · 숙박 제외. 이 대상에 이미 있는 사진만 건너뛴다."""

    target = _require_target(db, target_id, lock=True)
    _require_pending(target)
    word = keyword.strip()
    if not word:
        raise PhotoReviewError(422, "Keyword is required")
    have = {c.image_url for c in target.candidates}
    probe = _Probe(size_of)
    added = 0
    for spot in provider.search_spots_by_keyword(keyword=word, rows=SEARCH_ROWS, content_type_id=None):
        if added >= WANT:
            break
        if spot.content_type_id in SEARCH_EXCLUDED_TYPES or not spot.first_image or spot.first_image in have:
            continue
        ok, size = probe.passes(spot, target.sido)
        if not ok:
            continue
        repository.add_candidate(db, target, **_candidate_fields(spot, size=size, source="search", keyword=word[:100]))
        have.add(spot.first_image)
        added += 1
    return target


def get_target(db: Session, target_id: str) -> PhotoReviewTarget:
    return _require_target(db, target_id)


# ---------- 응답 ----------


def _photo(candidate: PhotoReviewCandidate | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    return {
        "candidateId": str(candidate.id),
        "title": candidate.title,
        "imageUrl": candidate.image_url,
        "thumbnailUrl": candidate.thumbnail_url,
        "copyrightType": candidate.copyright_type,
    }


def _candidate_item(candidate: PhotoReviewCandidate) -> dict[str, object]:
    return {
        "id": str(candidate.id),
        "title": candidate.title,
        "kind": CONTENT_TYPE_LABELS.get(candidate.content_type_id or "", "관광지"),
        "contentTypeId": candidate.content_type_id,
        "imageUrl": candidate.image_url,
        "thumbnailUrl": candidate.thumbnail_url,
        "copyrightType": candidate.copyright_type,
        "width": candidate.image_width,
        "height": candidate.image_height,
        "address": candidate.address,
        "source": candidate.source,
        "searchKeyword": candidate.search_keyword,
    }


def _photo_key(policy: Policy) -> tuple[str, str]:
    """응답 해석(RegionPhotoIndex.resolve)이 이 정책에 쓰는 시군 줄 - 정책의 시군 칸이 있으면 그 시군, 없으면 도 전체."""

    city = _norm_city(policy.city) if policy.city and policy.city != policy.region else SIDO_LEVEL_CITY
    return str(policy.region), city


@dataclass
class _Visible:
    """지금 앱에 보이는 것만 검토 · 수집한다 - 공개 정책과, 그 정책들이 사진을 받는 시군 줄.
    숨김 · 마감된 정책과 아무 정책도 안 쓰는 줄은 목록에 내지 않고 후보도 받지 않는다."""

    policies: dict[int, Policy]
    uses: dict[tuple[str, str], int]

    def shows(self, target: PhotoReviewTarget) -> bool:
        if target.target_type == "policy":
            return target.policy_id in self.policies
        return self.uses.get((target.sido, target.city), 0) > 0


def _visible(db: Session, *, today: date | None = None) -> _Visible:
    public = [policy for policy in list_active_policies_for_photo_backfill(db, today=today) if policy.region]
    uses: dict[tuple[str, str], int] = {}
    for policy in public:
        key = _photo_key(policy)
        uses[key] = uses.get(key, 0) + 1
    return _Visible({int(policy.id): policy for policy in public}, uses)


@dataclass
class _Context:
    """목록 · 상세 응답에 붙이는 것들 - 정책 정보, 쓰는 정책 수, 확정 사진, 정책이 물려받는 시군 사진."""

    visible: _Visible
    policies: dict[int, Policy]
    approved: dict[int, PhotoReviewCandidate]
    region_photo: dict[tuple[str, str], PhotoReviewCandidate]
    candidate_counts: dict[int, int]


def _context(
    db: Session, targets: list[PhotoReviewTarget], all_targets: list[PhotoReviewTarget], visible: _Visible
) -> _Context:
    policies = dict(visible.policies)
    missing = [t.policy_id for t in targets if t.policy_id is not None and t.policy_id not in policies]
    if missing:   # 숨김 정책 대상을 id 로 직접 열 때
        policies.update({int(p.id): p for p in db.scalars(select(Policy).where(Policy.id.in_(missing)))})
    regions = [t for t in all_targets if t.target_type == "region" and t.status == "approved" and t.approved_candidate_id]
    approved = repository.get_candidates(
        db, [t.approved_candidate_id for t in [*targets, *regions] if t.approved_candidate_id]
    )
    region_photo = {(t.sido, t.city): approved[t.approved_candidate_id] for t in regions if t.approved_candidate_id in approved}
    counts = repository.count_candidates(db, [t.id for t in targets])
    return _Context(visible, policies, approved, region_photo, counts)


def _item(target: PhotoReviewTarget, ctx: _Context) -> dict[str, object]:
    policy = ctx.policies.get(target.policy_id) if target.policy_id is not None else None
    inherited = ctx.region_photo.get(_photo_key(policy)) if target.target_type == "policy" and policy is not None else None
    return {
        "id": str(target.id),
        "unit": target.target_type,
        "status": target.status,
        "sido": target.sido,
        "city": target.city,
        "policySlug": policy.slug if policy else None,
        "policyTitle": policy.title if policy else None,
        "policyCategory": _normalize_policy_category(policy.policy_type) if policy else None,
        "benefitCount": ctx.visible.uses.get((target.sido, target.city), 0),
        "candidateCount": ctx.candidate_counts.get(target.id, 0),
        "photo": _photo(ctx.approved.get(target.approved_candidate_id)) if target.approved_candidate_id else None,
        "inheritedPhoto": _photo(inherited),
        "decidedAt": _utc_iso(target.decided_at),
    }


def list_targets(db: Session, *, unit: str, status: str | None) -> dict[str, object]:
    visible = _visible(db)
    all_targets = repository.list_all_targets(db)
    shown = [t for t in all_targets if visible.shows(t)]
    counts = {"pending": 0, "approved": 0, "none": 0}
    for target in shown:
        if target.target_type == unit:
            counts[target.status] += 1
    items = [t for t in shown if t.target_type == unit and (status is None or t.status == status)]
    if unit == "region":
        items.sort(key=lambda t: (t.sido, t.city == SIDO_LEVEL_CITY, t.city))
    else:
        items.sort(key=lambda t: (t.sido, t.city, visible.policies[t.policy_id].title))
    ctx = _context(db, items, all_targets, visible)
    keys = {t.target_key for t in all_targets}
    collected = repository.count_collected(db)
    return {
        "items": [_item(target, ctx) for target in items],
        "counts": {**counts, "all": sum(counts.values())},
        "pendingTotal": sum(1 for t in shown if t.status == "pending"),
        # '후보 채우기' 안내: 다음 수집이 새로 넣을 대상(공개됐지만 아직 대상이 아닌 정책 · 쓰이는 시군 줄)과 후보가 6장이 안 되는 대기 대상
        "newTargets": sum(1 for pid in visible.policies if policy_key(pid) not in keys)
        + sum(1 for sido, city in visible.uses if region_key(sido, city) not in keys),
        "shortTargets": sum(1 for t in shown if t.status == "pending" and collected.get(t.id, 0) < WANT),
    }


def target_detail(db: Session, target: PhotoReviewTarget) -> dict[str, object]:
    ctx = _context(db, [target], repository.list_all_targets(db), _visible(db))
    return {**_item(target, ctx), "candidates": [_candidate_item(c) for c in target.candidates]}
