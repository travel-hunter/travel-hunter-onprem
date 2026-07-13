const defaultTripDurationDays = 3;

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
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function getDefaultTripDateRange(now = new Date(), durationDays = defaultTripDurationDays) {
  const startDate = getKstDateInputValue(now);
  return {
    startDate,
    endDate: addDaysToDateInput(startDate, durationDays - 1),
  };
}
