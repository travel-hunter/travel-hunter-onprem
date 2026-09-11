/* 정책 지역 지도 - 양식화한 2.5D 한국 지도.
   시안(policy-map.html)의 지도 엔진을 그대로 옮겼다. React 가 안을 만지지 않는다:
   raise() 가 노드를 옮긴 뒤 getBoundingClientRect() 로 스타일을 확정해야 솟기 전환이
   살아나는데, 재조정기가 끼면 그 순서가 깨진다. 그래서 호스트 하나에 명령형으로 그린다. */
import { KOREA_REGION_SHAPES, type RegionShapeSource } from "./koreaRegionShapes";

export type RegionCount = {
  /** 이 지역 고유 정책 수. 흐림 판정은 이 값만 본다 - 전국 정책 하나에 17곳이 다 켜지면 안 된다. */
  own: number;
  /** 목록에 나오는 수 (전국 정책 포함). 이름표 읽기·aria 에 쓴다. */
  total: number;
};
export type RegionCounts = Record<string, RegionCount>;
/* 지도가 그리는 17개 시도. 건수 집계는 정책이 있는 지역이 아니라 이 목록을 돌아야 한다 -
   고유 정책 0건 지역도 전국 정책은 받는다. */
export const REGION_NAMES: readonly string[] = KOREA_REGION_SHAPES.map((s) => s.name);

export type PolicyRegionMapHandle = {
  setSelected(name: string | null): void;
  /** 그려 놓은 그림의 가로÷세로. 지도 칸을 이 비율로 맞추면 letterbox 여백이 0 이 된다. */
  aspect(): number;
  /** 솟은 지역 머리 위의 호스트 기준 픽셀 좌표. 핀 알약이 여기 선다. 레이아웃이 없는 환경이면 null. */
  anchorScreen(name: string): { x: number; y: number } | null;
  resize(): void;
  destroy(): void;
};

/* 시안에서 확정한 값. 슬라이더는 제품에 없으므로 상수로 굳힌다. */
const WALLN = 12; /* 옆면 겹 수 */
const K = 0.6; /* 기울기 - 세로 압축 */
const DEPTH = 4; /* 두께 */
const RISE = 6; /* 솟는 높이 */
const GROW = 32; /* 작은 지역을 키울 목표 폭(px) */
const GAPP = 0; /* 지역 틈 */
const PXU = 398 / 200;
const ROUND = 1.8551; /* 모양 */
const XW = 78; /* 가로 폭 % */
const NS = "http://www.w3.org/2000/svg";
/* 바다. 해안선을 따라 겹을 덧그린다 - 선 굵기의 절반은 땅 밑에 깔려 안 보이고 바깥쪽 절반만
   남아 파문이 된다. 지역 사이 경계에도 그어지지만 나중에 그리는 땅이 덮으므로 바깥 해안선에만
   보인다. 도형을 그대로 다시 쓰므로 새 좌표가 없고 모양이 바뀌어도 따라온다.
   맨 안쪽 흰 겹은 지도 삽화에서 흔한 장치다 - 육지가 바다에서 떠오르고 해안선이 또렷해진다.
   지역끼리 가르는 내부 경계는 여기 안 걸린다(각 지역 제 색의 어두운 쪽 유지).
   [선 굵기, 불투명도, 색] 순, 굵은 것부터. 여기 값은 가장 진하게 썼을 때이고 실제 진하기는
   CSS 의 --thmap-sea 가 곱해 정한다 - opacity 는 1 을 못 넘어서 여기를 최대치로 둬야
   변수로 올렸다 내렸다 할 수 있다. */
const SEA: readonly (readonly [number, number, string?])[] = [
  [13, 0.5, "#9dc6e6"], [7.9, 0.62, "#bcdcf0"], [2, 0.95, "#ffffff"],
];
/* 바닷물 색. 땅이 저채도 파스텔이라 이보다 옅으면 물로 안 읽힌다. */
const SEA_COLOR = "#5184c8";
/* 얕은 물 띠의 색. 해안에서 바깥으로 갈수록 바닷물색에 묻힌다 - 실제 지도가 그렇듯
   얕은 곳이 밝아야 육지가 여울을 두른 것으로 읽힌다. 전에는 파문이 바닷물과 같은 색이라
   해안이 오히려 어두웠고, 그래서 바다가 평평해 보였다. */
const SHALLOW_MID = "#9dc6e6";
/* 잔물결. 바다에 흩어 놓는 작은 ^ 자국이다. 자리는 고정 씨앗으로 뽑아 늘 같다 -
   그릴 때마다 새로 뽑으면 창 크기만 바뀌어도 자리가 튀어 깜박이는 것처럼 보인다.
   움직임은 CSS 가 맡는다: 좌우로 천천히 오가되 주기와 시작 시점을 자국마다 달리해
   한 몸처럼 움직이지 않게 한다(policy-map.css 의 thmap-wave). */
/* 구역별 할당량의 합이 실제 개수다 - 아래 zones 의 want 를 고친다. */
const RIPPLE_COUNT = 45;
/* 물마루끼리 최소로 벌어져야 하는 거리(viewBox 단위). 이게 없으면 무작위로 뽑은 자리들이
   뭉쳐서 몇 군데만 빽빽해진다. 자리가 모자라면 아래에서 조금씩 양보한다. */
const RIPPLE_GAP = 10;
const RIPPLE_SEED = 20260910;
const RIPPLE_W = 4.6;
/* 땅 둘레에 반드시 남기는 바다. 땅 폭 대비 비율이라 지도 크기가 바뀌어도 같은 비율로 따라온다.
   이건 최소값이다 - 칸이 더 넓거나 길면 남는 쪽은 바다로 더 채워진다(fitVB 참고). */
const SEA_MIN_PAD = 0.05; /* 물마루 하나의 가로 폭 */
/* 한반도 둘레의 자잘한 섬. 누를 수 없고 정책도 없다 - 바다가 비어 보이지 않게 하는 표시다.
   자리는 남한 그림 크기에 대한 비율이라 모양 상수가 바뀌어도 같은 데 붙는다.
   [가로 비율, 세로 비율, 크기] - 독도(0.94, 0.24)와 같은 방식. */
