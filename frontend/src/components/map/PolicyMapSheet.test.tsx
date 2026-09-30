// @ts-expect-error Vitest runs this assertion in Node, but this project does not install Node type declarations.
import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { Policy } from "../../api";
import { examplePolicyDetail } from "../../test/fixtures";
import { PolicyMapSheet } from "./PolicyMapSheet";
import { browseView, type SheetStop } from "./policyBrowse";

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

/* 목록 줄의 제휴처 수는 수집된 상세의 핵심 혜택 문장에서 읽는다(실데이터 모양 그대로) */
const partners = (place: string, count: number): Partial<Policy> => ({
  cardSummary: "지역 제휴 혜택",
  structuredDetail: {
    supportContent: [{ title: "핵심 혜택", description: `${place} 제휴처 ${count}곳의 숙박, 식음, 체험, 관광지 혜택을 제공합니다.` }],
  } as Policy["structuredDetail"],
});

const policies: Policy[] = [
  make("yg", "[영광] 디지털관광주민증 혜택", "전남", partners("영광", 12)),
  make("wd", "[완도] 디지털관광주민증 혜택", "전남", partners("완도", 9)),
  make("hd", "[하동] 대한민국 반값여행 지원", "경남"),
  make("rail", "내일로패스 할인", "전국"),
];

function mount({
  region = null,
  stop = "mid",
  onStop = vi.fn(),
  onBack = vi.fn(),
  onClear = vi.fn(),
  onNation = vi.fn(),
  enabled = true,
  list = policies,
}: {
  list?: Policy[];
  region?: string | null;
  stop?: SheetStop;
  onStop?: (stop: SheetStop) => void;
  onBack?: () => void;
  onClear?: () => void;
  onNation?: () => void;
  enabled?: boolean;
} = {}) {
  const view = browseView(list, region, null, null);
  const ui = (next: SheetStop) => (
    <MemoryRouter>
      <PolicyMapSheet
        enabled={enabled}
        view={view}
        stop={next}
        region={region}
        scopeKey={`${region}`}
        showBack={Boolean(region)}
        clearLabel={region ? "전체 지역" : null}
        onStop={onStop}
        onBack={onBack}
        onClear={onClear}
        onNation={onNation}
      />
    </MemoryRouter>
  );
  const result = render(ui(stop));
  return { ...result, restop: (next: SheetStop) => result.rerender(ui(next)), onStop, onBack, onClear, onNation };
}

const sheet = () => document.querySelector(".thmap-sheet") as HTMLElement;

