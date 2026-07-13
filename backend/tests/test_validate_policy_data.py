import json

from scripts.validate_policy_data import validate_policy_data


def write_policies(tmp_path, policies):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps(policies), encoding="utf-8")
    return path


def make_policy(**overrides):
    policy = {
        "slug": "fixture-policy",
        "title": "지역사랑 휴가지원",
        "org": "한국관광공사",
        "region": "전국",
        "deadline": "2026-10-31",
        "amount": "최대 30만원 환급",
        "summary": "국내 여행 지원 정책입니다.",
        "category": "지역할인",
        "requirements": ["국내 거주자"],
        "documents": ["신분증"],
        "officialUrl": "https://korean.visitkorea.or.kr/travelmonth/benefits/depopulation.do",
        "applyUrl": None,
    }
    policy.update(overrides)
    return policy


def test_validate_policy_data_accepts_valid_urls_and_null_apply_url(tmp_path) -> None:
    path = write_policies(tmp_path, [make_policy()])

    assert validate_policy_data(path) == []


def test_validate_policy_data_rejects_invalid_url_values(tmp_path) -> None:
    path = write_policies(
        tmp_path,
        [
            make_policy(slug="blank-url", officialUrl=""),
            make_policy(slug="localhost-url", officialUrl="http://127.0.0.1:5173/policies"),
            make_policy(slug="placeholder-url", officialUrl="https://example.com/policy"),
            make_policy(slug="bad-scheme", officialUrl="ftp://travel.example/policy"),
            make_policy(slug="padded-url", officialUrl=" https://travel.example/policy "),
        ],
    )

    errors = validate_policy_data(path)

    assert any("blank-url officialUrl" in error for error in errors)
    assert any("localhost-url officialUrl" in error for error in errors)
    assert any("placeholder-url officialUrl" in error for error in errors)
    assert any("bad-scheme officialUrl" in error for error in errors)
    assert any("padded-url officialUrl" in error for error in errors)


def test_validate_policy_data_allows_policy_without_any_application_links(tmp_path) -> None:
    path = write_policies(tmp_path, [make_policy(officialUrl=None, applyUrl=None)])

    assert validate_policy_data(path) == []
