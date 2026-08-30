import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ALWAYS_AVAILABLE_POLICY_LABEL,
  UNKNOWN_DEADLINE_LABEL,
  daysUntilPolicyDeadline,
  dday,
  formatPolicyDeadlineTag,
} from "./utils";

const KST_MORNING = new Date("2026-08-21T02:00:00.000Z");
const KST_LATE_NIGHT = new Date("2026-08-21T14:59:59.000Z");

afterEach(() => vi.useRealTimers());

function setCurrentTime(now: Date) {
  vi.useFakeTimers();
  vi.setSystemTime(now);
}

describe("policy deadline calendar labels", () => {
  it("treats the full KST calendar date as D-day", () => {
    expect(daysUntilPolicyDeadline("2026-08-21", KST_MORNING)).toBe(0);
    expect(daysUntilPolicyDeadline("2026-08-21", KST_LATE_NIGHT)).toBe(0);
    setCurrentTime(KST_MORNING);
    expect(dday("2026-08-21")).toBe("D-day");
    expect(formatPolicyDeadlineTag({ deadline: "2026-08-21" })).toBe("D-day \uB9C8\uAC10");
  });

  it("uses calendar-day distance for future deadlines", () => {
    expect(daysUntilPolicyDeadline("2026-08-22", KST_MORNING)).toBe(1);
    expect(daysUntilPolicyDeadline("2026-08-23", KST_MORNING)).toBe(2);
    setCurrentTime(KST_MORNING);
    expect(dday("2026-08-22")).toBe("D-1");
    expect(dday("2026-08-23")).toBe("D-2");
  });

  it("renders past deadlines once without duplicate copy", () => {
    expect(daysUntilPolicyDeadline("2026-08-20", KST_MORNING)).toBe(-1);
    setCurrentTime(KST_MORNING);
    expect(dday("2026-08-20")).toBe("\uB9C8\uAC10");
    expect(formatPolicyDeadlineTag({ deadline: "2026-08-20" })).toBe("\uB9C8\uAC10");
  });

  it("preserves unknown and always-issued labels", () => {
    setCurrentTime(KST_MORNING);
    expect(dday("not-a-date")).toBe(UNKNOWN_DEADLINE_LABEL);
    expect(formatPolicyDeadlineTag({ deadline: "" })).toBe(UNKNOWN_DEADLINE_LABEL);
    expect(formatPolicyDeadlineTag({
      title: "[\uAD00\uAD11\uC8FC\uBBFC\uCE74\uB4DC]",
      deadline: "",
      officialUrl: "/dgtourcard/biz/regn/regnMain.do",
    })).toBe(ALWAYS_AVAILABLE_POLICY_LABEL);
  });
});
