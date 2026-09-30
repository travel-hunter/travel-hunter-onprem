import type { Policy, PolicyStructuredDetailItem } from "../api";
import type { BenefitType } from "../components/benefitTile";
import { getKstDateInputValue } from "./dateDefaults";

/* 정책 상세 문구. 수집된 structuredDetail 만 읽어 화면에 쓸 모양으로 나눈다.
   시안(v27)에서 정책 107건을 앱 상세와 한 줄씩 대조하며 정한 규칙이다(benefit_text.py 이식).
   - 지역 이름만 바뀌는 틀 문장, 숫자 없는 일반 안내("공식 안내에서 최종 확인" 류)는 뺀다.
   - 비어 있는 칸은 지어내지 않는다. 화면이 '공식 안내에서 확인' 한 줄로 채운다. */

export type PolicyDetailPick = { category: string; name: string; benefit: string; note: string; url: string };

export type PolicyDetailPeriod = {
  label: string;
  text: string;
  start: string | null;
  end: string | null;
  /** 막대 옆에 남길 단서: '(예정)' 같은 괄호 속 말, 연도를 올해로 본 경우 true */
  note: string | true | null;
};

export type PolicyDetailText = {
  lead: string;
  more: string[];
  spend: string;
  partnerCount: number;
  partnerMix: string;
  picks: PolicyDetailPick[];
  steps: string[];
  conditions: string[];
  extra: Array<{ title: string; items: string[] }>;
  regions: Array<{ title: string; description: string; url: string | null }>;
  periods: PolicyDetailPeriod[];
  target: string[];
  /** '별도 제출 서류 없음' 이면 뒤에 붙은 말(풀어 쓴 것), 아니면 null */
  noDocuments: string | null;
  documents: string[];
  notes: string[];
  provenance: string[];
};

const TEMPLATE = /공식 안내에서 정한|세부 공고를 따릅니다/;
const GENERIC = /(공식|최종).{0,30}확인|변동될 수 있/;
const SPECIFIC = /\d|%/;
const CIRCLED_NUMBER = /^[①-⑨]\s*/;
const CATEGORY_BY_EMOJI: Array<[string, string]> = [
  ["🍽", "식음"],
  ["🏨", "숙박"],
  ["🎟", "관람"],
  ["🎡", "체험"],
  ["🛍", "쇼핑"],
  ["☕", "식음"],
];
/* 뜻은 그대로, 행정 말투만 풀어 쓴다 */
const PLAIN_DOCUMENT_NOTE: Record<string, string> = {
  "디지털관광주민증 발급 및 제시 기준으로 적용": "디지털관광주민증을 발급받아 제휴처에 보여 주면 돼요.",
  "온라인 할인권 발급 및 예약 기준으로 적용": "온라인에서 할인권을 받아 예약하면 적용돼요.",
};

/** 10,000원 / 20000원 -> 1만원 / 2만원 (만 단위로 나누어떨어질 때만) */
export function won(text: string): string {
  return text.replace(/(\d[\d,]*)\s*원/g, (match, digits: string) => {
    const value = Number(digits.replace(/,/g, ""));
    return value >= 10000 && value % 10000 === 0 ? `${value / 10000}만원` : match;
  });
}

function plain(text: string | null | undefined): string {
  return won(text ?? "").replace(/\s+/g, " ").trim();
}

function uniq(values: string[]): string[] {
  return values.filter((value, index) => value && values.indexOf(value) === index);
}

/* 숫자 없이 '공식 안내에서 최종 확인'·'변동될 수 있음'만 말하는 줄. 화면 끝의 한 줄 안내가 대신한다. */
function isGenericNotice(text: string): boolean {
  return GENERIC.test(text) && !/\d/.test(text);
}

