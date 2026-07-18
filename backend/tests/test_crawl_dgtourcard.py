from __future__ import annotations

import re

from scripts.crawl_dgtourcard import make_slug, parse_policies_from_html, slugify


def test_make_slug_uses_ascii_city_code_for_yeonggwang() -> None:
    assert make_slug("영광", "영광 디지털관광주민증 혜택") == "dgtour-yeonggwang"
    assert make_slug("전남", "영광 디지털관광주민증 혜택") == "dgtour-jeonnam-yeonggwang"


def test_slugify_does_not_emit_hangul_for_unknown_korean() -> None:
    assert slugify("없는지역") == ""
    assert not re.search(r"[가-힣]", slugify("없는지역"))


def test_map_entry_slug_uses_ascii_city_code_for_yeonggwang() -> None:
    html = """
    <html><body>
    <a href="javascript:func_go_detail('영광','8')" data-signgucd='46870'>영광</a>
    </body></html>
    """

    policies = parse_policies_from_html(html)

    assert [policy["slug"] for policy in policies] == ["dgtour-yeonggwang-8"]
    assert policies[0]["title"] == "영광 디지털관광주민증 혜택"
    assert "영광(전남)" in policies[0]["summary"]
