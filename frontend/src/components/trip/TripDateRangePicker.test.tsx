import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TripDateRangePicker } from "./TripDateRangePicker";

const value = { startDate: "2026-09-10", endDate: "2026-09-12" };

function renderPicker(overrides: Partial<Parameters<typeof TripDateRangePicker>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <TripDateRangePicker value={value} onChange={onChange} {...overrides} />,
  );
  return { onChange, user: userEvent.setup() };
}

describe("TripDateRangePicker", () => {
  it("summarizes the current range and day count before opening", () => {
    renderPicker();
    const trigger = screen.getByTestId("trip-date-range-trigger");
    expect(trigger).toHaveTextContent("2026-09-10 ~ 2026-09-12");
    expect(trigger).toHaveTextContent("3일");
    expect(screen.queryByTestId("trip-date-range-calendar")).toBeNull();
  });

  it("opens the calendar on the summary card", async () => {
    const { user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    const calendar = screen.getByTestId("trip-date-range-calendar");
    expect(within(calendar).getByText("2026년 9월")).toBeInTheDocument();
    expect(within(calendar).getByText("첫날을 선택하세요")).toBeInTheDocument();
  });

  it("normalizes a reversed selection into a forward range", async () => {
    const { onChange, user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    await user.click(screen.getByRole("button", { name: "2026-09-15" }));
    await user.click(screen.getByRole("button", { name: "2026-09-11" }));
    expect(onChange).toHaveBeenLastCalledWith({
      startDate: "2026-09-11",
      endDate: "2026-09-15",
    });
  });

  it("collapses the range onto the first click before the second one", async () => {
    const { onChange, user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    await user.click(screen.getByRole("button", { name: "2026-09-15" }));
    // 첫 클릭은 시작과 끝을 같은 날로 모은다. 그래야 중간 상태에서 범위가 뒤집히지 않는다.
    expect(onChange).toHaveBeenLastCalledWith({
      startDate: "2026-09-15",
      endDate: "2026-09-15",
    });
    expect(
      screen.getByText("마지막 날을 선택하세요"),
    ).toBeInTheDocument();
  });

  it("moves to the previous and next month", async () => {
    const { user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    const calendar = screen.getByTestId("trip-date-range-calendar");
    await user.click(within(calendar).getByRole("button", { name: "이전 달" }));
    expect(within(calendar).getByText("2026년 8월")).toBeInTheDocument();
    await user.click(within(calendar).getByRole("button", { name: "다음 달" }));
    await user.click(within(calendar).getByRole("button", { name: "다음 달" }));
    expect(within(calendar).getByText("2026년 10월")).toBeInTheDocument();
  });

  it("marks the selected range on the grid", async () => {
    const { user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    expect(screen.getByRole("button", { name: "2026-09-10" })).toHaveClass(
      "range-start",
    );
    expect(screen.getByRole("button", { name: "2026-09-12" })).toHaveClass(
      "range-end",
    );
    expect(screen.getByRole("button", { name: "2026-09-11" })).toHaveClass(
      "in-range",
    );
    expect(screen.getByRole("button", { name: "2026-08-31" })).toHaveClass(
      "outside-month",
    );
  });

  it("closes on the done button", async () => {
    const { user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    await user.click(screen.getByRole("button", { name: "완료" }));
    expect(screen.queryByTestId("trip-date-range-calendar")).toBeNull();
  });

  it("keeps the calendar closed while disabled", async () => {
    const { user } = renderPicker({ disabled: true });
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    expect(screen.queryByTestId("trip-date-range-calendar")).toBeNull();
  });

  it("shows an error message tied to the trigger", () => {
    renderPicker({ error: "마지막 날은 첫날과 같거나 뒤여야 해요." });
    expect(
      screen.getByText("마지막 날은 첫날과 같거나 뒤여야 해요."),
    ).toBeInTheDocument();
  });

  it("writes no English into the calendar", async () => {
    const { user } = renderPicker();
    await user.click(screen.getByTestId("trip-date-range-trigger"));
    const calendar = screen.getByTestId("trip-date-range-calendar");
    expect(calendar.textContent ?? "").not.toMatch(/[A-Za-z]{3,}/);
  });
});
