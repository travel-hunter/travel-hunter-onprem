/* 일정 생성·직접 편집·상세 기간 수정이 같은 달력을 쓰기 위한 순수 날짜 유틸.
   원본은 ItineraryCreatePage 안에 있던 로직이고 동작을 그대로 옮겼다. */

export type TripDateRangeValue = {
  startDate: string;
  endDate: string;
};

const DATE_INPUT_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const MS_PER_DAY = 86_400_000;
const CALENDAR_CELL_COUNT = 42;

/** `YYYY-MM-DD` 만 받는다. 존재하지 않는 날짜는 null 이다. */
export function parseTripDate(value: string): Date | null {
  const match = DATE_INPUT_PATTERN.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const date = new Date(year, month, day);
  // Date 생성자는 2026-02-30 을 3월 2일로 굴린다. 되굴려 확인해야 걸러진다.
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month ||
    date.getDate() !== day
  ) {
    return null;
  }
  return date;
}

export function formatTripDate(date: Date): string {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function startOfTripMonth(value: string): Date {
  const parsed = parseTripDate(value) ?? new Date();
  return new Date(parsed.getFullYear(), parsed.getMonth(), 1);
}

export function addTripMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

export function formatTripCalendarMonth(date: Date): string {
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
}

/** 항상 42칸이다. 달마다 높이가 바뀌면 달력이 출렁인다. */
export function buildCalendarDays(month: Date): Date[] {
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(firstDay);
  start.setDate(firstDay.getDate() - firstDay.getDay());
  return Array.from({ length: CALENDAR_CELL_COUNT }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return date;
  });
}

export function isTripDateInRange(
  value: string,
  startDate: string,
  endDate: string,
): boolean {
  return value >= startDate && value <= endDate;
}

export function tripDateDayCount(
  startDate: string,
  endDate: string,
): number | null {
  const start = parseTripDate(startDate);
  const end = parseTripDate(endDate);
  if (!start || !end) return null;
  return Math.round((end.getTime() - start.getTime()) / MS_PER_DAY) + 1;
}

/** 끝날을 첫날보다 앞서 골라도 정방향으로 되돌린다. 일수가 음수가 될 길을 막는다. */
export function normalizeSelectedRange(
  startDate: string,
  endDate: string,
): TripDateRangeValue {
  if (!startDate || !endDate) return { startDate, endDate };
  return endDate < startDate
    ? { startDate: endDate, endDate: startDate }
    : { startDate, endDate };
}
