import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlaceSuggestions } from "./PlaceSuggestions";

function boldOf(row: HTMLElement) {
  return Array.from(row.querySelectorAll("strong")).map((node) => node.textContent);
}

describe("PlaceSuggestions", () => {
  it("bolds the first match at the start of the name or after a space, else the first partial match", () => {
    render(
      <PlaceSuggestions
        onPick={vi.fn()}
        query="스타"
        suggestions={["아스타 스타벅스", "스타벅스 서울", "아스타리스크", "경복궁"]}
      />,
    );
    const list = screen.getByRole("list", { name: "완성 검색어" });
    const [afterSpace, atStart, partial, none] = within(list).getAllByRole("button");

    expect(boldOf(afterSpace)).toEqual(["스타"]);
    expect(afterSpace.innerHTML).toBe("아스타 <strong>스타</strong>벅스");
    expect(boldOf(atStart)).toEqual(["스타"]);
    expect(atStart.innerHTML).toBe("<strong>스타</strong>벅스 서울");
    expect(partial.innerHTML).toBe("아<strong>스타</strong>리스크");
    expect(boldOf(none)).toEqual([]);
    expect(none).toHaveTextContent("경복궁");
  });

  it("matches the bold part ignoring case and keeps the name's own letters", () => {
    render(<PlaceSuggestions onPick={vi.fn()} query="cgv" suggestions={["CGV 여수"]} />);

    expect(screen.getByRole("button", { name: "CGV 여수" }).innerHTML).toBe("<strong>CGV</strong> 여수");
  });

  it("hands the picked line's text to onPick", () => {
    const onPick = vi.fn();
    render(<PlaceSuggestions onPick={onPick} query="스타" suggestions={["아스타 스타벅스", "스타벅스 서울"]} />);

    fireEvent.click(screen.getByRole("button", { name: "스타벅스 서울" }));

    expect(onPick).toHaveBeenCalledExactlyOnceWith("스타벅스 서울");
  });

  it("keeps the search box focused: mouse down on a line and on the list is default-prevented", () => {
    render(<PlaceSuggestions onPick={vi.fn()} query="스타" suggestions={["스타벅스 서울"]} />);

    // fireEvent 는 기본 동작이 막히지 않았을 때만 true 를 돌려준다
    expect(fireEvent.mouseDown(screen.getByRole("button", { name: "스타벅스 서울" }))).toBe(false);
    expect(fireEvent.mouseDown(screen.getByRole("list", { name: "완성 검색어" }))).toBe(false);
  });

  it("draws nothing for an empty list", () => {
    const { container } = render(<PlaceSuggestions onPick={vi.fn()} query="스타" suggestions={[]} />);

    expect(container).toBeEmptyDOMElement();
  });
});
