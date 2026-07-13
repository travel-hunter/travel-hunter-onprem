"""Audit policy source URL quality.

Run:
    cd backend
    python scripts/audit_policy_sources.py --json path/to/policies.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

AuditStatus = Literal["verified", "needs_review", "invalid_source", "missing_source"]

ROOT_PATHS = {
    "/",
    "/sc",
    "/sc/portal",
    "/ct",
    "/ct/tour",
}
BLOCKED_HOST_MARKERS = ("localhost", "127.0.0.1", "example.com", "example.org", "example.net")


@dataclass(frozen=True)
class PolicySourceAuditResult:
    slug: str
    status: AuditStatus
    score: int
    source_url: str | None
    reasons: list[str]


def _source_url(policy: dict[str, Any]) -> str | None:
    value = policy.get("officialUrl") or policy.get("applyUrl")
    return value if isinstance(value, str) and value.strip() else None


def _url_reasons(url: str | None) -> list[str]:
    if not url:
        return ["missing source URL"]
    if url.strip() != url:
        return ["source URL has surrounding whitespace"]
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ["source URL is not an http/https URL"]
    host = (parsed.hostname or "").lower()
    if any(marker in host for marker in BLOCKED_HOST_MARKERS):
        return ["source URL uses placeholder or local host"]
    if parsed.path.rstrip("/") in ROOT_PATHS:
        return ["source URL points to a root or portal page"]
    return []


def _tokens(policy: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(policy.get(field) or "")
        for field in ("title", "org", "region", "summary", "amount", "category")
    )
    return {token for token in re.split(r"[^0-9A-Za-z가-힣]+", text) if len(token) >= 2}


def _alignment_score(policy: dict[str, Any], source_text: str | None) -> tuple[int, list[str]]:
    if source_text is None:
        return 40, ["source text was not supplied; URL shape only was checked"]
    tokens = _tokens(policy)
    if not tokens:
        return 0, ["policy has no comparable text tokens"]
    normalized_source = source_text.lower()
    matched = {token for token in tokens if token.lower() in normalized_source}
    score = int((len(matched) / max(len(tokens), 1)) * 100)
    if score < 35:
        return score, ["source text has weak title/summary alignment"]
    return score, [f"source text matched {len(matched)} policy tokens"]


def audit_policy(policy: dict[str, Any], source_text: str | None = None) -> PolicySourceAuditResult:
    slug = str(policy.get("slug") or "")
    url = _source_url(policy)
    url_reasons = _url_reasons(url)
    if not url:
        return PolicySourceAuditResult(
            slug=slug,
            status="missing_source",
            score=0,
            source_url=None,
            reasons=url_reasons,
        )
    if url_reasons:
        return PolicySourceAuditResult(
            slug=slug,
            status="invalid_source",
            score=0,
            source_url=url,
            reasons=url_reasons,
        )

    score, alignment_reasons = _alignment_score(policy, source_text)
    status: AuditStatus = "verified" if source_text is not None and score >= 35 else "needs_review"
    return PolicySourceAuditResult(
        slug=slug,
        status=status,
        score=score,
        source_url=url,
        reasons=alignment_reasons,
    )


def audit_policies(policies: list[dict[str, Any]]) -> list[PolicySourceAuditResult]:
    return [audit_policy(policy) for policy in policies]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit policy source URL quality.")
    parser.add_argument("--json", type=Path, required=True, help="Path to a policy JSON array.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    policies = json.loads(args.json.read_text(encoding="utf-8"))
    if not isinstance(policies, list):
        raise SystemExit("Policy audit input must be a JSON array.")
    results = [asdict(result) for result in audit_policies(policies)]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