const ISLETS: readonly (readonly [number, number, number])[] = [
  [0.895, 0.155, 1.5],  /* 울릉도 */
  [0.075, 0.245, 1.1],  /* 덕적·영흥 */
  [0.045, 0.34, 0.8],   /* 서해 중부 */
  [-0.01, 0.70, 1.3],   /* 신안·흑산 */
  [0.055, 0.80, 0.9],   /* 진도 남 */
  [0.30, 0.885, 1.0],   /* 거문도 */
  [0.20, 0.83, 0.75],   /* 추자 */
  [0.545, 0.86, 1.2],   /* 거제 남 */
  [0.70, 0.80, 0.85],   /* 대마 방향 */
];
/* 물마루 한 획. 한쪽은 곧게 서고 마루에서 휘어 반대쪽으로 내린다 - 좌우 대칭인 ^ 보다
   물결에 가깝다. flip 이면 좌우를 뒤집는다: 왼쪽으로 흐르는 물마루는 반대로 누워야 자연스럽다.
   폭 w, 높이 h 기준 상대 좌표. */
function crest(x: number, y: number, w: number, h: number, flip: boolean) {
  const f = (n: number) => n.toFixed(2);
  const s = flip ? -1 : 1;
  const x0 = flip ? x + w : x;
  return `M${f(x0)},${f(y)} l${f(s * w * 0.42)},${f(-h)} c${f(s * w * 0.18)},${f(-h * 0.15)} ${f(s * w * 0.34)},${f(h * 0.45)} ${f(s * w * 0.58)},${f(h)}`;
}
/* 물판은 SVG 가 아니라 지도 칸(.thmap-host)의 배경으로 깐다 - policy-map.css 참고.
   SVG 안에 두면 viewBox 만 덮는다. 화면이 짧아 좌우에 여백 띠가 생기면 거기가 비고,
   지도에 스프링 움직임을 넣으면 움직인 만큼 가장자리가 드러난다.
   칸 배경이면 지도가 흔들려도 물은 제자리에서 좌우를 꽉 채운 채 남는다. */

/* S 26~35, L 72~92 로 묶은 팔레트. 계열 = 권역. 제주는 섬이라 제 계열. */
const HUE: Record<string, string> = {
  서울: "#c9d6e3", 인천: "#c9dae3", 경기: "#dee6ed", 강원: "#b8d2b2",
  충북: "#dadfc4", 충남: "#eae6d7", 세종: "#e5decd", 대전: "#daceb9",
  전북: "#d1e5df", 전남: "#b7d7cf", 광주: "#e5f0ec", 경북: "#e0cfc2",
  대구: "#d7bfb2", 울산: "#e2d1c6", 경남: "#ebe0d6", 부산: "#cdafa2", 제주: "#c7c0da",
};
/* 이름표 글씨는 제 계열의 진한 색. 제 지역색 위에서 대비 최저 4.64 (AA). */
const FAM: Record<string, string> = {
  서울: "#3a4a5c", 인천: "#3a4a5c", 경기: "#3a4a5c", 강원: "#35503f",
  충북: "#5a4d34", 충남: "#5a4d34", 세종: "#5a4d34", 대전: "#5a4d34",
  전북: "#2f4f47", 전남: "#2f4f47", 광주: "#2f4f47", 제주: "#3d3654",
  경북: "#5c3f30", 대구: "#5c3f30", 울산: "#5c3f30", 경남: "#5c3f30", 부산: "#5c3f30",
};
/* 이름표 자리. 도형 안에서 가장 넓게 빈 지점을 오프라인으로 풀어 박아 뒀다.
   눌리기 전 좌표라 쓸 때 x 는 XW/100, y 는 K 를 곱한다. */
const LBLXY: Record<string, [number, number]> = {
  서울: [96.1, 52.6], 인천: [73.8, 54.5], 경기: [113.5, 56.3], 강원: [150.7, 47.1],
  충북: [125.3, 84.0], 충남: [88.6, 99.7], 세종: [104.1, 104.2], 대전: [115.7, 115.8],
  전북: [104.0, 142.4], 경북: [169.6, 106.1], 대구: [160.6, 136.9], 울산: [185.3, 146.0],
  경남: [144.6, 162.3], 부산: [180.9, 173.4], 전남: [110.1, 175.6], 광주: [90.2, 171.8],
  제주: [78.3, 235.3],
};

type Pt = [number, number];
type Feat = { name: string; d: string };
type Box = { cx: number; cy: number; x0: number; x1: number; y0: number; y1: number; min: number };
type Node = {
  /* 이 지역에 걸린 확대 배율. 잔물결 자리를 도형으로 판정할 때 좌표를 거꾸로 풀려면 필요하다. */
  k: number;
  g: SVGGElement;
  lift: SVGGElement;
  wg: SVGGElement;
  floor: SVGPathElement;
  lbl: SVGGElement;
  lblBase: string;
  risers: SVGPathElement[];
  rest: number;
  flat: string;
  sc: string;
};

