"""Collect photo review candidates from TourAPI (사진 검토 0047).

Run after deploy (and after normalize_external_policies.py so policies.city is populated):
    cd backend
    python scripts/collect_photo_candidates.py [--dry-run] [--only-sido 전남]

시군(도 전체 포함) · 공개 정책을 검토 대상으로 두고, 검토 대기 대상마다 후보가 6장이 되게 채운다.
관리자 화면 '사진 검토'의 '후보 채우기'가 같은 일을 뒤에서 한다 - 이 스크립트는 서버에서 직접 돌릴 때 쓴다.
앱에 사진을 내걸지 않는다 - 관리자가 '사진 검토'에서 한 장을 확정해야 나간다. 결정된 대상은 건드리지 않는다.
옛 backfill_region_photos.py · backfill_policy_photos.py 를 대신한다(그 둘은 검토 없이 사진을 내걸었다).

TOUR_API_ENABLED=true + TOUR_API_SERVICE_KEY 가 없으면 아무것도 하지 않고 0 으로 끝난다.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.photo_criteria import ImageSizeProbe
from app.services.photo_review import collect_candidates
from app.services.tour_api import build_tour_api_client


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect TourAPI photo candidates for admin photo review.")
    parser.add_argument("--dry-run", action="store_true", help="채운 결과를 세기만 하고 되돌린다")
    parser.add_argument("--only-sido", type=str, default=None)
    args = parser.parse_args(argv)

    provider = build_tour_api_client()
    if provider is None:
        print("tour_api_disabled; no-op")
        return 0

    from app.db.session import get_session_factory

    with get_session_factory()() as db:
        # 대상 하나마다 저장한다(관리자 '후보 채우기'와 같은 함수). dry-run 은 저장하지 않고 끝에 되돌린다
        summary = collect_candidates(
            db, provider, size_of=ImageSizeProbe(), only_sido=args.only_sido, commit=not args.dry_run
        )
        if args.dry_run:
            db.rollback()
    print(
        f"targets_created={summary.targets_created} targets_total={summary.targets_total} "
        f"targets_filled={summary.targets_filled} targets_empty={summary.targets_empty} "
        f"candidates_added={summary.candidates_added} decided_skipped={summary.decided_skipped} "
        f"probe_failures={summary.probe_failures}{' (dry-run)' if args.dry_run else ''}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
