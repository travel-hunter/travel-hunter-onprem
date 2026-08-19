import { afterEach, describe, expect, it, vi } from "vitest";
import { formatPolicyDeadlineTag } from "./utils";

describe("policy deadline formatting", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not repeat the deadline label for ended policies", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-19T00:00:00.000Z"));

    expect(formatPolicyDeadlineTag({ deadline: "2026-08-17" })).toBe("마감");
  });
});
