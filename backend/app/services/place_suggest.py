"""장소 검색 완성 검색어 - 우리 공공데이터(public_places) 이름으로 만든 최대 6줄.

후보는 저장소(suggest_candidates)가 이름에 검색어가 든 행을 묶어 주고, 이 모듈이 설계 0.3 의 순위 규칙(③~⑬)을 매긴다. 규칙은
docs/superpowers/plans/2026-10-12-place-search-suggestions.md 0.3 절을 실데이터로 검증한 순서 그대로 옮긴 것이다.
정렬의 가나다순은 파이썬 기본 str 비교(코드 포인트)이고, 문자열 비교 · 시작 · 포함은 모두 .lower() 끼리 한다.
카카오 값은 읽지도 저장하지도 않는다. 검색어 · 이름은 로그에 남기지 않는다(오류 종류와 개수만).
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import public_places as public_place_repository
from app.repositories.public_places import ATTRACTION_CATEGORIES, SuggestCandidate

logger = logging.getLogger(__name__)

SUGGEST_LIMIT = 6
MIN_QUERY_LENGTH = 2
# 열쇠 어절이 같은 줄은 이 수까지만 앞에 두고 나머지는 뒤로 민다(롯데월드 ○○ 6줄 막기)
KEY_WORD_FRONT_LINES = 2
# 핵심 이름이 이 수를 넘으면 _hub_counts 가 조각 색인을 만든다(색인은 이름 하나에 약 1us, 안 만들면 핵심 이름 하나가 이름 전부를 훑는다)
HUB_INDEX_MIN_CORES = 16
Scope = tuple[str, tuple[str, ...] | None] | None

_LETTER_OR_DIGIT = re.compile(r"[^\W_]")   # \w 에서 밑줄을 뺀 글자 · 숫자
_TAIL = re.compile(r"\s*(?:\[[^\]]*\]|\([^)]*\))")   # [유네스코 세계유산] · (부산) 꼬리표


@dataclass(slots=True)
class _Line:
    """④ 줄(line0 -> line -> cand): (tier, label, t)로 묶인 후보 행들."""

    tier: int
    label: str | None   # 체인 줄 뒤에 붙일 지역 말 - 지역 안이고 지역이 있을 때만(시군을 골랐으면 그 행의 시군, 아니면 시도)
    t: str   # 보일 말
    core: str   # 앞에 붙은 그 행 자신의 시도 · 시군 이름을 뗀 말
    attr: bool
    tour: bool
    n: int
    lvl: int
    text: str = ""   # ⑤ 합친 뒤의 말
    kw: str = ""   # ⑥ 열쇠 어절
    w1: str = ""   # 말의 첫 어절(상표)
    foldable: bool = False   # ⑨ 체인으로 접을 수 있나


@dataclass(slots=True)
class _Folded:
    tier: int
    text: str
    core: str
    lkw: str
    lvl: int
    attr: bool
    tour: bool
    chain: bool
    n: int


@dataclass(slots=True)
class _Agg:
    tier: int
    text: str
    core: str
    lkw: str
    lvl: int
    attr: bool
    tour: bool
    chain: bool
    n: int
    w: int = 0
    rl: int = 0
    rn: int = 0


@lru_cache(maxsize=256)
def _region_prefix(sido: str, city: str | None) -> re.Pattern[str]:
    names = [sido, city] if city else [sido]
    return re.compile(r"^(?:(?:" + "|".join(re.escape(name) for name in names) + r")\s*)+")


def _shown(name: str, ql: str) -> str:
    """③ 보일 말: 꼬리표를 지운 말. 지워서 검색어가 사라지면(목멱산(남산)) 원래 이름."""

    stripped = _TAIL.sub("", name).strip()
    return stripped if ql in stripped.lower() else name


def _core(shown: str, sido: str | None, city: str | None) -> str:
    """③ 앞에 붙은 그 행 자신의 시도 · 시군 이름을 되풀이해 뗀 말. 시도가 없으면 떼지 않는다. 뗀 뒤 비면 보일 말."""

    if sido is None:
        return shown
    return _region_prefix(sido, city).sub("", shown) or shown


def _hub_counts(cores: Collection[str], inside: Mapping[str, int]) -> dict[str, int]:
    """⑪ 대표성: 핵심 이름마다 그 말을 품은 지역 안 이름(inside: 이름 -> 행 수)의 행 수 합.
    핵심 이름이 많으면(관광지가 많은 흔한 2자 입력) 이름마다 모든 이름을 훑는 비용이 곱으로 늘어, 2글자 조각 -> 그 조각이 든 이름 목록을
    만들어 두고 핵심 이름의 가장 드문 조각이 든 이름만 훑는다(핵심 이름을 품은 이름은 그 조각을 반드시 품는다 - 결과는 전부 훑는 것과 같다)."""

    postings: dict[str, list[str]] | None = None
    if len(cores) > HUB_INDEX_MIN_CORES:
        postings = defaultdict(list)
        for name in inside:
            for pair in {name[start:start + 2] for start in range(len(name) - 1)}:
                postings[pair].append(name)
    counts: dict[str, int] = {}
    for core in cores:
        pool = inside if postings is None or len(core) < 2 else min((postings.get(core[start:start + 2], ()) for start in range(len(core) - 1)), key=len)
        counts[core] = sum(inside[name] for name in pool if core in name)
    return counts


def _order(item: _Agg) -> tuple[int, int, bool, int, int, str]:
    return item.tier, item.rl, not item.attr, -item.w, len(item.text), item.text


def rank_suggestions(query: str, candidates: Sequence[SuggestCandidate], *, scope: Scope, limit: int = SUGGEST_LIMIT) -> list[str]:
    """후보 묶음 -> 완성 검색어 최대 limit 줄(설계 0.3 ③~⑬). scope 는 후보를 가져온 범위((시도, 시군 목록 | None) 또는 지역 없음 None)이고
    tier 는 저장소가 붙인 값을 믿는다. 대표성 · 어절 수는 후보 목록 안에서 센다."""

    q = query.strip()
    ql = q.lower()
    has_area = scope is not None
    by_city = scope is not None and scope[1] is not None

    # ③ 행마다 계산해 ④ (tier, label, t)로 줄을 묶는다
    groups: dict[tuple[int, str | None, str], _Line] = {}
    for row in candidates:
        t = _shown(row.name, ql)
        core = _core(t, row.sido, row.city)
        label = (row.city if by_city else row.sido) if row.tier == 0 and has_area else None
        attr = row.source == "tourapi" and row.category in ATTRACTION_CATEGORIES
        tour = row.source == "tourapi"
        t_low, core_low = t.lower(), core.lower()
        lvl = 1 if t_low.startswith(ql) or core_low.startswith(ql) else 2 if f" {ql}" in t_low else 3
        line = groups.get((row.tier, label, t))
        if line is None:
            groups[(row.tier, label, t)] = _Line(row.tier, label, t, core, attr, tour, row.count, lvl)
        else:
            line.core = min(line.core, core)
            line.attr = line.attr or attr
            line.tour = line.tour or tour
            line.n += row.count
            line.lvl = min(line.lvl, lvl)
    lines = list(groups.values())

    # ⑤ 지역 밖 · 지역 없음에서 핵심 이름만 같은 줄(곡성 · 담양 메타세쿼이아길)은 핵심 이름 한 줄로 합친다. ⑥ 열쇠 어절
    same_core = Counter((line.tier, line.core.lower()) for line in lines)
    for line in lines:
        merge = (line.tier == 1 or not has_area) and same_core[(line.tier, line.core.lower())] >= 2
        line.text = line.core if merge else line.t
        first = line.t.split(" ")[0]
        line.kw = first if first.lower().startswith(ql) else line.core.split(" ")[0]

    # ⑦ 지역 안 관광지의 핵심 이름 모음
    acore = {line.core.lower() for line in lines if line.tier == 0 and line.attr}

    # ⑧ 어절 줄: 같은 열쇠 어절로 시작하는 지역 안 관광지가 2곳 이상이면 그 어절을 한 줄로 더한다(오동도 등대 · 오동도 유람선터미널 -> 오동도)
    by_word: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        low = line.kw.lower()
        if line.tier == 0 and line.attr and low.startswith(ql) and low != ql and low not in acore:
            by_word[low].append(line.kw)
    word_lines = {low: min(words) for low, words in by_word.items() if len(words) >= 2}

    # ⑨ 체인: 접을 수 있는 줄(지역 안 · 관광지 아님 · 말이 q 로 시작 · 상표가 관광지 이름이나 어절 줄이 아님)을 (지역, 상표)로 센다
    brands: Counter[tuple[str, str]] = Counter()
    for line in lines:
        label = line.label or ""
        line.w1 = line.text.split(" ")[0]
        low = line.w1.lower()
        line.foldable = (
            line.tier == 0 and not line.attr and line.text.lower().startswith(ql)
            and low != ql and low not in acore and low not in word_lines
        )
        if line.foldable:
            brands[(label, low)] += 1
    # 붙여 쓴 상표(롯데리아용인)는 그 앞부분인 더 큰 상표(줄 수가 더 많은 것 -> 짧은 것. 그러니 줄 수는 늘 2 이상이다)로 모은다
    merged_into: dict[tuple[str, str], str] = {}
    for (label, brand), count in brands.items():
        best: tuple[int, int] | None = None
        for size in range(1, len(brand)):
            bigger = brands.get((label, brand[:size]), 0)
            if bigger > count and (best is None or (-bigger, size) < best):
                best = (-bigger, size)
        if best is not None:
            merged_into[(label, brand)] = brand[: best[1]]
    partitions: dict[tuple[bool, str, str | None], list[_Line]] = defaultdict(list)
    for line in lines:
        label = line.label or ""
        low = line.w1.lower()
        brand = merged_into.get((label, low), low) if line.foldable else None
        partitions[(line.foldable, label, brand)].append(line)
    folded: list[_Folded] = []
    for (foldable, _label, _brand), members in partitions.items():
        chain = foldable and len(members) >= 2   # 1곳뿐이면 접지 않는다
        name = min(member.w1 for member in members)
        for member in members:
            if chain:
                text = name + (f" {member.label}" if member.label else "")
                folded.append(_Folded(member.tier, text, name, name.lower(), member.lvl, member.attr, member.tour, True, member.n))
            else:
                folded.append(_Folded(member.tier, member.text, member.core, member.kw.lower(), member.lvl, member.attr, member.tour, False, member.n))
    for low, text in word_lines.items():
        folded.append(_Folded(0, text, text, low, 1, True, False, False, 0))

    # ⑩ 합치기: 입력과 똑같은 말은 뺀다. (tier, 말)로 묶고, 같은 말이 지역 안 · 밖에 다 있으면 지역 안만 남긴다
    merged: dict[tuple[int, str], _Agg] = {}
    for item in folded:
        if item.text.lower() == ql:
            continue
        key = (item.tier, item.text)
        agg = merged.get(key)
        tour = item.tour and not item.chain
        if agg is None:
            merged[key] = _Agg(item.tier, item.text, item.core, item.lkw, item.lvl, item.attr, tour, item.chain, item.n)
        else:
            agg.core = min(agg.core, item.core)
            agg.lkw = min(agg.lkw, item.lkw)
            agg.lvl = min(agg.lvl, item.lvl)
            agg.attr = agg.attr or item.attr
            agg.tour = agg.tour or tour
            agg.chain = agg.chain or item.chain
            agg.n += item.n
    kept: dict[str, _Agg] = {}
    for agg in merged.values():
        current = kept.get(agg.text.lower())
        if current is None or (agg.tier, agg.text) < (current.tier, current.text):
            kept[agg.text.lower()] = agg

    # ⑪ 무게. 대표성 = 핵심 이름을 품은 지역 안 후보 행 수, 어절 수 = 첫 어절과 똑같은 낱말이 든 지역 안 후보 행 수
    inside: Counter[str] = Counter()   # 지역 안 이름(소문자) -> 행 수
    for row in candidates:
        if row.tier == 0:
            inside[row.name.lower()] += row.count
    words: Counter[str] = Counter()
    for name, count in inside.items():
        for word in name.split(" "):
            if word.startswith(ql) and word != ql:
                words[word] += count
    hubs = _hub_counts({agg.core.lower() for agg in kept.values() if agg.tier == 0 and agg.attr}, inside)
    for agg in kept.values():
        if agg.tier == 0 and agg.attr:
            agg.w = hubs[agg.core.lower()] or agg.n   # 그런 행이 없으면 n
        elif agg.attr:
            agg.w = agg.n
        elif agg.tour:
            agg.w = max(agg.n, words.get(agg.core.split(" ")[0].lower(), 0))
        else:
            agg.w = agg.n
        # ⑫ 등급: 3자 이상이면 지역 안 관광지는 어절 속에서 맞아도 맨 앞 맞춤으로 친다
        agg.rl = 1 if agg.tier == 0 and agg.attr and len(q) >= 3 else agg.lvl

    # ⑬ 순서와 2줄 제한: 같은 열쇠 어절 안에서 번호를 매겨 3번째부터는 뒤로 민다
    cells: dict[str, list[_Agg]] = defaultdict(list)
    for agg in kept.values():
        cells[agg.lkw].append(agg)
    for cell in cells.values():
        for number, agg in enumerate(sorted(cell, key=_order), start=1):
            agg.rn = number
    ranked = sorted(kept.values(), key=lambda agg: (agg.rn > KEY_WORD_FRONT_LINES, *_order(agg)))
    return [agg.text for agg in ranked[:limit]]


def suggest_place_names(db: Session, *, query: str, scope: Scope) -> list[str]:
    """① 입력 거름 -> 후보 질의 -> 순위. 2자 미만이거나 글자 · 숫자가 없으면(--) DB 를 부르지 않고 빈 목록. DB 오류도 빈 목록이고
    로그에는 오류 종류만 남긴다(검색어 · 질의 값은 예외 메시지에도 있을 수 있어 싣지 않는다)."""

    q = query.strip()
    if len(q) < MIN_QUERY_LENGTH or not _LETTER_OR_DIGIT.search(q):
        return []
    try:
        candidates = public_place_repository.suggest_candidates(db, query=q, scope=scope)
    except SQLAlchemyError as error:
        logger.warning("place_suggest_failed error=%s", type(error).__name__)
        return []
    return rank_suggestions(q, candidates, scope=scope)
