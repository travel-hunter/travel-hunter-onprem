from __future__ import annotations

from datetime import date

from app.services.policy_periods import ISSUE, USAGE, period_payload


def test_traffic_period_labels_map_to_issue_and_usage_evidence() -> None:
    evidence, decision, payload = period_payload(
        [
            ("예약 기간", "2026.09.15 ~ 2026.11.30"),
            ("탑승 및 이용 기간", "2026.10.01 ~ 2026.11.30"),
        ],
        default_year=2026,
        source="travelmonth-traffic",
    )

    assert [item.period_type for item in evidence] == [ISSUE, USAGE]
    assert decision.safe is True
    assert decision.period_type == ISSUE
    assert decision.deadline == date(2026, 11, 30)
    assert payload["periodEvidence"][0]["label"] == "예약 기간"