/* --- 도형 다듬기 ---------------------------------------------------- */
function rArea(p: Pt[]) {
  let s = 0;
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length];
    s += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(s) / 2;
}
function rCen(p: Pt[]): Pt {
  let x = 0, y = 0;
  for (const q of p) { x += q[0]; y += q[1]; }
  return [x / p.length, y / p.length];
}
function rPerim(p: Pt[]) {
  let s = 0;
  for (let i = 0; i < p.length; i++) {
    const a = p[i], b = p[(i + 1) % p.length];
    s += Math.hypot(b[0] - a[0], b[1] - a[1]);
  }
  return s;
}
function rSample(p: Pt[], n: number): Pt[] {
  const step = rPerim(p) / n, out: Pt[] = [p[0]];
  let acc = 0, i = 0, cur = p[0], guard = 0;
  while (out.length < n && guard < p.length * 8) {
    guard++;
    const nx = p[(i + 1) % p.length], dx = nx[0] - cur[0], dy = nx[1] - cur[1];
    const seg = Math.hypot(dx, dy);
    if (acc + seg >= step && seg > 0) {
      const t = (step - acc) / seg;
      cur = [cur[0] + dx * t, cur[1] + dy * t];
      out.push(cur);
      acc = 0;
    } else {
      acc += seg; cur = nx; i++;
    }
  }
  return out;
}
function lapOnce(p: Pt[], w: number): Pt[] {
  const n = p.length, o: Pt[] = new Array(n);
  for (let i = 0; i < n; i++) {
    const a = p[(i - 1 + n) % n], b = p[i], c = p[(i + 1) % n];
    o[i] = [b[0] + w * ((a[0] + c[0]) / 2 - b[0]), b[1] + w * ((a[1] + c[1]) / 2 - b[1])];
  }
  return o;
}
/* 장력 0 이면 제어점이 선분 위에 놓여 정확한 직선 = 원본 해안선 */
function curve(p: Pt[], tau: number): string | null {
  if (p.length < 3) return null;
  const n = p.length, o = ["M" + p[0][0].toFixed(1) + "," + p[0][1].toFixed(1)];
  for (let i = 0; i < n; i++) {
    const a = p[(i - 1 + n) % n], b = p[i], c = p[(i + 1) % n], d = p[(i + 2) % n];
    o.push(
      "C" + (b[0] + (c[0] - a[0]) * tau / 3).toFixed(1) + "," + (b[1] + (c[1] - a[1]) * tau / 3).toFixed(1) + " " +
      (c[0] - (d[0] - b[0]) * tau / 3).toFixed(1) + "," + (c[1] - (d[1] - b[1]) * tau / 3).toFixed(1) + " " +
      c[0].toFixed(1) + "," + c[1].toFixed(1),
    );
  }
  return o.join(" ") + "Z";
}
function shapeAt(src: RegionShapeSource[], round: number, xw: number): Feat[] {
  const t = (round - 1) / 99, kx = xw / 100, tau = Math.min(1, t * 6), amt = t * 18;
  return src.map((f) => {
    const ds: string[] = [];
    let aBig = 0, cBig: Pt = [0, 0];
    f.r.forEach((flat, ri) => {
      let p: Pt[] = [];
      for (let i = 0; i < flat.length; i += 2) p.push([flat[i], flat[i + 1]]);
      let a0 = rArea(p), c0 = rCen(p);
      if (ri === 0) { aBig = a0; cBig = c0; }
      else {
        if (a0 < 25) return; /* 점처럼 보이는 섬은 아예 안 그린다 */
        if (a0 < aBig * 0.10 * t) return; /* 자잘한 섬은 둥글어질수록 사라진다 */
        const pull = t * 0.55, grow = 1 + 0.45 * t; /* 나머지는 본체 쪽으로 당기고 키운다 */
        const nc: Pt = [c0[0] + (cBig[0] - c0[0]) * pull, c0[1] + (cBig[1] - c0[1]) * pull];
        p = p.map((q): Pt => [nc[0] + (q[0] - c0[0]) * grow, nc[1] + (q[1] - c0[1]) * grow]);
        c0 = nc; a0 = rArea(p);
      }
      const lo = Math.max(8, Math.min(48, Math.round(Math.sqrt(a0) * 0.96)));
      const n = Math.max(lo, Math.round(Math.exp(Math.log(p.length) * (1 - t) + Math.log(lo) * t)));
      if (n < p.length) p = rSample(p, n);
      const full = Math.floor(amt), frac = amt - full;
      for (let i = 0; i < full; i++) p = lapOnce(p, 0.62);
      if (frac > 0) p = lapOnce(p, 0.62 * frac);
      const a1 = rArea(p); /* 부드럽게 하면 오므라든다 - 넓이를 되돌린다 */
      if (a1 > 0) {
        const s = Math.sqrt(a0 / a1), cc = rCen(p);
        p = p.map((q): Pt => [cc[0] + (q[0] - cc[0]) * s, cc[1] + (q[1] - cc[1]) * s]);
      }
      const c2 = rCen(p);
      p = p.map((q): Pt => [(q[0] + c0[0] - c2[0]) * kx, q[1] + c0[1] - c2[1]]);
      const d = curve(p, tau);
      if (d) ds.push(d);
    });
    return { name: f.name, d: ds.join(" ") };
  });
}

/* --- 색 ------------------------------------------------------------- */
/* 채도를 지키며 밝기를 바꾼다. 그냥 곱하면 회색으로 죽는다. */
function shade(hex: string, k: number) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = (mx + mn) / 2;
  let c = [r, g, b].map((v) => d + (v - d) * 1.15);
  c = k <= 1 ? c.map((v) => v * k) : c.map((v) => v + (255 - v) * (k - 1));
  return "#" + c.map((v) => {
    const t = Math.round(Math.max(0, Math.min(255, v))).toString(16);
    return t.length < 2 ? "0" + t : t;
  }).join("");
}

/* --- 치수 ----------------------------------------------------------- */
function bbox(d: string) {
  const xs: number[] = [], ys: number[] = [];
  d.split("M").forEach((seg) => {
    if (!seg.trim()) return;
    const head = seg.trim().split("C")[0].replace("Z", "").trim();
    if (head) { const h = head.split(","); xs.push(Number(h[0])); ys.push(Number(h[1])); }
    const re = /C([^CZ]+)/g;
    let mm: RegExpExecArray | null;
    while ((mm = re.exec(seg))) {
      const n = mm[1].replace(/,/g, " ").split(/\s+/).filter(Boolean);
      if (n.length >= 6) { xs.push(Number(n[4])); ys.push(Number(n[5])); }
    }
  });
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}

