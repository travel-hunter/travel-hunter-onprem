import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PreferredRegionSelector } from "./PreferredRegionSelector";

const regions = ["서울", "부산", "강원", "제주", "전남"];

describe("PreferredRegionSelector", () => {
  it("filters regions by search text and emits the selected region list", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <PreferredRegionSelector
        maxSelections={3}
        onChange={onChange}
        options={regions}
        value={[]}
      />,
    );

    await user.type(screen.getByLabelText("지역 검색"), "부");
    const grid = screen.getByLabelText("관심 지역 선택");

    expect(within(grid).getByRole("button", { name: "부산" })).toBeInTheDocument();
    expect(within(grid).queryByRole("button", { name: "서울" })).toBeNull();

    await user.click(within(grid).getByRole("button", { name: "부산" }));

    expect(onChange).toHaveBeenLastCalledWith(["부산"]);
  });

  it("enforces the max selection count while keeping selected cards removable", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <PreferredRegionSelector
        maxSelections={3}
        onChange={onChange}
        options={regions}
        value={["서울", "부산", "강원"]}
      />,
    );

    expect(screen.getByText("3/3 선택")).toHaveClass("active");
    expect(screen.getByText("서울 · 부산 · 강원")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "제주" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "부산" }));

    expect(onChange).toHaveBeenLastCalledWith(["서울", "강원"]);
  });

  it("normalizes stale values outside the option list and supports empty deselection", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <PreferredRegionSelector
        maxSelections={3}
        onChange={onChange}
        options={regions}
        value={["없는지역", "제주"]}
      />,
    );

    expect(screen.getByText("1/3 선택")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "제주" }));

    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("shows an empty selected-region summary before the first choice", () => {
    render(
      <PreferredRegionSelector
        maxSelections={3}
        onChange={vi.fn()}
        options={regions}
        value={[]}
      />,
    );

    expect(screen.getByText("선택된 관심지역")).toBeInTheDocument();
    expect(screen.getByText("아직 선택한 지역이 없어요.")).toBeInTheDocument();
  });
});
