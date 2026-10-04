"""소상공인 상가(상권)정보 분기 파일을 public_places 에 넣는다(카카오 운영정책 2단계).

    cd backend
    python scripts/load_public_places_sangga.py <파일.zip|파일.csv ...> [--only 세종] [--dry-run] [--accept-shrink 세종]

음식(I2) · 숙박(I1) · 예술·스포츠(R1)만 넣는다(20260630판 약 104만 건). 끝까지 읽은 뒤 시도마다 이번 고유 행이 기존의 80% 이상인
시도의 오래된 행만 지운다. --only 는 그 말이 이름에 든 시도 파일만 넣고 지우지 않는다(로컬 시험용). --dry-run 은 DB 를 건드리지
않고 분류별 건수만 센다. 종료 코드: success 0, partial 2(못 지운 시도가 있거나 빠진 시도가 있음), error 1.

지우지 못한 시도는 출력의 kept= 에 까닭과 함께 나온다. '세종:10000->7000' 은 이번 판에서 읽었지만 기존의 80% 미만이라는 뜻이다 -
새 판에서 정말 줄었다고 확인했으면 같은 파일로 --accept-shrink 세종 을 붙여 한 번 더 돌린다(kept 에 나온 이름 그대로).
'세종:missing'(판에 그 시도 파일이 없음)은 받아들여도 지우지 않는다.
파일은 data.go.kr 15083033 의 분기판. 서버에서 돌리는 것은 실행할 때마다 승인받는다.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.public_places import iter_sangga_rows, load_sangga_places, sangga_row, utc_now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load SBIZ store data (food/stay/arts-sports) into public_places.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--only", default=None, help="이 말이 이름에 든 시도 파일만(지우지 않는다)")
    parser.add_argument("--dry-run", action="store_true", help="DB 를 건드리지 않고 분류별 건수만 센다")
    parser.add_argument(
        "--accept-shrink", default="",
        help="원인을 확인한, 크게 줄어든 시도(kept 에 나온 짧은 이름, 쉼표로 - 예: 세종). 그 시도의 80 퍼센트 기준을 끈다",
    )
    args = parser.parse_args(argv)
    accept = {value.strip() for value in args.accept_shrink.split(",") if value.strip()}
    if accept and args.only:
        parser.error("--accept-shrink 는 --only 없이 전체 판을 넣을 때만 쓴다")

    rows = iter_sangga_rows(args.paths, only=args.only)
    if args.dry_run:
        now = utc_now()
        counts = Counter((sangga_row(raw, now) or {}).get("category", "excluded") for raw in rows)
        print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())), "(dry-run)")
        return 0

    from app.db.session import get_session_factory

    try:
        with get_session_factory()() as db:
            result = load_sangga_places(db, rows, now=utc_now(), prune=args.only is None, accept_shrink=accept)
    except Exception as exc:   # 상태 표(public_place_sync_state)에는 error 로 남았다
        print(f"source=sangga outcome=error reason={type(exc).__name__}")
        return 1
    print(
        f"source={result.source} received={result.received_count} written={result.parsed_count} "
        f"skipped={result.skipped_count} pruned={result.pruned_count} outcome={result.outcome}"
        + (f" kept={','.join(result.kept)}" if result.kept else "")
    )
    return 0 if result.outcome == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
