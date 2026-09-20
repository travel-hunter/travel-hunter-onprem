import type { Policy } from "../api";

/* 정책 제목은 "[영광] 디지털관광주민증 혜택" 꼴이다. 앞의 시·군을 떼면 정책 종류가
   남는다 - 60건이 실은 2종이다. 시트의 "정책별" 묶음과 목록 그룹 헤더가 이 키를 쓴다. */
const TITLE_PATTERN = /^\[([^\]]+)\]\s*(.+)$/;

export const NATIONWIDE_REGION = "전국";

export function programOf(policy: Pick<Policy, "title">): string {
  const match = TITLE_PATTERN.exec(policy.title.trim());
  return (match ? match[2] : policy.title).trim();
}

export function cityOf(policy: Pick<Policy, "title">): string | null {
  const match = TITLE_PATTERN.exec(policy.title.trim());
  return match ? match[1].trim() : null;
}

export type PolicyGroup = {
  key: string;
  label: string;
  /** 타일 아래 작은 글씨 - "시·군 3곳" 또는 "시도 2곳" */
  subLabel: string;
  items: Policy[];
};

/* 지역별. 전국 정책은 넣지 않는다 - 17개 시도에 같은 정책이 반복돼 건수를 부풀렸다.
   전국은 홈 '전국 혜택' 카드가 따로 보여준다.
   regions 를 주면 정책 0건 지역도 카드로 낸다 - 지도가 17개 시도를 다 그리므로 시트도 맞춘다.
   0건은 건수 내림차순 정렬에서 자연히 뒤로 밀린다. */
export function groupByRegion(policies: Policy[], regions?: readonly string[]): PolicyGroup[] {
  const byRegion = new Map<string, Policy[]>();
  for (const region of regions ?? []) {
    if (region !== NATIONWIDE_REGION) byRegion.set(region, []);
  }
  for (const policy of policies) {
    if (policy.region === NATIONWIDE_REGION) continue;
    const bucket = byRegion.get(policy.region) ?? [];
    bucket.push(policy);
    byRegion.set(policy.region, bucket);
  }
  return Array.from(byRegion.entries())
    .map(([region, own]) => {
      const items = own;
      const cities = new Set(own.map(cityOf).filter((city): city is string => city !== null));
      return { key: region, label: region, subLabel: `시·군 ${cities.size}곳`, items };
    })
    .sort((left, right) => right.items.length - left.items.length);
}

/* 정책 종류별. 같은 종류가 몇 개 시도에 걸쳐 있는지를 부제로 낸다. */
export function groupByProgram(policies: Policy[]): PolicyGroup[] {
  const byProgram = new Map<string, Policy[]>();
  for (const policy of policies) {
    const key = programOf(policy);
    const bucket = byProgram.get(key) ?? [];
    bucket.push(policy);
    byProgram.set(key, bucket);
  }
  return Array.from(byProgram.entries())
    .map(([program, items]) => {
      const regions = new Set(items.map((policy) => policy.region));
      return { key: program, label: program, subLabel: `시도 ${regions.size}곳`, items };
    })
    .sort((left, right) => right.items.length - left.items.length);
}
