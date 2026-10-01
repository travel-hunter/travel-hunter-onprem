import { act, render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { useBrowseHistory } from "./useBrowseHistory";

/* 정책 탭 주소 층: 시군(place) 2 · 지역(region) 1 · 그 밖 0. 칩(type)·필터(category)는 층이 아니다 */
const depthOf = (params: URLSearchParams) => (params.has("place") ? 2 : params.has("region") ? 1 : 0);
const q = (search: string) => new URLSearchParams(search);

function mount(entries: string[]) {
  const live: { history?: ReturnType<typeof useBrowseHistory>; path?: string } = {};
  function Probe() {
    live.history = useBrowseHistory(depthOf);
    const location = useLocation();
    live.path = `${location.pathname}${location.search}`;
    return null;
  }
  render(
    <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
      <Probe />
    </MemoryRouter>,
  );
  const run = (fn: (history: ReturnType<typeof useBrowseHistory>) => void) => act(() => fn(live.history!));
  return { live, run };
}

describe("useBrowseHistory", () => {
  it("stacks the filter list on top of the map, and clearing the filters rewinds to that map entry", () => {
    const { live, run } = mount(["/home", "/policies?region=a"]);
    run((h) => h.push(q("region=a&category=x")));
    expect(live.path).toBe("/policies?region=a&category=x");
    run((h) => h.unwind(q("region=a")));
    expect(live.path).toBe("/policies?region=a");
    // 되감았으니 한 층 더 뒤로가면 이 화면 바로 앞 기록(홈)이다 - 빈 칸이 남지 않았다
    run((h) => h.back(null));
    expect(live.path).toBe("/home");
  });

  it("clears filters in place when they were not stacked here, without leaving the screen", () => {
    const { live, run } = mount(["/home", "/policies?category=x"]);
    run((h) => h.unwind(q("")));
    expect(live.path).toBe("/policies");
  });

  it("after a same-layer change on a stacked entry, back rewinds one entry and keeps the change", () => {
    const { live, run } = mount(["/policies"]);
    run((h) => h.go(q("region=a"))); // 층 0 → 1: 쌓는다
    run((h) => h.go(q("region=a&place=b"))); // 층 1 → 2: 쌓는다
    run((h) => h.go(q("region=a&place=b&type=stay"))); // 같은 층(칩): 덮어쓴다
    run((h) => h.back(q("region=a&type=stay"))); // 한 층 아래(칩은 남는다)
    expect(live.path).toBe("/policies?region=a&type=stay");
    // 덮어쓰지 않고 되감았으니 한 번 더 뒤로면 맨 처음 화면 - 옛 시군 칸이 끼어 있지 않다
    run((h) => h.back(null));
    expect(live.path).toBe("/policies");
  });
});
