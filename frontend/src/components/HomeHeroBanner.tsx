import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useMediaQuery } from "../lib/useMediaQuery";

export type HomeHeroSlide = {
  key: string;
  to: string;
  /* 장 바탕색: 혜택 형태 세 갈래(benefit-tile.css) + 지역(청록) */
  family: "stay" | "money" | "move" | "place";
  icon: ReactNode;
  eyebrow: ReactNode;
  title: string;
  sub: string;
};

export const HERO_INTERVAL_MS = 5500;
const SWIPE_PX = 40;

/* 홈 맨 위 배너(시안 v42). 5.5초마다 다음 장. 읽는 중에 넘어가지 않게 마우스가 올라가 있거나 안에 초점이 있으면 쉬고,
   멈춤 버튼과 기기의 '동작 줄이기'를 따른다(WCAG 2.2.2). 폰은 옆으로 밀어 넘긴다. 안 보이는 장은 inert. */
export function HomeHeroBanner({ slides }: { slides: HomeHeroSlide[] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const trackRef = useRef<HTMLDivElement>(null);
  const swipe = useRef<{ x: number; swiped: boolean } | null>(null);
  const count = slides.length;
  const current = count ? index % count : 0;
  const auto = count > 1 && !paused && !hovered && !focused && !reduceMotion;

  useEffect(() => {
    if (!auto) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) setIndex((value) => (value + 1) % count);
    }, HERO_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [auto, count]);

  // React 18 은 inert 속성 이름을 모른다 - 직접 단다(PolicyPages 목록 덮기와 같은 방식)
  useEffect(() => {
    trackRef.current?.querySelectorAll(".home-hero-slide").forEach((slide, i) => slide.toggleAttribute("inert", i !== current));
  }, [current, slides]);

  if (!count) return null;
  const go = (delta: number) => setIndex((value) => (((value + delta) % count) + count) % count);
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    swipe.current = { x: event.clientX, swiped: false };
  };
  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const start = swipe.current;
    if (!start || count < 2) return;
    const dx = event.clientX - start.x;
    if (Math.abs(dx) > SWIPE_PX) {
      start.swiped = true;
      go(dx < 0 ? 1 : -1);
    }
  };
  // 밀어 넘긴 끝의 클릭은 그 장을 누른 것이 아니다
  const onClickCapture = (event: MouseEvent<HTMLDivElement>) => {
    if (!swipe.current?.swiped) return;
    swipe.current = null;
    event.preventDefault();
    event.stopPropagation();
  };
  const onBlur = (event: FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
  };

  return (
    <section
      aria-label="이번 주 소식"
      aria-roledescription="넘어가는 배너"
      className="home-hero"
      onBlur={onBlur}
      onFocus={() => setFocused(true)}
      onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
      onPointerLeave={(event) => event.pointerType === "mouse" && setHovered(false)}
    >
      <div
        className="home-hero-track"
        onClickCapture={onClickCapture}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        ref={trackRef}
        style={{ transform: `translateX(-${current * 100}%)` }}
      >
        {slides.map((slide, i) => (
          <Link
            aria-hidden={i === current ? undefined : true}
            className={`home-hero-slide family-${slide.family}`}
            draggable={false}
            key={slide.key}
            to={slide.to}
          >
            {slide.icon}
            <span className="home-hero-copy">
              <span className="home-hero-eyebrow">{slide.eyebrow}</span>
              <b>{slide.title}</b>
              <span className="home-hero-sub">{slide.sub}</span>
            </span>
            <span className="home-hero-go" aria-hidden="true">
              ›
            </span>
          </Link>
        ))}
      </div>
      {count > 1 && (
        <div className="home-hero-controls">
          <button aria-label="이전 소식" onClick={() => go(-1)} type="button">
            <ChevronLeft aria-hidden="true" size={16} />
          </button>
          {/* 저절로 넘어가는 동안은 매번 읽어 주지 않는다 - 멈췄을 때만 알린다 */}
          <span aria-live={auto ? "off" : "polite"} className="home-hero-count">
            <b>{current + 1}</b> / {count}
          </span>
          <button aria-label="다음 소식" onClick={() => go(1)} type="button">
            <ChevronRight aria-hidden="true" size={16} />
          </button>
          {!reduceMotion && (
            <button
              aria-label={paused ? "자동 넘김 다시 켜기" : "자동 넘김 멈추기"}
              aria-pressed={paused}
              onClick={() => setPaused((value) => !value)}
              type="button"
            >
              {paused ? <Play aria-hidden="true" size={14} /> : <Pause aria-hidden="true" size={14} />}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