describe("PolicyMapSheet", () => {
  afterEach(() => cleanup());

  it("rests half open with the list head and program groups, nationwide first", () => {
    mount();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("모든 지역 4건");
    const nation = screen.getByRole("button", { name: /전국 공통 혜택/ });
    expect(nation).toHaveAttribute("aria-expanded", "false");
    const group = screen.getByRole("button", { name: /디지털관광주민증 혜택/ });
    expect(group).toHaveAttribute("aria-expanded", "false");
    // 같은 사업 두 곳이 한 줄로 묶이고, 한 곳짜리는 그냥 한 줄
    expect(group).toHaveTextContent("2곳 · 영광, 완도");
    expect(screen.getByRole("link", { name: /대한민국 반값여행 지원/ })).toHaveAttribute("href", "/policies/hd");
    expect(sheet()).toHaveClass("thmap-at-mid");
  });

  it("raises one page when a group opens in all regions and folds it again in place", () => {
    const { onStop } = mount();
    const group = screen.getByRole("button", { name: /디지털관광주민증 혜택/ });
    fireEvent.click(group);
    expect(onStop).toHaveBeenLastCalledWith("full");
    expect(group).toHaveAttribute("aria-expanded", "true");
    const kids = document.getElementById(group.getAttribute("aria-controls") as string) as HTMLElement;
    expect(within(kids).getByRole("link", { name: /영광/ })).toHaveAttribute("href", "/policies/yg");
    // 묶음 머리는 사업 공통 문구와 보이는 지역의 제휴처 합, 받는 것이 지역마다 다르면 지역 줄마다 보인다
    expect(group).toHaveTextContent("제휴처 21곳에서 할인");
    expect(kids).toHaveTextContent("제휴처 12곳 할인");
    fireEvent.click(group);
    expect(group).toHaveAttribute("aria-expanded", "false");
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("shows a place line every place shares once on the group head instead of on each row", () => {
    const refund = (place: string, id: string, pay: string) =>
      make(id, `[${place}] 대한민국 반값여행 지원`, "전남", {
        cardSummary: "최대 20만원 환급",
        summary: "여행 경비의 50%를 돌려드립니다.",
        structuredDetail: {
          supportContent: [{ title: "혜택 적용 조건", description: `관광지 2개소 방문 인증, ${pay} 앱으로 결제` }],
        } as Policy["structuredDetail"],
      });
    mount({ list: [refund("고흥", "gh", "chak"), refund("장흥", "jh", "chak")], region: "전남" });
    const group = screen.getByRole("button", { name: /대한민국 반값여행 지원/ });
    expect(group).toHaveTextContent("공통 · 관광지 2곳 인증 · chak 앱으로 결제");
    const kids = document.getElementById(group.getAttribute("aria-controls") as string) as HTMLElement;
    expect(kids).not.toHaveTextContent("관광지 2곳 인증");
    cleanup();
    // 곳마다 다르면 머리가 아니라 지역 줄마다
    mount({ list: [refund("고흥", "gh", "chak"), refund("영광", "yg", "코나아이")], region: "전남" });
    const mixed = screen.getByRole("button", { name: /대한민국 반값여행 지원/ });
    expect(mixed).not.toHaveTextContent("공통 ·");
    const rows = document.getElementById(mixed.getAttribute("aria-controls") as string) as HTMLElement;
    expect(rows).toHaveTextContent("관광지 2곳 인증 · chak 앱으로 결제");
    expect(rows).toHaveTextContent("관광지 2곳 인증 · 코나아이 앱으로 결제");
  });

  it("opens groups by default in a picked region and offers the nationwide ones", () => {
    const { onNation, onClear, onBack } = mount({ region: "전남" });
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("전남 2건");
    const group = screen.getByRole("button", { name: /디지털관광주민증 혜택/ });
    expect(group).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "전국 공통 혜택 1건도 여기서 쓸 수 있어요" }));
    expect(onNation).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "전체 지역" }));
    expect(onClear).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    expect(onBack).toHaveBeenCalled();
  });

  it("moves between half and one page with the head toggle, and the whole head lifts it from the map", () => {
    const { onStop, restop } = mount();
    fireEvent.click(screen.getByRole("button", { name: "목록 펼치기" }));
    expect(onStop).toHaveBeenLastCalledWith("full");
    restop("full");
    fireEvent.click(screen.getByRole("button", { name: "목록 접기" }));
    expect(onStop).toHaveBeenLastCalledWith("mid");
    restop("low");
    expect(screen.getByText("누르거나 끌어 올리면 목록이 나와요")).toBeInTheDocument();
    fireEvent.click(document.querySelector(".thmap-head") as HTMLElement);
    expect(onStop).toHaveBeenLastCalledWith("mid");
  });

  it("settles a head drag at the nearest stop and swallows the click that follows", () => {
    const tall = vi.spyOn(window, "innerHeight", "get").mockReturnValue(800);
    try {
      const { onStop } = mount();
      const head = document.querySelector(".thmap-head") as HTMLElement;
      const pointer = (type: string, clientY: number, timeStamp = 0) => {
        const event = new Event(type, { bubbles: true });
        Object.defineProperties(event, { clientY: { value: clientY }, pointerId: { value: 1 }, button: { value: 0 }, timeStamp: { value: timeStamp } });
        fireEvent(head, event);
      };
      // 반반(자리 넓이의 절반)에서 위로 크게 끌면 한 페이지에 가깝다
      pointer("pointerdown", 500, 0);
      pointer("pointermove", 200, 200);
      pointer("pointerup", 200, 400);
      expect(onStop).toHaveBeenLastCalledWith("full");
      // 끌기 뒤에 따라오는 click 이 머리의 ∧ 를 한 번 더 누르지 않는다
      fireEvent.click(screen.getByRole("button", { name: "목록 펼치기" }));
      expect(onStop).toHaveBeenCalledTimes(1);
    } finally {
      tall.mockRestore();
    }
  });

  it("keeps the list scrolling in place at half height - the wheel over the list does not move the sheet", () => {
    const { onStop } = mount();
    const list = document.querySelector(".thmap-list") as HTMLElement;
    fireEvent.wheel(list, { deltaY: 300 });
    expect(onStop).not.toHaveBeenCalled();
  });

  it("disappears when disabled", () => {
    mount({ enabled: false });
    expect(sheet()).toBeNull();
  });

  it("does not flash the mobile tap highlight over map regions and labels", () => {
    // 지역과 이름표는 누를 수 있는 SVG 그룹이다. 모바일 브라우저는 탭 하이라이트를 요소의 외곽
    // 사각형으로 칠하므로, 지역 모양과 상관없는 네모 박스가 번쩍였다가 사라졌다.
    const mapCss = readFileSync("src/styles/policy-map.css", "utf8");
    expect(mapCss).toMatch(/\.thmap-host,\s*\.thmap-host \*\s*\{[^}]*-webkit-tap-highlight-color:\s*transparent/s);
  });

  it("keeps the app tab bar above the list sheet and the search panel", () => {
    // 시트는 탭바 위에 서지만 레이어는 아래여야 한다 - 위면 모바일에서 하단 메뉴가 가려진다.
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
    expect(zIndexOf(mapCss, ".thmap-search")).toBeLessThan(tabBar);
    expect(zIndexOf(mapCss, ".thmap-search")).toBeGreaterThan(zIndexOf(mapCss, ".thmap-sheet"));
  });
});
