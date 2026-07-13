from types import SimpleNamespace

import pytest

from app.scripts import smoke_kakao_local_candidates as smoke


def area(area_id: str = "jeju-all"):
    return SimpleNamespace(id=area_id, name="제주 전체", sido="제주")


def test_run_smoke_uses_catalog_fallback_when_kakao_env_is_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "settings",
        SimpleNamespace(kakao_local_enabled=False, kakao_local_rest_api_key=""),
    )

    rows = smoke.run_smoke(
        areas=[area()],
        style="휴식",
        day_count=3,
        limit=12,
        min_candidates=1,
        require_kakao=False,
    )

    assert len(rows) == 1
    assert rows[0].mode == "catalog_fallback"
    assert rows[0].status == "PASS"
    assert rows[0].candidateCount > 0
    assert rows[0].sampleTitles


def test_run_smoke_requires_kakao_when_requested(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "settings",
        SimpleNamespace(kakao_local_enabled=False, kakao_local_rest_api_key=""),
    )

    with pytest.raises(smoke.KakaoLocalConfigurationError):
        smoke.run_smoke(
            areas=[area()],
            style="휴식",
            day_count=3,
            limit=12,
            min_candidates=1,
            require_kakao=True,
        )


def test_default_fallback_smoke_areas_are_non_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke,
        "settings",
        SimpleNamespace(kakao_local_enabled=False, kakao_local_rest_api_key=""),
    )

    rows = smoke.run_smoke(
        areas=smoke.resolve_areas(smoke.DEFAULT_AREA_IDS),
        style="휴식",
        day_count=3,
        limit=12,
        min_candidates=6,
        require_kakao=False,
    )

    assert len(rows) == len(smoke.DEFAULT_AREA_IDS)
    assert all(row.mode == "catalog_fallback" for row in rows)
    assert all(row.status == "PASS" for row in rows)


def test_resolve_areas_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError) as error:
        smoke.resolve_areas(["not-a-real-area"])

    assert "not-a-real-area" in str(error.value)


def test_print_report_includes_mode_counts_and_summary(capsys) -> None:
    row = smoke.SmokeRow(
        travelAreaId="jeju-all",
        area="제주 전체",
        sido="제주",
        mode="catalog_fallback",
        candidateCount=2,
        categoryCounts={"other": 2},
        metadata={"withAddress": 0, "withCoordinates": 0, "withExternalPlaceId": 2, "withPlaceUrl": 0},
        status="PASS",
        sampleTitles=["함덕해수욕장", "사려니숲길"],
    )

    smoke.print_report([row], include_json=False)

    output = capsys.readouterr().out
    assert "| jeju-all | 제주 전체 | catalog_fallback | 2 | other:2 |" in output
    assert "Summary: 1 PASS / 0 FAIL / 1 total" in output
