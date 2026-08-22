import json

from scripts.validate_policy_data import validate_policy_data


def write_policy_file(tmp_path, policies):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps(policies, ensure_ascii=False), encoding="utf-8")
    return path


def valid_policy(slug: str = "dgtour-jeju") -> dict[str, object]:
    return {
        "slug": slug,
        "title": "제주 디지털관광주민증 혜택",
        "org": "한국관광공사",
        "region": "제주",
        "deadline": "2026-12-31",
        "amount": "혜택 제공",
        "summary": "디지털관광주민증 소지자 대상 지역 방문 혜택입니다.",
        "category": "지역할인",
        "requirements": ["디지털관광주민증 발급자"],
        "documents": ["디지털관광주민증"],
        "officialUrl": "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        "applyUrl": None,
    }


def test_validate_policy_data_accepts_valid_payload(tmp_path) -> None:
    path = write_policy_file(tmp_path, [valid_policy()])

    assert validate_policy_data(path) == []


def test_validate_policy_data_rejects_duplicates_bad_dates_and_mojibake(tmp_path) -> None:
    first = valid_policy("dup")
    second = valid_policy("dup")
    second["deadline"] = "2026.12.31"
    second["title"] = "諛???붿??멸? 혜택"
    second["documents"] = "디지털관광주민증"
    path = write_policy_file(tmp_path, [first, second])

    errors = validate_policy_data(path)

    assert any("중복 slug" in error for error in errors)
    assert any("deadline 형식" in error for error in errors)
    assert any("인코딩 깨짐" in error for error in errors)
    assert any("documents" in error for error in errors)


def test_seed_dgtour_active_policies_use_official_participating_regions_and_urls() -> None:
    from pathlib import Path

    from app.services import digital_tourism_resident_card as official

    policies = json.loads(
        (Path(__file__).parents[1] / "app" / "data" / "dgtourcard_policies.json").read_text(
            encoding="utf-8"
        )
    )
    active_dgtour = [
        policy
        for policy in policies
        if policy.get("sourceCategory") == official.SOURCE_CATEGORY
        and policy.get("status", "active") != "hidden"
    ]

    assert active_dgtour
    for policy in active_dgtour:
        title = str(policy["title"])
        city = title[1 : title.index("]")] if title.startswith("[") and "]" in title else ""
        assert city in official.PARTICIPATING_CITY_REGIONS
        canonical_slug = official.canonical_policy_slug_for_city(city)
        assert canonical_slug is not None
        assert policy["slug"] == canonical_slug
        official_url = str(policy.get("officialUrl") or "")
        assert official.is_visitkorea_dgtourcard_url(official_url)
        assert "haenam50.kr" not in official_url
        assert "tour50.do" not in official_url
        assert policy.get("sourceName") == official.SOURCE_NAME
        assert policy.get("applyUrl") is None
        structured_detail = policy.get("structuredDetail")
        assert isinstance(structured_detail, dict)
        assert "반값여행" not in str(structured_detail)

    by_title_city = {policy["title"][1 : policy["title"].index("]")]: policy for policy in active_dgtour}
    assert by_title_city["하동"]["officialUrl"] == official.HADONG_REGIONAL_URL


def test_seed_dgtour_non_participating_regions_are_hidden() -> None:
    from pathlib import Path

    policies = json.loads(
        (Path(__file__).parents[1] / "app" / "data" / "dgtourcard_policies.json").read_text(
            encoding="utf-8"
        )
    )
    by_slug = {policy["slug"]: policy for policy in policies}

    for slug in ("dgtour-강진-7", "dgtour-남해-11", "dgtour-영암-12", "dgtour-횡성-14"):
        assert by_slug[slug]["status"] == "hidden"
