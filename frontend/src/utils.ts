import { getKstDateInputValue } from "./utils/dateDefaults";

export const UNKNOWN_DEADLINE_LABEL = "마감일 확인 필요";

export const ALWAYS_AVAILABLE_POLICY_LABEL = "상시 발급";
/* 카드 아래 줄·상세 "기간" 칸. 앞의 "상시 발급"은 오른쪽 위 마감 배지와 겹쳐서 뺐다. */
export const DIGITAL_TOURISM_PERIOD_LABEL = "제휴처별 운영기간 확인";
export const DIGITAL_TOURISM_PERIOD_NOTICE =
  "별도 신청 마감일 없이 발급 후 이용할 수 있습니다. 제휴처별 할인율, 운영 기간, 이용 조건은 공식 안내에서 확인하세요.";

type PolicyDeadlineDisplayContext = {
  title?: string | null;
  officialUrl?: string | null;
  startDate?: string | null;
  deadline?: string | null;
};

export function isDigitalTourismResidentCardPolicy(policy: PolicyDeadlineDisplayContext): boolean {
  const title = policy.title ?? "";
  const officialUrl = policy.officialUrl ?? "";
  return title.includes("디지털관광주민증") || officialUrl.includes("/dgtourcard/biz/regn/regnMain.do");
}

export function formatPolicyDeadlineTag(policy: PolicyDeadlineDisplayContext): string {
  if (isDigitalTourismResidentCardPolicy(policy)) return ALWAYS_AVAILABLE_POLICY_LABEL;
  if (!isSafePolicyDeadline(policy.deadline)) return UNKNOWN_DEADLINE_LABEL;
  const ddayLabel = dday(policy.deadline);
  return ddayLabel === "마감" ? ddayLabel : `${ddayLabel} 마감`;
}

export function formatPolicyPeriodSummary(policy: PolicyDeadlineDisplayContext): string {
  if (isDigitalTourismResidentCardPolicy(policy)) return DIGITAL_TOURISM_PERIOD_LABEL;
  const startLabel = isSafePolicyDeadline(policy.startDate)
    ? `${formatDottedPolicyDeadline(policy.startDate)} 시작`
    : "";
  const deadlineLabel = isSafePolicyDeadline(policy.deadline)
    ? `${formatDottedPolicyDeadline(policy.deadline)} 마감`
    : "";
  return [startLabel, deadlineLabel].filter(Boolean).join(" · ");
}

export function formatPolicyDeadlineNotice(policy: PolicyDeadlineDisplayContext): string {
  if (isDigitalTourismResidentCardPolicy(policy)) return DIGITAL_TOURISM_PERIOD_NOTICE;
  return isSafePolicyDeadline(policy.deadline)
    ? `${dday(policy.deadline)} · 서둘러 신청하세요`
    : `${UNKNOWN_DEADLINE_LABEL} · 공식 안내에서 기간을 확인하세요`;
}

function parseIsoDateParts(value: string): { year: number; month: number; day: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

export function isSafePolicyDeadline(deadline: string | null | undefined): deadline is string {
  return Boolean(deadline && parseIsoDateParts(deadline));
}

export function policyDeadlineTime(deadline: string | null | undefined): number {
  const parts = deadline ? parseIsoDateParts(deadline) : null;
  if (!parts) return Number.MAX_SAFE_INTEGER;
  return new Date(Date.UTC(parts.year, parts.month - 1, parts.day, 23, 59, 59)).getTime();
}

const MILLISECONDS_PER_DAY = 86_400_000;

function isoDatePartsToUtcTime(parts: { year: number; month: number; day: number }): number {
  return Date.UTC(parts.year, parts.month - 1, parts.day);
}

export function daysUntilPolicyDeadline(deadline: string | null | undefined, now = new Date()): number | null {
  const deadlineParts = deadline ? parseIsoDateParts(deadline) : null;
  const todayParts = parseIsoDateParts(getKstDateInputValue(now));
  if (!deadlineParts || !todayParts) return null;
  return (
    isoDatePartsToUtcTime(deadlineParts) - isoDatePartsToUtcTime(todayParts)
  ) / MILLISECONDS_PER_DAY;
}

export function dday(deadline: string | null | undefined) {
  const days = daysUntilPolicyDeadline(deadline);
  if (days === null) return UNKNOWN_DEADLINE_LABEL;
  if (days < 0) return "마감";
  return days === 0 ? "D-day" : `D-${days}`;
}

export function formatCompactPolicyDeadline(deadline: string | null | undefined) {
  const parts = deadline ? parseIsoDateParts(deadline) : null;
  if (!parts) return UNKNOWN_DEADLINE_LABEL;
  return `${parts.month}.${parts.day}`;
}

export function formatDottedPolicyDeadline(deadline: string | null | undefined) {
  const parts = deadline ? parseIsoDateParts(deadline) : null;
  if (!parts) return UNKNOWN_DEADLINE_LABEL;
  return `${parts.year}.${String(parts.month).padStart(2, "0")}.${String(parts.day).padStart(2, "0")}`;
}

export function money(value: number) {
  return new Intl.NumberFormat("ko-KR").format(value);
}
