import { afterEach, describe, expect, it, vi } from "vitest";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import {
  browseDepth,
  browseView,
  chipCounts,
  deadlineChip,
  lowerBrowseState,
  nearOn,
  readBrowseState,
  regionSummary,
  searchBrowse,
  writeBrowseState,
  type BrowseState,
} from "./policyBrowse";

const make = (id: string, title: string, region: string, extra: Partial<Policy> = {}): Policy => ({
  ...examplePolicyDetail,
  id,
  slug: id,
  title,
  region,
  deadline: "",
  officialUrl: null,
  cardSummary: null,
  ...extra,
});

const policies: Policy[] = [
  make("yg", "[영광] 디지털관광주민증 혜택", "전남", { category: "지역할인" }),
  make("wd", "[완도] 디지털관광주민증 혜택", "전남", { category: "지역할인" }),
  make("hd", "[하동] 2026 대한민국 반값여행 지원", "경남", { deadline: "2026-09-25", category: "여행상품" }),
  make("rail", "내일로패스 할인", "전국", { deadline: "2026-12-31", category: "교통" }),
];

/* KST 2026-09-20 오전 */
const NOW = new Date("2026-09-20T01:00:00.000Z");
afterEach(() => vi.useRealTimers());

describe("policy tab browse model", () => {
  it("groups the same program across places and puts nationwide benefits first", () => {
    const view = browseView(policies, null, null, null);
    expect(view.title).toBe("모든 지역");
    expect(view.count).toBe(4);
    expect(view.entries.map((entry) => entry.kind)).toEqual(["nation", "row", "group"]);
    const group = view.entries.find((entry) => entry.kind === "group");
    expect(group && group.kind === "group" && group.items.map((p) => p.id)).toEqual(["yg", "wd"]);
  });

  it("lists a region's own benefits and points at nationwide ones, or falls back to them when empty", () => {
    const jeonnam = browseView(policies, "전남", null, null);
    expect(jeonnam.title).toBe("전남");
    expect(jeonnam.count).toBe(2);
    expect(jeonnam.nationMore).toBe(1);
    const city = browseView(policies, "전남", "완도", null);
    expect(city.title).toBe("완도");
    expect(city.sub).toBe("전남 · 마감 임박순");
    expect(city.count).toBe(1);
    const empty = browseView(policies, "대구", null, "move");
    expect(empty.count).toBe(0);
    expect(empty.empty).toBe("대구 전용 교통 혜택은 아직 없어요. 전국 어디서나 쓰는 교통 혜택 1건을 대신 보여 드려요.");
  });

  it("counts chips inside the picked region", () => {
    const counts = chipCounts(policies, "전남", null);
    expect(counts.get(null)).toBe(2);
    expect(counts.get("partner")).toBe(2);
    expect(counts.get("move")).toBe(0);
    expect(chipCounts(policies, null, null).get("move")).toBe(1);
    // 시군을 고르면 그 시군 안에서 센다 - 목록과 같은 범위(도 전체를 세면 칩을 눌러 빈 목록이 나왔다)
    expect(chipCounts(policies, "전남", null, "완도").get(null)).toBe(1);
  });

  it("marks deadlines by urgency and keeps the app's always-issued label for resident cards", () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    expect(deadlineChip(policies[0])).toEqual({ tone: "always", text: "상시" });
    expect(deadlineChip(make("x", "숙박 할인", "제주"))).toEqual({ tone: "always", text: "기간 확인" });
    expect(deadlineChip(policies[2])).toEqual({ tone: "urgent", text: "D-5" });
    expect(deadlineChip(policies[2], true)).toEqual({ tone: "urgent", text: "D-5부터" });
    expect(deadlineChip(make("t", "숙박", "제주", { deadline: "2026-09-20" }))).toEqual({ tone: "urgent", text: "오늘 마감" });
    expect(deadlineChip(make("s", "숙박", "제주", { deadline: "2026-10-10" }))).toEqual({ tone: "soon", text: "D-20" });
    expect(deadlineChip(policies[3])).toEqual({ tone: "later", text: "12.31 마감" });
    expect(deadlineChip(make("p", "숙박", "제주", { deadline: "2026-09-01" }))).toEqual({ tone: "later", text: "마감" });
  });

  it("summarises a region for the map card", () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const summary = regionSummary(policies, "경남");
    expect(summary).toMatchObject({ fullName: "경상남도", count: 1, lead: "refund", cities: 1 });
    expect(summary.soonest).toBe("하동 여행비 환급 D-5");
    expect(regionSummary(policies, "전남").soonest).toBeNull();
  });

  it("finds regions, places and programs from the magnifier", () => {
    const found = searchBrowse(policies, "완도");
    expect(found.places).toEqual([{ place: "완도", region: "전남", count: 1 }]);
    const programs = searchBrowse(policies, "반값").programs;
    expect(programs).toEqual([{ name: "대한민국 반값여행 지원", count: 1, type: "refund", nation: false }]);
    /* 전북은 이제 '전북특별자치도'라 '전라'로는 전남만 찾힌다 */
    expect(searchBrowse(policies, "전라").regions.map((r) => r.region)).toEqual(["전남"]);
  });
});

