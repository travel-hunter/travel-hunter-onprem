import { describe, expect, it } from "vitest";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import { geoToMap, KM_PER_UNIT, nearbyCities, nearTarget, shortCity } from "./nearby";
import { SIGUN_POINTS } from "./sigunPoints";

const make = (id: string, title: string, region: string): Policy => ({ ...examplePolicyDetail, id, slug: id, title, region });
/* 오동도(여수) */
const ODONGDO = geoToMap("전남", 34.745, 127.766);

describe("위치로 찾기의 근처", () => {
  it("puts a real place close to its city point on the map", () => {
    const [x, y] = SIGUN_POINTS["전남|여수"];
    expect(Math.hypot(ODONGDO[0] - x, ODONGDO[1] - y) * KM_PER_UNIT).toBeLessThan(15);
  });

  it("falls back from the city to the nearest city, the province, then nationwide", () => {
    const yeosu = make("ys", "[여수] 숙박 할인", "전남");
    const gwangyang = make("gy", "[광양] 숙박 할인", "전남");
    const yeonggwang = make("yg", "[영광] 숙박 할인", "전남");
    const nation = make("rail", "내일로패스 할인", "전국");

    expect(nearTarget([yeosu, gwangyang], "전남", "여수", ODONGDO)).toEqual({ region: "전남", city: "여수", count: 1, note: null });
    const near = nearTarget([gwangyang, yeonggwang], "전남", "여수", ODONGDO);
    expect(near).toMatchObject({ region: "전남", city: "광양", count: 1 });
    expect(near.km).toBeGreaterThan(0);   // 넓힌 시군까지 거리 - 홈 장소 카드 버튼이 '광양 약 23km'로 보인다
    expect(near.note).toBe("여수 전용 혜택이 없어 가까운 시군 혜택을 보여 드려요");
    expect(nearTarget([yeonggwang], "전남", "여수", ODONGDO)).toMatchObject({ region: "전남", city: null, count: 1, note: "여수 전용 혜택이 없어 전라남도 혜택을 보여 드려요" });
    expect(nearTarget([nation], "전남", "여수", ODONGDO)).toMatchObject({ region: "전국", city: null, count: 1 });
    expect(nearTarget([nation], null, null, null)).toMatchObject({ region: "전국", count: 1 });
    expect(nearTarget([nation], "__proto__", null, null)).toMatchObject({ region: "전국", count: 1 });
  });

  it("lists nearby cities closest first and skips the one already shown", () => {
    const list = [make("ys", "[여수] 숙박 할인", "전남"), make("gy", "[광양] 숙박 할인", "전남"), make("yg", "[영광] 숙박 할인", "전남")];
    expect(nearbyCities(list, ODONGDO).map((city) => city.city)).toEqual(["여수", "광양"]);
    expect(nearbyCities(list, ODONGDO, "전남|여수").map((city) => city.city)).toEqual(["광양"]);
    expect(nearbyCities(list, null)).toEqual([]);
  });

  it("matches metro policy titles that carry the city name prefix", () => {
    const yeongdo = make("yd", "[부산영도] 숙박 할인", "부산");
    expect(nearTarget([yeongdo], "부산", "영도", null)).toMatchObject({ region: "부산", city: "부산영도", note: null });
    expect(shortCity("부산", "부산영도")).toBe("영도");
    expect(shortCity("전남", "여수")).toBe("여수");
  });
});
