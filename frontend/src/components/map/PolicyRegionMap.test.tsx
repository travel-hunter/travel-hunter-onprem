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
  return el as SVGGElement;
}

describe("PolicyRegionMap", () => {
  afterEach(() => cleanup());

  it("draws all 17 regions and dims only the ones with no policies of their own", () => {
    render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    expect(document.querySelectorAll(".thmap-rg")).toHaveLength(17);
    expect(region("전남").classList.contains("thmap-empty")).toBe(false);
    expect(region("경기").classList.contains("thmap-empty")).toBe(false);
    // 지금 API 기준 대구는 0건 - 시안이 굽던 92건 데이터와 다르다
    expect(region("대구").classList.contains("thmap-empty")).toBe(true);
    // 건수를 안 준 지역은 0건으로 그린다
    expect(region("서울").classList.contains("thmap-empty")).toBe(true);
  });

  it("keeps a region dimmed when only nationwide policies reach it, but counts them in the label", () => {
    // 전국 정책은 목록엔 나오되(total) 흐림 판정(own)엔 불참 - 전국 1건에 17곳이 다 켜지면 안 된다
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
    fireEvent.click(region("전남"));
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("raises the selected region above its neighbours and lowers it when deselected", () => {
    const { rerender } = render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    const labels = document.querySelector(".thmap-labels") as Element;
    expect(labels).toBeTruthy();
    const zoomer = labels.parentNode as Element;
    const label = (name: string) => Array.from(document.querySelectorAll(".thmap-lbl")).find((l) => l.textContent === name) as Element;
    const after = (a: Element, b: Element) => (a.compareDocumentPosition(b) & window.Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected="경기" />);
    // 고른 지역은 이름표 층보다 위 - 솟은 땅이 이웃 이름표(서울·인천)를 덮는다
    expect(after(labels, region("경기"))).toBe(true);
    // 제 이름표만 그 위에 얹힌다
    expect(zoomer.lastElementChild).toBe(label("경기"));
    expect(label("서울").parentNode).toBe(labels);
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    expect(region("경기").classList.contains("thmap-on")).toBe(false);
    // 풀면 지역은 이름표 층 아래로, 이름표는 층 안으로 돌아온다
    expect(after(region("경기"), labels)).toBe(true);
    expect(label("경기").parentNode).toBe(labels);
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
    // 칸이 그림보다 길쭉하면 남는 쪽을 바다로 늘린다 - 비율이 같아지므로 빈 띠가 안 생기고
    // 땅도 안 잘린다. 칸을 못 재는 환경에서는 그림 제 비율을 그대로 쓴다.
    const width = vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(390);
    const height = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
    /* jsdom 에는 getBBox 가 없다 - 없으면 엔진이 추정 viewBox 를 그대로 쓰는 폴백으로 빠진다.
       여기서 재려는 것은 그 폴백이 아니라 칸에 맞추는 계산이라 땅 범위를 흉내 낸다. */
    const svgProto = window.SVGElement.prototype as unknown as { getBBox?: () => DOMRect };
    const hadBBox = "getBBox" in svgProto;
    svgProto.getBBox = () => ({ x: 0, y: 0, width: 100, height: 150 }) as DOMRect;
    try {
      render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
      const box = (document.querySelector(".thmap-svg") as SVGSVGElement).getAttribute("viewBox") as string;
      const [, , vw, vh] = box.split(" ").map(Number);
      expect(vw / vh).toBeCloseTo(390 / 600, 2);
    } finally {
      if (!hadBBox) delete svgProto.getBBox;
      height.mockRestore();
      width.mockRestore();
    }
  });

  it("keeps the sea under the land after a selection is cleared", () => {
    // 선택을 풀면 레이어 순서를 되돌리는데, 그때 바다가 땅 위로 올라오던 적이 있다.
    // 바다가 앞으로 나오면 해안 흰 테두리가 옆면·바닥을 덮어 지도 색이 달라 보인다.
    const { rerender } = render(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    const zoomer = document.querySelector(".thmap-svg > g") as SVGGElement;
    const seaFirst = () => (zoomer.firstElementChild as Element).classList.contains("thmap-sea");
    expect(seaFirst()).toBe(true);
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected="전남" />);
    rerender(<PolicyRegionMap counts={counts} onSelect={() => undefined} selected={null} />);
    expect(seaFirst()).toBe(true);
  });

  it("clears the selection on Escape and on a background click", () => {
    const onSelect = vi.fn();
    render(<PolicyRegionMap counts={counts} onSelect={onSelect} selected="전남" />);
    fireEvent.keyDown(region("전남"), { key: "Escape" });
    expect(onSelect).toHaveBeenLastCalledWith(null);
    fireEvent.click(document.querySelector(".thmap-svg > rect") as SVGRectElement);
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });
});
