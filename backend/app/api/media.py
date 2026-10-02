"""확정 사진 파일을 /api/media 로 내보낸다(app/services/photo_storage.py).

Caddy 는 지금처럼 /api 를 백엔드로 넘기기만 한다(두 호스트 모두) - Caddyfile · 로컬 4173 설정을 바꾸지 않아도 된다.
파일 이름이 내용 해시라 내용이 바뀌면 이름도 바뀐다 - 오래 캐시해도 안전하다.
"""

from __future__ import annotations

from starlette.staticfiles import StaticFiles


class MediaFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
