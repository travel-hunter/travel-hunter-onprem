from __future__ import annotations


SOURCE_CATEGORY = "local_half_trip"
TITLE_SUFFIX = "대한민국 반값여행 지원"


def display_city_name(city: str | None) -> str:
    if not city:
        return ""
    city = city.strip()
    if len(city) > 1 and city.endswith(("시", "군")):
        return city[:-1]
    return city


def title_with_city_prefix(title: str, city: str | None = None) -> str:
    title = title.strip()
    if title.startswith("["):
        return title
    display_city = display_city_name(city)
    if not display_city and title.endswith(TITLE_SUFFIX):
        display_city = title[: -len(TITLE_SUFFIX)].strip()
    if not display_city:
        return title
    return f"[{display_city}] {TITLE_SUFFIX}"


def city_from_title(title: str) -> str:
    title = title.strip()
    if title.startswith("[") and "]" in title:
        return title[1 : title.index("]")].strip()
    if title.endswith(TITLE_SUFFIX):
        return title[: -len(TITLE_SUFFIX)].strip()
    return ""


def policy_title(title: str, source_category: str | None, city: str | None = None) -> str:
    if source_category != SOURCE_CATEGORY:
        return title
    return title_with_city_prefix(title, city)
