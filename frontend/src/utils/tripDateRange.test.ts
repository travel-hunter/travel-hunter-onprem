import { describe, expect, it } from "vitest";

import {
  addTripMonths,
  buildCalendarDays,
  formatTripCalendarMonth,
  formatTripDate,
  isTripDateInRange,
  normalizeSelectedRange,
  parseTripDate,
  startOfTripMonth,
  tripDateDayCount,
} from "./tripDateRange";

describe("tripDateRange", () => {
  it("parses a valid date input", () => {
    const parsed = parseTripDate("2026-09-10");
    expect(parsed?.getFullYear()).toBe(2026);
    expect(parsed?.getMonth()).toBe(8);
    expect(parsed?.getDate()).toBe(10);
  });

  it("rejects a date that does not exist", () => {
    // Date 생성자는 2026-02-30 을 3월 2일로 굴려버린다. 되굴려 확인해야 한다.
    expect(parseTripDate("2026-02-30")).toBeNull();
    expect(parseTripDate("2026-13-01")).toBeNull();
    expect(parseTripDate("")).toBeNull();
    expect(parseTripDate("2026-9-10")).toBeNull();
  });

  it("formats a date back into the input form", () => {
    expect(formatTripDate(new Date(2026, 8, 5))).toBe("2026-09-05");
  });

  it("normalizes a reversed selection into a forward range", () => {
    expect(normalizeSelectedRange("2026-09-12", "2026-09-10")).toEqual({
      startDate: "2026-09-10",
      endDate: "2026-09-12",
    });
  });

  it("leaves a forward selection untouched", () => {
    expect(normalizeSelectedRange("2026-09-10", "2026-09-12")).toEqual({
      startDate: "2026-09-10",
      endDate: "2026-09-12",
    });
  });

  it("counts days inclusively", () => {
    expect(tripDateDayCount("2026-09-10", "2026-09-12")).toBe(3);
    expect(tripDateDayCount("2026-09-10", "2026-09-10")).toBe(1);
    expect(tripDateDayCount("2026-09-10", "")).toBeNull();
  });

  it("counts days across a daylight-saving-free month boundary", () => {
    expect(tripDateDayCount("2026-08-30", "2026-09-02")).toBe(4);
  });

  it("builds a fixed 42 cell month grid starting on Sunday", () => {
    const days = buildCalendarDays(new Date(2026, 8, 1));
    expect(days).toHaveLength(42);
    expect(days[0].getDay()).toBe(0);
    // 2026-09-01 은 화요일이므로 그리드는 8월 30일(일)부터 시작한다.
    expect(formatTripDate(days[0])).toBe("2026-08-30");
    expect(formatTripDate(days[41])).toBe("2026-10-10");
  });

  it("moves months without drifting on long months", () => {
    expect(formatTripDate(addTripMonths(new Date(2026, 0, 31), 1))).toBe(
      "2026-02-01",
    );
    expect(formatTripDate(addTripMonths(new Date(2026, 8, 1), -1))).toBe(
      "2026-08-01",
    );
  });

  it("resolves the first day of the month that holds a date", () => {
    expect(formatTripDate(startOfTripMonth("2026-09-17"))).toBe("2026-09-01");
  });

  it("labels the month in Korean", () => {
    expect(formatTripCalendarMonth(new Date(2026, 8, 1))).toBe("2026년 9월");
  });

  it("tells whether a date sits inside the selected range", () => {
    expect(isTripDateInRange("2026-09-11", "2026-09-10", "2026-09-12")).toBe(
      true,
    );
    expect(isTripDateInRange("2026-09-10", "2026-09-10", "2026-09-12")).toBe(
      true,
    );
    expect(isTripDateInRange("2026-09-13", "2026-09-10", "2026-09-12")).toBe(
      false,
    );
  });
});
