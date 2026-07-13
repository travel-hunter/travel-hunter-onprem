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
