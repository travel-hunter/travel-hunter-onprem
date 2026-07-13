"""Probe local PostgreSQL timestamp/timezone behavior for G002 evidence.

Run locally:
    cd backend
    python scripts/timezone_probe.py

The probe is intentionally local-only. It writes markdown evidence under
``.omx/tmp/g002-timezone-probe.md`` and falls back to a blocker note when a
local database is not reachable; deterministic pytest coverage still exercises
its SQL builder and markdown analysis without requiring a live DB.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

DEFAULT_DATABASE_URL = "postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter"
PROBE_TIMEZONES = ("UTC", "Asia/Seoul")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = REPO_ROOT / ".omx" / "tmp" / "g002-timezone-probe.md"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class SqlStep:
    """A labeled SQL statement in the timezone probe."""

    label: str
    sql: str


def get_database_url() -> str:
    """Return the configured database URL or the local development default."""

    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def is_local_database_url(database_url: str) -> bool:
    """Return True only for local PostgreSQL URLs.

    The support script must never point at staging/production by accident.
    Unix-socket URLs are rejected because their target server is ambiguous for
    this local evidence probe.
    """

    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("postgresql"):
        return False
    hostname = parsed.hostname
    return hostname in LOCAL_HOSTS


def assert_local_database_url(database_url: str) -> None:
    """Raise ValueError if the URL is not an explicitly local PostgreSQL URL."""

    if not is_local_database_url(database_url):
        raise ValueError(
            "Refusing to run timezone probe against a non-local database URL. "
            "Use localhost, 127.0.0.1, or ::1."
        )


def build_probe_steps() -> list[SqlStep]:
    """Build the PostgreSQL statements used for each session timezone."""

    return [
        SqlStep("show_timezone", "SHOW timezone"),
        SqlStep(
            "timestamp_interpretation",
            """
            SELECT
                now() AS now_timestamptz,
                localtimestamp AS localtimestamp_without_time_zone,
                TIMESTAMP '2024-01-01 00:00:00' AS literal_without_time_zone,
                TIMESTAMP '2024-01-01 00:00:00' AT TIME ZONE current_setting('TimeZone')
                    AS literal_at_session_timezone,
                TIMESTAMP '2024-01-01 00:00:00' AT TIME ZONE 'UTC'
                    AS literal_at_utc,
                EXTRACT(
                    EPOCH FROM (
                        (TIMESTAMP '2024-01-01 00:00:00' AT TIME ZONE 'UTC')
                        - (TIMESTAMP '2024-01-01 00:00:00' AT TIME ZONE current_setting('TimeZone'))
                    )
                ) / 3600.0 AS literal_utc_minus_session_hours
            """,
        ),
        SqlStep("drop_temp_table", "DROP TABLE IF EXISTS timezone_probe_defaults"),
        SqlStep(
            "create_temp_table",
            """
            CREATE TEMP TABLE timezone_probe_defaults (
                id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                created_from_now timestamp without time zone DEFAULT now(),
                created_from_localtimestamp timestamp without time zone DEFAULT localtimestamp,
                created_timestamptz_now timestamp with time zone DEFAULT now()
            ) ON COMMIT DROP
            """,
        ),
        SqlStep("insert_defaults", "INSERT INTO timezone_probe_defaults DEFAULT VALUES"),
        SqlStep(
            "default_offsets",
            """
            SELECT
                created_from_now,
                created_from_localtimestamp,
                created_timestamptz_now,
                created_from_now AT TIME ZONE current_setting('TimeZone')
                    AS created_from_now_session_normalized,
                created_from_now AT TIME ZONE 'UTC'
                    AS created_from_now_utc_normalized,
                created_from_localtimestamp AT TIME ZONE current_setting('TimeZone')
                    AS localtimestamp_session_normalized,
                created_from_localtimestamp AT TIME ZONE 'UTC'
                    AS localtimestamp_utc_normalized,
                EXTRACT(
                    EPOCH FROM (
                        created_from_now
                        - (created_timestamptz_now AT TIME ZONE 'UTC')
                    )
                ) / 3600.0 AS now_default_minus_timestamptz_utc_hours,
                EXTRACT(
                    EPOCH FROM (
                        created_from_localtimestamp
                        - (created_timestamptz_now AT TIME ZONE 'UTC')
                    )
                ) / 3600.0 AS localtimestamp_default_minus_timestamptz_utc_hours
            FROM timezone_probe_defaults
            ORDER BY id DESC
            LIMIT 1
            """,
        ),
    ]


def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def _execute_session_probe(connection: Connection, timezone: str) -> dict[str, Any]:
    if timezone not in PROBE_TIMEZONES:
        raise ValueError(f"Unsupported probe timezone: {timezone}")
    escaped_timezone = timezone.replace("\'", "\'\'")
    connection.execute(text(f"SET TIME ZONE '{escaped_timezone}'"))
    session_result: dict[str, Any] = {"timezone": timezone, "steps": {}}

    for step in build_probe_steps():
        result = connection.execute(text(step.sql))
        if step.label in {"drop_temp_table", "create_temp_table", "insert_defaults"}:
            session_result["steps"][step.label] = {"rowcount": result.rowcount}
            continue
        rows = [_row_to_dict(row) for row in result.fetchall()]
        session_result["steps"][step.label] = rows

    return session_result


def run_probe(database_url: str) -> list[dict[str, Any]]:
    """Run the probe against a local PostgreSQL database."""

    assert_local_database_url(database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [_execute_session_probe(connection, timezone) for timezone in PROBE_TIMEZONES]
    finally:
        engine.dispose()


def _format_value(value: Any) -> str:
    if isinstance(value, float | Decimal):
        numeric = float(value)
        return f"{numeric:+.1f}h" if abs(numeric) < 24 else f"{numeric:.6g}"
    return str(value)


def _first_row(session: dict[str, Any], step_name: str) -> dict[str, Any]:
    rows = session.get("steps", {}).get(step_name, [])
    if isinstance(rows, list) and rows:
        return rows[0]
    return {}


def analyze_probe_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract deterministic evidence points from raw probe rows."""

    sessions: dict[str, dict[str, Any]] = {}
    for session in results:
        timezone = str(session.get("timezone", ""))
        interpretation = _first_row(session, "timestamp_interpretation")
        offsets = _first_row(session, "default_offsets")
        sessions[timezone] = {
            "shown_timezone": _first_row(session, "show_timezone").get("TimeZone")
            or _first_row(session, "show_timezone").get("timezone"),
            "literal_utc_minus_session_hours": interpretation.get("literal_utc_minus_session_hours"),
            "now_default_minus_timestamptz_utc_hours": offsets.get(
                "now_default_minus_timestamptz_utc_hours"
            ),
            "localtimestamp_default_minus_timestamptz_utc_hours": offsets.get(
                "localtimestamp_default_minus_timestamptz_utc_hours"
            ),
        }

    seoul_shift = sessions.get("Asia/Seoul", {}).get("localtimestamp_default_minus_timestamptz_utc_hours")
    if seoul_shift is None:
        seoul_shift = sessions.get("Asia/Seoul", {}).get("literal_utc_minus_session_hours")

    return {"sessions": sessions, "seoul_shift_hours": seoul_shift}


