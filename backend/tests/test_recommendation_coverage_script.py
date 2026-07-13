from types import SimpleNamespace

import pytest

from app.scripts import check_new_trip_recommendation_coverage as diagnostic


class FakeApiClient:
    def __init__(self, recommendation_payloads):
        self.recommendation_payloads = recommendation_payloads
        self.created = []

    def post_json(self, path, payload):
        trip_id = str(900 + len(self.created))
        self.created.append((path, payload, trip_id))
        return diagnostic.ApiResponse(200, {"id": trip_id, "title": payload["title"]})

    def get_json(self, path):
        trip_id = path.split("/")[-2]
        payload = self.recommendation_payloads.get(trip_id, [])
        return diagnostic.ApiResponse(200, payload)


def test_run_coverage_marks_pass_and_fail_and_keeps_ai_results_url():
    areas = [
        SimpleNamespace(id="jeju-all", name="제주 전체", sido="제주"),
        SimpleNamespace(id="chungbuk-cheongju", name="청주", sido="충북"),
    ]
    api = FakeApiClient({"900": [{"title": "추천 장소"}], "901": []})

    rows = diagnostic.run_coverage(
        areas=areas,
        api_client=api,
        frontend_base_url="http://127.0.0.1:4173",
        title_prefix="diag",
        style="휴식",
        duration_days=3,
        failure_diagnostics=lambda trip_id, area: {"tripId": trip_id, "area": area.id},
    )

    assert [row.status for row in rows] == ["PASS", "FAIL"]
    assert rows[0].recommendation_count == 1
    assert rows[1].recommendation_count == 0
    assert rows[1].ai_results_url == "http://127.0.0.1:4173/ai-results?tripId=901"
    assert rows[1].failure_detail == {
        "createResponse": {"id": "901", "title": "diag 청주 recommendation coverage"},
        "recommendationResponse": [],
        "diagnostics": {"tripId": "901", "area": "chungbuk-cheongju"},
    }


def test_format_markdown_table_includes_status_counts_and_urls():
    rows = [
        diagnostic.CoverageRow(
            travel_area_id="jeju-all",
            area_name="제주 전체",
            sido="제주",
            trip_id="900",
            recommendation_count=3,
            status="PASS",
            ai_results_url="http://127.0.0.1:4173/ai-results?tripId=900",
        )
    ]

    table = diagnostic.format_markdown_table(rows)

    assert "| travelAreaId | area | sido | tripId | recommendationCount | status | aiResultsUrl |" in table
    assert "| jeju-all | 제주 전체 | 제주 | 900 | 3 | PASS | http://127.0.0.1:4173/ai-results?tripId=900 |" in table


def test_print_report_includes_summary_failure_details_and_ai_results_url(capsys):
    rows = [
        diagnostic.CoverageRow(
            travel_area_id="chungbuk-cheongju",
            area_name="청주",
            sido="충북",
            trip_id="901",
            recommendation_count=0,
            status="FAIL",
            ai_results_url="http://127.0.0.1:4173/ai-results?tripId=901",
            failure_detail={
                "createResponse": {"id": "901"},
                "recommendationResponse": [],
                "diagnostics": {"exactCatalogRegionMatchCount": 0},
            },
        )
    ]

    diagnostic._print_report(rows, include_json=False)

    output = capsys.readouterr().out
    assert "Summary: 0 PASS / 1 FAIL / 1 total" in output
    assert "Failure details:" in output
    assert "http://127.0.0.1:4173/ai-results?tripId=901" in output
    assert "exactCatalogRegionMatchCount" in output


def test_validate_persistent_diagnostic_target_rejects_protected_env_without_override():
    with pytest.raises(SystemExit) as error:
        diagnostic.validate_persistent_diagnostic_target(
            base_url="http://127.0.0.1:8000",
            protected_env=True,
            allow_persistent_diagnostics=False,
        )

    assert error.value.code == 2


def test_validate_persistent_diagnostic_target_rejects_non_local_base_url_without_override():
    with pytest.raises(SystemExit) as error:
        diagnostic.validate_persistent_diagnostic_target(
            base_url="https://staging.example.com",
            protected_env=False,
            allow_persistent_diagnostics=False,
        )

    assert error.value.code == 2


def test_catalog_diagnostics_split_exact_and_related_counts():
    area = SimpleNamespace(
        id="jeju-east",
        name="제주 동부",
        sido="제주",
        included_cities=("제주시",),
        aliases=("성산",),
    )
    catalog = [
        {"region": "제주 동부"},
        {"region": "제주"},
        {"region": "성산"},
        {"region": "부산"},
    ]

    assert diagnostic.catalog_match_counts(area, catalog) == {
        "exactCatalogRegionMatchCount": 1,
        "relatedCatalogRegionMatchCount": 3,
    }
