export const UNKNOWN_DEADLINE_LABEL = "마감일 확인 필요";

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

export function daysUntilPolicyDeadline(deadline: string | null | undefined, now = new Date()): number | null {
  const time = policyDeadlineTime(deadline);
  if (time === Number.MAX_SAFE_INTEGER) return null;
  return Math.ceil((time - now.getTime()) / 86400000);
}

export function dday(deadline: string | null | undefined) {
  const days = daysUntilPolicyDeadline(deadline);
  if (days === null) return UNKNOWN_DEADLINE_LABEL;
  return days >= 0 ? `D-${days}` : "마감";
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
