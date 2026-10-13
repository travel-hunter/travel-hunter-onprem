import pytest

from app.services.geo_reference import (
    DATASET_OF, EXCLUDED_JIMOK, EXPECTED_REGION_CODES, PARCEL_GATE_M, GeoHit, content_duplicate_problems, fill_item, is_feature_key, is_pnu,
    jibun_address, jimok_of, keep_parcel, manifest_problems, parse_source, quality_problems, row_count_problems, swap_statements, unnamed_dong_problems, within_gate,
)


def test_a_jibun_address_is_the_legal_dong_name_and_the_lot_number_from_the_pnu() -> None:
    # PNU 19자리 = 법정동코드 10 · 산 여부 1(1 일반, 2 산) · 본번 4 · 부번 4. 세종 실데이터 한 줄(A4 '세종특별자치시  부강면 문곡리', A5 '302-2')
    assert jibun_address("세종특별자치시  부강면 문곡리", "3611033025103020002") == "세종특별자치시 부강면 문곡리 302-2"
    assert jibun_address("세종특별자치시 반곡동", "3611010100109300000") == "세종특별자치시 반곡동 930"
    assert jibun_address("경기도 양평군 양평읍 백안리", "4183025026200120001") == "경기도 양평군 양평읍 백안리 산12-1"
    assert jibun_address("", "3611033025103020002") == "302-2"   # 법정동 이름이 빠진 경우(적재 검사가 막지만) 결과를 버리지 않는다


def test_a_malformed_pnu_or_feature_key_is_refused() -> None:
    assert is_pnu("3611033025103020002") and not is_pnu("361103302510302000") and not is_pnu(None) and not is_pnu("36110330251030200x2")
    # 끝의 줄바꿈 · 전각 숫자 · 다른 문자 체계의 숫자는 고유번호가 아니다
    assert not is_pnu("3611033025103020002\n") and not is_pnu("３" * 19) and not is_pnu("٣" * 19)
    with pytest.raises(ValueError):
        jibun_address("세종특별자치시 반곡동", "123")
    # 빈 값 · None · 'None' 문자열(str(None)) · 공백은 식별자가 아니다(코덱스 재검토 MEDIUM)
    assert is_feature_key("0000235425653372309500000000") and is_feature_key("1114010300100310000")
    assert not any(is_feature_key(v) for v in (None, "", "   ", "None", "nan"))
    # 열이 varchar(40)이다(전국 실측 최대 28) - 더 긴 식별자는 COPY를 멈추지 않고 식별자 없는 줄로 센다
    assert is_feature_key("x" * 40) and not is_feature_key("x" * 41) and is_feature_key(" " + "x" * 40 + " ")


def test_the_land_category_is_the_hangul_at_the_end_of_the_lot_label() -> None:
    assert (jimok_of("203-24전"), jimok_of("930 공"), jimok_of("산12-1임"), jimok_of(""), jimok_of(None)) == ("전", "공", "임", None, None)
    # 정식 이름은 약식 부호로(전국 약 2,300줄), 겹친 글자 · 부호가 아닌 글자 · 깨진 글자는 못 읽음 - 열(varchar(4))을 넘는 값이 나오지 않는다
    assert (jimok_of("12임야"), jimok_of("5과수원"), jimok_of("3목장용지"), jimok_of("7도로"), jimok_of("9잡종지")) == ("임", "과", "목", "도", "잡")
    assert (jimok_of("4답답"), jimok_of("8가"), jimok_of("빈값"), jimok_of("1주유소용지아님")) == (None, None, None, None)


def test_farmland_and_forest_are_not_loaded_but_unknown_categories_are_kept_and_counted() -> None:
    assert EXCLUDED_JIMOK == frozenset({"전", "답", "과", "목", "임"})
    assert not keep_parcel("답") and keep_parcel("대") and keep_parcel("차") and keep_parcel(None)
    assert not keep_parcel(jimok_of("12임야")) and not keep_parcel(jimok_of("5과수원"))   # 정식 이름으로 적힌 농지 · 임야도 거른다


