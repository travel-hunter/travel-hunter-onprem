"""사진 수집 기준(app/services/photo_criteria.py) - 홈 배너 사진과 같은 기준."""

from __future__ import annotations

import struct

import httpx
import pytest

from app.services.photo_criteria import (
    ImageProbeError,
    ImageSizeProbe,
    attribution_for,
    image_size,
    metadata_rejections,
    size_rejections,
)


def jpeg_header(width: int, height: int) -> bytes:
    """SOI · APP0 · SOF0 만 있는 최소 JPEG 머리."""

    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    return b"\xff\xd8" + app0 + sof0


def png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def test_metadata_rejections_cover_copyright_facility_and_missing_image() -> None:
    assert metadata_rejections(title="법성포", image_url="https://x/1.jpg", copyright_type="Type1") == []
    assert metadata_rejections(title="법성포", image_url="https://x/1.jpg", copyright_type="Type3") == []
    assert metadata_rejections(title="법성포", image_url="https://x/1.jpg", copyright_type=None) == ["copyright:none"]
    assert metadata_rejections(title="법성포", image_url="https://x/1.jpg", copyright_type="Type2") == ["copyright:Type2"]
    assert metadata_rejections(title="영광 군청 주차장", image_url=None, copyright_type="Type1") == [
        "no-image",
        "facility:주차장",
    ]
    # 보기 좋고 나쁨은 규칙으로 가르지 않는다 - 염전은 사람 검토 몫
    assert metadata_rejections(title="천일염전", image_url="https://x/2.jpg", copyright_type="Type1") == []


def test_cheongsapo_village_is_not_a_government_building() -> None:
    assert metadata_rejections(title="청사포 다릿돌전망대", image_url="https://x/a.jpg", copyright_type="Type1") == []
    assert metadata_rejections(title="영광군청사", image_url="https://x/a.jpg", copyright_type="Type1") == ["facility:청사"]


def test_facility_word_is_reported() -> None:
    reasons = metadata_rejections(title="해남 태양광 단지", image_url="https://x/1.jpg", copyright_type="Type1")
    assert reasons == ["facility:태양광"]


def test_size_rejections_need_landscape_and_800px() -> None:
    assert size_rejections((940, 626)) == []
    assert size_rejections((699, 466)) == ["too-small:699x466"]
    assert size_rejections((626, 940)) == ["not-landscape:626x940", "too-small:626x940"]
    assert size_rejections(None) == ["size:unknown"]


def test_image_size_reads_jpeg_and_png_headers() -> None:
    assert image_size(jpeg_header(940, 626)) == (940, 626)
    assert image_size(png_header(1280, 720)) == (1280, 720)
    assert image_size(b"GIF89a....") is None
    assert image_size(b"\xff\xd8\xff\xe0") is None  # 잘린 머리


def _probe(handler) -> ImageSizeProbe:
    return ImageSizeProbe(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_size_probe_asks_for_the_header_only_and_caches() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(206, content=jpeg_header(940, 626))

    probe = _probe(handler)
    assert probe("https://tong.visitkorea.or.kr/a.jpg") == (940, 626)
    assert probe("https://tong.visitkorea.or.kr/a.jpg") == (940, 626)
    assert len(calls) == 1
    assert calls[0].headers["Range"].startswith("bytes=0-")


def test_size_probe_stops_at_128kb_when_the_server_ignores_range() -> None:
    sent: list[int] = []

    def chunks():
        yield jpeg_header(940, 626)
        for _ in range(64):  # 8MB 를 다 보내려는 서버
            sent.append(1)
            yield b"\0" * 131_072

    probe = _probe(lambda request: httpx.Response(200, content=chunks()))
    assert probe("https://x/big.jpg") == (940, 626)
    assert len(sent) <= 2


def test_size_probe_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old.jpg":
            return httpx.Response(301, headers={"Location": "https://x/new.jpg"})
        return httpx.Response(206, content=jpeg_header(1024, 683))

    assert _probe(handler)("https://x/old.jpg") == (1024, 683)


def test_size_probe_drops_only_that_candidate_on_4xx() -> None:
    assert _probe(lambda request: httpx.Response(404))("https://x/404.jpg") is None


def test_size_probe_raises_when_the_image_server_is_unreachable_and_retries_next_time() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectTimeout("slow", request=request)

    probe = _probe(handler)
    # 기준 미달이 아니다 - 수집 스크립트가 그 대상을 실패로 세고 있던 줄을 두게 한다
    with pytest.raises(ImageProbeError):
        probe("https://x/a.jpg")
    with pytest.raises(ImageProbeError):
        probe("https://x/a.jpg")
    assert len(calls) == 2  # 캐시하지 않는다
    with pytest.raises(ImageProbeError):
        _probe(lambda request: httpx.Response(503))("https://x/b.jpg")


def test_attribution_names_the_kogl_type() -> None:
    assert attribution_for("Type1") == "사진: 한국관광공사 · 공공누리 제1유형"
    assert attribution_for("Type3") == "사진: 한국관광공사 · 공공누리 제3유형(변경금지)"
    assert attribution_for(None) == "사진: 한국관광공사"
