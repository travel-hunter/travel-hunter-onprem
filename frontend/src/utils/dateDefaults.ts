const defaultTripDurationDays = 3;
const KST_OFFSET_MILLISECONDS = 9 * 60 * 60 * 1000;

function formatDateInputValue(date: Date): string {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function addDaysToDateInput(dateInputValue: string, days: number): string {
  const [year, month, day] = dateInputValue.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + days);
  return formatDateInputValue(date);
}

export function getKstDateInputValue(now = new Date()): string {
  const kstDate = new Date(now.getTime() + KST_OFFSET_MILLISECONDS);
  return [
    kstDate.getUTCFullYear(),
    String(kstDate.getUTCMonth() + 1).padStart(2, "0"),
    String(kstDate.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

export function getDefaultTripDateRange(now = new Date(), durationDays = defaultTripDurationDays) {
  const startDate = getKstDateInputValue(now);
  return {
    startDate,
    endDate: addDaysToDateInput(startDate, durationDays - 1),
  };
}

/**
 * 첫날과 마지막 날을 항상 앞뒤 순서로 맞춘다. 역순으로 고르면 맞바꿔
 * 절댓값 범위가 되게 한다. 이걸 거치지 않으면 일수가 0 이하로 내려가
 * 생성 버튼이 잠긴다.
 *
 * 값이 비었거나 형식이 아니면 그대로 돌려준다 — 순서 문제가 아니라
 * 입력이 없는 것이므로 호출부가 따로 알려야 한다.
 */
export function normalizeTripDateRange(
  startDate: string,
  endDate: string,
): { startDate: string; endDate: string } {
  if (!startDate || !endDate) return { startDate, endDate };
  return endDate < startDate
    ? { startDate: endDate, endDate: startDate }
    : { startDate, endDate };
}
