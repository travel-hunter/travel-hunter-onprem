import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { apiConfig } from "../../api";
import { PlacePhoto } from "./PlacePhoto";

const url = "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg";

describe("PlacePhoto", () => {
  it("renders nothing without a url", () => {
    const { container, rerender } = render(<PlacePhoto alt="오동도" url={null} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" url={undefined} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" url="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the photo with its credit chip", () => {
    const { container } = render(<PlacePhoto alt="오동도 전경" url={url} />);

    const photo = screen.getByRole("img", { name: "오동도 전경" });
    expect(photo).toHaveAttribute("src", url);
    expect(container.querySelector(".place-photo")).not.toBeNull();
    expect(container.querySelector(".place-photo--compact")).toBeNull();
    expect(container.querySelector(".place-photo-credit")).toHaveTextContent("사진: 한국관광공사");
  });

  it("keeps the credit to the source only - the license type lives in the app-wide photo credits", () => {
    const { container } = render(<PlacePhoto alt="" url={url} />);

    expect(container.querySelector(".place-photo-credit")?.textContent).toBe("사진: 한국관광공사");
  });

  it("adds the compact modifier", () => {
    const { container } = render(<PlacePhoto alt="" compact url={url} />);

    expect(container.querySelector(".place-photo")).toHaveClass("place-photo--compact");
  });

  it("puts the API address in front of a photo the server stored", () => {
    render(<PlacePhoto alt="저장한 사진" url="/api/media/policy-photos/1.jpg" />);

    expect(screen.getByRole("img", { name: "저장한 사진" })).toHaveAttribute(
      "src",
      `${apiConfig.baseUrl}/api/media/policy-photos/1.jpg`,
    );
  });

  it("hides the photo and its credit when the image fails to load", () => {
    const { container } = render(<PlacePhoto alt="오동도" url={url} />);

    fireEvent.error(screen.getByRole("img", { name: "오동도" }));

    expect(container).toBeEmptyDOMElement();
  });

  it("tries the next url after a failure", () => {
    const { container, rerender } = render(<PlacePhoto alt="오동도" url={url} />);
    fireEvent.error(screen.getByRole("img", { name: "오동도" }));
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" url={`${url}?v=2`} />);

    expect(screen.getByRole("img", { name: "오동도" })).toHaveAttribute("src", `${url}?v=2`);
  });
});
