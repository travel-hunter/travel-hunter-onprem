"""사진 수집 기준 - 홈 배너 사진과 같은 기준(docs/photo-sourcing/2026-10-01-home-banner-photos.md,
docs/superpowers/plans/2026-10-01-photo-collection-criteria.md). 지역 사진·정책 사진 수집이 같이 쓴다.

- 저작권: TourAPI 목록의 cpyrhtDivCd. 공공누리 제1유형, 제3유형(변경금지)은 원본 주소 그대로 보여 줄 때만
  (2026-10-01 사용자 결정 - 자체 보관으로 다시 인코딩할 때는 제3유형을 빼야 한다). 값이 없으면 쓰지 않는다.
- 내용: 관광지로 등록된 시설(발전소·청사 등)은 뺀다. 보기 좋고 나쁨(예: 염전)은 규칙으로 가르지 않는다 - 사람 검토 몫.
- 모양: 가로 사진(가로 ≥ 세로 × 1.2), 가로 800px 이상. 실측(전남 20곳): TourAPI 원본은 거의 940px, 699px 하나.
"""

from __future__ import annotations

import re
import struct

import httpx

COPYRIGHT_LABELS = {
    "Type1": "공공누리 제1유형",
    "Type3": "공공누리 제3유형(변경금지)",
}
MIN_WIDTH = 800
LANDSCAPE_RATIO = 1.2
# 관광지(contenttypeid 12)로 등록돼 있어도 여행 사진으로 쓰지 않을 시설. 넓게 잡지 않는다 - '센터'·'염전' 등은 사람 검토로.
FACILITY_WORDS = (
    "발전소",
    "태양광",
    "변전소",
    "청사",
    "주차장",
    "터미널",
    "처리장",
    "산업단지",
    "공단",
    "매립장",
    "소각장",
)
# '청사'는 관공서 건물 - 해운대 '청사포'(바닷가 마을)는 빼지 않는다
FACILITY_PATTERNS = tuple(
    (word, re.compile(re.escape(word) + ("(?!포)" if word == "청사" else ""))) for word in FACILITY_WORDS
)
SIZE_PROBE_BYTES = 131_071


def attribution_for(copyright_type: str | None) -> str:
    """출처 문구는 한 가지 표기로 - 저작권 유형까지 적는다(공공누리 출처표시 조건)."""

    label = COPYRIGHT_LABELS.get(copyright_type or "")
    return f"사진: 한국관광공사 · {label}" if label else "사진: 한국관광공사"


def metadata_rejections(*, title: str, image_url: str | None, copyright_type: str | None) -> list[str]:
    """목록 응답만으로 가를 수 있는 이유들(사진을 받지 않는다)."""

    reasons: list[str] = []
    if not image_url:
        reasons.append("no-image")
    if copyright_type not in COPYRIGHT_LABELS:
        reasons.append(f"copyright:{copyright_type or 'none'}")
    word = next((word for word, pattern in FACILITY_PATTERNS if pattern.search(title)), None)
    if word:
        reasons.append(f"facility:{word}")
    return reasons


def size_rejections(size: tuple[int, int] | None) -> list[str]:
    if size is None:
        return ["size:unknown"]
    width, height = size
    reasons: list[str] = []
    if width < height * LANDSCAPE_RATIO:
        reasons.append(f"not-landscape:{width}x{height}")
    if width < MIN_WIDTH:
        reasons.append(f"too-small:{width}x{height}")
    return reasons


def image_size(data: bytes) -> tuple[int, int] | None:
    """JPEG(SOF) · PNG(IHDR) 머리에서 가로·세로만 읽는다. 다른 형식이나 잘린 머리는 None."""

    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    if data[:2] != b"\xff\xd8":
        return None
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
        # SOF0~SOF15(DHT C4 · JPG C8 · DAC CC 제외)에 높이·가로가 있다
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
            return width, height
        offset += 2 + length
    return None


class ImageProbeError(RuntimeError):
    """사진 서버에 닿지 못했다(시간 초과 · 연결 실패 · 5xx · 429). 기준 미달이 아니다 - 그 대상은 이번 실행에서
    건너뛰고(수집 스크립트가 실패로 센다) 있던 줄은 그대로 둔다. 기준 미달로 보면 첫 실행에 사진 서버가 잠깐 느려도
    멀쩡한 줄이 한꺼번에 숨겨진다."""


class ImageSizeProbe:
    """사진 앞 128KB 만 받아 크기를 잰다. 같은 주소는 한 번만 - 후보를 순서대로 하나씩 볼 때만 부른다.

    - 서버가 Range 를 무시하고 200 으로 다 보내도 128KB 에서 끊는다. 주소 넘김(3xx)은 따라간다.
    - 4xx(사진 없음 등)는 그 후보만 탈락(None → size:unknown). 머리를 읽지 못한 형식(WEBP·GIF 등)도 None.
    - 그 밖의 연결 문제는 ImageProbeError - 캐시하지 않아 다음 실행에 다시 본다.
    """

    def __init__(self, client: httpx.Client | None = None, timeout: float = 10.0) -> None:
        self._client = client
        self._timeout = timeout
        self._cache: dict[str, tuple[int, int] | None] = {}

    def _head(self, url: str) -> bytes:
        stream = (self._client or httpx).stream
        with stream(
            "GET", url, headers={"Range": f"bytes=0-{SIZE_PROBE_BYTES}"}, timeout=self._timeout, follow_redirects=True
        ) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > SIZE_PROBE_BYTES:
                    break
            return bytes(data[: SIZE_PROBE_BYTES + 1])

    def __call__(self, url: str) -> tuple[int, int] | None:
        if url not in self._cache:
            try:
                self._cache[url] = image_size(self._head(url))
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500 and status != 429:
                    self._cache[url] = None
                else:
                    raise ImageProbeError(f"size probe {status}: {url}") from exc
            except httpx.HTTPError as exc:
                raise ImageProbeError(f"size probe failed: {url}: {type(exc).__name__}") from exc
        return self._cache[url]
