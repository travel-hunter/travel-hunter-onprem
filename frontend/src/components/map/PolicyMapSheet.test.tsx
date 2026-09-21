// @ts-expect-error Vitest runs this assertion in Node, but this project does not install Node type declarations.
import { readFileSync } from "node:fs";
import { useState } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import { PolicyMapSheet, WHEEL_DAMP } from "./PolicyMapSheet";

/* 올라온 정도(0=지도, 1=한 페이지). 시트·딤·탭바가 전부 이 값 하나를 읽는다 -
   매 프레임 문서 전체가 다시 계산되지 않게 body 가 아니라 읽는 요소에 직접 쓴다 */
const progress = () =>
  Number((document.querySelector(".thmap-sheet") as HTMLElement).style.getPropertyValue("--thmap-progress"));

/* 휠 입력을 '페이지가 움직일 px' 로 준다. 감도(WHEEL_DAMP)가 바뀌어도 아래 계산이 그대로 맞는다.
   음수 = 아래로 끌어내림, 양수 = 위로 되올림 */
const wheelBy = (px: number) => fireEvent.wheel(document.body, { deltaY: px / WHEEL_DAMP });

/* <b> 로 쪼개진 글자가 접근성 이름으로 합쳐질 때 공백이 들쭉날쭉하다 - 공백을 빼고 견준다 */
const named = (expected: string) => (name: string) => name.replace(/\s+/g, "") === expected.replace(/\s+/g, "");

