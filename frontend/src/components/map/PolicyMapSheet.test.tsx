import { useState } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import { PolicyMapSheet } from "./PolicyMapSheet";

/* 올라온 정도(0=지도, 1=한 페이지). 시트·딤·탭바가 전부 이 값 하나를 읽는다 -
   매 프레임 문서 전체가 다시 계산되지 않게 body 가 아니라 읽는 요소에 직접 쓴다 */
const progress = () =>
  Number((document.querySelector(".thmap-sheet") as HTMLElement).style.getPropertyValue("--thmap-progress"));

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
          fireEvent.wheel(document.body, { deltaY: -25 });
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

  it("stays where it was left when the pull stops short of the middle", () => {
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));

      // 두 칸(160px)은 중간(190)에 못 미친다 - 도로 올라가지 않고 그 자리에 선다
      fireEvent.wheel(document.body, { deltaY: -100 });
      fireEvent.wheel(document.body, { deltaY: -100 });
      expect(sheet.classList.contains("thmap-open")).toBe(true);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);

      // 손을 뗀 뒤에도 그대로 - 뒤로 지도가 보이는 채로 멈춰 있는다
      vi.advanceTimersByTime(600);
      expect(progress()).toBeCloseTo(1 - 160 / 380, 2);
      expect(sheet.classList.contains("thmap-open")).toBe(true);

      // 멈춘 자리에서 도로 올려도 중간을 건너가지 않으니 또 그 자리에 선다
      fireEvent.wheel(document.body, { deltaY: 100 });
      expect(progress()).toBeCloseTo(1 - 80 / 380, 2);
      // 끝 언저리(8%)까지 올리면 그때 검색창 밑에 붙는다
      fireEvent.wheel(document.body, { deltaY: 100 });
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

  it("does not listen to the wheel when disabled", () => {
    const spy = vi.spyOn(document, "addEventListener");
    mount(false);
    expect(spy.mock.calls.some(([type]) => type === "wheel")).toBe(false);
    spy.mockRestore();
  });
});