export function createPolicyRegionMap(
  host: HTMLElement,
  counts: RegionCounts,
  onSelect: (name: string | null) => void,
): PolicyRegionMapHandle {
  const FEATS = shapeAt(KOREA_REGION_SHAPES, ROUND, XW);
  const BB: Record<string, Box> = {};
  const W = { x0: 1e9, x1: -1e9, y0: 1e9, y1: -1e9 };
  FEATS.forEach((f) => {
    const b = bbox(f.d);
    BB[f.name] = {
      cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, x0: b.x0, x1: b.x1, y0: b.y0, y1: b.y1,
      min: Math.min(b.x1 - b.x0, b.y1 - b.y0),
    };
    W.x0 = Math.min(W.x0, b.x0); W.x1 = Math.max(W.x1, b.x1);
    W.y0 = Math.min(W.y0, b.y0); W.y1 = Math.max(W.y1, b.y1);
  });
  const anchorOf = (name: string) => {
    const a = LBLXY[name], b = BB[name];
    if (!a) return { x: b ? b.cx : 0, y: b ? b.cy * K : 0 };
    return { x: a[0] * (XW / 100), y: a[1] * K };
  };
  const countOf = (name: string): RegionCount => counts[name] ?? { own: 0, total: 0 };

  /* --- SVG 뼈대 --- */
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "thmap-svg");

  svg.setAttribute("aria-hidden", "false");
  const VB = { x: 0, y: 0, w: 0, h: 0 };
  const applyVB = () => {
    svg.setAttribute("viewBox", VB.x.toFixed(1) + " " + VB.y.toFixed(1) + " " + VB.w.toFixed(1) + " " + VB.h.toFixed(1));
    bg.setAttribute("x", String(VB.x)); bg.setAttribute("y", String(VB.y));
    bg.setAttribute("width", String(VB.w)); bg.setAttribute("height", String(VB.h));
  };
  /* 그리기 전 추정치. getBBox 가 없는 환경(jsdom)에선 이 값이 끝까지 쓰인다. */
  VB.x = W.x0 - (W.x1 - W.x0) * SEA_MIN_PAD; VB.y = W.y0 * K - (RISE + 2);
  VB.w = (W.x1 - W.x0) * (1 + SEA_MIN_PAD * 2); VB.h = (W.y1 - W.y0) * K + (RISE + 2) + (DEPTH + 3);

  const bg = document.createElementNS(NS, "rect");
  /* 빈 곳 클릭으로 선택을 푸는 판. 색은 칸 배경이 맡으므로 여기는 투명하다. */
  bg.setAttribute("fill", "transparent");
  bg.addEventListener("click", () => { if (current) onSelect(null); });
  svg.appendChild(bg);
  const zoomer = document.createElementNS(NS, "g");
  svg.appendChild(zoomer);

  const NODE: Record<string, Node> = {};
  /* 파문은 겹마다 따로 모은다 - 한 겹에 섞어 그리면 옆 지역의 굵은 겹이 이 지역의 얇은 겹을
     덮어 이음매가 보인다. 굵은 겹 전부 → 중간 → 얇은 겹 순으로 깔린다. */
  const seaLayer = document.createElementNS(NS, "g");
  seaLayer.setAttribute("class", "thmap-sea");
  seaLayer.setAttribute("pointer-events", "none");
  /* 잔물결은 바다 겹 안에 둔다 - --thmap-sea 로 물과 같이 진해지고 옅어진다. */
  const rippleLayer = document.createElementNS(NS, "g");
  rippleLayer.setAttribute("class", "thmap-ripple");
  rippleLayer.setAttribute("fill", "none");
  rippleLayer.setAttribute("stroke", "#ffffff");
  rippleLayer.setAttribute("stroke-width", "0.85");
  rippleLayer.setAttribute("stroke-linecap", "round");
  rippleLayer.setAttribute("stroke-linejoin", "round");
  /* 진하기는 keyframes 가 흐름에 따라 정한다 - 여기서 또 곱하면 다 가라앉는다 */
  rippleLayer.setAttribute("opacity", "1");
  const seaRings = SEA.map(([width, opacity, color]) => {
    const ring = document.createElementNS(NS, "g");
    ring.setAttribute("stroke", color ?? SEA_COLOR);
    ring.setAttribute("stroke-width", String(width));
    ring.setAttribute("stroke-linejoin", "round");
    ring.setAttribute("fill", "none");
    ring.setAttribute("opacity", String(opacity));
    seaLayer.appendChild(ring);
    return ring;
  });
  /* 흰 테두리 한 벌 더. 위 겹들은 땅의 평면(바닥면) 자리에 그려지는데, 눈에 보이는 땅의
     아랫변은 옆면 두께(DEPTH)만큼 더 아래다. 그래서 남쪽 해안에서만 선이 위로 밀려 보였다.
     두께 아래에도 같은 선을 깔면 아랫변이 맞고, 위쪽 해안에서는 이 벌이 땅 밑으로 숨는다.
     파란 파문 겹은 폭이 넓어 4단위 차이가 안 보이므로 한 벌로 둔다. */
  const rimDeep = document.createElementNS(NS, "g");
  const rim = SEA[SEA.length - 1];
  rimDeep.setAttribute("stroke", rim[2] ?? SEA_COLOR);
  rimDeep.setAttribute("stroke-width", String(rim[0]));
  rimDeep.setAttribute("stroke-linejoin", "round");
  rimDeep.setAttribute("fill", "none");
  rimDeep.setAttribute("opacity", String(rim[1]));
  seaLayer.appendChild(rimDeep);
  const wallLayer = document.createElementNS(NS, "g");
  wallLayer.setAttribute("class", "thmap-walls");
  const floorLayer = document.createElementNS(NS, "g");
  floorLayer.setAttribute("class", "thmap-floors");
  const labelLayer = document.createElementNS(NS, "g");
  labelLayer.setAttribute("class", "thmap-labels");
  let WGORDER: Element[] = [], FLORDER: Element[] = [], RGORDER: Element[] = [];
  let dokdoG: SVGGElement | null = null;
  let current: string | null = null;

  /* --- 그리기 --- */
  function build() {
    /* 바다가 맨 밑이다 - 땅과 옆면이 그 위에 얹힌다 */
    seaLayer.appendChild(rippleLayer);
    zoomer.appendChild(seaLayer);
    /* 옆면은 전부 여기 모아 지역 윗면보다 먼저 깐다 - 어떤 옆면도 남의 지면 위로 못 올라온다. */
    zoomer.appendChild(wallLayer);
    /* 솟아도 자리에 남는 바닥면. 없으면 올라간 자리에 구멍이 뚫려 뒷배경이 비친다. */
    zoomer.appendChild(floorLayer);
    const goal = GROW / PXU, fac: Record<string, number> = {};
    /* 틈은 절대값으로 정하고 지역 크기로 나눠 배율을 만든다 - 어느 지역이든 틈이 같아 보인다.
       슬라이더 0 = 틈 없음이라 각 지역을 0.68 씩 부풀려 서로 물린다. */
    const gapUnit = (GAPP - 4.5) * 0.15;
    FEATS.forEach((f) => {
      const b = BB[f.name];
      const base = b.min < goal ? Math.min(3.2, goal / b.min) : 1; /* 작은 지역은 먼저 키운다 */
      const k = base - 2 * gapUnit / b.min; /* 그다음 같은 폭만큼 깎는다 */
      fac[f.name] = Math.max(base * 0.55, k);
    });
    const minMin = FEATS.reduce((a, f) => Math.min(a, BB[f.name].min), Infinity);
    const floatCut = Math.max(goal, minMin * 1.6);
    const floats = (name: string) => BB[name].min < floatCut;
    /* 그리는 순서가 곧 위아래. 북→남으로 그리되, 키운 작은 지역은 맨 뒤로 미뤄 항상 위에 온다. */
    FEATS.slice().sort((a, b) => {
      const ga = floats(a.name) ? 1 : 0, gb = floats(b.name) ? 1 : 0;
      if (ga !== gb) return ga - gb;
      return BB[a.name].cy - BB[b.name].cy;
    }).forEach((f) => {
      const cnt = countOf(f.name), n = cnt.own, k = fac[f.name], b = BB[f.name];
      const base = HUE[f.name] || "#e6e8ee";
      const g = document.createElementNS(NS, "g");
      g.setAttribute("class", "thmap-rg" + (n ? "" : " thmap-empty"));
      g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
      g.setAttribute("aria-label", f.name + " 정책 " + cnt.total + "건");
      g.setAttribute("data-region", f.name);
      const flat = "scale(1," + K + ")";
      const sc = Math.abs(k - 1) > 0.001
        ? "translate(" + b.cx + "," + b.cy + ") scale(" + k.toFixed(3) + ") translate(" + (-b.cx) + "," + (-b.cy) + ")"
        : "";
      /* 키운 작은 지역은 평소에도 두 칸 띄운다 - 광역시가 도 위에 얹힌 타일로 읽힌다. */
      const rest = floats(f.name) ? 2 * DEPTH / WALLN : 0;
      const lift = document.createElementNS(NS, "g");
      lift.setAttribute("class", "thmap-lift");
      if (rest) lift.setAttribute("transform", "translate(0," + (-rest).toFixed(3) + ")");
      const wg = document.createElementNS(NS, "g");
      for (let i = WALLN; i >= 1; i--) {
        const w = document.createElementNS(NS, "path");
        w.setAttribute("class", "thmap-wall");
        w.setAttribute("d", f.d);
        /* 솟기 옆면이 평면에서 0.86 으로 끝난다. 바닥 옆면은 거기서 이어받아 더 어두워진다. */
        w.setAttribute("fill", shade(base, 0.74 + 0.12 * (WALLN - i) / (WALLN - 1)));
        /* 바닥에 가까운 두 겹은 흐리게 - 끝을 진하게 끊으면 판때기로 보인다. */
        if (i === WALLN) w.setAttribute("opacity", "0.32");
        else if (i === WALLN - 1) w.setAttribute("opacity", "0.62");
        w.setAttribute("transform", "translate(0," + (DEPTH * i / WALLN).toFixed(2) + ") " + flat + " " + sc);
        wg.appendChild(w);
      }
      /* 이 지역 몫의 파문. 땅과 같은 자리에 놓아야 해안선이 맞는다. */
      seaRings.forEach((ring) => {
        const wave = document.createElementNS(NS, "path");
        wave.setAttribute("d", f.d);
        wave.setAttribute("transform", flat + " " + sc);
        ring.appendChild(wave);
      });
      /* 옆면 맨 아래와 같은 자리 - 옆면 겹이 translate(0, DEPTH) 까지 내려간다 */
      const deep = document.createElementNS(NS, "path");
      deep.setAttribute("d", f.d);
      deep.setAttribute("transform", "translate(0," + (DEPTH - rest).toFixed(2) + ") " + flat + " " + sc);
      rimDeep.appendChild(deep);
      const fl = document.createElementNS(NS, "path");
      fl.setAttribute("class", "thmap-floor"); fl.setAttribute("d", f.d);
      fl.setAttribute("fill", n ? shade(base, 0.86) : shade(base, 1.18));
      fl.setAttribute("transform", flat + " " + sc);
      floorLayer.appendChild(fl);
      /* 솟을 때만 쓰는 옆면. 평소엔 평면에 접혀 안 보인다. 바닥 옆면은 여기 관여하지 않아 두께가 안 흔들린다. */
      const rz = document.createElementNS(NS, "g");
      const risers: SVGPathElement[] = [];
      for (let j = WALLN; j >= 1; j--) {
        const rw = document.createElementNS(NS, "path");
        rw.setAttribute("class", "thmap-wall");
        rw.setAttribute("d", f.d);
        rw.setAttribute("fill", shade(base, 0.86 + 0.14 * (WALLN - j) / (WALLN - 1)));
        /* 투명도를 주지 않는다 - 반투명이면 바닥면 색이 비쳐 명암이 끊긴다. */
        rw.setAttribute("data-i", String(j));
        rw.setAttribute("transform", "translate(0," + (rest * j / WALLN).toFixed(3) + ") " + flat + " " + sc);
        rz.appendChild(rw); risers.push(rw);
      }
      const top = document.createElementNS(NS, "path");
      top.setAttribute("class", "thmap-top"); top.setAttribute("d", f.d);
      top.setAttribute("fill", n ? base : shade(base, 1.42));
      /* 테두리는 제 색의 어두운 쪽. 흰 선은 종이 도안처럼 만든다. */
      top.setAttribute("stroke", shade(base, n ? 0.86 : 1.0));
      top.setAttribute("stroke-width", (0.65 / Math.max(1, k)).toFixed(2));
      top.setAttribute("stroke-linejoin", "round");
      top.setAttribute("transform", flat + " " + sc);
      lift.appendChild(rz); lift.appendChild(top);
      /* 이름표는 지역 그룹 밖 맨 위 레이어에 모은다 - 안에 두면 나중에 그린 이웃이 덮는다. */
      const an = anchorOf(f.name), lx = an.x, ly = an.y;
      const lg = document.createElementNS(NS, "g");
      lg.setAttribute("class", "thmap-lbl" + (n ? "" : " thmap-empty"));
      lg.setAttribute("pointer-events", "auto");
      const fam = FAM[f.name] || "#40485a";
      /* 상자는 없고 손가락 받는 투명 판만 남긴다. 글씨보다 넓어 클릭이 쉽다. */
      const pw = f.name.length * 6.1 + 7.0, ph = 11.4;
      const cap = document.createElementNS(NS, "rect");
      cap.setAttribute("x", (lx - pw / 2).toFixed(2)); cap.setAttribute("y", (ly - ph / 2).toFixed(2));
      cap.setAttribute("width", pw.toFixed(2)); cap.setAttribute("height", String(ph));
      cap.setAttribute("rx", (ph / 2).toFixed(2));
      cap.setAttribute("fill", "transparent");
      lg.appendChild(cap);
      const t = document.createElementNS(NS, "text");
      t.setAttribute("class", "thmap-nm"); t.setAttribute("x", String(lx)); t.setAttribute("y", String(ly));
      t.setAttribute("fill", n ? fam : "#8c94a2");
      t.textContent = f.name; lg.appendChild(t);
      /* 가로 폭을 줄인 만큼 이름표도 줄인다 - 안 그러면 이름표끼리 부딪힌다. */
      const lk = Math.min(1, XW / 100);
      const lbase = lk < 0.999
        ? "translate(" + lx.toFixed(2) + "," + ly.toFixed(2) + ") scale(" + lk.toFixed(3) + ") translate(" + (-lx).toFixed(2) + "," + (-ly).toFixed(2) + ")"
        : "";
      if (rest || lbase) lg.setAttribute("transform", "translate(0," + (-rest).toFixed(3) + ") " + lbase);
      labelLayer.appendChild(lg);
      wallLayer.appendChild(wg);
      g.appendChild(lift); zoomer.appendChild(g);
      NODE[f.name] = { k, g, lift, wg, floor: fl, lbl: lg, lblBase: lbase, risers, rest, flat, sc };
      const go = () => onSelect(current === f.name ? null : f.name);
      g.addEventListener("click", go);
      /* 이름표는 딴 레이어라 지역 클릭이 안 닿는다. 작은 지역은 이름표가 실제 과녁이다. */
      lg.addEventListener("click", (e) => { e.stopPropagation(); go(); });
      g.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
      });
    });
    WGORDER = Array.from(wallLayer.children);
    FLORDER = Array.from(floorLayer.children);
    /* FEATS 순서가 아니라 실제로 그려 넣은 순서 - 작은 지역은 뒤로 미뤄 놨다 */
    RGORDER = Array.from(zoomer.children).filter((e) => /(^| )thmap-rg( |$)/.test(e.getAttribute("class") || ""));
    zoomer.appendChild(labelLayer); /* 모든 지역 위에 온다 */
    drawDokdo(); /* labelLayer 가 붙은 뒤라야 그 앞에 끼울 수 있다 */
  }

  /* 독도. 클릭 대상이 아니고 정책 수도 없다 - 지도 오른쪽 끝을 잡아 주는 표시다.
     지도 안쪽 여백(동해 앞바다 위도 24%, 동쪽 94%)에 둬야 viewBox 가 안 넓어진다. */
  /* 바다인지 도형으로 직접 판정한다. bbox 로 자르면 서해안 만처럼 오목하게 들어온 바다가
     전부 육지로 걸려, 남는 자리가 동해뿐이라 잔물결이 오른쪽에만 몰렸다.
     isPointInFill 은 도형의 제 좌표계에서 재므로 그리기 transform 을 거꾸로 푼 뒤 넘긴다.
     좌표계를 못 다루는 환경(jsdom)에서는 예전처럼 bbox 로 넉넉히 버린다. */
  function onLandAt(x: number, y: number) {
    return FEATS.some((f) => {
      const b = BB[f.name], node = NODE[f.name];
      /* 먼저 bbox 로 거른다 - 도형 판정은 비싸다 */
      if (x < b.x0 - 2 || x > b.x1 + 2 || y < b.y0 * K - 2 || y > b.y1 * K + 2) return false;
      const floor = node?.floor as SVGGeometryElement | undefined;
      if (!floor || typeof floor.isPointInFill !== "function" || typeof svg.createSVGPoint !== "function") return true;
      /* scale(1,K) 를 풀고, 이어서 (cx,cy) 를 중심으로 k 배 한 것을 푼다 */
      const k = node.k || 1;
      const pt = svg.createSVGPoint();
      pt.x = b.cx + (x - b.cx) / k;
      pt.y = b.cy + (y / K - b.cy) / k;
      try { return floor.isPointInFill(pt); } catch { return true; }
    });
  }

  /* 육지에서 떨어진 바다에만 물마루를 찍는다. 자리는 고정 씨앗이라 다시 그려도 같다.
     그냥 뿌리면 넓은 동해에만 몰린다 - 서해·남해는 만이 좁아 뽑힐 확률이 낮기 때문이다.
     좌·우·아래 세 구역에 돌아가며 심어 어느 쪽도 비지 않게 한다. */
  function drawRipples() {
    /* viewBox 가 바뀌면 바다 범위가 달라지므로 통째로 다시 심는다. 씨앗이 고정이라
       같은 규격이면 늘 같은 자리가 나온다. */
    rippleLayer.replaceChildren();
    let seed = RIPPLE_SEED;
    const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    const lx = W.x0, lw = W.x1 - W.x0, ly1 = W.y1 * K;
    /* 구역마다 몇 개를 심을지 정해 둔다. 돌아가며 뽑기만 하면 넓은 바다가 확률을 먹어
       좁은 바다가 빈다. bias 는 구역 안에서 어느 쪽으로 몰 것인가다 - 고르게 뽑으면
       해안에 붙어 바깥이 비므로 제곱해서 가장자리로 밀어낸다. */
    const cn = BB["충남"], jb = BB["전북"];
    const westEdge = Math.min(cn ? cn.x0 : lx, jb ? jb.x0 : lx);
    const zones = [
      /* 충남 서쪽과 전북 서쪽을 따로 뗀다. 하나로 묶으면 바다가 넓은 쪽(전북)에 다 몰리고
         충남 쪽이 통째로 빈다. 좌우로도 퍼지도록 치우침 없이 고르게 뽑는다. */
      /* 충남과 전북을 세로로 이어 한 구역으로 본다. 따로 떼면 충남 앞바다는 열린 폭이
         3단위뿐이라 - 물마루 하나도 못 들어간다 - 늘 통째로 비고 그만큼 개수가 준다.
         gap 을 두 배로 줘야 좁은 바다 안에서도 서로 밀어내 흩어진다. */
      { x0: VB.x, x1: westEdge + 20, y0: (cn ? cn.y0 : 0) * K, y1: (jb ? jb.y1 : 0) * K, bias: 0, want: 5, gap: RIPPLE_GAP * 2 },
      { x0: VB.x, x1: lx + lw * 0.35, y0: VB.y, y1: VB.y + VB.h, bias: -1, want: 6, gap: RIPPLE_GAP },   /* 나머지 서해 */
      { x0: lx + lw * 0.55, x1: VB.x + VB.w, y0: VB.y, y1: VB.y + VB.h, bias: 1, want: 18, gap: RIPPLE_GAP }, /* 동해 */
      { x0: VB.x, x1: VB.x + VB.w, y0: ly1 - VB.h * 0.22, y1: VB.y + VB.h, bias: 0, want: 16, gap: RIPPLE_GAP }, /* 남해 */
    ];
    /* 할당량을 다 합쳐 순번마다 어느 구역인지 미리 펼쳐 둔다 */
    const order: typeof zones = [];
    zones.forEach((z) => { for (let i = 0; i < z.want; i++) order.push(z); });
    const placed: [number, number][] = [];
    /* 간격 양보는 구역마다 따로 한다. 하나로 묶으면 좁은 서해가 못 채우는 동안 동해까지
       간격이 줄어 넓은 바다가 괜히 뭉친다. */
    const gaps = new Map<(typeof zones)[number], number>(zones.map((z) => [z, z.gap ?? RIPPLE_GAP]));
    let made = 0, tries = 0;
    while (made < order.length) {
      const z = order[made];
      tries++;
      /* 60번 걸러 그 구역만 간격을 양보한다. 400번까지 못 넣으면 이 한 자리만 포기하고
         다음 자리로 넘어간다 - 여기서 통째로 멈추면 뒤에 오는 구역이 아예 안 그려진다. */
      if (tries % 60 === 0) gaps.set(z, (gaps.get(z) ?? z.gap ?? RIPPLE_GAP) * 0.8);
      if (tries > 400) { made++; tries = 0; continue; }
      const gap = gaps.get(z) ?? RIPPLE_GAP;
      const r = rnd(), span = z.x1 - z.x0;
      const x = z.bias === 0 ? z.x0 + r * span
        : z.bias < 0 ? z.x0 + r * r * span          /* 왼쪽 끝으로 */
        : z.x1 - r * r * span;                      /* 오른쪽 끝으로 */
      const y = z.y0 + rnd() * (z.y1 - z.y0);
      /* 크기 편차. 고르게 뽑으면 다 비슷해 무늬처럼 보인다 - 제곱해서 작은 것이 많고
         큰 것이 드물게 나오게 한다. 0.35~1.5 배, 작은 쪽이 훨씬 흔하다.
         자리 검사보다 먼저 뽑는다 - 늘 최대 폭으로 검사하면 충남 서쪽처럼 15px 밖에 안 되는
         좁은 바다는 어떤 자리도 통과하지 못해 통째로 빈다. */
      const scale = 0.35 + rnd() ** 2 * 1.15;
      const w = RIPPLE_W * scale, h = w * 0.3;
      /* 그리게 될 폭만큼 좌우로 여유를 둬야 꼬리가 해안에 안 걸린다 */
      if (onLandAt(x, y) || onLandAt(x + w, y) || onLandAt(x + w / 2, y - h)) continue;
      /* 이미 놓은 것과 너무 가까우면 버린다 */
      if (placed.some(([px, py]) => Math.hypot(px - x, py - y) < gap)) continue;
      placed.push([x, y]);
      tries = 0;
      /* 흐르는 방향을 반씩 나눈다. 왼쪽으로 흐르는 것은 keyframes 를 거꾸로 돌린다 -
         같은 자리에서 반대로 떠내려가다 잦아든다. */
      const leftward = rnd() < 0.5;
      const mark = document.createElementNS(NS, "path");
      mark.setAttribute("d", crest(x, y, w, h, leftward));
      /* 선 굵기도 같이 줄인다 - 작은 물마루에 굵은 선을 그으면 획이 뭉쳐 점처럼 보인다 */
      mark.setAttribute("stroke-width", (0.5 + scale * 0.4).toFixed(2));
      if (leftward) mark.style.animationDirection = "reverse";
      /* 주기 5~9초, 시작 시점을 뒤로 당겨 첫 화면부터 제각각인 지점에 있게 한다 -
         자국마다 달라야 한 몸처럼 안 움직이고 파도처럼 흩어져 보인다 */
      mark.style.setProperty("--thmap-wave-dur", (5 + rnd() * 4).toFixed(2) + "s");
      mark.style.setProperty("--thmap-wave-delay", (-rnd() * 9).toFixed(2) + "s");
      rippleLayer.appendChild(mark);
      made++;
    }
  }

  function drawDokdo() {
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "thmap-dokdo");
    g.setAttribute("pointer-events", "none");
    /* 섬은 파문 없이 맨 도형만 그린다 - 섬이 작아 띠를 두르면 섬보다 띠가 더 커 보인다. */
    const put = (cx: number, cy: number, r: number) => {
      const e = document.createElementNS(NS, "ellipse");
      e.setAttribute("cx", cx.toFixed(2));
      e.setAttribute("cy", (cy * K).toFixed(2));
      e.setAttribute("rx", r.toFixed(2)); e.setAttribute("ry", (r * K).toFixed(2));
      e.setAttribute("fill", "#c3ccd4");
      e.setAttribute("stroke", "#b3bcc5"); e.setAttribute("stroke-width", "0.4");
      g.appendChild(e);
    };
    const x = W.x0 + (W.x1 - W.x0) * 0.94, y = W.y0 + (W.y1 - W.y0) * 0.24;
    ([[0, 0, 1.5], [2.5, 0.7, 1.0]] as const).forEach((q) => put(x + q[0], y + q[1], q[2]));
    /* 나머지 섬. 하나짜리는 점처럼 보이므로 옆에 더 작은 것을 하나씩 붙여 무리로 만든다. */
    ISLETS.forEach(([fx, fy, r]) => {
      const ix = W.x0 + (W.x1 - W.x0) * fx, iy = W.y0 + (W.y1 - W.y0) * fy;
      put(ix, iy, r);
      put(ix + r * 1.9, iy + r * 0.8, r * 0.55);
    });
    zoomer.insertBefore(g, labelLayer);
    dokdoG = g;
  }

  /* 그린 실제 범위로 viewBox 를 다시 맞춘다. 작은 지역을 키워 추정치 밖으로 나가기 때문이다.
     독도는 범위에서 뺀다 - 넣으면 오른쪽으로 넓어져 지도가 줄어든다. */
  function fitVB() {
    /* 독도는 크기 계산에서 뺀다 - 넣으면 오른쪽으로 넓어져 지도가 줄어든다.
       잔물결도 뺀다 - 선이 아니라 기하라 getBBox 에 잡히고, 그리기 전 추정 여백까지
       뿌려져 있어서 그대로 두면 위쪽 여백이 두 배로 벌어진다(강원 위 35px 의 정체). */
    seaLayer.setAttribute("display", "none");
    let b: DOMRect | null = null;
    try { b = zoomer.getBBox(); } catch { b = null; }
    if (dokdoG) dokdoG.removeAttribute("display");
    seaLayer.removeAttribute("display");
    if (!b || !b.width || !b.height) { drawRipples(); return; }
    /* 땅에 최소 여백을 두른 것이 출발점이다. */
    const pad = b.width * SEA_MIN_PAD;
    let w = b.width + pad * 2;
    let h = b.height + (RISE + 2) + 2;
    const cx = b.x + b.width / 2, cy = b.y - (RISE + 2) + h / 2;
    /* 칸의 실제 비율에 맞춰 모자란 쪽을 바다로 늘린다. viewBox 비율과 칸 비율이 같아지므로
       meet 이든 slice 든 결과가 같다 - 빈 띠도, 잘리는 땅도 없다. 기기가 길쭉하면 위아래
       바다가, 넓적하면 좌우 바다가 저절로 넓어진다. 칸을 못 재면(jsdom) 제 비율 그대로 둔다. */
    const bw = host.clientWidth, bh = host.clientHeight;
    if (bw > 0 && bh > 0) {
      const box = bw / bh;
      if (w / h < box) w = h * box; else h = w / box;
    }
    VB.x = cx - w / 2; VB.y = cy - h / 2; VB.w = w; VB.h = h;
    applyVB();
    /* 물마루는 VB 기준으로 자리를 잡으므로 여기서 그린다 */
    drawRipples();
  }

  /* 고른 지역은 이름표 층보다 위로 올리고 제 이름표만 그 위에 같이 얹는다. 이름표 층 아래까지만
     올리면 이웃 지역 이름이 솟은 땅 위에 그대로 겹쳐 보인다 - 솟은 땅이 그것들을 덮어야 한다.
     놓으면 원래 순서로 되돌린다 - 안 되돌리면 솟지도 않은 지역이 이웃을 덮은 채로 남는다.
     lifted 는 층 밖으로 꺼낸 이름표와 그 원래 자리다. */
  let lifted: { lbl: Element; next: ChildNode | null } | null = null;
  function raise(name: string | null) {
    const nd = name ? NODE[name] : null;
    if (nd) {
      if (zoomer.lastChild === nd.lbl) return; /* 이미 맨 위 */
      lifted = { lbl: nd.lbl, next: nd.lbl.nextSibling };
      /* 바닥 → 옆면 → 윗면 → 제 이름표 순서. 바닥이 옆면 위로 가면 기둥 아랫부분을 잘라먹는다. */
      zoomer.appendChild(nd.floor);
      zoomer.appendChild(nd.g);
      zoomer.appendChild(nd.lbl);
      /* 노드를 옮기면 진행 중인 전환이 취소된다. 한 번 읽어 스타일을 확정시켜야
         바로 뒤에 거는 솟기 전환이 살아난다. 없으면 툭 튀어오른다. */
      nd.g.getBoundingClientRect();
      return;
    }
    if (lifted) { labelLayer.insertBefore(lifted.lbl, lifted.next); lifted = null; }
    WGORDER.forEach((g) => wallLayer.appendChild(g));
    FLORDER.forEach((g) => floorLayer.appendChild(g));
    /* 바다를 맨 앞에 다시 못 박는다. zoomer.firstChild 앞에 옆면을 끼우면 바다가 뒤로 밀려
       땅 위로 올라오고, 해안 흰 테두리가 지역 옆면·바닥을 덮어 색이 달라 보인다.
       선택을 풀 때마다 이 경로를 타므로 바다를 클릭하면 색감이 바뀌던 원인이었다.
       다만 이미 제자리면 건드리지 않는다 - 노드를 옮기면 그 안의 CSS 애니메이션이 전부 처음부터
       다시 돈다. 물마루마다 달리 준 지연이 한꺼번에 0 이 되어 45개가 같은 박자로 튀었다. */
    /* Node 는 이 파일에서 지역 하나를 뜻하는 이름이라 DOM 쪽은 Element 로 받는다 */
    const put = (node: Element, before: Element | null) => {
      if (node.previousSibling !== before || node.parentNode !== zoomer) {
        zoomer.insertBefore(node, before ? before.nextSibling : zoomer.firstChild);
      }
    };
    put(seaLayer, null);
    put(wallLayer, seaLayer);
    put(floorLayer, wallLayer);
    RGORDER.forEach((g) => zoomer.insertBefore(g, labelLayer));
  }

  /* 솟기 - 윗면을 올리고 기둥을 늘린다. 바닥 옆면은 제자리라 지도 두께는 안 움직인다. */
  function setRise(name: string, on: boolean) {
    const nd = NODE[name]; if (!nd) return;
    if (on) raise(name);
    const rise = on ? RISE : nd.rest; /* 안 골랐어도 작은 지역은 두 칸 떠 있다 */
    nd.lift.setAttribute("transform", "translate(0," + (-rise).toFixed(3) + ")");
    nd.lbl.setAttribute("transform", "translate(0," + (-rise).toFixed(3) + ") " + nd.lblBase);
    /* lift 가 -rise 만큼 올라가므로 각 겹을 그만큼 되내려 평면부터 윗면까지 채운다.
       맨 아래 겹(i=WALLN)은 언제나 정확히 평면(y=0)에 붙는다 - 고정점이다. */
    nd.risers.forEach((w) => {
      const i = Number(w.getAttribute("data-i"));
      w.setAttribute("transform", "translate(0," + (rise * i / WALLN).toFixed(3) + ") " + nd.flat + " " + nd.sc);
    });
    nd.g.classList.toggle("thmap-on", on);
  }

  build();
  applyVB();
  host.appendChild(svg);
  fitVB();
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && current) onSelect(null); };
  host.addEventListener("keydown", onKey);

  /* SVG 는 letterbox 로 맞춰지므로 폭/뷰박스 비율로 환산하면 어긋난다.
     getScreenCTM 이 실제 배치를 그대로 안다 - jsdom 엔 없으니 그땐 null. */
  function anchorScreen(name: string) {
    const b = BB[name]; if (!b) return null;
    if (typeof svg.getScreenCTM !== "function" || typeof svg.createSVGPoint !== "function") return null;
    const ctm = svg.getScreenCTM(); if (!ctm) return null;
    const pt = svg.createSVGPoint();
    pt.x = anchorOf(name).x; pt.y = b.y0 * K - RISE;
    const sp = pt.matrixTransform(ctm);
    const hb = host.getBoundingClientRect();
    return { x: sp.x - hb.left, y: sp.y - hb.top };
  }

  return {
    anchorScreen,
    /* 칸 크기가 바뀌면 부른다 - 회전·주소창·창 크기 */
    resize: fitVB,
    aspect: () => (VB.h > 0 ? VB.w / VB.h : 1),
    setSelected(name) {
      if (name && !NODE[name]) name = null;
      if (name === current) return;
      if (current) { setRise(current, false); raise(null); }
      current = name;
      if (name) setRise(name, true);
    },
    destroy() {
      host.removeEventListener("keydown", onKey);
      svg.remove();
    },
  };
}
