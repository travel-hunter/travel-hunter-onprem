"""확정한 사진을 원본 그대로 우리 볼륨에 둔다(0047 사진 검토).

관광공사 주소를 그대로 걸면 그쪽이 주소를 바꾸거나 지울 때 확정한 사진이 조용히 사라진다. 그래서 관리자가 확정할 때 그 한 장만
받아 MEDIA_ROOT/photos/<해시 앞 2자>/<sha256>.<확장자> 에 둔다 - 내용 해시 이름이라 같은 사진(시군과 정책이 같은 사진을 고른 때 ·
다시 확정)은 한 번만 저장된다. 다시 인코딩 · 리사이즈하지 않는다(공공누리 제3유형은 변경금지). 내보내기는 app/api/media.py(/api/media).
형식은 응답 머리가 아니라 파일 첫 바이트로 가린다 - 사진 서버가 오류 페이지를 200 으로 줘도 저장하지 않는다.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import settings

MEDIA_URL_PREFIX = "/api/media/"
MAX_BYTES = 5 * 1024 * 1024
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}


class PhotoStorageError(RuntimeError):
    """사진을 받지 못했다(접속 실패 · 4xx/5xx · 사진이 아님 · 5MB 초과 · 보관 위치 없음). 확정은 되지 않는다."""


@dataclass(frozen=True)
class StoredImage:
    path: str   # MEDIA_ROOT 아래 상대 경로 - photos/ab/ab12….jpg
    byte_size: int
    content_type: str


def media_url(path: str) -> str:
    """응답에 싣는 주소. API 와 같은 곳을 가리키는 상대 경로라 화면이 API 주소를 앞에 붙인다."""

    return MEDIA_URL_PREFIX + path


def media_root() -> Path | None:
    return Path(settings.media_root) if settings.media_root else None


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def store_remote_image(
    url: str, *, root: Path | None = None, client: httpx.Client | None = None, timeout: float = 10.0
) -> StoredImage:
    base = root or media_root()
    if base is None:
        raise PhotoStorageError("MEDIA_ROOT is not configured")
    data = bytearray()
    try:
        with (client or httpx).stream("GET", url, timeout=timeout, follow_redirects=True) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > MAX_BYTES:
                    raise PhotoStorageError("image is larger than 5MB")
    except httpx.HTTPError as error:
        raise PhotoStorageError(f"download failed: {type(error).__name__}") from error
    ext = _sniff(bytes(data[:16]))
    if ext is None:
        raise PhotoStorageError("not an image")
    digest = hashlib.sha256(data).hexdigest()
    path = f"photos/{digest[:2]}/{digest}.{ext}"
    target = base / path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, target)   # 반쯤 쓴 파일이 이름을 갖지 않게
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return StoredImage(path, len(data), CONTENT_TYPES[ext])