def test_a_building_always_fills_but_a_parcel_only_within_thirty_meters() -> None:
    building = GeoHit("building", 7, "3611033025103020002", "세종 302-2", 36.5, 127.3, 120.0)
    near = GeoHit("parcel", 8, "3611033025103020002", "세종 302-2", 36.5, 127.3, float(PARCEL_GATE_M))
    far = GeoHit("parcel", 9, "3611033025103020002", "세종 302-2", 36.5, 127.3, PARCEL_GATE_M + 0.5)
    assert within_gate(building) and within_gate(near) and not within_gate(far)
    assert fill_item(near) == {"kind": "parcel", "id": 8, "pnu": "3611033025103020002", "address": "세종 302-2", "latitude": 36.5, "longitude": 127.3, "distanceMeters": 30}


def test_the_monthly_swap_renames_next_tables_and_all_their_indexes_and_drops_the_old_ones() -> None:
    sql = swap_statements("parcel")
    assert sql[:4] == [
        "ALTER TABLE geo.parcel RENAME TO parcel_old",
        "ALTER INDEX geo.parcel_pkey RENAME TO parcel_old_pkey",
        "ALTER INDEX geo.parcel_geom_gix RENAME TO parcel_old_geom_gix",
        "ALTER INDEX geo.parcel_pnu_ix RENAME TO parcel_old_pnu_ix",
    ]
    assert sql[4:] == [
        "ALTER TABLE geo.parcel_next RENAME TO parcel",
        "ALTER INDEX geo.parcel_next_pkey RENAME TO parcel_pkey",
        "ALTER INDEX geo.parcel_next_geom_gix RENAME TO parcel_geom_gix",
        "ALTER INDEX geo.parcel_next_pnu_ix RENAME TO parcel_pnu_ix",
        "DROP TABLE geo.parcel_old",
    ]
    with pytest.raises(ValueError):
        swap_statements("users; drop table trips")


def full_set(dataset: str, date: str) -> list[str]:
    return [f"/data/{dataset}/AL_{dataset}_{code}_{date}/AL_{dataset}_{code}_{date}.shp" for code in sorted(EXPECTED_REGION_CODES)]


def test_a_complete_single_date_set_with_part_files_passes_the_manifest() -> None:
    files = full_set("D010", "20260909") + ["/data/D010/AL_D010_41_20260909/AL_D010_41_20260909(2).shp"]
    assert parse_source(files[-1]).code == "41" and parse_source(files[-1]).name == "AL_D010_41_20260909(2).shp"
    assert (parse_source(files[-1]).dataset, parse_source(files[-1]).part, parse_source(files[0]).part) == ("D010", 2, None)
    assert manifest_problems(files, "D010") == []


def test_manifest_refuses_a_missing_region_two_dates_and_a_duplicated_region_file() -> None:
    files = full_set("D002", "20260908")
    assert manifest_problems(files[1:], "D002") == [f"missing region codes: {sorted(EXPECTED_REGION_CODES)[0]}"]
    assert "more than one base date: 20260808, 20260908" in manifest_problems(files[:-1] + [files[-1].replace("20260908", "20260808")], "D002")
    duplicated = files + ["/data/D002/other-folder/AL_D002_11_20260908.shp"]   # 같은 파일이 다른 폴더에 한 번 더
    assert "duplicated file: AL_D002_11_20260908.shp" in manifest_problems(duplicated, "D002")
    assert manifest_problems(files + ["/data/D002/readme.shp"], "D002") == ["unknown file name: readme.shp"]


def test_manifest_takes_one_dataset_only_so_a_mixed_set_cannot_pass() -> None:
    assert DATASET_OF == {"building": "D010", "parcel": "D002"}
    last = sorted(EXPECTED_REGION_CODES)[-1]
    mixed = full_set("D010", "20260909")[:-1] + [f"/data/D002/AL_D002_{last}_20260909.shp"]   # 지역 15개는 건물, 하나는 땅
    problems = manifest_problems(mixed, "D010")
    assert problems == [f"wrong dataset: AL_D002_{last}_20260909.shp", f"missing region codes: {last}"]
    assert manifest_problems(full_set("D002", "20260909"), "D002") == []
    assert manifest_problems(full_set("D002", "20260909"), "D010")[0] == f"wrong dataset: AL_D002_{sorted(EXPECTED_REGION_CODES)[0]}_20260909.shp"
    with pytest.raises(ValueError):
        manifest_problems(full_set("D010", "20260909"), "D999")


