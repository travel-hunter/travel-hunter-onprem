"""확정 사진 보관(photo_storage)과 /api/media 내보내기. 바깥 HTTP 없이 httpx.MockTransport 로 시험한다."""

from __future__ import annotations

import hashlib

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.media import MediaFiles
from app.services.photo_storage import MAX_BYTES, PhotoStorageError, media_url, store_remote_image

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-body" * 10
PNG = b"\x89PNG\r\n\x1a\n" + b"png-body"


def client_for(status: int = 200, body: bytes = JPEG) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body)))


def test_stores_the_original_under_its_content_hash(tmp_path) -> None:
    stored = store_remote_image("https://tong.visitkorea.or.kr/a.jpg", root=tmp_path, client=client_for())
    digest = hashlib.sha256(JPEG).hexdigest()
    assert stored.path == f"photos/{digest[:2]}/{digest}.jpg"
    assert (stored.byte_size, stored.content_type) == (len(JPEG), "image/jpeg")
    assert (tmp_path / stored.path).read_bytes() == JPEG
    assert media_url(stored.path) == f"/api/media/{stored.path}"
    # 같은 사진은 다른 주소로 받아도 한 파일 - 남는 조각 파일도 없다
    again = store_remote_image("https://tong.visitkorea.or.kr/b.jpg", root=tmp_path, client=client_for())
    assert again.path == stored.path
    assert [p.name for p in tmp_path.rglob("*") if p.is_file()] == [f"{digest}.jpg"]


def test_format_comes_from_the_bytes_not_the_url(tmp_path) -> None:
    stored = store_remote_image("https://tong.visitkorea.or.kr/photo.jpg", root=tmp_path, client=client_for(body=PNG))
    assert stored.path.endswith(".png") and stored.content_type == "image/png"


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (200, b"<html>error page</html>"),   # 사진 서버가 오류 페이지를 200 으로 준다
        (404, JPEG),
        (200, b"\xff\xd8\xff" + b"0" * MAX_BYTES),
    ],
    ids=["error-page", "not-found", "over-5mb"],
)
def test_rejects_what_is_not_a_usable_image(tmp_path, status: int, body: bytes) -> None:
    with pytest.raises(PhotoStorageError):
        store_remote_image("https://tong.visitkorea.or.kr/x.jpg", root=tmp_path, client=client_for(status, body))
    assert not any(p.is_file() for p in tmp_path.rglob("*"))


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000/api/health", "https://example.com/a.jpg", "file:///etc/passwd", "https://evilvisitkorea.or.kr/a.jpg"],
)
def test_fetches_only_from_the_tour_photo_server(tmp_path, url: str) -> None:
    # 후보 주소가 오염돼도 내부망이나 다른 곳으로 요청하지 않는다
    with pytest.raises(PhotoStorageError):
        store_remote_image(url, root=tmp_path, client=client_for())


def test_does_not_follow_a_redirect_elsewhere(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "tong.visitkorea.or.kr":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest"})
        return httpx.Response(200, content=JPEG)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(PhotoStorageError):
        store_remote_image("https://tong.visitkorea.or.kr/a.jpg", root=tmp_path, client=client)


def test_refuses_without_a_media_root(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import photo_storage

    monkeypatch.setattr(photo_storage, "media_root", lambda: None)
    with pytest.raises(PhotoStorageError):
        store_remote_image("https://tong.visitkorea.or.kr/x.jpg", client=client_for())


def test_media_files_are_served_with_a_long_immutable_cache(tmp_path) -> None:
    (tmp_path / "photos" / "ab").mkdir(parents=True)
    (tmp_path / "photos" / "ab" / "ab12.jpg").write_bytes(JPEG)
    app = FastAPI()
    app.mount("/api/media", MediaFiles(directory=tmp_path), name="media")
    with TestClient(app) as client:
        found = client.get("/api/media/photos/ab/ab12.jpg")
        assert found.status_code == 200 and found.content == JPEG
        assert found.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert client.get("/api/media/photos/ab/none.jpg").status_code == 404
        # 클라이언트가 ../ 를 미리 접지 않게 %2e%2e 로 보낸다 - StaticFiles 의 막기를 실제로 거친다
        assert client.get("/api/media/%2e%2e/%2e%2e/secret").status_code == 404
