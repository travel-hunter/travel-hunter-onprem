import { Pause, Play } from "lucide-react";
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

/* 장 i 가 가운데 장에서 몇 칸 옆인지(-1 왼쪽, 0 가운데, 1 오른쪽). 세 장이면 늘 셋 다 보인다 */
function slidePos(i: number, current: number, count: number) {
  const ahead = (((i - current) % count) + count) % count;
  return ahead > count / 2 ? ahead - count : ahead;
}

/* 홈 맨 위 배너(시안 v45). 가운데 장 하나를 좁게 두고 앞뒤 장은 작고 흐리게 뒤에 겹쳐 양옆으로 비친다 - 몇 장인지
   숫자 없이 보인다. 옆 장을 누르면 그 장이 가운데로, 폰은 밀어 넘긴다. 5.5초마다 다음 장, 마우스가 올라가 있거나
   안에 초점이 있으면 쉰다. 번호·이전·다음 버튼은 화면에서 뺐고(사용자 결정), 멈춤 버튼은 WCAG 2.2.2 때문에 남기되
   키보드 초점이 갈 때만 보인다(home.css). 기기의 '동작 줄이기'가 켜져 있으면 자동으로 넘기지 않는다. */
export function HomeHeroBanner({ slides }: { slides: HomeHeroSlide[] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
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

  if (!count) return null;
  const go = (delta: number) => setIndex((value) => (((value + delta) % count) + count) % count);
  const onPointerDown = (event: PointerEvent<HTMLElement>) => {
    swipe.current = { x: event.clientX, swiped: false };
  };
  const onPointerUp = (event: PointerEvent<HTMLElement>) => {
    const start = swipe.current;
    if (!start || count < 2) return;
    const dx = event.clientX - start.x;
    if (Math.abs(dx) > SWIPE_PX) {
      start.swiped = true;
      go(dx < 0 ? 1 : -1);
    }
  };
  // 밀어 넘긴 끝의 클릭은 그 장을 누른 것이 아니다
  const onClickCapture = (event: MouseEvent<HTMLElement>) => {
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
      onClickCapture={onClickCapture}
      onFocus={() => setFocused(true)}
      onPointerDown={onPointerDown}
      onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
      onPointerLeave={(event) => event.pointerType === "mouse" && setHovered(false)}
      onPointerUp={onPointerUp}
    >
      {slides.map((slide, i) => {
        const pos = slidePos(i, current, count);
        const center = pos === 0;
        return (
          <Link
            aria-hidden={center ? undefined : true}
            className={`home-hero-slide family-${slide.family}`}
            data-pos={Math.abs(pos) <= 1 ? pos : "x"}
            draggable={false}
            key={slide.key}
            // 옆에 비친 장을 누르면 그 장의 화면으로 가지 않고 가운데로 온다
            onClick={center ? undefined : (event) => { event.preventDefault(); setIndex(i); }}
            tabIndex={center ? undefined : -1}
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
        );
      })}
      {count > 1 && !reduceMotion && (
        <button
          aria-pressed={paused}
          className="home-hero-pause"
          onClick={() => setPaused((value) => !value)}
          type="button"
        >
          {paused ? <Play aria-hidden="true" size={12} /> : <Pause aria-hidden="true" size={12} />}
          {paused ? "자동 넘김 다시 켜기" : "자동 넘김 멈추기"}
        </button>
      )}
    </section>
  );
}
