from datetime import date

from app.services import itinerary_recommendations as recommendations


class FakeExternalProvider:
    def __init__(self, candidates_by_code):
        self.candidates_by_code = candidates_by_code
        self.calls = []

    def search(self, *, area_name: str, city: str, category_group_code: str):
        self.calls.append(
            {
                "area_name": area_name,
                "city": city,
                "category_group_code": category_group_code,
            }
        )
        return list(self.candidates_by_code.get(category_group_code, []))


class CountingExternalProvider(FakeExternalProvider):
    def __init__(self, candidates_by_code, *, fail_after_calls: int | None = None):
        super().__init__(candidates_by_code)
        self.fail_after_calls = fail_after_calls

    def search(self, *, area_name: str, city: str, category_group_code: str):
        if self.fail_after_calls is not None and len(self.calls) >= self.fail_after_calls:
            raise AssertionError("external search continued after the expected call budget")
        return super().search(area_name=area_name, city=city, category_group_code=category_group_code)


def external_candidate(index: int, category_code: str, title: str):
    return recommendations.ExternalPlaceCandidate(
        source_provider="kakao_local",
        external_place_id=f"kakao-{index}",
        title=title,
        category_group_code=category_code,
        category_group_name=category_code,
        address=f"Region road {index}",
        latitude=37.0 + index,
        longitude=127.0 + index,
        place_url=f"http://place.map.kakao.com/{index}",
    )


def gangwon_candidate(index: int, category_code: str, title: str, address: str):
    return recommendations.ExternalPlaceCandidate(
        source_provider="kakao_local",
        external_place_id=f"kakao-gangwon-{index}",
        title=title,
        category_group_code=category_code,
        category_group_name=category_code,
        address=address,
        latitude=37.0 + index,
        longitude=127.0 + index,
        place_url=f"http://place.map.kakao.com/gangwon-{index}",
    )


def test_category_group_for_code_groups_kakao_codes() -> None:
    assert recommendations.category_group_for_code("AT4") == "attraction"
    assert recommendations.category_group_for_code("CT1") == "attraction"
    assert recommendations.category_group_for_code("FD6") == "food"
    assert recommendations.category_group_for_code("CE7") == "food"
    assert recommendations.category_group_for_code("AD5") == "stay"
    assert recommendations.category_group_for_code("ZZZ") == "other"
    assert recommendations.category_group_for_code(None) == "other"


def test_recommendation_from_candidate_includes_map_metadata() -> None:
    candidate = recommendations.ExternalPlaceCandidate(
        source_provider="kakao_local",
        external_place_id="food-1",
        title="Candidate food",
        category_name="Restaurant",
        category_group_code="FD6",
        category_group_name="Food",
        phone="033-123-4567",
        address="Gangwon road 1",
        latitude=38.1,
        longitude=128.6,
        place_url="http://place.map.kakao.com/food-1",
    )

    item = recommendations.recommendation_from_candidate(
        candidate,
        suggested_day=2,
        region="Gangwon",
        style="food",
    )

    assert item["id"] == "kakao_local:food-1"
    assert item["categoryGroup"] == "food"
    assert item["categoryCode"] == "FD6"
    assert item["categoryName"] == "Restaurant"
    assert item["phone"] == "033-123-4567"
    assert item["address"] == "Gangwon road 1"
    assert item["latitude"] == 38.1
    assert item["longitude"] == 128.6
    assert item["placeUrl"] == "http://place.map.kakao.com/food-1"
    assert item["suggestedDay"] == 2
    assert item["sourceProvider"] == "kakao_local"
    assert item["externalPlaceId"] == "food-1"
    assert item["sourceType"] == "freshCandidate"


def _category_counts(candidates):
    counts: dict[str, int] = {}
    for candidate in candidates:
        category = recommendations.category_group_for_code(candidate.category_group_code)
        counts[category] = counts.get(category, 0) + 1
    return counts