const policies: Policy[] = [
  { ...examplePolicyDetail, id: "s1", slug: "s1", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
  { ...examplePolicyDetail, id: "s2", slug: "s2", title: "[완도] 디지털관광주민증 혜택", region: "전남" },
  { ...examplePolicyDetail, id: "s3", slug: "s3", title: "[하동] 대한민국 반값여행 지원", region: "경남" },
];

/* 열림 상태는 이제 바깥(URL)이 들고 있다 - 테스트에서는 이 껍데기가 대신 들어 준다 */
function SheetHarness({ enabled }: { enabled: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="thmap-wrap" data-testid="map-area" />
      <PolicyMapSheet
        enabled={enabled}
        open={open}
        onOpenChange={setOpen}
        policies={policies}
        savedSlugs={new Set()}
        onToggleSave={async () => undefined}
      />
    </>
  );
}

function mount(enabled = true) {
  return render(
    <MemoryRouter>
      <SheetHarness enabled={enabled} />
    </MemoryRouter>,
  );
}

describe("PolicyMapSheet", () => {
  afterEach(() => cleanup());

  it("waits closed with the grab label and opens on the handle", () => {
    mount();
    const grab = screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") });
    expect(grab).toHaveAttribute("aria-expanded", "false");
    expect(grab).not.toHaveAttribute("aria-controls");
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    expect(document.querySelectorAll(".thmap-tile")).toHaveLength(0);
    fireEvent.click(grab);
    expect(grab).toHaveAttribute("aria-expanded", "true");
    expect(grab).toHaveAttribute("aria-controls", "thmap-sheet-body");
    expect(document.querySelectorAll(".thmap-tile")).toHaveLength(17);
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(true);
  });

  it("groups by region by default and by program on the segment", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    const tiles = () => document.querySelectorAll(".thmap-tile");
    // 17개 시도를 다 낸다 - 정책 0건 지역도 사진 카드로 보여야 지도와 짝이 맞는다
    expect(tiles()).toHaveLength(17);
    expect(within(tiles()[0] as HTMLElement).getByText("전남", { selector: "strong" })).toBeInTheDocument();
    expect(within(tiles()[1] as HTMLElement).getByText("경남", { selector: "strong" })).toBeInTheDocument();
    // 0건 지역은 건수 내림차순에서 뒤로 밀린다
    expect(within(tiles()[16] as HTMLElement).getByText("0")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "정책별" }));
    expect(screen.getByText("디지털관광주민증 혜택")).toBeInTheDocument();
    expect(screen.getByText("대한민국 반값여행 지원")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: named("정책 3건 · 2가지로 묶임") })).toBeInTheDocument();
  });

  it("opens a tile into its cards and comes back", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    fireEvent.click(screen.getByRole("button", { name: /^전남/ }));
    expect(screen.getByText("[영광] 디지털관광주민증 혜택")).toBeInTheDocument();
    expect(screen.getByText("[완도] 디지털관광주민증 혜택")).toBeInTheDocument();
    expect(screen.queryByText("[하동] 대한민국 반값여행 지원")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: named("전남 2건") })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "카테고리로" }));
    expect(document.querySelectorAll(".thmap-tile")).toHaveLength(17);
  });

  it("closes on Escape and on the dim, and disappears when disabled", () => {
    const { rerender } = mount();
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    expect(document.querySelector(".thmap-sheet-body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    fireEvent.click(document.querySelector(".thmap-dim") as HTMLElement);
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    rerender(
      <MemoryRouter>
        <SheetHarness enabled={false} />
      </MemoryRouter>,
    );
    expect(document.querySelector(".thmap-sheet")).toBeNull();
  });

  it("opens on a single downward wheel anywhere on the map screen", () => {
    // 닫는 문턱은 시트 높이에 비례한다 - jsdom 의 0 높이로는 한 칸에 닫혀 버린다
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const isOpen = () => document.querySelector(".thmap-sheet")?.classList.contains("thmap-open");
      // 여는 건 가볍게 한 번 - 지도 위든 그 밖이든 아래로 굴리면 올라온다
      fireEvent.wheel(document.body, { deltaY: 40 });
      expect(isOpen()).toBe(true);
      expect(progress()).toBe(1);
      // 한 번 위로 굴린다고 닫히지 않는다 (닫는 문턱은 아래 두 테스트가 본다)
      fireEvent.wheel(document.body, { deltaY: -40 });
      expect(isOpen()).toBe(true);
    } finally {
      tall.mockRestore();
    }
  });

  it("needs a slow pull past half the way down before it closes", () => {
    // jsdom 은 높이가 0 이라 문턱이 사라진다 - 실제 키를 흉내 내야 규칙이 검증된다.
    // 내려가는 거리는 400 - 손잡이 20 = 380, 절반은 190.
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      const isOpen = () => sheet.classList.contains("thmap-open");
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
      expect(isOpen()).toBe(true);

      // 트랙패드처럼 한 번에 20px 씩, 천천히(50ms 간격) 끌어내린다
      const slowPull = (times: number) => {
        for (let i = 0; i < times; i += 1) {
          wheelBy(-20);
          vi.advanceTimersByTime(50);
        }
      };

      // 절반(190)에 못 미치는 동안은 열린 채로 따라 내려오기만 한다
      slowPull(8);
      expect(isOpen()).toBe(true);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);

      // 절반을 넘기면 닫힌다
      slowPull(2);
      expect(isOpen()).toBe(false);
      expect(progress()).toBe(0);
    } finally {
      tall.mockRestore();
      vi.useRealTimers();
    }
  });

  it("rests where it was left, then returns to the nearer end on its own", () => {
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));

      // 두 칸(160px)은 중간(190)에 못 미친다 - 도로 올라가지 않고 그 자리에 선다
      wheelBy(-80);
      wheelBy(-80);
      expect(sheet.classList.contains("thmap-open")).toBe(true);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);

      // 손을 뗀 직후에는 그대로다(굴림이 멎었다고 보는 140ms + 머무는 300ms 가 아직 안 찼다)
      vi.advanceTimersByTime(300);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);
      expect(sheet.classList.contains("thmap-open")).toBe(true);

      // 머무는 동안 다시 만지면 자동 복귀는 그 시점부터 다시 센다
      wheelBy(20);
      const nudged = 1 - 160 / 380 + 20 / 380;
      vi.advanceTimersByTime(300);
      expect(progress()).toBeCloseTo(nudged, 2);

      // 그대로 두면 중간보다 위였으니 스스로 올라붙는다 - 다시 올리는 수고가 없다
      vi.advanceTimersByTime(200);
      expect(progress()).toBe(1);
      expect(sheet.classList.contains("thmap-open")).toBe(true);

      // 다시 끌어내려 아래 단계로 이어 간다
      wheelBy(-80);
      wheelBy(-80);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);

      // 멈춘 자리에서 도로 올려도 중간을 건너가지 않으니 또 그 자리에 선다
      wheelBy(80);
      expect(progress()).toBeCloseTo(1 - 80 / 380, 2);
      // 끝 언저리(8%)까지 올리면 그때 검색창 밑에 붙는다
      wheelBy(80);
      expect(progress()).toBe(1);
    } finally {
      tall.mockRestore();
      vi.useRealTimers();
    }
  });

  it("keeps the result of a handle drag instead of toggling it again on click", () => {
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      const grab = screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") });

      const dispatchPointer = (type: string, clientY: number) => {
        const event = new Event(type, { bubbles: true });
        Object.defineProperties(event, {
          clientY: { value: clientY },
          pointerId: { value: 1 },
        });
        fireEvent(grab, event);
      };

      dispatchPointer("pointerdown", 300);
      dispatchPointer("pointermove", 100);
      // 0 에서 200px 위로 = 0.53, 중간을 건너갔으니 그 자리에서 끝까지 붙는다
      expect(progress()).toBe(1);
      dispatchPointer("pointerup", 100);
      fireEvent.click(grab);

      expect(sheet).toHaveClass("thmap-open");
    } finally {
      tall.mockRestore();
    }
  });

  it("does not swallow the next click when a drag produces no synthetic click", () => {
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      const grab = screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") });
      const dispatchPointer = (type: string, clientY: number) => {
        const event = new Event(type, { bubbles: true });
        Object.defineProperties(event, {
          clientY: { value: clientY },
          pointerId: { value: 1 },
        });
        fireEvent(grab, event);
      };

      dispatchPointer("pointerdown", 300);
      dispatchPointer("pointermove", 100);
      dispatchPointer("pointerup", 100);
      expect(sheet).toHaveClass("thmap-open");

      vi.runAllTimers();
      fireEvent.click(grab);
      expect(sheet).not.toHaveClass("thmap-open");
    } finally {
      tall.mockRestore();
      vi.useRealTimers();
    }
  });

  it("lets the list be pulled down by touch when it is scrolled to the top", () => {
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
      const body = document.querySelector(".thmap-sheet-body") as HTMLElement;
      const touch = (type: string, clientY: number) =>
        fireEvent[type === "touchstart" ? "touchStart" : type === "touchmove" ? "touchMove" : "touchEnd"](
          body,
          { touches: type === "touchend" ? [] : [{ clientY }] },
        );

      // 손잡이는 다 올라오면 안 보인다 - 목록 맨 위에서 끌어도 페이지가 따라 내려와야 한다
      touch("touchstart", 200);
      touch("touchmove", 260);
      expect(progress()).toBeCloseTo(1 - 60 / 380, 2);
      touch("touchend", 260);
      // 중간 전이라 그 자리에 멈춘다
      expect(progress()).toBeCloseTo(1 - 60 / 380, 2);
      expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(true);

      // 중간을 건너가면 지도까지 내려간다
      touch("touchstart", 200);
      touch("touchmove", 400);
      expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    } finally {
      tall.mockRestore();
    }
  });

  it("steps back with the floating button - cards to categories, then closed", () => {
    mount();
    const fab = () => screen.queryByRole("button", { name: "뒤로 가기" });
    // 닫혀 있을 땐 없다
    expect(fab()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    fireEvent.click(screen.getByRole("button", { name: /^전남/ }));
    expect(screen.getByText("[영광] 디지털관광주민증 혜택")).toBeInTheDocument();
    // 상세에서 누르면 목록으로 - 시트는 그대로 열려 있다
    fireEvent.click(fab() as HTMLElement);
    expect(screen.queryByText("[영광] 디지털관광주민증 혜택")).not.toBeInTheDocument();
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(true);
    // 목록에서 누르면 닫히고 버튼도 사라진다
    fireEvent.click(fab() as HTMLElement);
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    expect(fab()).toBeNull();
  });

  it("drops back to the map when it was left resting below the middle", () => {
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      const grab = screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") });
      const pointer = (type: string, clientY: number) => {
        const event = new Event(type, { bubbles: true });
        Object.defineProperties(event, { clientY: { value: clientY }, pointerId: { value: 1 } });
        fireEvent(grab, event);
      };

      // 닫힌 데서 114px(30%)만 끌어올리고 놓는다 - 중간을 못 건넜으니 그 자리에 선다
      pointer("pointerdown", 300);
      pointer("pointermove", 186);
      pointer("pointerup", 186);
      expect(progress()).toBeCloseTo(114 / 380, 2);

      // 위쪽과 같은 규칙 - 잠깐 뒤 가까운 끝(지도)으로 돌아간다. 밑에서만 영영 서 있지 않는다
      vi.advanceTimersByTime(200);
      expect(progress()).toBeCloseTo(114 / 380, 2);
      vi.advanceTimersByTime(200);
      expect(progress()).toBe(0);
      expect(sheet.classList.contains("thmap-open")).toBe(false);
    } finally {
      tall.mockRestore();
      vi.useRealTimers();
    }
  });

  it("does not flash the mobile tap highlight over map regions and labels", () => {
    // 지역과 이름표는 누를 수 있는 SVG 그룹이다. 모바일 브라우저는 탭 하이라이트를 요소의 외곽
    // 사각형으로 칠하므로, 지역 모양과 상관없는 네모 박스가 번쩍였다가 사라졌다.
    const mapCss = readFileSync("src/styles/policy-map.css", "utf8");
    expect(mapCss).toMatch(/\.thmap-host,\s*\.thmap-host \*\s*\{[^}]*-webkit-tap-highlight-color:\s*transparent/s);
  });

  it("keeps the app tab bar above the resting policy page", () => {
    // 페이지는 바닥(bottom: 0)까지 내려가 있어, 닫혀 있을 때도 아랫부분이 탭바 자리와 겹친다.
    // 페이지가 탭바보다 위 레이어면 올리기도 전에 탭바가 가려진다(모바일에서 하단 메뉴가 사라졌던 원인).
    const zIndexOf = (css: string, selector: string) => {
      const block = new RegExp(`(?:^|\\n)${selector.replace(/[.]/g, "\\.")}\\s*\\{([^}]*)\\}`).exec(css);
      const value = /z-index:\s*(\d+)/.exec(block?.[1] ?? "");
      return value ? Number(value[1]) : Number.NaN;
    };
    const mapCss = readFileSync("src/styles/policy-map.css", "utf8");
    const appCss = readFileSync("src/styles/app.css", "utf8");
    const tabBar = zIndexOf(appCss, ".bottom-tabs");

    expect(tabBar).toBeGreaterThan(0);
    expect(zIndexOf(mapCss, ".thmap-sheet")).toBeLessThan(tabBar);
    expect(zIndexOf(mapCss, ".thmap-dim")).toBeLessThan(tabBar);
    // 떠 있는 뒤로가기는 페이지가 다 올라왔을 때만 뜬다 - 그때는 탭바 위여야 눌린다
    expect(zIndexOf(mapCss, ".thmap-fab")).toBeGreaterThan(tabBar);
  });

  it("does not listen to the wheel when disabled", () => {
    const spy = vi.spyOn(document, "addEventListener");
    mount(false);
    expect(spy.mock.calls.some(([type]) => type === "wheel")).toBe(false);
    spy.mockRestore();
  });
});
