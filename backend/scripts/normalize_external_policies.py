"""Promote and repair public policies from collected external source records.

Run after deploy when normalization rules change:
    cd backend
    python scripts/normalize_external_policies.py
"""

from __future__ import annotations

from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.db.session import get_session_factory
from app.services.policy_normalization import promote_external_benefits_to_policies


def main() -> int:
    session_factory = get_session_factory()
    with session_factory() as db:
        result = promote_external_benefits_to_policies(db)
        db.commit()
    print(f"promoted_or_repaired={result.promoted_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