def test_a_part_file_needs_its_base_file_and_an_unexpected_region_is_reported() -> None:
    files = full_set("D010", "20260909") + ["/data/D010/AL_D010_41_20260909(2).shp"]
    without_base = [f for f in files if not f.endswith("AL_D010_41_20260909.shp")]
    assert manifest_problems(without_base, "D010") == ["part file without base file: AL_D010_41_20260909(2).shp"]
    assert manifest_problems(full_set("D010", "20260909") + ["/data/D010/AL_D010_99_20260909.shp"], "D010") == ["unexpected region codes: 99"]
    assert parse_source("readme.shp") is None and parse_source("/data/D010/AL_D010_41_20260909.shp.bak") is None
    assert parse_source("/data/D010/al_d010_41_20260909.SHP").dataset == "D010"   # 대 · 소문자는 가리지 않고 데이터셋은 대문자로
    assert parse_source("/data/D010/AL_D010_41_20260909.ſhp") is None   # 긴 s(ſ)는 유니코드 대소문자 무시에서 s 로 걸린다 - ASCII 만 받는다


def test_a_part_file_with_the_same_content_as_another_is_a_duplicate_download() -> None:
    # '(2).shp'가 진짜 나눈 조각인지 같은 파일을 두 번 받은 것인지는 이름으로 모른다 - 내용 지문이 같으면 멈춘다(코덱스 재검토 MEDIUM)
    assert content_duplicate_problems({"AL_D010_41_20260909.shp": "aa", "AL_D010_41_20260909(2).shp": "bb"}) == []
    assert content_duplicate_problems({"AL_D010_41_20260909.shp": "aa", "AL_D010_41_20260909(2).shp": "aa"}) == [
        "same content: AL_D010_41_20260909(2).shp, AL_D010_41_20260909.shp"
    ]


def test_quality_checks_count_duplicates_missing_keys_and_unknown_land_categories() -> None:
    assert quality_problems("building", 14_392_124, 14_305_380, missing_keys=1, unknown_jimok=0) == []   # 2026-09 판 전국 실측 그대로
    assert quality_problems("parcel", 19_406_867, 19_406_867, missing_keys=0, unknown_jimok=4_526) == []
    assert quality_problems("building", 14_392_125, 14_000_000, missing_keys=0, unknown_jimok=0) == ["building: duplicate feature keys 2.7% > 2.0%"]
    assert quality_problems("parcel", 19_500_000, 18_000_000, missing_keys=0, unknown_jimok=0) == ["parcel: duplicate feature keys 7.7% > 1.0%"]
    assert quality_problems("building", 14_000_000, 14_000_000, missing_keys=20_000, unknown_jimok=0) == ["building: rows without a feature key 0.14% > 0.10%"]
    assert quality_problems("parcel", 19_500_000, 19_500_000, missing_keys=0, unknown_jimok=300_000) == ["parcel: unknown land category 1.54% > 1.00%"]
    # 빈 적재 · 식별자 수가 줄 수보다 큰 적재는 통과할 수 없다
    assert quality_problems("building", 0, 0, missing_keys=0, unknown_jimok=0) == ["building: no rows"]
    assert quality_problems("building", 100, 101, missing_keys=0, unknown_jimok=0) == ["building: more distinct keys than rows"]


def test_rows_with_an_unnamed_legal_dong_code_pass_up_to_one_percent_of_what_was_read() -> None:
    assert unnamed_dong_problems("building", 14_346_610, 45_515) == []   # 2026-09 판 전국 실측 0.32%
    assert unnamed_dong_problems("parcel", 19_406_867, 0) == []
    assert unnamed_dong_problems("building", 9_900, 100) == []   # 정확히 1.00% 는 통과
    assert unnamed_dong_problems("building", 9_899, 101) == ["building: rows with an unnamed legal-dong code 1.01% > 1.00%"]
    assert unnamed_dong_problems("parcel", 0, 0) == []   # 읽은 줄이 없으면 나눌 수 없다 - 빈 적재는 quality_problems 가 막는다
    with pytest.raises(ValueError):
        unnamed_dong_problems("users", 1, 1)


def test_row_count_bounds_are_a_separate_check_that_alone_can_be_accepted() -> None:
    assert row_count_problems("building", 14_392_125) == []
    assert row_count_problems("building", 9_000_000) == ["building: 9000000 rows is outside 12000000..17000000"]


def test_an_unknown_table_is_a_value_error_not_a_key_error() -> None:
    with pytest.raises(ValueError):
        quality_problems("users", 1, 1, missing_keys=0, unknown_jimok=0)
    with pytest.raises(ValueError):
        row_count_problems("users", 1)
