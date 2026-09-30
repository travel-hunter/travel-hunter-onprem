/* 정책 지역 지도 - 시안(2026-09-29 정책 탭 시안 v24~v36)의 평면 지도를 그대로 옮겼다.
   땅은 도안 모양 그대로 평평하게, 고른 도만 살짝 띄운다(그늘 → 옆면 → 위가 밝은 윗면).
   제주는 오른쪽 아래 바다에 삽입 지도로 옮겨 그 빈 바다만큼 본토가 커진다.
   React 가 안을 만지지 않는다 - 호스트 하나에 명령형으로 그리고, 상태가 바뀌면 이름표·점만 다시 칠한다. */
import { KOREA_REGION_SHAPES } from "./koreaRegionShapes";
import { SIGUN_POINTS } from "./sigunPoints";

export type RegionCount = {
  /** 이 지역 고유 정책 수. 색·흐림 판정은 이 값만 본다 - 전국 정책 하나에 17곳이 다 켜지면 안 된다. */
  own: number;
  /** 목록에 나오는 수. 이름표 건수·aria 에 쓴다. */
  total: number;
};
export type RegionCounts = Record<string, RegionCount>;
/* 지도가 그리는 17개 시도. 건수 집계는 정책이 있는 지역이 아니라 이 목록을 돌아야 한다. */
export const REGION_NAMES: readonly string[] = KOREA_REGION_SHAPES.map((s) => s.name);

export type PolicyRegionMapHandle = {
  setSelected(name: string | null): void;
  /** 지금 viewBox 의 가로÷세로 */
  aspect(): number;
  /** 고른 지역 이름표 자리의 호스트 기준 픽셀 좌표. 핀 알약이 여기 선다. 레이아웃이 없는 환경이면 null. */
  anchorScreen(name: string): { x: number; y: number } | null;
  /** 칸 아래쪽이 목록 시트에 가린다 - 위쪽 visible(px)에 그림을 맞추고 가린 쪽은 바다로 잇는다.
   *  low 면 시트가 머리만 남긴 지도 중심 자리다(고른 지역을 가운데 아래로). */
  setView(view: { visible: number | null; low: boolean }): void;
  /** 고른 지역 안의 시·군 점(건수). 이름은 SIGUN_POINTS 의 "시도|시군" 뒤쪽이다. */
  setPlaces(places: readonly RegionMapPlace[], selected: string | null): void;
  resize(): void;
  destroy(): void;
};

export type RegionMapPlace = { name: string; count: number };

export type RegionMapOptions = {
  /** 고른 지역으로 다가가고 둘레 지역은 옅은 땅으로 눌러 둔다(정책 탭). 끄면 띄우기만 한다. */
  focus?: boolean;
  /** 이름표 옆에 건수를 쓴다 */
  showCounts?: boolean;
  /** 시·군 점을 누르면. 같은 점을 다시 누르면 null */
  onPlace?: (place: string | null) => void;
};

/* 땅 색: 그 지역 혜택 건수 칸(0 · 1~2 · 3~5 · 6~10 · 11~20 · 21~). ColorBrewer BuGn 6단계에서
   바다와 겹치는 가장 옅은 칸을 뺀 5단계에 0건 회색을 더했다(시안 PALETTES.teal). */