def test_additional_place_candidates_balances_minimum_ten_candidates() -> None:
    provider = FakeExternalProvider(
        {
            "AT4": [external_candidate(index, "AT4", f"Attraction {index}") for index in range(1, 5)],
            "FD6": [external_candidate(index, "FD6", f"Food {index}") for index in range(10, 15)],
            "CE7": [external_candidate(index, "CE7", f"Cafe {index}") for index in range(20, 25)],
            "AD5": [external_candidate(index, "AD5", f"Stay {index}") for index in range(30, 34)],
        }
    )

    candidates = recommendations.additional_place_candidates(
        region="Jeju",
        style="맛집",
        day_count=4,
        travel_area_id=None,
        external_provider=provider,
        limit=10,
    )

    counts = _category_counts(candidates)
    assert len(candidates) >= 10
    assert counts["attraction"] >= 3
    assert counts["food"] >= 3
    assert counts["stay"] >= 2


def test_additional_place_candidates_backfills_when_stays_are_sparse() -> None:
    provider = FakeExternalProvider(
        {
            "AT4": [external_candidate(1, "AT4", "Only attraction")],
            "FD6": [external_candidate(index, "FD6", f"Food {index}") for index in range(10, 16)],
            "CE7": [external_candidate(index, "CE7", f"Cafe {index}") for index in range(20, 26)],
            "AD5": [],
        }
    )

    candidates = recommendations.additional_place_candidates(
        region="Jeju",
        style="맛집",
        day_count=6,
        travel_area_id=None,
        external_provider=provider,
        limit=10,
    )

    assert len(candidates) >= 10
    assert _category_counts(candidates).get("stay", 0) == 0
    assert all(candidate.source_provider == "kakao_local" for candidate in candidates)


def test_generate_course_uses_external_candidates_before_catalog() -> None:
    provider = FakeExternalProvider(
        {
            "AT4": [
                external_candidate(1, "AT4", "External attraction 1"),
                external_candidate(2, "AT4", "External attraction 2"),
            ],
            "FD6": [
                external_candidate(3, "FD6", "External food 1"),
                external_candidate(4, "FD6", "External food 2"),
            ],
            "CE7": [
                external_candidate(5, "CE7", "External cafe 1"),
                external_candidate(6, "CE7", "External cafe 2"),
            ],
            "AD5": [external_candidate(7, "AD5", "External stay 1")],
        }
    )

    course = recommendations.generate_auto_course(
        region="Busan",
        style="Food",
        start_date=date(2026, 7, 12),
        day_count=2,
        travel_area_id=None,
        external_provider=provider,
    )

    assert [place.title for place in course.places] == [
        "External attraction 1",
        "External food 1",
        "External cafe 1",
        "External stay 1",
        "External attraction 2",
        "External food 2",
        "External cafe 2",
    ]
    assert [place.time for place in course.places] == ["10:00", "13:00", "16:00", "20:00", "10:00", "13:00", "16:00"]
    assert course.places[0].source_provider == "kakao_local"
    assert course.places[0].external_place_id == "kakao-1"
    assert course.places[0].place_url == "http://place.map.kakao.com/1"
    assert course.recommendations[0]["title"] == "External attraction 1"


def test_generate_course_falls_back_to_catalog_when_external_candidates_are_sparse(monkeypatch) -> None:
    provider = FakeExternalProvider({"AT4": [external_candidate(1, "AT4", "Only one place")]})
    catalog = [
        recommendations.CatalogPlace("Fallback", "Nature", "NA", f"Fallback place {index}", "Nature", "Fallback reason")
        for index in range(1, 7)
    ]
    monkeypatch.setattr(recommendations, "CATALOG", catalog)

    course = recommendations.generate_auto_course(
        region="Fallback",
        style="Nature",
        start_date=date(2026, 7, 12),
        day_count=2,
        external_provider=provider,
    )

    assert len(course.places) == 6
    assert all(place.source_provider is None for place in course.places)


