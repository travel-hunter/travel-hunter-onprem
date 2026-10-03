import type { Policy } from "../../api";
import { cityOf, NATIONWIDE_REGION } from "../../utils/policyPrograms";
import { isRegionName, REGION_FULL_NAMES } from "./policyBrowse";
import { INSET } from "./regionMapEngine";
import { SIGUN_POINTS } from "./sigunPoints";

/* 위치로 찾기의 근처(통합 검색, 시안 v56). 혜택에는 좌표가 없어 시군 점 자리(SIGUN_POINTS)로 거리를 센다.
   위경도 → 지도 도안 단위는 시군 점을 만든 맞춤과 같은 바탕의 1차 맞춤이다(시안 geo.json: 본토 아핀, 제주는 섬 상자).
   시군 점은 해안 안으로 당긴 근사값이라 거리도 근사다 - '약 15km' 처럼 둥글려 보인다. */
const FX = [40.38827280086289, 0.12351437223106819, -5037.754583113213] as const;
const FY = [0.1335067368968111, -49.37713562793364, 1889.8834982462804] as const;
const JEJU_BOX = [63.1, 93.5, 226.8, 244.7] as const;   // x0, x1, y0, y1 (삽입 지도로 옮기기 전)

export function geoToMap(sido: string, lat: number, lng: number): readonly [number, number] {
  if (sido === "제주") {
    const [x0, x1, y0, y1] = JEJU_BOX, [dx, dy] = INSET["제주"];
    return [x0 + ((lng - 126.16) / 0.81) * (x1 - x0) + dx, y0 + ((33.57 - lat) / 0.38) * (y1 - y0) + dy];
  }
  return [FX[0] * lng + FX[1] * lat + FX[2], FY[0] * lng + FY[1] * lat + FY[2]];
}

const unitsPerDegree = (() => {
  const [ax, ay] = geoToMap("전남", 35, 127), [bx, by] = geoToMap("전남", 36, 127);
  return Math.hypot(ax - bx, ay - by);
})();
export const KM_PER_UNIT = 111 / unitsPerDegree;
/** '가까운 시군'으로 보일 거리(약 km) */
export const NEAR_KM = 45;

export type NearbyCity = { region: string; city: string; km: number; count: number };

const pointOf = (key: string): readonly [number, number] | null => {
  const at = SIGUN_POINTS[key];
  if (!at) return null;
  const [ix, iy] = INSET[key.split("|")[0]] ?? [0, 0];
  return [at[0] + ix, at[1] + iy];
};

/** 정책 제목 [시군] 이름(부산은 '부산영도'처럼 도 이름이 붙는다)과 장소 주소의 시군('영도')을 맞춘다 */
export function policyCityFor(policies: readonly Policy[], sido: string, city: string | null): string | null {
  if (!city) return null;
  for (const policy of policies) {
    if (policy.region !== sido) continue;
    const c = cityOf(policy);
    if (c === city || c === `${sido}${city}`) return c;
  }
  return null;
}

/** 장소 자리에서 가까운 혜택 있는 시군(가까운 순, NEAR_KM 안). skip = 이미 보고 있는 "도|시군" */
export function nearbyCities(policies: readonly Policy[], xy: readonly [number, number] | null, skip: string | null = null): NearbyCity[] {
  if (!xy) return [];
  const counts = new Map<string, number>();
  for (const policy of policies) {
    const c = cityOf(policy);
    if (!c || policy.region === NATIONWIDE_REGION) continue;
    const key = `${policy.region}|${c}`;
    if (SIGUN_POINTS[key]) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const out: NearbyCity[] = [];
  for (const [key, count] of counts) {
    if (key === skip) continue;
    const at = pointOf(key);
    if (!at) continue;
    const km = Math.round(Math.hypot(at[0] - xy[0], at[1] - xy[1]) * KM_PER_UNIT);
    if (km > NEAR_KM) continue;
    const [region, city] = key.split("|");
    out.push({ region, city, km, count });
  }
  return out.sort((l, r) => l.km - r.km || r.count - l.count);
}

/** 시군 이름을 화면에 - '부산영도' → '영도' */
export const shortCity = (region: string, city: string) => (city.startsWith(region) && city.length > region.length ? city.slice(region.length) : city);

export type NearTarget = {
  region: string;
  city: string | null;
  count: number;
  note: string | null;
  /** 가장 가까운 시군으로 넓혔을 때 그 시군까지(약 km) */
  km?: number;
};

/** 근처 혜택을 어디로 보일지: 그 시군 전용 → 가장 가까운 시군 → 도 → 전국 공통. note 는 넓힌 이유 */
export function nearTarget(
  policies: readonly Policy[],
  sido: string | null,
  city: string | null,
  xy: readonly [number, number] | null,
): NearTarget {
  const nation = policies.filter((policy) => policy.region === NATIONWIDE_REGION).length;
  if (!sido || !isRegionName(sido)) return { region: NATIONWIDE_REGION, city: null, count: nation, note: "이 지역 전용 혜택이 없어 전국 공통 혜택을 보여 드려요" };
  const own = policyCityFor(policies, sido, city);
  if (own) return { region: sido, city: own, count: policies.filter((p) => p.region === sido && cityOf(p) === own).length, note: null };
  const here = city || REGION_FULL_NAMES[sido];
  const near = nearbyCities(policies, xy)[0];
  if (near) return { region: near.region, city: near.city, count: near.count, km: near.km, note: `${here} 전용 혜택이 없어 가까운 시군 혜택을 보여 드려요` };   // 칩을 바꿔 눌러도 맞는 말
  const inSido = policies.filter((policy) => policy.region === sido).length;
  if (inSido) return { region: sido, city: null, count: inSido, note: `${here} 전용 혜택이 없어 ${REGION_FULL_NAMES[sido]} 혜택을 보여 드려요` };
  return { region: NATIONWIDE_REGION, city: null, count: nation, note: `${REGION_FULL_NAMES[sido]} 전용 혜택이 없어 전국 공통 혜택을 보여 드려요` };
}