export const MAP_FILLS = ["#e2e5ea", "#ccece6", "#99d8c9", "#66c2a4", "#2ca25f", "#006d2c"] as const;
const bucket = (n: number) => (n === 0 ? 0 : n <= 2 ? 1 : n <= 5 ? 2 : n <= 10 ? 3 : n <= 20 ? 4 : 5);
const NS = "http://www.w3.org/2000/svg";
type Box = { x: number; y: number; w: number; h: number };
/* 도안 단위(200 x 269) 전체 틀. 제주를 옮긴 뒤의 땅이 여백 없이 들어온다 */
const FULL_VB: Readonly<Box> = { x: 56, y: -2, w: 145, h: 219 };
/* 제주는 오른쪽 아래 바다에 따로 그린다 - 섬까지의 빈 바다가 빠진 만큼 본토가 커진다 */
const INSET: Record<string, readonly [number, number]> = { 제주: [106, -31] };
const INSET_FRAME = { x: 165.5, y: 193.5, w: 35, h: 22 } as const;
/* 이름표 자리. 도형 기본 자리(lx, ly)가 이웃과 부딪히는 곳만 옮긴다 */
const LABEL_AT: Record<string, readonly [number, number]> = {
  서울: [96, 47], 경기: [110, 66], 인천: [73, 58], 경남: [146, 166], 부산: [184, 164], 제주: [183, 187],
};
/* 손가락으로 누르기 어려운 작은 지역 - 모양보다 넓게(지름 44px) 받는다 */
const SMALL = ["서울", "인천", "세종", "대전", "광주", "대구", "울산"];
/* 해안 물결선: 땅 모양을 굵은 선 → 바다색 조금 덜 굵은 선 순으로 겹쳐 해안에서 5·10·15px 떨어진
   가는 선 세 줄만 남긴다. [굵기(화면 px), 진하기] - 0 은 바다색 덮개. 굵기는 non-scaling-stroke 라
   다가가도 간격이 같다. */
const RIPPLES = [[31, 0.4], [29, 0], [21, 0.65], [19, 0], [11, 1], [9, 0]] as const;
/* 이름표 글자(화면 px). 다가가도 화면에서 같은 크기 */
const LABEL_PX = 11.5;
/* 지역으로 다가갈 때 세로로 최소 이만큼(도안 단위)은 보인다 - 서울·세종처럼 작은 곳도 둘레가 보이게 */
const FOCUS_MIN_H = 60;
/* 칸을 못 재는 환경(jsdom)은 폰 화면쯤(1단위 ≈ 2.9px)으로 친다 */
const FALLBACK_PPU = 2.9;

type Rings = readonly (readonly number[])[];
type ViewShape = { name: string; lx: number; ly: number; r: Rings };
type Rect = [number, number, number, number];

const VIEW: ViewShape[] = KOREA_REGION_SHAPES.map((s) => {
  const d = INSET[s.name];
  return d ? { ...s, lx: s.lx + d[0], ly: s.ly + d[1], r: s.r.map((ring) => ring.map((v, i) => v + d[i % 2])) } : s;
});
const BOX: Record<string, { x0: number; y0: number; x1: number; y1: number }> = Object.fromEntries(
  VIEW.map((s) => {
    const xs = s.r.flatMap((ring) => ring.filter((_, i) => i % 2 === 0));
    const ys = s.r.flatMap((ring) => ring.filter((_, i) => i % 2 === 1));
    return [s.name, { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) }];
  }),
);
const pathOf = (rings: Rings) =>
  rings.map((r) => {
    let d = "";
    for (let i = 0; i < r.length; i += 2) d += (i ? "L" : "M") + r[i] + "," + r[i + 1];
    return d + "Z";
  }).join("");
const labelAt = (s: ViewShape) => LABEL_AT[s.name] ?? [s.lx, s.ly];

/* 인스턴스마다 defs id 가 달라야 한 화면에 지도가 둘일 때 섞이지 않는다 */
let mapSeq = 0;

function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

