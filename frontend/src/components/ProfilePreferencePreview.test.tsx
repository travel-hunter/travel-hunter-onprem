import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProfilePreferencePreview } from "./ProfilePreferencePreview";

describe("ProfilePreferencePreview", () => {
  it("summarizes selected recommendation criteria", () => {
    render(
      <ProfilePreferencePreview
        profile={{
          preferredRegions: ["부산", "강원"],
          style: "사진",
          budget: "상관없음",
        }}
      />,
    );

    const preview = screen.getByLabelText("현재 추천 기준");
    expect(within(preview).getByText("부산 · 강원")).toBeInTheDocument();
    expect(within(preview).getByText("사진")).toBeInTheDocument();
    expect(within(preview).getByText("상관없음")).toBeInTheDocument();
  });

  it("shows an unset region label when preferred regions are absent", () => {
    render(
      <ProfilePreferencePreview
        profile={{
          preferredRegions: null,
          style: null,
          budget: null,
        }}
      />,
    );

    const preview = screen.getByLabelText("현재 추천 기준");
    expect(within(preview).getByText("관심지역 미정")).toBeInTheDocument();
    expect(within(preview).getByText("스타일 미정")).toBeInTheDocument();
    expect(within(preview).getByText("예산 미정")).toBeInTheDocument();
  });

  it("allows a context-specific preview callout", () => {
    render(
      <ProfilePreferencePreview
        cta="저장하면 홈 추천과 맞춤 일정에 바로 반영됩니다."
        profile={{
          preferredRegions: ["제주"],
          style: "휴식",
          budget: "1인 40만원 이하",
        }}
      />,
    );

    expect(screen.getByText("저장하면 홈 추천과 맞춤 일정에 바로 반영됩니다.")).toBeInTheDocument();
  });
});
