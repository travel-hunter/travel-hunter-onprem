import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import { PolicyMapSheet } from "./PolicyMapSheet";

/* <b> 로 쪼개진 글자가 접근성 이름으로 합쳐질 때 공백이 들쭉날쭉하다 - 공백을 빼고 견준다 */
const named = (expected: string) => (name: string) => name.replace(/\s+/g, "") === expected.replace(/\s+/g, "");

const policies: Policy[] = [
  { ...examplePolicyDetail, id: "s1", slug: "s1", title: "[영광] 디지털관광주민증 혜택", region: "전남" },
  { ...examplePolicyDetail, id: "s2", slug: "s2", title: "[완도] 디지털관광주민증 혜택", region: "전남" },
  { ...examplePolicyDetail, id: "s3", slug: "s3", title: "[하동] 대한민국 반값여행 지원", region: "경남" },
];

function mount(enabled = true) {
  return render(
    <MemoryRouter>
      <div className="thmap-wrap" data-testid="map-area" />
      <PolicyMapSheet enabled={enabled} policies={policies} savedSlugs={new Set()} onToggleSave={async () => undefined} />
    </MemoryRouter>,
  );
}

describe("PolicyMapSheet", () => {
  afterEach(() => cleanup());

  it("waits closed with the grab label and opens on the handle", () => {
    mount();
    const grab = screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") });
    expect(grab).toHaveAttribute("aria-expanded", "false");
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    fireEvent.click(grab);
    expect(grab).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(true);
  });

  it("groups by region by default and by program on the segment", () => {
    mount();
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
    fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
    fireEvent.click(document.querySelector(".thmap-dim") as HTMLElement);
    expect(document.querySelector(".thmap-sheet")?.classList.contains("thmap-open")).toBe(false);
    rerender(
      <MemoryRouter>
        <PolicyMapSheet enabled={false} policies={policies} savedSlugs={new Set()} onToggleSave={async () => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector(".thmap-sheet")).toBeNull();
  });

  it("opens on a single downward wheel anywhere on the map screen", () => {
    mount();
    const isOpen = () => document.querySelector(".thmap-sheet")?.classList.contains("thmap-open");
    // 여는 건 가볍게 한 번 - 지도 위든 그 밖이든 아래로 굴리면 올라온다
    fireEvent.wheel(document.body, { deltaY: 40 });
    expect(isOpen()).toBe(true);
    // 한 번 위로 굴린다고 닫히지 않는다 (닫는 문턱은 아래 두 테스트가 본다)
    fireEvent.wheel(document.body, { deltaY: -40 });
    expect(isOpen()).toBe(true);
  });

  it("needs the sheet dragged past half its height before it closes", () => {
    // jsdom 은 높이가 0 이라 문턱이 사라진다 - 실제 키를 흉내 내야 규칙이 검증된다
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      const isOpen = () => sheet.classList.contains("thmap-open");
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
      expect(isOpen()).toBe(true);

      // 한 칸에 80px - 두 칸(160)은 절반(200)에 못 미쳐 열린 채로 남는다
      fireEvent.wheel(document.body, { deltaY: -100 });
      expect(isOpen()).toBe(true);
      expect(sheet.style.transform).toBe("translateX(-50%) translateY(80px)");
      fireEvent.wheel(document.body, { deltaY: -100 });
      expect(isOpen()).toBe(true);

      // 세 칸(240)이면 절반을 넘겨 닫히고, 밀어 둔 자리도 지워진다
      fireEvent.wheel(document.body, { deltaY: -100 });
      expect(isOpen()).toBe(false);
      expect(sheet.style.transform).toBe("");
    } finally {
      tall.mockRestore();
    }
  });

  it("springs back to open when the pull stops above half", () => {
    vi.useFakeTimers();
    const tall = vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(400);
    try {
      mount();
      const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
      fireEvent.click(screen.getByRole("button", { name: named("정책 3건 · 시도 2곳") }));
      fireEvent.wheel(document.body, { deltaY: -100 });
      expect(sheet.style.transform).toBe("translateX(-50%) translateY(80px)");

      // 손을 멈추면 제자리로 돌아가고 열린 채로 남는다
      vi.advanceTimersByTime(200);
      expect(sheet.style.transform).toBe("");
      expect(sheet.classList.contains("thmap-open")).toBe(true);
    } finally {
      tall.mockRestore();
      vi.useRealTimers();
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
