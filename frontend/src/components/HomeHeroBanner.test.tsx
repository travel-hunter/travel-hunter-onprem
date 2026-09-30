import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HERO_INTERVAL_MS, HomeHeroBanner, type HomeHeroSlide } from "./HomeHeroBanner";

const slides: HomeHeroSlide[] = ["첫째", "둘째", "셋째"].map((title, i) => ({
  key: title,
  to: `/policies/${i}`,
  family: "money",
  icon: null,
  eyebrow: <span>소식</span>,
  title,
  sub: `${title} 설명`,
}));

function mount(list = slides) {
  render(
    <MemoryRouter>
      <HomeHeroBanner slides={list} />
    </MemoryRouter>,
  );
  return document.querySelector(".home-hero") as HTMLElement;
}

const shown = () => document.querySelector(".home-hero-slide:not([inert])")?.textContent ?? "";
const tick = () => act(() => void vi.advanceTimersByTime(HERO_INTERVAL_MS));

/* '동작 줄이기' 설정은 matchMedia 로 읽는다 - jsdom 에는 없으므로 필요할 때만 흉내 낸다 */
function reduceMotion() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

/* jsdom 에는 PointerEvent 가 없어 pointerType·clientX 가 빠진 채 전달된다 - 마우스 사건에 종류만 얹은 대역 */
class TestPointerEvent extends MouseEvent {
  pointerType: string;
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerType = init.pointerType ?? "mouse";
  }
}

describe("HomeHeroBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("PointerEvent", TestPointerEvent);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows one slide at a time and moves on by itself", () => {
    mount();
    expect(shown()).toContain("첫째");
    expect(document.querySelectorAll(".home-hero-slide[inert]")).toHaveLength(2);
    expect(screen.getByText("1", { selector: ".home-hero-count b" })).toBeInTheDocument();
    tick();
    expect(shown()).toContain("둘째");
    tick();
    tick();
    expect(shown()).toContain("첫째");
    // 보이는 장만 누를 수 있고, 그 장의 정책으로 간다
    expect(screen.getByRole("link", { name: /첫째/ })).toHaveAttribute("href", "/policies/0");
  });

  it("stops with the pause button and moves with previous and next", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "자동 넘김 멈추기" }));
    expect(screen.getByRole("button", { name: "자동 넘김 다시 켜기" })).toHaveAttribute("aria-pressed", "true");
    tick();
    expect(shown()).toContain("첫째");
    fireEvent.click(screen.getByRole("button", { name: "다음 소식" }));
    expect(shown()).toContain("둘째");
    fireEvent.click(screen.getByRole("button", { name: "이전 소식" }));
    fireEvent.click(screen.getByRole("button", { name: "이전 소식" }));
    expect(shown()).toContain("셋째");
    // 멈춘 동안은 몇째 장인지 읽어 준다
    expect(document.querySelector(".home-hero-count")).toHaveAttribute("aria-live", "polite");
  });

  it("rests while a mouse is over it or focus is inside, so nothing moves while reading", () => {
    const hero = mount();
    fireEvent.pointerEnter(hero, { pointerType: "mouse" });
    tick();
    expect(shown()).toContain("첫째");
    fireEvent.pointerLeave(hero, { pointerType: "mouse" });
    fireEvent.focus(screen.getByRole("button", { name: "다음 소식" }));
    tick();
    expect(shown()).toContain("첫째");
    fireEvent.blur(screen.getByRole("button", { name: "다음 소식" }), { relatedTarget: document.body });
    tick();
    expect(shown()).toContain("둘째");
  });

  it("follows a sideways swipe and swallows the click at the end of it", () => {
    mount();
    const track = document.querySelector(".home-hero-track") as HTMLElement;
    fireEvent.pointerDown(track, { clientX: 220 });
    fireEvent.pointerUp(track, { clientX: 120 });
    expect(shown()).toContain("둘째");
    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    screen.getByRole("link", { name: /둘째/ }).dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    // 짧게 누른 것은 밀기가 아니다
    fireEvent.pointerDown(track, { clientX: 220 });
    fireEvent.pointerUp(track, { clientX: 210 });
    expect(shown()).toContain("둘째");
  });

  it("never moves by itself when the device asks for less motion", () => {
    reduceMotion();
    mount();
    tick();
    expect(shown()).toContain("첫째");
    expect(screen.queryByRole("button", { name: "자동 넘김 멈추기" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "다음 소식" }));
    expect(shown()).toContain("둘째");
  });

  it("draws a single slide without controls and nothing without slides", () => {
    mount(slides.slice(0, 1));
    expect(screen.queryByRole("button", { name: "다음 소식" })).toBeNull();
    cleanup();
    mount([]);
    expect(document.querySelector(".home-hero")).toBeNull();
  });
});
