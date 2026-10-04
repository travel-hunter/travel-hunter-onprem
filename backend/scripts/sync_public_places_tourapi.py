"""TourAPI 공공데이터 장소를 지금 받는다(카카오 운영정책 2단계 - public_places).

    cd backend
    python scripts/sync_public_places_tourapi.py [--accept-shrink 39]

6개 유형 전국 목록(약 50회 호출 - 개발 계정 하루 1,000회 몫)을 받아 넣는다. 유형마다 끝까지 받았는지 본 뒤 통과한 유형의 오래된
행만 지운다. 자동 동기화(PUBLIC_PLACES_SYNC_ENABLED)와 같은 함수지만 때(오늘 시도 · 7일)를 가리지 않는다 - 처음 적재나 손으로 다시
받을 때 쓴다. 종료 코드: success 0, partial 2(못 지운 유형이 있음), error 1. 서버에서 돌리는 것은 실행할 때마다 승인받는다.

지우지 못한 유형은 출력의 kept= 에 까닭과 함께 나온다. '39:10000->7000' 은 끝까지 받았지만 기존의 80% 미만이라는 뜻이다 -
관광공사 쪽에서 정말 줄었다고 확인했으면 --accept-shrink 39 로 한 번 더 돌려 그 유형만 80% 기준 없이 지운다.
'39:incomplete'(끝까지 못 받음)는 받아들여도 지우지 않는다.
TOUR_API_ENABLED=true + TOUR_API_SERVICE_KEY 가 없으면 아무것도 하지 않는다. 키는 찍지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.public_places import TOURAPI_CONTENT_TYPES, sync_tourapi_places, utc_now
from app.services.tour_api import build_tour_api_client


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync TourAPI places into public_places.")
    parser.add_argument(
        "--accept-shrink", default="",
        help="원인을 확인한, 크게 줄어든 유형(contentTypeId, 쉼표로 - 예: 39). 끝까지 받았으면 그 유형의 80 퍼센트 기준을 끈다",
    )
    args = parser.parse_args(argv)
    accept = {value.strip() for value in args.accept_shrink.split(",") if value.strip()}
    unknown = sorted(accept - set(TOURAPI_CONTENT_TYPES))
    if unknown:
        parser.error(f"모르는 유형 {','.join(unknown)} - {','.join(TOURAPI_CONTENT_TYPES)} 중에서 고른다")

    client = build_tour_api_client()
    if client is None:
        print("tour_api_disabled; no-op")
        return 0

    from app.db.session import get_session_factory

    try:
        with get_session_factory()() as db:
            result = sync_tourapi_places(db, client, now=utc_now(), accept_shrink=accept)
    except Exception as exc:   # 상태 표(public_place_sync_state)에는 error 로 남았다
        print(f"source=tourapi outcome=error reason={type(exc).__name__}")
        return 1
    print(
        f"source={result.source} received={result.received_count} written={result.parsed_count} "
        f"skipped={result.skipped_count} pruned={result.pruned_count} outcome={result.outcome}"
        + (f" kept={','.join(result.kept)}" if result.kept else "")
    )
    return 0 if result.outcome == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
