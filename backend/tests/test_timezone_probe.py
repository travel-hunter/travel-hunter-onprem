from __future__ import annotations

import pytest

from scripts import timezone_probe


def test_local_database_url_guard_accepts_only_local_postgres_urls() -> None:
    assert timezone_probe.is_local_database_url("postgresql+psycopg://u:p@127.0.0.1:55432/db")
    assert timezone_probe.is_local_database_url("postgresql://u:p@localhost/db")
    assert timezone_probe.is_local_database_url("postgresql+psycopg://u:p@[::1]:55432/db")

    assert not timezone_probe.is_local_database_url("mysql://u:p@127.0.0.1/db")
    assert not timezone_probe.is_local_database_url("postgresql+psycopg://u:p@db.example.com/db")
    assert not timezone_probe.is_local_database_url("postgresql+psycopg:///travelhunter")

    with pytest.raises(ValueError, match="non-local database URL"):
        timezone_probe.assert_local_database_url("postgresql+psycopg://u:p@db.example.com/db")


def test_sql_builder_contains_required_timezone_probe_shape() -> None:
    sql = "\n".join(step.sql for step in timezone_probe.build_probe_steps())

    assert "SHOW timezone" in sql
    assert "now() AS now_timestamptz" in sql
    assert "localtimestamp AS localtimestamp_without_time_zone" in sql
    assert "TIMESTAMP '2024-01-01 00:00:00'" in sql
    assert "AT TIME ZONE current_setting('TimeZone')" in sql
    assert "CREATE TEMP TABLE timezone_probe_defaults" in sql
    assert "created_from_now timestamp without time zone DEFAULT now()" in sql
    assert "created_from_localtimestamp timestamp without time zone DEFAULT localtimestamp" in sql
    assert "created_timestamptz_now timestamp with time zone DEFAULT now()" in sql
    assert "now_default_minus_timestamptz_utc_hours" in sql
    assert "localtimestamp_default_minus_timestamptz_utc_hours" in sql
    assert (
        "created_from_now\n"
        "                        - (created_timestamptz_now AT TIME ZONE 'UTC')"
    ) in sql
    assert (
        "created_from_localtimestamp\n"
        "                        - (created_timestamptz_now AT TIME ZONE 'UTC')"
    ) in sql


def test_markdown_analysis_renders_plus_nine_hour_seoul_shift() -> None:
    results = [
        {
            "timezone": "UTC",
            "steps": {
                "show_timezone": [{"TimeZone": "UTC"}],
                "timestamp_interpretation": [{"literal_utc_minus_session_hours": 0.0}],
                "default_offsets": [
                    {
                        "now_default_minus_timestamptz_utc_hours": 0.0,
                        "localtimestamp_default_minus_timestamptz_utc_hours": 0.0,
                    }
                ],
            },
        },
        {
            "timezone": "Asia/Seoul",
            "steps": {
                "show_timezone": [{"TimeZone": "Asia/Seoul"}],
                "timestamp_interpretation": [{"literal_utc_minus_session_hours": 9.0}],
                "default_offsets": [
                    {
                        "now_default_minus_timestamptz_utc_hours": 9.0,
                        "localtimestamp_default_minus_timestamptz_utc_hours": 9.0,
                    }
                ],
            },
        },
    ]

    analysis = timezone_probe.analyze_probe_results(results)
    markdown = timezone_probe.render_markdown(
        results,
        database_url="postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter",
    )

    assert analysis["seoul_shift_hours"] == 9.0
    assert "Asia/Seoul" in markdown
    assert "+9.0h" in markdown
    assert "timestamp without time zone" in markdown
