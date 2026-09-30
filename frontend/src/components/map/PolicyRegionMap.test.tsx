import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PolicyRegionMap } from "./PolicyRegionMap";
import type { RegionCounts } from "./regionMapEngine";

const counts: RegionCounts = {
  전남: { own: 11, total: 11 },
  경기: { own: 2, total: 2 },
  대구: { own: 0, total: 0 },
};

function region(name: string) {
  const el = document.querySelector(`.thmap-rg[data-region="${name}"]`);
  expect(el).toBeTruthy();
  return el as SVGPathElement;
}
const badgeTexts = () => Array.from(document.querySelectorAll(".thmap-bd text")).map((t) => t.textContent);

describe("PolicyRegionMap", () => {
  afterEach(() => cleanup());

  it("draws all 17 regions flat and marks only the ones with no policies of their own as empty", () => {
    render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    expect(document.querySelectorAll(".thmap-rg")).toHaveLength(17);
    expect(region("전남").classList.contains("thmap-empty")).toBe(false);
    expect(region("경기").classList.contains("thmap-empty")).toBe(false);
    expect(region("대구").classList.contains("thmap-empty")).toBe(true);
    // 건수를 안 준 지역은 0건으로 그린다
    expect(region("서울").classList.contains("thmap-empty")).toBe(true);
    // 시안처럼 평면 - 옆면을 켜켜이 쌓던 2.5D 벽은 없다
    expect(document.querySelector(".thmap-walls, .thmap-floors")).toBeNull();
  });

  it("keeps a region empty when only nationwide policies reach it, but counts them in the label", () => {
    render(<PolicyRegionMap counts={{ 대구: { own: 0, total: 1 } }} onSelect={() => undefined} selected={null} />);
    expect(region("대구").classList.contains("thmap-empty")).toBe(true);
    expect(region("대구").getAttribute("aria-label")).toBe("대구 정책 1건");
  });

  it("reports the clicked region and toggles it off on a second click", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<PolicyRegionMap counts={counts} onSelect={onSelect} selected={null} />);
    fireEvent.click(region("전남"));
    expect(onSelect).toHaveBeenLastCalledWith("전남");
    rerender(<PolicyRegionMap counts={counts} onSelect={onSelect} selected="전남" />);
    expect(region("전남").classList.contains("thmap-on")).toBe(true);
    expect(region("전남").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(region("전남"));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("lifts only the picked region - shade, teal wall, bright top - and puts it back when released", () => {
    const { rerender } = render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    const lift = document.querySelector(".thmap-lift") as SVGGElement;
    expect(lift.childElementCount).toBe(0);
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected="경기" />);
    expect(Array.from(lift.children).map((p) => p.getAttribute("class"))).toEqual(["shade", "wall", "top"]);
    expect((lift.querySelector(".top") as SVGPathElement).getAttribute("fill")).toMatch(/^url\(#thmap-face-/);
    expect(lift.querySelector(".top")?.getAttribute("d")).toBe(region("경기").getAttribute("d"));
    // 고른 도는 땅 무리의 맨 위 - 흰 경계선이 이웃에 덮이지 않는다
    expect(document.querySelector(".thmap-rgs")?.lastElementChild).toBe(region("경기"));
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    expect(lift.childElementCount).toBe(0);
    expect(region("경기").classList.contains("thmap-on")).toBe(false);
  });

  it("mounts the pill only while a region is selected", () => {
    const pill = (region: string) => <button className="thmap-pill" type="button">{region} 보기</button>;
    const { rerender } = render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} renderPill={pill} />);
    expect(document.querySelector(".thmap-pill")).toBeNull();
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected="전남" renderPill={pill} />);
    // jsdom 은 좌표를 못 재지만 알약은 떠야 한다 - 자리만 가운데로 간다
    expect(document.querySelector(".thmap-pill")?.textContent).toBe("전남 보기");
    expect(document.querySelector(".thmap-marks")).toBeTruthy();
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} renderPill={pill} />);
    expect(document.querySelector(".thmap-pill")).toBeNull();
  });

  it("gives the map the leftover height and stops at the floor", () => {
    const width = vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(390);
    const tall = window.innerHeight;
    try {
      render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
      const host = document.querySelector(".thmap-host") as HTMLElement;
      // 높이는 그림 비율이 아니라 남은 화면이 정한다 - 빈 띠는 viewBox 쪽에서 없앤다
      // (jsdom 은 스크롤 칸이 없어 innerHeight - 안내문 30)
      expect(host.style.height).toBe(tall - 30 + "px");

      Object.defineProperty(window, "innerHeight", { configurable: true, value: 400 });
      fireEvent(window, new Event("resize"));
      expect(host.style.height).toBe("370px");

      // 그보다 더 짧아지면 바닥값에서 멈춘다
      Object.defineProperty(window, "innerHeight", { configurable: true, value: 120 });
      fireEvent(window, new Event("resize"));
      expect(host.style.height).toBe("220px");
    } finally {
      Object.defineProperty(window, "innerHeight", { configurable: true, value: tall });
      width.mockRestore();
    }
  });

  it("stretches the viewBox to the box so no letterbox band is left", () => {
    // 칸 비율과 viewBox 비율이 같아 빈 띠도, 잘리는 땅도 없다. 남는 쪽은 바다로 늘어난다.
    const width = vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(390);
    const height = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
    try {
      render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
      const box = (document.querySelector(".thmap-svg") as SVGSVGElement).getAttribute("viewBox") as string;
      const [, , vw, vh] = box.split(" ").map(Number);
      expect(vw / vh).toBeCloseTo(390 / 600, 2);
    } finally {
      height.mockRestore();
      width.mockRestore();
    }
  });

  it("draws the three coastal ripple lines under the land", () => {
    render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected="전남" />);
    const svg = document.querySelector(".thmap-svg") as SVGSVGElement;
    const sea = svg.querySelector(".thmap-sea") as SVGGElement;
    const rgs = svg.querySelector(".thmap-rgs") as SVGGElement;
    expect((sea.compareDocumentPosition(rgs) & window.Node.DOCUMENT_POSITION_FOLLOWING) !== 0).toBe(true);
    // 굵은 선 세 겹과 바다색 덮개 세 겹이 번갈아 - 땅 모양 하나(defs)를 같이 쓴다
    const uses = Array.from(sea.querySelectorAll("use"));
    expect(uses).toHaveLength(6);
    expect(uses.filter((u) => u.classList.contains("cut"))).toHaveLength(3);
    const landId = (svg.querySelector("defs .thmap-land") as SVGGElement).id;
    expect(uses.every((u) => u.getAttribute("href") === `#${landId}`)).toBe(true);
  });

  it("colours each region by its benefit count and writes the count in a label pill", () => {
    render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} showCounts />);
    // 청록 5단계: 11건은 11~20 칸, 2건은 1~2 칸, 0건은 회색
    expect(region("전남").getAttribute("fill")).toBe("#2ca25f");
    expect(region("경기").getAttribute("fill")).toBe("#ccece6");
    expect(region("대구").getAttribute("fill")).toBe("#e2e5ea");
    expect(badgeTexts()).toEqual(expect.arrayContaining(["전남 11", "경기 2", "대구"]));
  });

  it("hides zero-benefit labels while the sheet covers half the map, and shows them with the map up", () => {
    const { rerender } = render(
      <PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} showCounts coverTop={300} />,
    );
    // 반반 - 지도가 작아 이름끼리 부딪히므로 혜택 있는 곳만
    expect(badgeTexts()).toEqual(expect.arrayContaining(["전남 11", "경기 2"]));
    expect(badgeTexts()).not.toContain("대구");
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} showCounts coverTop={300} sheetLow />);
    expect(badgeTexts()).toContain("대구");
  });

  it("moves 제주 into a small inset at the bottom right so the mainland is larger", () => {
    render(<PolicyRegionMap counts={{ 제주: { own: 2, total: 2 } }} onSelect={() => undefined} selected={null} showCounts />);
    expect(document.querySelector(".thmap-inset")).toBeTruthy();
    const [x, y] = (region("제주").getAttribute("d") as string).slice(1).split("L")[0].split(",").map(Number);
    // 도안의 제주(가로 60~90, 세로 225~245)를 오른쪽 아래 삽입 틀(165.5~200.5, 193.5~215.5)로
    expect(x).toBeGreaterThan(160);
    expect(y).toBeLessThan(220);
    const jeju = Array.from(document.querySelectorAll(".thmap-bd")).find((g) => g.textContent === "제주 2") as Element;
    expect(jeju.getAttribute("transform")).toBe("translate(183,187)");
  });

  it("lets a small metro be picked from a generous invisible target", () => {
    const onSelect = vi.fn();
    const onBackground = vi.fn();
    render(<PolicyRegionMap counts={counts} onSelect={onSelect} selected={null} onBackground={onBackground} />);
    const seoul = document.querySelector('.thmap-hit[data-region="서울"]') as SVGCircleElement;
    expect(seoul).toBeTruthy();
    fireEvent.click(seoul);
    expect(onSelect).toHaveBeenLastCalledWith("서울");
    expect(onBackground).not.toHaveBeenCalled();
  });

  it("fades the neighbours to plain land and puts tappable city dots on the picked region", () => {
    const onPlace = vi.fn();
    const { rerender } = render(
      <PolicyRegionMap
        counts={counts}
        onSelect={() => undefined}
        selected="전남"
        focus
        showCounts
        places={[{ name: "완도", count: 2 }, { name: "좌표없는곳", count: 1 }]}
        onSelectPlace={onPlace}
      />,
    );
    expect(document.querySelector(".thmap-svg")?.classList.contains("thmap-focus")).toBe(true);
    expect(region("경기").classList.contains("thmap-dim")).toBe(true);
    expect(region("전남").classList.contains("thmap-dim")).toBe(false);
    // 고른 도의 이름표는 지역 카드가 말한다 - 둘레 도 이름만 옅게
    expect(document.querySelectorAll(".thmap-bd")).toHaveLength(0);
    const neighbours = Array.from(document.querySelectorAll(".thmap-nb")).map((t) => t.textContent);
    expect(neighbours).toContain("경기 2");
    expect(neighbours.some((text) => text?.startsWith("전남"))).toBe(false);
    // 좌표가 없는 시군은 점을 찍지 않는다
    const dots = document.querySelectorAll(".thmap-dot");
    expect(dots).toHaveLength(1);
    expect(dots[0].getAttribute("aria-label")).toBe("완도 혜택 2건");
    fireEvent.click(dots[0]);
    expect(onPlace).toHaveBeenLastCalledWith("완도");
    // 다시 누르면 도 전체로
    rerender(
      <PolicyRegionMap counts={counts} onSelect={() => undefined} selected="전남" focus places={[{ name: "완도", count: 2 }]} selectedPlace="완도" onSelectPlace={onPlace} />,
    );
    fireEvent.click(document.querySelector(".thmap-dot") as Element);
    expect(onPlace).toHaveBeenLastCalledWith(null);
    // 선택을 풀면 흐림·점·띄운 도가 걷힌다
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} focus onSelectPlace={onPlace} />);
    expect(document.querySelector(".thmap-dim")).toBeNull();
    expect(document.querySelector(".thmap-dot")).toBeNull();
    expect(document.querySelector(".thmap-lift")?.childElementCount).toBe(0);
  });

  it("tells the page when empty sea is tapped with nothing picked", () => {
    const onBackground = vi.fn();
    render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} onBackground={onBackground} />);
    fireEvent.click(document.querySelector(".thmap-wrap") as HTMLElement);
    expect(onBackground).toHaveBeenCalled();
    fireEvent.click(region("전남"));
    expect(onBackground).toHaveBeenCalledTimes(1);
  });

  it("clears the selection on Escape and on a tap on empty sea", () => {
    const onSelect = vi.fn();
    render(<PolicyRegionMap counts={counts} onSelect={onSelect} selected="전남" />);
    fireEvent.keyDown(region("전남"), { key: "Escape" });
    expect(onSelect).toHaveBeenLastCalledWith(null);
    onSelect.mockClear();
    fireEvent.click(document.querySelector(".thmap-svg") as SVGSVGElement);
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("picks a region from the keyboard", () => {
    const onSelect = vi.fn();
    render(<PolicyRegionMap counts={counts} onSelect={onSelect} selected={null} />);
    expect(region("전남").getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(region("전남"), { key: "Enter" });
    expect(onSelect).toHaveBeenLastCalledWith("전남");
  });
});
