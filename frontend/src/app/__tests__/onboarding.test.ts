import { describe, expect, it } from "vitest";
import type { User } from "../../api";
import { getOnboardingPath } from "../onboarding";

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    nickname: "여행러",
    email: "user@example.com",
    role: "user",
    hasPassword: true,
    preferredRegions: null,
    persona: "Travel Hunter 사용자",
    savedAmount: 0,
    onboardingCompleted: false,
    nicknameSetupCompleted: false,
    socialAccounts: [{ provider: "google", providerNickname: "Google User", connectedAt: "2026-06-17T00:00:00Z" }],
    createdAt: "2026-06-17T00:00:00Z",
    updatedAt: "2026-06-17T00:00:00Z",
    ...overrides,
  };
}

describe("getOnboardingPath", () => {
  it("keeps social 신규 사용자 on nickname setup until nickname is confirmed", () => {
    expect(getOnboardingPath(makeUser())).toBe("/nickname-setup");
  });

  it("moves to profile setup after nickname confirmation while onboarding is incomplete", () => {
    expect(
      getOnboardingPath(
        makeUser({
          nickname: "확정닉네임",
          nicknameSetupCompleted: true,
        }),
      ),
    ).toBe("/profile-setup");
  });

  it("does not re-enter onboarding after completion", () => {
    expect(
      getOnboardingPath(
        makeUser({
          onboardingCompleted: true,
          nicknameSetupCompleted: true,
        }),
      ),
    ).toBeNull();
  });
});
