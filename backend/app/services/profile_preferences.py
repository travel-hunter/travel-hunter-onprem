from __future__ import annotations

from app.data import seed


MAX_PREFERRED_REGIONS = 3


class ProfilePreferenceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def parse_preferred_regions(value: str | None) -> list[str] | None:
    if value is None:
        return None
    regions = _dedupe_preserving_order(item.strip() for item in value.split(","))
    return regions or None


def serialize_preferred_regions(value: list[str] | None) -> str | None:
    regions = normalize_preferred_regions(value)
    if not regions:
        return None
    return ",".join(regions)


def normalize_preferred_regions(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    regions = _dedupe_preserving_order(str(item).strip() for item in value)
    invalid = [region for region in regions if region not in seed.REGIONS]
    if invalid:
        raise ProfilePreferenceError(422, "지원하지 않는 관심 지역입니다.")
    if len(regions) > MAX_PREFERRED_REGIONS:
        raise ProfilePreferenceError(422, f"관심 지역은 최대 {MAX_PREFERRED_REGIONS}개까지 선택할 수 있습니다.")
    return regions or None


def _dedupe_preserving_order(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
