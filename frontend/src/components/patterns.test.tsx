import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthFormShell, HomeRail, ProfilePanel, ProfileSetupStep } from "./patterns";
import { StatusPanel, SurfaceCard, Tag } from "./ui";

describe("design-system primitives", () => {
  it("renders design-system tags with semantic tone classes", () => {
    render(
      <MemoryRouter>
        <div>
          <Tag tone="draft">작성 중</Tag>
          <Tag tone="confirmed">확정됨</Tag>
          <Tag tone="benefit">예상 혜택</Tag>
        </div>
      </MemoryRouter>,
    );

    expect(screen.getByText("작성 중")).toHaveClass("tag", "draft");
    expect(screen.getByText("확정됨")).toHaveClass("tag", "confirmed");
    expect(screen.getByText("예상 혜택")).toHaveClass("tag", "benefit");
  });

  it("renders surface cards and status panels with design-system classes", () => {
    render(
      <MemoryRouter>
        <SurfaceCard tone="confirmed" className="test-card">
          <span>카드 내용</span>
        </SurfaceCard>
        <StatusPanel
          tone="draft"
          badge="작성 중"
          title="편집 가능"
          body="확정 전까지 수정할 수 있습니다."
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("카드 내용").closest(".ds-card")).toHaveClass(
      "confirmed",
      "test-card",
    );
    expect(
      screen.getByText("편집 가능").closest(".ds-status-panel"),
    ).toHaveClass("draft");
  });
});

describe("design-system pattern contracts", () => {
  it("renders mapped pattern components with stable classes", () => {
    render(
      <MemoryRouter>
        <AuthFormShell title="로그인" body="계속하려면 로그인하세요">
          <button type="button">계속</button>
        </AuthFormShell>
        <HomeRail title="이번 주 혜택">
          <a href="/policies">정책 보기</a>
        </HomeRail>
        <ProfilePanel title="프로필" meta="test@example.com">
          <span>프로필 내용</span>
        </ProfilePanel>
        <ProfileSetupStep
          eyebrow="1/3"
          title="관심 지역"
          body="지역을 선택하세요"
        >
          <button type="button">제주</button>
        </ProfileSetupStep>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("로그인").closest(".ds-auth-form-shell"),
    ).toBeTruthy();
    expect(
      screen.getByText("이번 주 혜택").closest(".ds-home-rail"),
    ).toBeTruthy();
    expect(
      screen.getByText("프로필").closest(".ds-profile-panel"),
    ).toBeTruthy();
    expect(
      screen.getByText("관심 지역").closest(".ds-profile-setup-step"),
    ).toBeTruthy();
  });
});
