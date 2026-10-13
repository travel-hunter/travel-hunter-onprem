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
    assert '"publicMatch"' in search and "15곳" in search and "always present" in search
    entry = golden("GET", "/api/trips/1/place-search")
    assert entry["requiredArrayItemFields"]["publicMatch"] == "object|null"
    assert "publicMatch" not in entry["optionalArrayItemFields"]
    assert "publicMatch" in entry["dbModeBehavior"] and "15 places" in entry["dbModeBehavior"]
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


def test_place_suggest_is_gone_from_the_contract_the_golden_and_the_feature_spec() -> None:
    assert "place-suggest" not in CONTRACT
    assert all("place-suggest" not in item["path"] for item in GOLDEN["endpoints"])
    assert "place-suggest" not in (ROOT / "docs/implemented-feature-spec.md").read_text(encoding="utf-8")


def test_the_search_docs_describe_pages_marks_and_completed_word_search() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    for needle in ("마다 15곳이다", "(밖이면 422)", "45곳", "1~3쪽", "새 장소가 0개", "`nearby` 는 카카오가 준 거리", "'다른 지역' 구분 줄",
                   "반경 밖 장소는 결과에 들지 않", "이웃 지역", "1쪽 1~2번, 2쪽 최대 5번, 3쪽 최대 6번", "반경 쪽이 실패하면 빈 배열(2 · 3쪽도)",
                   "전국 쪽만 실패하면 모은 줄 그대로", "완성어 상위 3개", "대신 찾은 결과는 2쪽이 없다", "모두 최대 8번이다",
                   "2자는 TourAPI 이름만, 3자 이상이면 가게 이름도", "말 하나의 카카오 실패는 건너뛴다", "검색어 · 완성어 · 좌표는 로그에 남기지 않는다"):
        assert needle in search, needle
    assert "6곳" not in search
    assert "- `page`: integer, 1-3(기본 1). 15곳씩." in search
    assert "`page` 가 1~3 밖" in search
    home = section("### GET /places/search", "### GET /places/nearby")
    for needle in ("**덜 친 말**", "완성어 상위 3개", "2자는 TourAPI 이름만, 3자 이상이면 가게 이름도", "대신 찾은 줄은 `viaWord` 에 찾은 말을 싣고",
                   "완성어 읽기가 실패하면 빈 배열", "말 하나의 카카오 실패는 건너뛰며", "DB 세션이 없으면 대신 찾지 않는다", "키워드 호출이 실패하지 않았으면"):
        assert needle in home, needle
    assert "| nearby | boolean \\| null |" in CONTRACT and "| viaWord | string \\| null |" in CONTRACT
    assert "전국 관광지류" not in CONTRACT
    entry = golden("GET", "/api/trips/1/place-search")
    assert "page" in entry["query"]
    assert entry["requiredArrayItemFields"]["nearby"] == "boolean|null" and entry["requiredArrayItemFields"]["viaWord"] == "string|null"
    behavior = entry["dbModeBehavior"]
    for needle in ("Returns 15 places per page (page 1-3;", "45 places per word", "nearby (true within 20 km", "viaWord", "top 3 completed words",
                   "at most 8 Kakao calls", "page outside 1-3 is 422", "once without coordinates", "empty array (also on pages 2-3)",
                   "failed nationwide call keeps the rows gathered", "completed-word results have no page 2", "never logged"):
        assert needle in behavior, needle
    assert "6 places" not in behavior
    home_behavior = golden("GET", "/api/places/search")["dbModeBehavior"]
    for needle in ("viaWord", "top 3 completed words", "did not fail"):
        assert needle in home_behavior, needle
    assert golden("GET", "/api/places/search")["optionalArrayItemFields"]["viaWord"] == "string|null"
