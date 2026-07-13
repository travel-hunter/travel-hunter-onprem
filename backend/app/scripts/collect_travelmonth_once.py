from __future__ import annotations

import argparse
import json
import traceback
from collections.abc import Sequence

from app.db.session import get_session_factory
from app.services.external_benefit_collection import collect_external_benefits_from_live_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch official external policy benefit sources once, upsert parsed records, "
            "and promote active/fresh records into public policies."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds for the official TravelMonth page fetch.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit traceback details when collection fails.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session_factory = get_session_factory()
    try:
        with session_factory() as db:
            result = collect_external_benefits_from_live_sources(db, timeout=args.timeout)
    except Exception as error:
        payload = {"error": str(error)}
        if args.verbose:
            payload["trace"] = traceback.format_exc()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    print(
        json.dumps(
            {
                "sourceName": result.source_name,
                "sourceCategory": result.source_category,
                "parsedCount": result.parsed_count,
                "createdOrUpdatedCount": result.created_or_updated_count,
                "outcome": result.outcome,
                "sources": [
                    {
                        "sourceCategory": source.source_category,
                        "parsedCount": source.parsed_count,
                        "createdOrUpdatedCount": source.created_or_updated_count,
                        "outcome": source.outcome,
                        "error": source.error,
                    }
                    for source in result.sources
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
