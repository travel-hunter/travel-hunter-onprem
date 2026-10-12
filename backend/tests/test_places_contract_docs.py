"""3단계 담는 흐름의 API 계약 · 골든이 코드와 같은 모양을 말하는지 - 카카오 값을 받지 않는다는 규칙이 문서에서 되살아나지 않게 한다."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / ".agent/evals/api-contract-golden.json").read_text(encoding="utf-8"))
CONTRACT = (ROOT / "docs/mvp-api-contract.md").read_text(encoding="utf-8")
OLD_KAKAO_FIELDS = {"label", "meta", "address", "latitude", "longitude", "category", "categoryCode", "placeUrl", "sourceProvider", "externalPlaceId"}


def golden(method: str, path: str) -> dict:
    return next(item for item in GOLDEN["endpoints"] if (item["method"], item["path"]) == (method, path))


def section(start: str, end: str) -> str:
    return CONTRACT.split(start)[1].split(end)[0]


def test_golden_place_requests_use_public_or_custom_places_and_no_kakao_fields() -> None:
    requests = [golden("POST", "/api/trips/1/days/1/places")["request"], golden("POST", "/api/trips/1/days/1/places")["customPlaceRequestExample"]]
    requests += golden("POST", "/api/trips/1/days/1/places/batch")["request"]["places"]
    for request in requests:
        assert ("publicPlace" in request) != ("customPlace" in request)
        assert not OLD_KAKAO_FIELDS & set(request)
    update = golden("PATCH", "/api/trips/1/places/2")
    assert {"label", "memo"} <= set(update["request"]) and "meta" not in update["request"]
    assert all(("publicPlace" in item) != ("customPlace" in item) for item in update["replaceRequestExamples"])


def test_the_new_routes_are_in_the_golden_the_contract_and_the_app() -> None:
    served = {(method.upper(), served_path) for served_path, item in app.openapi()["paths"].items() for method in item}
    for golden_path, served_path in (
        ("/api/trips/1/places/2/public-candidates", "/api/trips/{trip_id}/places/{place_id}/public-candidates"),
        ("/api/trips/1/area-center", "/api/trips/{trip_id}/area-center"),
    ):
        golden("GET", golden_path)
        assert ("GET", served_path) in served
        assert f"### GET {served_path.removeprefix('/api')}" in CONTRACT


def test_the_contract_and_golden_describe_the_new_place_fields_and_recommendations() -> None:
    days = golden("GET", "/api/trips")["requiredArrayItemFields"]["days"]
    for field in ("memo", "placeOrigin", "publicSource", "publicSourceId", "publicCategory", "photoUrl", "photoLicense", "needsConfirmation"):
        assert f"| {field} |" in CONTRACT
        assert field in days
    recommendations = golden("GET", "/api/trips/1/recommendations")
    assert "public_place" in recommendations["optionalArrayItemFields"]["sourceType"]
    assert {"publicSource", "publicSourceId", "publicCategory", "photoUrl", "photoLicense"} <= set(recommendations["optionalArrayItemFields"])
    assert "cafe" in recommendations["categoryGroupValues"]
    assert "`public_place`" in CONTRACT


def test_the_place_docs_say_unknown_nested_fields_are_422_and_a_public_row_keeps_its_name_apart() -> None:
    for method, path in (("POST", "/api/trips/1/days/1/places"), ("POST", "/api/trips/1/days/1/places/batch"), ("PATCH", "/api/trips/1/places/2")):
        assert "unknown field" in golden(method, path)["dbModeBehavior"] and "inside publicPlace or customPlace" in golden(method, path)["dbModeBehavior"]
    update = section("### PATCH /trips/{trip_id}/places/{place_id}\n", "### PATCH /trips/{trip_id}/places/{place_id}/move")
    assert "`user_label`" in update and "안의 모르는 필드" in update
    assert "user_label" in golden("PATCH", "/api/trips/1/places/2")["dbModeBehavior"]
    assert "| label | string | 화면에 보이는 장소 이름." in CONTRACT


def test_the_search_docs_say_503_for_a_misconfigured_kakao_and_an_empty_list_for_an_off_one() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    assert "- 503:" in search and "Place search is unavailable" in search
    behavior = golden("GET", "/api/trips/1/place-search")["dbModeBehavior"]
    assert "503" in behavior and "switched off" in behavior and "not a 500" not in behavior


def test_the_search_docs_describe_the_prematch_on_each_row() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    assert '"publicMatch"' in search and "6곳" in search and "always present" in search
    entry = golden("GET", "/api/trips/1/place-search")
    assert entry["requiredArrayItemFields"]["publicMatch"] == "object|null"
    assert "publicMatch" not in entry["optionalArrayItemFields"]
    assert "publicMatch" in entry["dbModeBehavior"] and "6 places" in entry["dbModeBehavior"]
    design = (ROOT / "docs/superpowers/specs/2026-10-03-public-place-storage-design.md").read_text(encoding="utf-8")
    assert "검색 결과 6곳을 검색 요청 안에서 한꺼번에 맞춰" in design


def test_the_match_docs_describe_the_per_source_lookup_boxes() -> None:
    assert "1km 상자는 TourAPI 만" in section("### POST /places/match", "### GET /trips/{trip_id}/recommendations")
    assert "a 200 m box for store rows" in golden("POST", "/api/places/match")["dbModeBehavior"]


def test_the_contract_documents_address_fill_locate_and_geo_reference_without_raw_coordinates() -> None:
    for needle in ("publicMatch.fill", "POST /api/places/locate", "nearCenter", "customPlace.geoRef", "Address reference not found",
                   "Address lookup is unavailable", "geoKind", "151842"):
        assert needle in CONTRACT, needle
    # 나만의 장소는 이름 · 지번 참조뿐 - 위도 · 경도를 받지 않는다는 문장이 계약에 있고, 3단계 때의 좌표 예시는 남아 있지 않다
    assert "위도 · 경도 · 주소는 받지 않음" in CONTRACT
    assert '"customPlace": { "name": "우리 아지트", "latitude"' not in CONTRACT
    golden_text = json.dumps(GOLDEN, ensure_ascii=False)
    assert "/api/places/locate" in golden_text
    # 골든의 담기 · 수정 요청에는 customPlace 의 좌표가 없다(name · geoRef 만)
    for method, path in (("POST", "/api/trips/1/days/1/places"), ("PATCH", "/api/trips/1/places/2")):
        assert '"latitude": 34.75' not in json.dumps(golden(method, path), ensure_ascii=False)
    batch = golden("POST", "/api/trips/1/days/1/places/batch")["request"]["places"]
    assert all(not {"latitude", "longitude"} & set(item.get("customPlace", {})) for item in batch)
    assert "geoKind" in json.dumps(golden("GET", "/api/trips"), ensure_ascii=False)


def test_the_locate_route_is_in_the_golden_the_contract_and_the_app() -> None:
    served = {(method.upper(), served_path) for served_path, item in app.openapi()["paths"].items() for method in item}
    assert ("POST", "/api/places/locate") in served
    assert "### POST /places/locate" in CONTRACT
    assert set(golden("POST", "/api/places/locate")["requiredFields"]) == {"fill", "nearCenter"}


SUGGEST_HEADING = "### GET /trips/{trip_id}/place-suggest"


def test_the_suggest_route_is_in_the_golden_the_contract_and_the_app() -> None:
    paths = app.openapi()["paths"]
    served = {(method.upper(), served_path) for served_path, item in paths.items() for method in item}
    assert ("GET", "/api/trips/{trip_id}/place-suggest") in served
    assert f"{SUGGEST_HEADING}\n" in CONTRACT
    entry = golden("GET", "/api/trips/1/place-suggest")
    assert entry["authRequired"] is True and entry["status"] == 200
    assert entry["query"] == {"query": "메타세쿼"} and entry["responseKind"] == "string[]"
    # 응답은 문자열 배열이다 - 객체 필드 키(requiredArrayItemFields)를 달지 않는다
    assert not {"requiredArrayItemFields", "optionalArrayItemFields"} & set(entry)
    schema = paths["/api/trips/{trip_id}/place-suggest"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "array" and schema["items"] == {"type": "string"}


def test_the_suggest_docs_state_the_access_the_input_rules_the_order_and_what_is_never_logged() -> None:
    suggest = section(SUGGEST_HEADING, "### GET /places/search")
    for needle in ("- 401:", "- 404:", "- 422:", "`string[]`", "최대 6", "2자 미만", "`__`", "80자", "일정 지역", "시군마다",
                   "스타벅스 강릉", "스타벅스 동해", "이름만", "로그에 남기지 않는다", "DB 오류", "빈 배열"):
        assert needle in suggest, needle
    behavior = golden("GET", "/api/trips/1/place-suggest")["dbModeBehavior"]
    for needle in ("trip members", "404", "422", "80", "fewer than 2", "at most 6", "travel area", "per city", "names only",
                   "never logged", "database error", "empty array"):
        assert needle in behavior, needle


def test_the_search_docs_describe_the_area_first_search_and_its_fallback() -> None:
    search = section("### GET /trips/{trip_id}/place-search", SUGGEST_HEADING)
    for needle in ("지역 먼저", "반경 20km", "6곳 미만", "2차", "1차가 실패", "응답 모양은 같다", "좌표 없이", "로그에 남기지 않는다", "반경 밖 장소는 결과에 들지 않", "이웃 지역"):
        assert needle in search, needle
    assert "지역 밖 장소도 결과에서 빠지지 않는다" not in search   # 옛 설명 - 20km 안에서 6곳이 차면 반경 밖 장소는 없다
    behavior = golden("GET", "/api/trips/1/place-search")["dbModeBehavior"]
    for needle in ("20 km", "fewer than 6", "second", "first request fails", "response shape is the same", "without coordinates"):
        assert needle in behavior, needle


def test_the_feature_spec_lists_the_suggest_endpoint() -> None:
    spec = (ROOT / "docs/implemented-feature-spec.md").read_text(encoding="utf-8")
    assert "`GET /api/trips/{trip_id}/place-suggest`" in spec