def test_generate_course_filters_external_candidates_outside_travel_area() -> None:
    provider = FakeExternalProvider(
        {
            "AT4": [
                gangwon_candidate(1, "AT4", "속초 전망대", "강원특별자치도 속초시 중앙동"),
                gangwon_candidate(2, "AT4", "강릉 해변", "강원특별자치도 강릉시 강문동"),
            ],
            "FD6": [
                gangwon_candidate(3, "FD6", "양양 식당", "강원특별자치도 양양군 양양읍"),
                gangwon_candidate(4, "FD6", "통영 맛집", "경남 통영시 항남동"),
            ],
            "CE7": [
                gangwon_candidate(5, "CE7", "고성 카페", "강원특별자치도 고성군 토성면"),
            ],
        }
    )

    course = recommendations.generate_auto_course(
        region="속초·고성·양양",
        style="맛집",
        start_date=date(2026, 7, 12),
        day_count=1,
        travel_area_id="gangwon-sokcho-goseong-yangyang",
        external_provider=provider,
    )

    assert [place.title for place in course.places] == ["속초 전망대", "양양 식당", "고성 카페"]


def test_generate_course_limits_external_area_fanout_and_stops_when_category_has_enough_candidates() -> None:
    provider = CountingExternalProvider(
        {
            "AT4": [
                gangwon_candidate(1, "AT4", "속초 전망대", "강원특별자치도 속초시 중앙동"),
                gangwon_candidate(2, "AT4", "양양 해변", "강원특별자치도 양양군 강현면"),
                gangwon_candidate(3, "AT4", "고성 전망대", "강원특별자치도 고성군 토성면"),
            ],
            "FD6": [
                gangwon_candidate(4, "FD6", "속초 식당", "강원특별자치도 속초시 중앙동"),
                gangwon_candidate(5, "FD6", "양양 식당", "강원특별자치도 양양군 양양읍"),
                gangwon_candidate(6, "FD6", "고성 식당", "강원특별자치도 고성군 토성면"),
            ],
            "CE7": [
                gangwon_candidate(7, "CE7", "속초 카페", "강원특별자치도 속초시 중앙동"),
                gangwon_candidate(8, "CE7", "양양 카페", "강원특별자치도 양양군 강현면"),
                gangwon_candidate(9, "CE7", "고성 카페", "강원특별자치도 고성군 토성면"),
            ],
            "AD5": [
                gangwon_candidate(10, "AD5", "속초 숙소", "강원특별자치도 속초시 중앙동"),
                gangwon_candidate(11, "AD5", "양양 숙소", "강원특별자치도 양양군 강현면"),
            ],
        },
        fail_after_calls=5,
    )

    course = recommendations.generate_auto_course(
        region="속초·고성·양양",
        style="휴식",
        start_date=date(2026, 7, 12),
        day_count=3,
        travel_area_id="gangwon-sokcho-goseong-yangyang",
        external_provider=provider,
    )

    assert len(course.places) == 11
    assert len(provider.calls) <= 5
    assert {call["city"] for call in provider.calls}.issubset({"속초", "고성"})


def test_generate_course_uses_catalog_fallback_when_external_search_time_budget_expires(monkeypatch) -> None:
    provider = CountingExternalProvider(
        {
            "AT4": [gangwon_candidate(1, "AT4", "속초 전망대", "강원특별자치도 속초시 중앙동")],
            "FD6": [gangwon_candidate(2, "FD6", "속초 식당", "강원특별자치도 속초시 중앙동")],
            "CE7": [gangwon_candidate(3, "CE7", "속초 카페", "강원특별자치도 속초시 중앙동")],
        },
    )
    catalog = [
        recommendations.CatalogPlace("속초·고성·양양", "휴식", "RS", f"Fallback place {index}", "휴식", "Fallback")
        for index in range(1, 7)
    ]
    ticks = iter([0.0, 0.0, 10.0, 10.0, 10.0])
    monkeypatch.setattr(recommendations, "CATALOG", catalog)
    monkeypatch.setattr(recommendations.time, "monotonic", lambda: next(ticks, 10.0))

    course = recommendations.generate_auto_course(
        region="속초·고성·양양",
        style="휴식",
        start_date=date(2026, 7, 12),
        day_count=2,
        travel_area_id="gangwon-sokcho-goseong-yangyang",
        external_provider=provider,
    )

    assert [place.title for place in course.places] == [f"Fallback place {index}" for index in range(1, 7)]
    assert len(provider.calls) <= 2


