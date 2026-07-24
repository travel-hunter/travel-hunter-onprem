from __future__ import annotations


CANONICAL_KEY_VERSION = "snapshot-v1"
STAY_DISCOUNT_LOGICAL_KEY = "stay-discount:2026-summer"


def logical_key_for_source(
    *, source_category: str, region: str | None, city: str | None, campaign_year: int | None
) -> str | None:
    if source_category == "stay_discount":
        return STAY_DISCOUNT_LOGICAL_KEY
    if source_category == "local_half_trip" and region and city and campaign_year:
        return f"local-half-trip:{campaign_year}:{region}:{city}"
    if source_category == "regional_benefit" and region and city and campaign_year:
        return f"travelmonth:regional-benefit:{campaign_year}:{region}:{city}"
    if source_category == "traffic_benefit" and region and city and campaign_year:
        return f"travelmonth:traffic-benefit:{campaign_year}:{region}:{city}"
    return None