export function createPolicyRegionMap(
  host: HTMLElement,
  counts: RegionCounts,
  onSelect: (name: string | null) => void,
  options: RegionMapOptions = {},
): PolicyRegionMapHandle {
  const key = ++mapSeq;
  const countOf = (name: string): RegionCount => counts[name] ?? { own: 0, total: 0 };

  /* --- 뼈대: 바다 물결선 → 제주 삽입 틀 → 땅 → 띄운 도 → 작은 지역 누르기 범위 → 이름표 → 시군 점 --- */
  const svg = el("svg", { class: "thmap-svg", preserveAspectRatio: "xMidYMid meet" });
  const defs = el("defs");
  const land = el("g", { id: `thmap-land-${key}`, class: "thmap-land" });
  VIEW.forEach((s) => land.appendChild(el("path", { d: pathOf(s.r) })));
  const blur = el("filter", { id: `thmap-blur-${key}`, x: "-10%", y: "-10%", width: "120%", height: "130%" });
  const blurStd = el("feGaussianBlur", { stdDeviation: 1 });
  blur.appendChild(blurStd);
  /* 띄운 윗면의 결: 위가 밝고 아래가 옅은 청록(policy-map.css 의 --thmap-focus-hi → --thmap-focus) */
  const face = el("linearGradient", { id: `thmap-face-${key}`, x1: 0, y1: 0, x2: 0, y2: 1 });
  (["--thmap-focus-hi", "--thmap-focus"] as const).forEach((token, index) => {
    const stop = el("stop", { offset: index });
    stop.style.setProperty("stop-color", `var(${token})`);
    face.appendChild(stop);
  });
  defs.append(land, blur, face);

  const sea = el("g", { class: "thmap-sea", "aria-hidden": "true" });
  RIPPLES.forEach(([w, o]) => {
    const use = el("use", { href: `#thmap-land-${key}`, class: o ? "thmap-rp" : "thmap-rp cut" });
    use.style.strokeWidth = `${w}px`;
    if (o) use.style.opacity = String(o);
    sea.appendChild(use);
  });
  const inset = el("g", { class: "thmap-insets", "aria-hidden": "true" });
  inset.appendChild(el("rect", { class: "thmap-inset", x: INSET_FRAME.x, y: INSET_FRAME.y, width: INSET_FRAME.w, height: INSET_FRAME.h, rx: 3 }));

  const rgs = el("g", { class: "thmap-rgs" });
  const PATH: Record<string, SVGPathElement> = {};
  VIEW.forEach((s) => {
    const cnt = countOf(s.name);
    const p = el("path", {
      class: "thmap-rg" + (cnt.own ? "" : " thmap-empty"),
      d: pathOf(s.r),
      fill: MAP_FILLS[bucket(cnt.own)],
      tabindex: 0,
      role: "button",
      "aria-pressed": "false",
      "aria-label": `${s.name} 정책 ${cnt.total}건`,
      "data-region": s.name,
    });
    rgs.appendChild(p);
    PATH[s.name] = p;
  });
  const ORDER = VIEW.map((s) => PATH[s.name]);
  const lift = el("g", { class: "thmap-lift", "aria-hidden": "true" });
  const hits = el("g", { class: "thmap-hits" });
  const labels = el("g", { class: "thmap-labels", "aria-hidden": "true" });
  const dotLayer = el("g", { class: "thmap-dots" });
  svg.append(defs, sea, inset, rgs, lift, hits, labels, dotLayer);

  let current: string | null = null;
  /* 칸 위쪽 몇 px 이 보이는가(0 = 다). low = 목록이 머리만 남긴 지도 중심 자리 */
  const view = { visible: 0, low: false };
  let viewSet = false;
  let placeItems: readonly RegionMapPlace[] = [];
  let placeSel: string | null = null;
  let dotHits: Array<{ name: string; sx: number; sy: number; lab: Rect | null }> = [];

  /* --- viewBox --- */
  const VB: Box = { ...FULL_VB };
  /* 지금 목표 viewBox. 이름표·점 크기는 움직이는 도중 값이 아니라 도착할 값으로 잰다 */
  let goal: Box = { ...FULL_VB };
  const applyVB = () => svg.setAttribute("viewBox", [VB.x, VB.y, VB.w, VB.h].map((n) => n.toFixed(2)).join(" "));
  const box = () => ({ bw: host.clientWidth, bh: host.clientHeight });
  const ppuOf = (vb: { w: number; h: number }) => {
    const { bw, bh } = box();
    return bw > 0 && bh > 0 ? Math.min(bw / vb.w, bh / vb.h) : FALLBACK_PPU;
  };
  const focusRegion = () => (options.focus && current ? current : null);

  /* 전국: 보이는 칸 가운데에 다 들어오게. 고르면 그 도로 다가간다 - 지역 카드가 왼쪽 위를 쓰므로 반반에서는
     카드 오른쪽 빈자리에, 지도 중심(목록 내림)에서는 가운데 아래에. 칸을 못 재면(jsdom) 전체 틀 그대로. */
  function target(): Box {
    const { bw, bh } = box();
    if (!(bw > 0 && bh > 0)) return { ...FULL_VB };
    const vis = view.visible > 0 ? Math.min(view.visible, bh) : bh;
    const b = focusRegion() ? BOX[current as string] : null;
    let x: number, y: number, w: number, h: number;
    if (!b) {
      const ppu = Math.min(bw / FULL_VB.w, vis / FULL_VB.h);
      w = bw / ppu; h = vis / ppu;
      x = FULL_VB.x + (FULL_VB.w - w) / 2; y = FULL_VB.y + (FULL_VB.h - h) / 2;
    } else {
      const low = view.low;
      /* 반반에서는 왼쪽 위 지역 카드가 지도를 가린다(policy-map.css .thmap-rcard: left 12px,
         폭 min(196px, 100% - 80px), 여기에 틈 8px). 폰 폭에서는 카드가 절반 넘게 덮으므로 카드 오른쪽
         빈자리에 도를 맞추고, 넓은 화면은 시안 자리(0.735) 그대로. 시군 이름은 drawFocus 가 카드와 겹치는
         자리를 피해 붙이므로 여백을 따로 두지 않는다. 카드 크기를 바꾸면 여기도 맞출 것. */
      const left = low ? 0 : Math.min(216, bw - 60) / bw;
      const room = low ? 0.8 : Math.min(0.49, 0.97 - left);
      const at = low ? 0.5 : Math.max(0.735, left + room / 2), down = low ? 0.62 : 0.5;
      const rw = b.x1 - b.x0, rh = b.y1 - b.y0;
      h = Math.max(rh * (low ? 2.2 : 1.35), FOCUS_MIN_H); w = (h * bw) / vis;
      if (rw / room > w) { w = rw / room; h = (w * vis) / bw; }
      x = (b.x0 + b.x1) / 2 - at * w; y = (b.y0 + b.y1) / 2 - down * h;
    }
    /* 그림은 보이는 윗부분(vis)에 맞추고 가려진 아래쪽까지 이어 그린다 - 목록이 내려가면 지도가 커지는
       게 아니라 드러나기만 한다 */
    return { x, y, w, h: (h * bh) / vis };
  }

  /* 다가가기는 0.32초 동안 부드럽게. 처음 그림과 움직임을 줄인 환경은 바로 */
  let raf = 0;
  let placed = false;
  function frame(animate: boolean) {
    const to = target(), from = { ...VB };
    goal = to;
    paint();
    if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
    const reduce = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!animate || !placed || reduce || typeof requestAnimationFrame !== "function") {
      placed = true;
      Object.assign(VB, to);
      applyVB();
      return;
    }
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / 320), e = 1 - Math.pow(1 - t, 3);
      VB.x = from.x + (to.x - from.x) * e; VB.y = from.y + (to.y - from.y) * e;
      VB.w = from.w + (to.w - from.w) * e; VB.h = from.h + (to.h - from.h) * e;
      applyVB();
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }

  /* --- 칠하기: 땅 색·흐림, 띄운 도, 이름표, 시군 점, 작은 지역 누르기 범위 --- */
  function paint() {
    const ppu = ppuOf(goal), fs = LABEL_PX / ppu;
    const focus = focusRegion();
    for (const s of VIEW) {
      const p = PATH[s.name], sel = current === s.name;
      p.classList.toggle("thmap-on", sel);
      /* 도를 고르면 둘레 도는 옅은 땅으로 눌러 둔다 */
      p.classList.toggle("thmap-dim", Boolean(focus) && !sel);
      p.setAttribute("aria-pressed", String(sel));
    }
    /* 고른 도를 맨 위로 - 흰 경계선이 이웃에 덮이지 않게. 풀면 원래 순서로 */
    ORDER.forEach((p) => rgs.appendChild(p));
    if (current) rgs.appendChild(PATH[current]);
    svg.classList.toggle("thmap-focus", Boolean(focus));

    /* 고른 도를 살짝 띄운다: 흐린 그늘 → 옆면 → 윗면(위가 밝은 결) */
    lift.replaceChildren();
    const shape = current ? VIEW.find((s) => s.name === current) : null;
    if (shape) {
      const d = pathOf(shape.r);
      blurStd.setAttribute("stdDeviation", (5 / ppu).toFixed(3));
      lift.append(
        el("path", { class: "shade", d, transform: `translate(0,${(7 / ppu).toFixed(3)})`, filter: `url(#thmap-blur-${key})` }),
        el("path", { class: "wall", d, transform: `translate(0,${(3.5 / ppu).toFixed(3)})` }),
        el("path", { class: "top", d, fill: `url(#thmap-face-${key})` }),
      );
    }

    /* 작은 지역은 모양보다 넓게(지름 44px) 누를 수 있게 */
    hits.replaceChildren(...SMALL.map((name) => {
      const s = VIEW.find((v) => v.name === name) as ViewShape;
      return el("circle", { class: "thmap-hit", "data-region": name, cx: s.lx, cy: s.ly, r: (22 / ppu).toFixed(3) });
    }));

    labels.replaceChildren();
    dotLayer.replaceChildren();
    dotHits = [];
    if (!focus) {
      /* 시트가 지도를 반쯤 덮은 자리에서는 0건 지역 이름을 뺀다 - 지도가 작아 이름끼리 부딪힌다 */
      const showZeros = view.low || view.visible === 0;
      for (const s of VIEW) {
        const n = countOf(s.name).total, sel = current === s.name, zero = !n && !sel;
        if (zero && !showZeros) continue;
        const [x, y] = labelAt(s);
        const shown = options.showCounts && n > 0 ? String(n) : "";
        const w = s.name.length * fs + shown.length * fs * 0.6 + fs * 1.5, h = fs * 1.6;
        const g = el("g", { class: "thmap-bd" + (zero ? " zero" : "") + (sel ? " sel" : ""), transform: `translate(${x},${y})` });
        g.appendChild(el("rect", { x: -w / 2, y: -h / 2, width: w, height: h, rx: h / 2, "stroke-width": (0.8 / ppu).toFixed(3) }));
        const t = el("text", { "text-anchor": "middle", y: (fs * 0.35).toFixed(3), "font-size": fs.toFixed(3) });
        t.textContent = s.name;
        if (shown) {
          const tn = el("tspan");
          tn.textContent = " " + shown;
          t.appendChild(tn);
        }
        g.appendChild(t);
        labels.appendChild(g);
      }
      return;
    }
    drawFocus(focus, ppu);
  }

  /* 고른 도: 둘레 도 이름은 옅게만(고른 도는 지역 카드가 말한다), 도 안 혜택 있는 시군은 건수 점으로.
     붙어 있는 시군은 조금씩 벌리고, 이름은 빈 쪽(오른쪽 → 왼쪽 → 위 → 아래)에 붙이되 자리가 없으면 뺀다.
     지도 위 카드·버튼과 겹치는 자리도 쓰지 않는다. 크기는 화면 px 기준. */
  function drawFocus(focus: string, ppu: number) {
    const { bw, bh } = box();
    const offX = bw > 0 ? (bw - goal.w * ppu) / 2 : 0, offY = bh > 0 ? (bh - goal.h * ppu) / 2 : 0;
    const toPx = (x: number, y: number) => [(x - goal.x) * ppu + offX, (y - goal.y) * ppu + offY] as const;
    const toU = (sx: number, sy: number) => [(sx - offX) / ppu + goal.x, (sy - offY) / ppu + goal.y] as const;
    const [ix, iy] = INSET[focus] ?? [0, 0];
    const R = 8, NF = 11;
    const dots = placeItems.flatMap((item) => {
      const at = SIGUN_POINTS[`${focus}|${item.name}`];
      if (!at) return [];
      const [sx, sy] = toPx(at[0] + ix, at[1] + iy);
      return [{ name: item.name, n: item.count, sx, sy, on: item.name === placeSel, label: null as null | { anchor: string; dx: number; dy: number }, rect: null as Rect | null }];
    }).sort((l, r) => Number(r.on) - Number(l.on) || r.n - l.n || l.name.localeCompare(r.name, "ko"));
    for (let it = 0; it < 24; it++) {
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const a = dots[i], c = dots[j], dx = c.sx - a.sx, dy = c.sy - a.sy, dd = Math.hypot(dx, dy), gap = 2 * R + 3 - dd;
          if (gap <= 0) continue;
          const [ux, uy] = dd ? [dx / dd, dy / dd] : [1, 0];
          a.sx -= (ux * gap) / 2; a.sy -= (uy * gap) / 2; c.sx += (ux * gap) / 2; c.sy += (uy * gap) / 2;
        }
      }
    }
    /* 이미 차지한 자리(px): 지도 위 카드·버튼(지도 칸의 다른 자식들), 점, 붙인 이름. 목록에 가린 아래쪽은 쓰지 않는다 */
    const taken: Rect[] = [];
    const stage = host.closest(".thmap-stage");
    if (stage && bw > 0) {
      const hb = host.getBoundingClientRect();
      for (const child of Array.from(stage.children)) {
        if (child.contains(host)) continue;
        const r = child.getBoundingClientRect();
        if (!r.width || !r.height) continue;
        taken.push([r.left - hb.left - 4, r.top - hb.top - 4, r.right - hb.left + 4, r.bottom - hb.top + 4]);
      }
    }
    const clash = (r: Rect) => taken.some((t) => r[0] < t[2] && r[2] > t[0] && r[1] < t[3] && r[3] > t[1]);
    const visH = view.visible > 0 ? Math.min(view.visible, bh || view.visible) : bh;
    const inView = (r: Rect) => !(bw > 0) || (r[0] >= 2 && r[2] <= bw - 2 && r[1] >= 2 && r[3] <= visH - 2);
    const shortName = (name: string) => (name.startsWith(focus) && name.length > focus.length ? name.slice(focus.length) : name);
    for (const d of dots) taken.push([d.sx - R, d.sy - R, d.sx + R, d.sy + R]);
    for (const d of dots) {
      const name = shortName(d.name), w = name.length * NF + 2, h = 15;
      const spots: Array<[string, number, number, number, number]> = [
        ["start", R + 4, 4, d.sx + R + 3, d.sy - h / 2],
        ["end", -(R + 4), 4, d.sx - R - 3 - w, d.sy - h / 2],
        ["middle", 0, -(R + 5), d.sx - w / 2, d.sy - R - 3 - h],
        ["middle", 0, R + 14, d.sx - w / 2, d.sy + R + 2],
      ];
      for (const [anchor, dx, dy, lx, ly] of spots) {
        const r: Rect = [lx, ly, lx + w, ly + h];
        if ((d.on || inView(r)) && !clash(r)) { taken.push(r); d.label = { anchor, dx, dy }; d.rect = r; break; }
      }
    }
    /* 둘레 도 이름: 점·시군 이름·카드와 겹치면 뺀다 */
    for (const s of VIEW) {
      if (s.name === focus) continue;
      const n = countOf(s.name).total, text = options.showCounts && n ? `${s.name} ${n}` : s.name;
      const [x, y] = labelAt(s), [sx, sy] = toPx(x, y), w = text.length * 9.5;
      const r: Rect = [sx - w / 2, sy - 7, sx + w / 2, sy + 7];
      if (clash(r)) continue;
      taken.push(r);
      const t = el("text", {
        class: "thmap-nb", x, y: (y + 3.6 / ppu).toFixed(3), "font-size": (10.5 / ppu).toFixed(3),
        "stroke-width": (3 / ppu).toFixed(3), "text-anchor": "middle",
      });
      t.textContent = text;
      labels.appendChild(t);
    }
    dotHits = dots.map((d) => ({ name: d.name, sx: d.sx, sy: d.sy, lab: d.rect }));
    for (const d of dots) {
      const [x, y] = toU(d.sx, d.sy), name = shortName(d.name);
      const g = el("g", {
        class: d.on ? "thmap-dot on" : "thmap-dot", role: "button", tabindex: 0,
        "aria-pressed": String(d.on), "aria-label": `${name} 혜택 ${d.n}건`, "data-place": d.name,
      });
      g.appendChild(el("circle", { class: "b", cx: x.toFixed(3), cy: y.toFixed(3), r: ((d.on ? R + 1.5 : R) / ppu).toFixed(3) }));
      const n = el("text", { class: "c", x: x.toFixed(3), y: (y + 3.5 / ppu).toFixed(3), "font-size": (10 / ppu).toFixed(3), "text-anchor": "middle" });
      n.textContent = String(d.n);
      g.appendChild(n);
      if (d.label) {
        const t = el("text", {
          class: "nm", x: (x + d.label.dx / ppu).toFixed(3), y: (y + d.label.dy / ppu).toFixed(3),
          "font-size": (NF / ppu).toFixed(3), "stroke-width": (3 / ppu).toFixed(3), "text-anchor": d.label.anchor,
        });
        t.textContent = name;
        g.appendChild(t);
      }
      g.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        options.onPlace?.(d.name === placeSel ? null : d.name);
      });
      dotLayer.appendChild(g);
    }
  }

  /* --- 누르기 --- */
  /* 점은 작아서 손가락이 빗나간다 - 보이지 않는 반경 27px 과 이름 둘레까지 받고, 겹치면 가장 가까운 시군.
     지역 모양보다 먼저 판정한다(잡는 단계). */
  svg.addEventListener("click", (event) => {
    if (!dotHits.length || !options.onPlace) return;
    const own = (event.target as Element).closest?.(".thmap-dot")?.getAttribute("data-place");
    let best: string | null = own ?? null;
    if (!best) {
      const hb = host.getBoundingClientRect();
      const x = event.clientX - hb.left, y = event.clientY - hb.top;
      let bd = 27;
      for (const s of dotHits) {
        let d = Math.hypot(x - s.sx, y - s.sy);
        if (s.lab && x >= s.lab[0] - 6 && x <= s.lab[2] + 6 && y >= s.lab[1] - 14 && y <= s.lab[3] + 14) d = Math.min(d, 1);
        if (d < bd) { bd = d; best = s.name; }
      }
    }
    if (!best) return;
    event.stopPropagation();
    options.onPlace(best === placeSel ? null : best);
  }, true);
  /* 지역 모양이나 작은 지역의 누르기 범위. 빈 바다는 지도 칸(PolicyRegionMap)이 받는다 */
  svg.addEventListener("click", (event) => {
    const name = (event.target as Element).closest?.("[data-region]")?.getAttribute("data-region");
    if (name) onSelect(current === name ? null : name);
  });
  svg.addEventListener("keydown", (event) => {
    const name = (event.target as Element).closest?.(".thmap-rg")?.getAttribute("data-region");
    if (!name || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    onSelect(current === name ? null : name);
  });
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && current) onSelect(null); };
  host.addEventListener("keydown", onKey);

  applyVB();
  host.appendChild(svg);
  frame(false);

  /* SVG 배치는 getScreenCTM 이 그대로 안다 - jsdom 엔 없으니 그땐 null */
  function anchorScreen(name: string) {
    const s = VIEW.find((v) => v.name === name);
    if (!s || typeof svg.getScreenCTM !== "function" || typeof svg.createSVGPoint !== "function") return null;
    const ctm = svg.getScreenCTM(); if (!ctm) return null;
    const pt = svg.createSVGPoint();
    [pt.x, pt.y] = labelAt(s);
    const sp = pt.matrixTransform(ctm);
    const hb = host.getBoundingClientRect();
    return { x: sp.x - hb.left, y: sp.y - hb.top };
  }

  return {
    anchorScreen,
    /* 칸 크기가 바뀌면 부른다 - 회전·주소창·창 크기 */
    resize: () => frame(false),
    aspect: () => (VB.h > 0 ? VB.w / VB.h : 1),
    setSelected(name) {
      if (name && !PATH[name]) name = null;
      if (name === current) return;
      current = name;
      if (!name) placeSel = null;
      frame(Boolean(options.focus));
    },
    setView(next) {
      const visible = next.visible && next.visible > 0 ? Math.round(next.visible) : 0;
      if (visible === view.visible && next.low === view.low) return;
      /* 처음 자리 잡기는 움직임 없이 - 화면을 열자마자 지도가 한 번 떠오르면 어지럽다 */
      const first = !viewSet;
      viewSet = true;
      view.visible = visible;
      view.low = next.low;
      frame(!first);
    },
    setPlaces(places, selected) {
      placeItems = places;
      placeSel = selected;
      paint();
    },
    destroy() {
      if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
      host.removeEventListener("keydown", onKey);
      svg.remove();
    },
  };
}