def test_generate_course_prefers_region_and_style() -> None:
    course = recommendations.generate_auto_course(
        region="제주",
        style="자연",
        start_date=date(2026, 7, 12),
        day_count=2,
    )

    assert len(course.places) == 6
    assert [place.day_number for place in course.places] == [1, 1, 1, 2, 2, 2]
    assert [place.time for place in course.places[:3]] == ["10:00", "14:00", "18:00"]
    assert all(place.region == "제주" for place in course.places)
    assert course.places[0].style == "자연"
    assert course.recommendations[0] == {
        "label": course.places[0].label,
        "title": course.places[0].title,
        "meta": f"Day 1 · 10:00 · {course.places[0].meta}",
        "reason": course.places[0].reason,
    }


def test_generate_course_supports_travel_area_display_region() -> None:
    course = recommendations.generate_auto_course(
        region="속초·고성·양양",
        style="바다",
        start_date=date(2026, 7, 12),
        day_count=2,
    )

    assert len(course.places) == 6
    assert len(course.recommendations) == 6
    assert all(place.region == "속초·고성·양양" for place in course.places)
    assert all(place.style == "바다" for place in course.places)
    assert [place.day_number for place in course.places] == [1, 1, 1, 2, 2, 2]
    assert course.recommendations[0]["title"] == course.places[0].title


def test_generate_course_falls_back_to_travel_area_sido_catalog() -> None:
    course = recommendations.generate_auto_course(
        region="부산 전체",
        style="휴식",
        start_date=date(2026, 7, 12),
        day_count=2,
        travel_area_id="busan-all",
    )

    assert len(course.places) == 6
    assert all(place.region == "부산 전체" for place in course.places)
    assert course.places[0].title == "부평깡통시장"


def test_generate_course_falls_back_to_same_region_other_styles(monkeypatch) -> None:
    catalog = [
        recommendations.CatalogPlace("제주", "자연", "NA", "제주 자연 1", "자연 · 제주", "자연 취향에 맞습니다."),
        recommendations.CatalogPlace("제주", "맛집", "FO", "제주 맛집 1", "맛집 · 제주", "맛집 취향에 맞습니다."),
        recommendations.CatalogPlace("부산", "자연", "BN", "부산 자연 1", "자연 · 부산", "부산 자연 후보입니다."),
    ]
    monkeypatch.setattr(recommendations, "CATALOG", catalog)

    course = recommendations.generate_auto_course(
        region="제주",
        style="자연",
        start_date=date(2026, 7, 12),
        day_count=1,
    )

    assert [place.title for place in course.places] == ["제주 자연 1", "제주 맛집 1"]
    assert all(place.region == "제주" for place in course.places)


def test_generate_course_returns_partial_course_when_candidates_are_insufficient(monkeypatch) -> None:
    catalog = [
        recommendations.CatalogPlace("강원", "휴식", "RS", "강원 휴식 1", "휴식 · 강원", "쉬어가기 좋습니다."),
        recommendations.CatalogPlace("강원", "사진", "PH", "강원 사진 1", "사진 · 강원", "사진 찍기 좋습니다."),
    ]
    monkeypatch.setattr(recommendations, "CATALOG", catalog)

    course = recommendations.generate_auto_course(
        region="강원",
        style="휴식",
        start_date=date(2026, 8, 1),
        day_count=2,
    )

    assert len(course.places) == 2
    assert [(place.day_number, place.time) for place in course.places] == [(1, "10:00"), (1, "14:00")]
    assert len(course.recommendations) == 2


def test_generate_course_returns_empty_for_unknown_region(monkeypatch) -> None:
    catalog = [
        recommendations.CatalogPlace("제주", "자연", "NA", "제주 자연 1", "자연 · 제주", "자연 취향에 맞습니다."),
    ]
    monkeypatch.setattr(recommendations, "CATALOG", catalog)

    course = recommendations.generate_auto_course(
        region="경주",
        style="자연",
        start_date=date(2026, 8, 1),
        day_count=3,
    )

    assert course.places == []
    assert course.recommendations == []


def test_generate_course_returns_empty_for_zero_day_count() -> None:
    course = recommendations.generate_auto_course(
        region="제주",
        style="자연",
        start_date=date(2026, 8, 1),
        day_count=0,
    )

    assert course.places == []
    assert course.recommendations == []
