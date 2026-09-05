from __future__ import annotations

from scripts.crawl_dgtourcard import parse_policies_from_html

MAP_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('하동', '3')" data-signgucd='48850'>하동</a>"""
)

DUPLICATE_CITY_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('영광', '21')" data-signgucd='46870'>영광</a>"""
)


def test_parse_policies_from_html_uses_canonical_slugs_without_page_order() -> None:
    policies = parse_policies_from_html(MAP_HTML)

    slugs = [policy["slug"] for policy in policies]
    assert slugs == ["dgtour-영광", "dgtour-하동"]


def test_parse_policies_from_html_collapses_a_city_listed_twice() -> None:
    policies = parse_policies_from_html(DUPLICATE_CITY_HTML)

    slugs = [policy["slug"] for policy in policies]
    assert slugs == ["dgtour-영광"]


def test_parse_policies_from_html_maps_signgucd_prefix_to_a_province() -> None:
    """크롤러의 SIGNGU_PREFIX_PROVINCE 매핑이 도는지 확인한다.

    주의: 이 픽스처는 VisitKorea 실제 페이지에서 캡처한 것이 아니라
    _MAP_ENTRY_RE 와 그 매핑에 맞춰 구성한 최소 입력이다. 실제 페이지의
    data-signgucd 가 같은 체계인지는 원본 HTML이 없어 확인되지 않았다.
    이 테스트는 크롤러 자신의 로직을 고정할 뿐 실제 페이지를 대표하지 않는다.
    """
    policies = parse_policies_from_html(MAP_HTML)

    # 슬러그로 키를 잡으면 슬러그 규칙 변경에 딸려가므로 region 만 본다.
    assert [policy["region"] for policy in policies] == ["전남", "경남"]
