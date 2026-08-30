import { describe, expect, it } from "vitest";
import {
  addDaysToDateInput,
  getDefaultTripDateRange,
  getKstDateInputValue,
  normalizeTripDateRange,
} from "./dateDefaults";

describe("date defaults", () => {
  it("formats the current KST date for date inputs", () => {
    expect(getKstDateInputValue(new Date("2026-05-17T15:30:00.000Z"))).toBe("2026-05-18");
  });

  it("builds a default three day trip range from KST today", () => {
    expect(getDefaultTripDateRange(new Date("2026-05-18T00:00:00.000Z"))).toEqual({
      startDate: "2026-05-18",
      endDate: "2026-05-20",
    });
  });

  it("adds days to a date input value", () => {
    expect(addDaysToDateInput("2026-05-30", 2)).toBe("2026-06-01");
  });

  it("swaps a reversed trip date range so the day count can never go negative", () => {
    expect(normalizeTripDateRange("2026-05-20", "2026-05-18")).toEqual({
      startDate: "2026-05-18",
      endDate: "2026-05-20",
    });
  });

  it("leaves an ordered or single-day range untouched", () => {
    expect(normalizeTripDateRange("2026-05-18", "2026-05-20")).toEqual({
      startDate: "2026-05-18",
      endDate: "2026-05-20",
    });
    expect(normalizeTripDateRange("2026-05-18", "2026-05-18")).toEqual({
      startDate: "2026-05-18",
      endDate: "2026-05-18",
    });
  });

  it("leaves incomplete input alone so the caller can still report it", () => {
    expect(normalizeTripDateRange("", "2026-05-18")).toEqual({
      startDate: "",
      endDate: "2026-05-18",
    });
    expect(normalizeTripDateRange("2026-05-18", "")).toEqual({
      startDate: "2026-05-18",
      endDate: "",
    });
  });
});
