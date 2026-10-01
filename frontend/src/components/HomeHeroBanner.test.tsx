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

const slide = (title: string) =>
  Array.from(document.querySelectorAll<HTMLElement>(".home-hero-slide")).find((el) => el.textContent?.includes(title)) as HTMLElement;
const center = () => document.querySelector('.home-hero-slide[data-pos="0"]')?.textContent ?? "";
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

  it("puts one slide in the middle with the others peeking on both sides, and moves on by itself", () => {
    mount();
    expect(slide("첫째")).toHaveAttribute("data-pos", "0");
    expect(slide("둘째")).toHaveAttribute("data-pos", "1");
    expect(slide("셋째")).toHaveAttribute("data-pos", "-1");
    // 옆 장은 낭독·탭 순서에서 빠진다 - 가운데 장만 그 정책 링크
    expect(screen.getByRole("link", { name: /첫째/ })).toHaveAttribute("href", "/policies/0");
    expect(screen.queryByRole("link", { name: /둘째/ })).toBeNull();
    expect(slide("둘째")).toHaveAttribute("tabindex", "-1");
    // 번호·이전·다음 버튼은 화면에 없다
    expect(screen.queryByRole("button", { name: /이전|다음/ })).toBeNull();
    expect(document.querySelector(".home-hero")).not.toHaveTextContent("1 / 3");
    tick();
    expect(center()).toContain("둘째");
    expect(slide("첫째")).toHaveAttribute("data-pos", "-1");
    tick();
    tick();
    expect(center()).toContain("첫째");
  });

  it("brings a peeking slide to the middle instead of opening it", () => {
    mount();
    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    act(() => void slide("셋째").dispatchEvent(click));
    expect(click.defaultPrevented).toBe(true);
    expect(center()).toContain("셋째");
  });

  it("keeps a pause button for keyboard users that stops the slides", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "자동 넘김 멈추기" }));
    expect(screen.getByRole("button", { name: "자동 넘김 다시 켜기" })).toHaveAttribute("aria-pressed", "true");
    tick();
    expect(center()).toContain("첫째");
  });

  it("rests while a mouse is over it or focus is inside, so nothing moves while reading", () => {
    const hero = mount();
    fireEvent.pointerEnter(hero, { pointerType: "mouse" });
    tick();
    expect(center()).toContain("첫째");
    fireEvent.pointerLeave(hero, { pointerType: "mouse" });
    fireEvent.focus(screen.getByRole("link", { name: /첫째/ }));
    tick();
    expect(center()).toContain("첫째");
    fireEvent.blur(screen.getByRole("link", { name: /첫째/ }), { relatedTarget: document.body });
    tick();
    expect(center()).toContain("둘째");
  });

  it("follows a sideways swipe and swallows the click at the end of it", () => {
    const hero = mount();
    fireEvent.pointerDown(hero, { clientX: 220 });
    fireEvent.pointerUp(hero, { clientX: 120 });
    expect(center()).toContain("둘째");
    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    screen.getByRole("link", { name: /둘째/ }).dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    // 짧게 누른 것은 밀기가 아니다
    fireEvent.pointerDown(hero, { clientX: 220 });
    fireEvent.pointerUp(hero, { clientX: 210 });
    expect(center()).toContain("둘째");
  });

  it("never moves by itself when the device asks for less motion", () => {
    reduceMotion();
    mount();
    tick();
    expect(center()).toContain("첫째");
    expect(screen.queryByRole("button", { name: "자동 넘김 멈추기" })).toBeNull();
  });

  it("draws a single slide without a pause button and nothing without slides", () => {
    mount(slides.slice(0, 1));
    expect(slide("첫째")).toHaveAttribute("data-pos", "0");
    expect(screen.queryByRole("button", { name: "자동 넘김 멈추기" })).toBeNull();
    cleanup();
    mount([]);
    expect(document.querySelector(".home-hero")).toBeNull();
  });
});