function safeUrl(url: string | null | undefined): string | null {
  try {
    const parsed = new URL((url ?? "").trim());
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function itemText(item: PolicyStructuredDetailItem): string {
  return item.description ?? item.value ?? "";
}

/* 수집 때 괄호 속 쉼표에서 잘린 조각('여행유형(가족', '개인', '청년) 중복신청…')을 괄호가 닫힐 때까지 다시 잇는다 */
function rejoin(parts: string[]): string[] {
  const out: string[] = [];
  const count = (text: string, char: string) => text.split(char).length - 1;
  for (const part of parts.map(plain)) {
    if (!part) continue;
    const last = out[out.length - 1];
    if (last !== undefined && count(last, "(") > count(last, ")")) out[out.length - 1] = `${last}, ${part}`;
    else out.push(part);
  }
  return out;
}

/* 받는 혜택 첫 문장: 숫자가 든 구체적인 문장만. 조건 나열·기호 섞인 요약은 뺀다 */
function leadOf(summary: string, body: string[]): string {
  return [plain(summary), ...body].find(
    (text) => text && SPECIFIC.test(text) && !text.startsWith("이용 조건") && !/[*→]/.test(text),
  ) ?? "";
}

function isoDate(year: string | number, month: string, day: string): string {
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/* '신청 기간: 신청 기간: 2026-04-01~2026-11-30' -> 라벨·문구·시작·끝. 수집된 시작·끝 날짜가 있으면 그걸 쓴다 */
function periodOf(item: PolicyStructuredDetailItem): PolicyDetailPeriod {
  const label = (item.title ?? item.label ?? "").trim() || "기간";
  let text = itemText(item).trim().replace(new RegExp(`^${escapeRegExp(label)}\\s*:\\s*`), "");
  if (/^\d차/.test(label)) text = text.replace(/^[^:]{1,12}:\s*/, "");   // '3차 여행기간: …' 처럼 띄어쓰기만 다른 머리
  if (item.startDate && item.endDate) {
    // '(예정)'·'(…와 같은 기간)' 같은 단서는 막대 옆에 남긴다. '(목)' 같은 요일은 뺀다
    const note = /\(([^)]{2,})\)\s*$/.exec(text)?.[1] ?? null;
    return { label, text, start: item.startDate, end: item.endDate, note };
  }
  const full = /(\d{4})[-.](\d{1,2})[-.](\d{1,2})\s*~\s*(\d{4})[-.](\d{1,2})[-.](\d{1,2})/.exec(text);
  if (full) {
    return { label, text, start: isoDate(full[1], full[2], full[3]), end: isoDate(full[4], full[5], full[6]), note: null };
  }
  const short = /(\d{1,2})\.(\d{1,2})\s*~\s*(\d{1,2})\.(\d{1,2})/.exec(text);
  if (short) {   // 연도 없는 '10.1~11.1' 은 올해로 본다(근사) - 화면에 그렇게 적는다
    const year = getKstDateInputValue().slice(0, 4);
    return { label, text, start: isoDate(year, short[1], short[2]), end: isoDate(year, short[3], short[4]), note: true };
  }
  return { label, text, start: null, end: null, note: null };
}

function partnerCountAndMix(core: string): { count: number; mix: string } {
  const count = Number(/제휴처\s*(\d+)곳/.exec(core)?.[1] ?? 0);
  const mixText = /주요 분야:\s*(.+)/.exec(core)?.[1] ?? "";
  const mix = Array.from(mixText.matchAll(/([가-힣A-Za-z]+)\s*(\d+)곳/g))
    .sort((left, right) => Number(right[2]) - Number(left[2]))
    .map(([, kind, n]) => `${kind} ${n}`)
    .join(" · ");
  return { count, mix };
}

const EMPTY: PolicyDetailText = {
  lead: "",
  more: [],
  spend: "",
  partnerCount: 0,
  partnerMix: "",
  picks: [],
  steps: [],
  conditions: [],
  extra: [],
  regions: [],
  periods: [],
  target: [],
  noDocuments: null,
  documents: [],
  notes: [],
  provenance: [],
};

export function policyDetailText(policy: Policy): PolicyDetailText {
  const detail = policy.structuredDetail;
  if (!detail) {
    // 구조화 전 정책: 요약·조건·서류 원문만 그대로 싣는다(일반 안내 줄은 뺀다)
    return {
      ...EMPTY,
      lead: plain(policy.summary),
      target: uniq(policy.requirements.map(plain)).filter((text) => !isGenericNotice(text)),
      documents: uniq(policy.documents.map(plain)).filter((text) => !isGenericNotice(text)),
    };
  }

  const picks: PolicyDetailPick[] = [];
  const steps: string[] = [];
  const body: string[] = [];
  const conditions: string[] = [];
  const regions: PolicyDetailText["regions"] = [];
  const extra: PolicyDetailText["extra"] = [];
  let partner = { count: 0, mix: "" };

  for (const item of detail.supportContent ?? []) {
    const title = (item.title ?? item.label ?? "").trim();
    const description = itemText(item);
    const url = safeUrl(item.url);
    if (title === "카테고리별 인기 혜택") {
      // 제휴처마다 그 제휴처 안내 페이지로 간다. 주소 없는 줄은 목록 소개 문장이라 뺀다
      if (!url) continue;
      const [first, ...rest] = description.split("\n");
      const category = CATEGORY_BY_EMOJI.find(([emoji]) => first.startsWith(emoji))?.[1] ?? "";
      const line = first.replace(/^[^\p{L}\p{N}_]+/u, "");
      const colon = line.indexOf(":");
      const name = (colon < 0 ? line : line.slice(0, colon)).trim();
      const benefit = colon < 0 ? "" : line.slice(colon + 1).trim();
      picks.push({ category, name, benefit: plain(benefit).replace(/>/g, "→"), note: plain(rest.join(" ")), url });
    } else if (title.startsWith("받는 방법")) {
      steps.push(plain(description).replace(CIRCLED_NUMBER, ""));
    } else if (title === "지원내용" || title === "지원 내용") {
      body.push(plain(description));
    } else if (title === "혜택 적용 조건") {
      conditions.push(description);
    } else if (title.startsWith("대상 지역")) {
      regions.push({ title, description: plain(description), url });
    } else if (title === "핵심 혜택") {
      partner = partnerCountAndMix(description);   // 제휴처 수·분야만 쓴다. 나머지는 받는 것 칸과 같은 말
    } else if (title === "혜택" && description.length < 20 && [policy.amount, policy.cardSummary].some((value) => plain(value) === plain(description))) {
      // 받는 것 칸과 같은 말
    } else {
      // 대상 열차·지급 기준·추가 혜택·포함 혜택·지급 포인트·대상 노선·할인 금액·대상 차량 …
      const text = plain(description).replace(CIRCLED_NUMBER, "");
      const last = extra[extra.length - 1];
      if (last && last.title === title) last.items.push(text);
      else extra.push({ title, items: [text] });
    }
  }

  const bodyUnique = uniq(body);
  const kept = bodyUnique.filter((text) => !TEMPLATE.test(text));
  const lead = leadOf(policy.summary, kept);
  const notes = uniq((detail.notes ?? []).map((item) => plain(itemText(item))));
  const provenance = notes.filter((text) => /^[^:]{2,20} 목록:/.test(text));   // 목록 출처는 출처 줄로
  let noDocuments: string | null = null;
  const documents: string[] = [];
  for (const text of uniq((detail.requiredDocuments ?? []).map((item) => plain(itemText(item))))) {
    const none = /^별도 제출 서류 없음\s*[,·]?\s*(.*)$/.exec(text);
    if (none) noDocuments = PLAIN_DOCUMENT_NOTE[none[1]] ?? none[1];
    else documents.push(text);
  }

  return {
    lead,
    more: kept.filter((text) => text !== lead),   // 정산·지급 방식처럼 구체적인 나머지 문장
    spend: bodyUnique.map((text) => /^(.+?) 등 지역 여행 지출을 대상으로/.exec(text)?.[1]).find(Boolean) ?? "",
    partnerCount: partner.count,
    partnerMix: partner.mix,
    picks,
    steps,
    conditions: rejoin(conditions),
    extra,
    regions,
    periods: (detail.periods ?? []).map(periodOf),
    target: uniq((detail.applicationTarget ?? []).map((item) => plain(itemText(item)))),
    noDocuments,
    documents,
    notes: notes.filter((text) => !provenance.includes(text) && !isGenericNotice(text)),
    provenance,
  };
}

/** 받는 방법 칸: 수집된 대상 문장에 그 말이 있을 때만 줄여 쓴다. 구체적인 말이 없으면 칸을 뺀다 */
export function policyHowTo(policy: Pick<Policy, "applyUrl">, type: BenefitType, target: string[]): string {
  const text = target.join(" ");
  if (policy.applyUrl) return "바로 신청";
  if (type === "partner" && /주민증/.test(text)) return "주민증 발급 후 제시";
  if (type === "stay" && /여행사/.test(text)) return "참여 여행사 예약";
  if (type === "refund" && /사전 신청/.test(text)) return "사전 신청 후 여행";
  return "";
}

/** 제목 앞 '[거창] ' 은 지역 줄로 옮기고, 연도 머리 '2026 ' 은 뺀다 */
export function policyPlaceAndProgram(title: string): { place: string | null; program: string } {
  const match = /^\[([^\]]+)\]\s*/.exec(title);
  const place = match?.[1]?.trim() || null;
  return { place, program: title.slice(match ? match[0].length : 0).replace(/^20\d\d\s+/, "") };
}

export type PolicyTimelineRow = { label: string; start: string; end: string; note: string | true | null };

/* 날짜가 둘 다 있는 기간만 막대로 그린다. 무슨 기간인지 모르면 '신청'이라 하지 않고 '기간'이라 한다 */
export function policyTimeline(
  periods: PolicyDetailPeriod[],
  startDate: string | null | undefined,
  deadline: string | null | undefined,
): { rows: PolicyTimelineRow[]; loose: string[] } {
  let rows: PolicyTimelineRow[] = periods
    .filter((period): period is PolicyDetailPeriod & { start: string; end: string } => Boolean(period.start && period.end))
    .map((period) => ({ label: period.label.replace(/\s*기간$/, ""), start: period.start, end: period.end, note: period.note }));
  if (rows.length === 0 && startDate && deadline) rows = [{ label: "기간", start: startDate, end: deadline, note: null }];
  const loose = periods.filter((period) => !(period.start && period.end)).map((period) => `${period.label}: ${period.text}`);
  return { rows, loose };
}
