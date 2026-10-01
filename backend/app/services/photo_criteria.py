"""사진 수집 기준 - 홈 배너 사진과 같은 기준(docs/photo-sourcing/2026-10-01-home-banner-photos.md,
docs/superpowers/plans/2026-10-01-photo-collection-criteria.md). 지역 사진·정책 사진 수집이 같이 쓴다.

- 저작권: TourAPI 목록의 cpyrhtDivCd. 공공누리 제1유형, 제3유형(변경금지)은 원본 주소 그대로 보여 줄 때만
  (2026-10-01 사용자 결정 - 자체 보관으로 다시 인코딩할 때는 제3유형을 빼야 한다). 값이 없으면 쓰지 않는다.
- 내용: 관광지로 등록된 시설(발전소·청사 등)은 뺀다. 보기 좋고 나쁨(예: 염전)은 규칙으로 가르지 않는다 - 사람 검토 몫.
- 모양: 가로 사진(가로 ≥ 세로 × 1.2), 가로 800px 이상. 실측(전남 20곳): TourAPI 원본은 거의 940px, 699px 하나.
"""

from __future__ import annotations

import struct
from collections.abc import Callable

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
    word = next((word for word in FACILITY_WORDS if word in title), None)
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


class ImageSizeProbe:
    """사진 머리 128KB 만 받아 크기를 잰다. 같은 주소는 한 번만 - 후보를 순서대로 하나씩 볼 때만 부른다."""

    def __init__(self, http_get: Callable[..., httpx.Response] = httpx.get, timeout: float = 10.0) -> None:
        self._http_get = http_get
        self._timeout = timeout
        self._cache: dict[str, tuple[int, int] | None] = {}

    def __call__(self, url: str) -> tuple[int, int] | None:
        if url not in self._cache:
            try:
                response = self._http_get(
                    url, headers={"Range": f"bytes=0-{SIZE_PROBE_BYTES}"}, timeout=self._timeout
                )
                response.raise_for_status()
                self._cache[url] = image_size(response.content)
            except httpx.HTTPError:
                self._cache[url] = None
        return self._cache[url]
