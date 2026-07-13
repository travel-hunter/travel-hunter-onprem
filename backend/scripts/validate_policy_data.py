"""Validate policy JSON data used by development seeds.

Run:
    cd backend
    python scripts/validate_policy_data.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_POLICY_DATA_PATH = Path(__file__).parent.parent / "app" / "data" / "dgtourcard_policies.json"
REQUIRED_FIELDS = {
    "slug",
    "title",
    "org",
    "region",
    "deadline",
    "amount",
    "summary",
    "category",
    "requirements",
    "documents",
    "officialUrl",
}
OPTIONAL_URL_FIELDS = ("officialUrl", "applyUrl")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOJIBAKE_MARKERS = ("占", "獄", "夷", "揶", "筌")
BLOCKED_URL_HOST_MARKERS = ("localhost", "127.0.0.1", "example.com", "example.org", "example.net")


def _validate_url(value: Any, *, field: str, slug: str | int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return f"{slug} {field} must be null or a URL string."

    stripped = value.strip()
    if stripped != value or not stripped:
        return f"{slug} {field} must not be blank or padded with whitespace."

    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"{slug} {field} must be an http/https URL: {value}"

    host = (parsed.hostname or "").lower()
    if any(marker in host for marker in BLOCKED_URL_HOST_MARKERS):
        return f"{slug} {field} must not use placeholder/local host: {value}"
    return None


def _has_mojibake_marker(value: str) -> bool:
    return any(marker in value for marker in MOJIBAKE_MARKERS) or any(0x7F <= ord(char) <= 0x9F for char in value)


def validate_policy_data(path: Path = DEFAULT_POLICY_DATA_PATH) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return [f"Cannot read {path}: {error}"]
    except json.JSONDecodeError as error:
        return [f"{path} is not valid JSON: {error}"]

    if not isinstance(payload, list):
        return ["Policy data must be a list."]

    seen_slugs: set[str] = set()
    for index, policy in enumerate(payload, start=1):
        if not isinstance(policy, dict):
            errors.append(f"Item {index} must be an object.")
            continue

        missing = sorted(REQUIRED_FIELDS - set(policy))
        if missing:
            errors.append(f"Item {index} is missing required fields: {', '.join(missing)}")

        slug = str(policy.get("slug", "")).strip()
        label: str | int = slug or index
        if not slug:
            errors.append(f"Item {index} has a blank slug.")
        elif slug in seen_slugs:
            errors.append(f"중복 slug: {slug}")
        seen_slugs.add(slug)

        deadline = str(policy.get("deadline", "")).strip()
        if deadline and not DATE_RE.match(deadline):
            errors.append(f"{label} deadline 형식은 YYYY-MM-DD여야 합니다: {deadline}")

        for field in ("title", "org", "region", "amount", "summary"):
            value = str(policy.get(field, ""))
            if _has_mojibake_marker(value):
                errors.append(f"{label} {field}에 인코딩 깨짐 의심 문자가 있습니다.")

        for field in ("requirements", "documents"):
            value = policy.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{label} {field} must be a list of strings.")

        for field in OPTIONAL_URL_FIELDS:
            url_error = _validate_url(policy.get(field), field=field, slug=label)
            if url_error:
                errors.append(url_error)

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate policy JSON data.")
    parser.add_argument("--path", type=Path, default=DEFAULT_POLICY_DATA_PATH)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    errors = validate_policy_data(args.path)
    if errors:
        print("Policy data validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Policy data validation passed: {args.path}")


if __name__ == "__main__":
    main()