describe("policy tab layers in the URL", () => {
  const state = (patch: Partial<BrowseState>): BrowseState => ({
    region: null, city: null, program: null, filter: null, sheet: "mid", search: false, detail: null, near: null, ...patch,
  });

  it("reads the old list and open-sheet links as the new stops", () => {
    expect(readBrowseState(new URLSearchParams("place=전남&view=list")).sheet).toBe("full");
    expect(readBrowseState(new URLSearchParams("place=부산&sheet=1"))).toMatchObject({ region: "부산", sheet: "mid" });
    expect(readBrowseState(new URLSearchParams("city=완도")).city).toBeNull();
    // 예전 필터 목록 화면의 키(category · region · period · amount · saved)는 쓸 때 지운다 - 조건은 주소 밖에 산다
    const written = writeBrowseState(new URLSearchParams("category=숙박&period=7일 이내&view=list"), readBrowseState(new URLSearchParams("place=전남&view=list")));
    expect(written.toString()).toBe(new URLSearchParams("place=전남&sheet=full").toString());
    // 예전 지역 필터 주소(region=)는 지도 선택으로 읽는다
    expect(readBrowseState(new URLSearchParams("region=전남")).region).toBe("전남");
  });

  it("peels one layer at a time: search, one page, city, region, list, then out", () => {
    let current: BrowseState | null = state({ region: "전남", city: "완도", sheet: "full", search: true });
    const depths: number[] = [];
    while (current) {
      depths.push(browseDepth(current));
      current = lowerBrowseState(current);
    }
    expect(depths).toEqual([4, 3, 2, 1, 1, 0]);
  });

  it("keeps the place found by location only while its region and city stay picked", () => {
    const near = { name: "오동도", lat: 34.745, lng: 127.766, sido: "전남", region: "전남", city: "여수", note: null };
    const params = writeBrowseState(new URLSearchParams(), state({ region: "전남", city: "여수", near }));
    const read = readBrowseState(params);
    expect(read.near).toEqual(near);
    expect(nearOn(read)).toEqual(near);
    expect(nearOn({ ...read, city: "광양" })).toBeNull();
    expect(readBrowseState(new URLSearchParams("near=%7Bbroken")).near).toBeNull();
    expect(readBrowseState(new URLSearchParams(`near=${encodeURIComponent('{"name":1}')}`)).near).toBeNull();
  });

  it("on wide screens peels the panel detail first and ignores the sheet stop", () => {
    expect(readBrowseState(new URLSearchParams("place=전남&detail=yg")).detail).toBe("yg");
    expect(writeBrowseState(new URLSearchParams(), state({ region: "전남", detail: "yg" })).get("detail")).toBe("yg");
    let current: BrowseState | null = state({ region: "전남", city: "완도", sheet: "full", search: true, detail: "yg" });
    const depths: number[] = [];
    while (current) {
      depths.push(browseDepth(current, true));
      current = lowerBrowseState(current, true);
    }
    expect(depths).toEqual([4, 3, 2, 1, 0]);
  });
});
