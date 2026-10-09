import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PublicPlaceItem } from "../../../api";
import { PlaceMatchChoices } from "./PlaceMatchChoices";

const withPhoto: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  photoUrl: "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
  photoLicense: "Type3",
  distanceMeters: 4,
};
const withoutPhoto: PublicPlaceItem = {
  source: "sangga",
  sourceId: "MA010120220800000002",
  name: "오동도 공원",
  address: "전남 여수시 수정동 1",
  latitude: 34.745,
  longitude: 127.766,
  category: "culture",
  distanceMeters: 340,
};

function renderChoices(onChoose = vi.fn(), onNone = vi.fn()) {
  render(<PlaceMatchChoices candidates={[withPhoto, withoutPhoto]} onChoose={onChoose} onNone={onNone} />);
  return screen.getByRole("region", { name: "이 장소가 맞나요?" });
}

describe("PlaceMatchChoices", () => {
  it("lists each candidate with its name, category, address and distance", () => {
    const group = renderChoices();

    const first = within(group).getByRole("button", { name: "오동도 선택" });
    expect(first).toHaveTextContent("관광지");
    expect(first).toHaveTextContent("전남 여수시 오동도로 222");
    expect(first).toHaveTextContent("고른 곳과 같은 자리");
    const second = within(group).getByRole("button", { name: "오동도 공원 선택" });
    expect(second).toHaveTextContent("문화시설");
    expect(second).toHaveTextContent("고른 곳에서 약 340m");
  });

  it("gives two candidates with the same name different button names that carry the category, address and distance", () => {
    const twin: PublicPlaceItem = { ...withoutPhoto, name: "오동도", address: "전남 여수시 수정동 3", category: "food", distanceMeters: 120 };
    render(<PlaceMatchChoices candidates={[withPhoto, twin]} onChoose={vi.fn()} onNone={vi.fn()} />);

    const first = screen.getByRole("button", { name: "오동도 선택 · 관광지 · 전남 여수시 오동도로 222 · 고른 곳과 같은 자리" });
    const second = screen.getByRole("button", { name: /^오동도 선택 · .* · 전남 여수시 수정동 3 · 고른 곳에서 약 120m$/ });
    expect(first).not.toBe(second);
  });

  it("shows a small photo with its credit only for a candidate that has a photo", () => {
    const group = renderChoices();

    const first = within(group).getByRole("button", { name: "오동도 선택" });
    expect(first.querySelector("img")).toHaveAttribute("src", withPhoto.photoUrl);
    expect(first).toHaveTextContent("사진: 한국관광공사 · 변경 금지");
    const second = within(group).getByRole("button", { name: "오동도 공원 선택" });
    expect(second.querySelector("img")).toBeNull();
    expect(second).not.toHaveTextContent("사진:");
  });

  it("hides a photo that fails to load together with its credit", () => {
    const group = renderChoices();
    const first = within(group).getByRole("button", { name: "오동도 선택" });

    fireEvent.error(first.querySelector("img") as HTMLImageElement);

    expect(first.querySelector("img")).toBeNull();
    expect(first).not.toHaveTextContent("사진:");
  });

  it("reports the candidate the user picked", () => {
    const onChoose = vi.fn();
    const group = renderChoices(onChoose);

    fireEvent.click(within(group).getByRole("button", { name: "오동도 공원 선택" }));

    expect(onChoose).toHaveBeenCalledExactlyOnceWith(withoutPhoto);
  });

  it("offers to write the place by hand when none of the candidates is right", () => {
    const onNone = vi.fn();
    const group = renderChoices(vi.fn(), onNone);

    fireEvent.click(within(group).getByRole("button", { name: "아니요, 직접 적을게요" }));

    expect(onNone).toHaveBeenCalledTimes(1);
  });
});