def render_markdown(results: list[dict[str, Any]], *, database_url: str) -> str:
    """Render markdown evidence for the timezone probe."""

    analysis = analyze_probe_results(results)
    lines = [
        "# G002 Timezone Probe Evidence",
        "",
        "Local-only PostgreSQL probe completed.",
        "",
        f"- Database URL host: `{urlparse(database_url).hostname}`",
        f"- Sessions probed: {', '.join(PROBE_TIMEZONES)}",
        "- Probe focus: timestamp without time zone defaults, `now()`, `localtimestamp`, and comparison against the UTC-normalized `created_timestamptz_now` instant.",
        "",
        "## Offset summary",
        "",
        "| Session | SHOW timezone | literal UTC-session | now() default vs timestamptz UTC | localtimestamp vs timestamptz UTC |",
        "| --- | --- | ---: | ---: | ---: |",
    ]

    for timezone in PROBE_TIMEZONES:
        session = analysis["sessions"].get(timezone, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    timezone,
                    _format_value(session.get("shown_timezone")),
                    _format_value(session.get("literal_utc_minus_session_hours")),
                    _format_value(session.get("now_default_minus_timestamptz_utc_hours")),
                    _format_value(session.get("localtimestamp_default_minus_timestamptz_utc_hours")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Analysis",
            "",
            f"- Asia/Seoul timestamp-without-time-zone defaults show a {_format_value(analysis.get('seoul_shift_hours'))} silent wall-clock shift when compared with the UTC-normalized `created_timestamptz_now` instant.",
            "- A `timestamp without time zone` stores a wall-clock value; `AT TIME ZONE` supplies the timezone used to normalize that wall-clock value to a timestamptz instant.",
            "- `created_timestamptz_now` remains an instant, while `created_from_now` and `created_from_localtimestamp` are session-local wall-clock timestamps before interpretation.",
            "",
            "## Raw session rows",
            "",
        ]
    )

    for session in results:
        lines.extend([f"### {session.get('timezone')}", ""])
        for step_name, payload in session.get("steps", {}).items():
            lines.extend([f"#### {step_name}", "", "```text", repr(payload), "```", ""])

    return "\n".join(lines).rstrip() + "\n"


def render_blocker_markdown(error: Exception, *, database_url: str) -> str:
    """Render blocker evidence when the local DB is unavailable."""

    return (
        "# G002 Timezone Probe Evidence\n\n"
        "Local-only PostgreSQL probe could not connect or complete.\n\n"
        f"- Database URL host: `{urlparse(database_url).hostname}`\n"
        f"- Blocker: `{type(error).__name__}: {error}`\n"
        "- Deterministic pytest coverage still verifies the local-only guard, SQL builder, markdown analysis, and the expected +9.0h Asia/Seoul shift without requiring a live DB.\n"
    )


def write_evidence(markdown: str, path: Path = DEFAULT_EVIDENCE_PATH) -> Path:
    """Write evidence markdown and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def main() -> None:
    database_url = get_database_url()
    try:
        results = run_probe(database_url)
        markdown = render_markdown(results, database_url=database_url)
    except Exception as error:  # local support script must leave auditable evidence
        markdown = render_blocker_markdown(error, database_url=database_url)
    evidence_path = write_evidence(markdown)
    print(f"Wrote timezone probe evidence: {evidence_path}")


if __name__ == "__main__":
    main()
