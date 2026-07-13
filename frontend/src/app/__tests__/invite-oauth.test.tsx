import {
  cleanup,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type InviteLinksState,
  type InviteRole,
  type InviteState,
  type Trip,
} from "../../api";
import {
  examplePolicyDetail,
  examplePolicyPath,
  getPreviewTrip,
  testEmail,
  testPassword,
} from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";


const acceptedAgreements = {
  termsAccepted: true,
  privacyAccepted: true,
  termsVersion: "2026-06-26",
  privacyVersion: "2026-06-26",
};

function makeInviteState(overrides: Partial<InviteState> = {}): InviteState {
  return {
    id: "9",
    tripId: "55",
    inviteToken: "abc",
    inviteUrl: "http://127.0.0.1:5173/invites/abc/accept",
    expiresAt: "2026-06-30T00:00:00Z",
    createdAt: "2026-05-04T00:00:00Z",
    acceptedAt: null,
    invited: false,
    copied: false,
    role: "editor",
    alreadyMember: false,
    ...overrides,
  };
}

function makeInviteLinksState(overrides: Partial<InviteLinksState> = {}): InviteLinksState {
  return {
    tripId: "55",
    viewer: makeInviteState({
      id: "10",
      inviteToken: "viewer-token",
      inviteUrl: "http://127.0.0.1:5173/invites/viewer-token/accept",
      role: "viewer",
    }),
    editor: makeInviteState({
      id: "11",
      inviteToken: "editor-token",
      inviteUrl: "http://127.0.0.1:5173/invites/editor-token/accept",
      role: "editor",
    }),
    ...overrides,
  };
}

describe("Travel Hunter app — profile, invites, OAuth & sharing", () => {
  it("saves profile setup choices before showing the personalized home", async () => {
    await login();
    cleanup();
    renderAppRoute("/profile-setup");
    const user = userEvent.setup();

    await waitFor(() =>
      expect(document.querySelector(".profile-setup-preference-card")).toBeTruthy(),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "어디로 떠나고 싶나요?" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("현재 추천 기준")).toBeInTheDocument();
    const regionGrid = document.querySelector(".preferred-region-grid");
    expect(regionGrid).toBeTruthy();
    const busanButton = screen.getByRole("button", { name: "부산" });
    expect(busanButton).toHaveClass("preferred-region-card");
    if (busanButton.getAttribute("aria-pressed") !== "true") {
      await user.click(busanButton);
    }
    await user.click(screen.getByRole("button", { name: "다음" }));
    const styleButton = screen.getByRole("button", { name: "맛집" });
    expect(styleButton).toHaveClass("preference-choice-card");
    await user.click(styleButton);
    await user.click(screen.getByRole("button", { name: "다음" }));
    await user.click(screen.getByRole("button", { name: "1인 30만원 이하" }));
    await user.click(screen.getByRole("button", { name: "추천 홈 보기" }));

    await waitFor(() => expect(document.body).toHaveTextContent("안녕,"));
    expect(document.body).toHaveTextContent("AI 추천 맞춤 일정");
    expect(screen.queryByLabelText("인기 국내 여행지 목록")).toBeNull();
    expect(document.body).toHaveTextContent(/코스 만들기/);
  });

  it("renders separate invite links and prepares each role independently", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "Invite role trip",
    };
    const inviteLinks = makeInviteLinksState();
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const getInviteSpy = vi
      .spyOn(appDataApi, "getInviteState")
      .mockResolvedValue(inviteLinks);
    const confirmInviteSpy = vi
      .spyOn(appDataApi, "confirmInviteSent")
      .mockImplementation(async (tripId, role: InviteRole = "editor") =>
        makeInviteState({
          tripId: tripId ?? "55",
          role,
          inviteToken: `${role}-prepared-token`,
          inviteUrl: `http://127.0.0.1:5173/invites/${role}-prepared-token/accept`,
          invited: true,
        }),
      );

    try {
      await login();
      cleanup();
      renderAppRoute("/friend-invite?tripId=55");
      const user = userEvent.setup();

      await waitFor(() => expect(getInviteSpy).toHaveBeenCalledWith("55"));
      expect(await screen.findByText("http://127.0.0.1:5173/invites/viewer-token/accept")).toBeInTheDocument();
      expect(screen.getByText("http://127.0.0.1:5173/invites/editor-token/accept")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "보기 링크 만들기" }));
      await waitFor(() =>
        expect(confirmInviteSpy).toHaveBeenCalledWith("55", "viewer"),
      );

      await user.click(screen.getByRole("button", { name: "함께 편집 링크 준비 완료" }));
      await waitFor(() =>
        expect(confirmInviteSpy).toHaveBeenLastCalledWith("55", "editor"),
      );
    } finally {
      getTripSpy.mockRestore();
      getInviteSpy.mockRestore();
      confirmInviteSpy.mockRestore();
    }
  });

  it("requests a password reset email from the forgot password page", async () => {
    const requestSpy = vi
      .spyOn(appDataApi, "requestPasswordReset")
      .mockResolvedValue({ requested: true });

    try {
      renderAppRoute("/forgot-password");
      expect(document.querySelector("main")).toHaveClass(
        "prototype-login-layout",
      );
      expect(document.querySelector(".prototype-auth-screen")).toBeTruthy();
      expect(document.querySelector(".ds-auth-form-shell")).toBeTruthy();
      const user = userEvent.setup();

      await user.type(
        screen.getByRole("textbox", { name: "이메일" }),
        testEmail,
      );
      await user.click(
        screen.getByRole("button", { name: "재설정 링크 받기" }),
      );

      await waitFor(() =>
        expect(requestSpy).toHaveBeenCalledWith({ email: testEmail }),
      );
      expect(
        await screen.findByText(
          "재설정 링크 요청을 접수했어요. 계정이 있는 이메일이면 메일이 도착합니다.",
        ),
      ).toBeInTheDocument();
    } finally {
      requestSpy.mockRestore();
    }
  });

  it("confirms a password reset token and links back to login", async () => {
    const confirmSpy = vi
      .spyOn(appDataApi, "confirmPasswordReset")
      .mockResolvedValue({ reset: true });

    try {
      renderAppRoute("/reset-password?token=abc123");
      const user = userEvent.setup();

      await user.type(
        document.querySelector('input[name="password"]') as HTMLInputElement,
        "new-password123",
      );
      await user.click(screen.getByRole("button", { name: "비밀번호 변경" }));

      await waitFor(() =>
        expect(confirmSpy).toHaveBeenCalledWith({
          token: "abc123",
          newPassword: "new-password123",
        }),
      );
      expect(document.body).toHaveTextContent("비밀번호를 변경했어요");
    } finally {
      confirmSpy.mockRestore();
    }
  });

  it("shows missing email delivery configuration on the forgot password page", async () => {
    const requestSpy = vi
      .spyOn(appDataApi, "requestPasswordReset")
      .mockRejectedValue(new Error("Email delivery is not configured"));

    try {
      renderAppRoute("/forgot-password");
      const user = userEvent.setup();

      await user.type(
        screen.getByRole("textbox", { name: "이메일" }),
        testEmail,
      );
      await user.click(screen.getByRole("button", { name: "재설정 링크 받기" }));

      await waitFor(() => expect(requestSpy).toHaveBeenCalledWith({ email: testEmail }));
      expect(
        await screen.findByText(
          "현재 로컬 환경은 이메일 발송 설정이 없어 재설정 링크를 보낼 수 없어요. SMTP 설정 후 다시 시도해 주세요.",
        ),
      ).toBeInTheDocument();
    } finally {
      requestSpy.mockRestore();
    }
  });

  it("shows a clear reset-password missing token state", () => {
    renderAppRoute("/reset-password");

    expect(screen.getByText("재설정 링크가 올바르지 않아요")).toBeInTheDocument();
    expect(
      screen.getByText("이메일에 있는 전체 링크를 다시 열거나 새 재설정 링크를 요청해 주세요."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "새 링크 요청하기" })).toBeInTheDocument();
  });

  it("offers a new reset link when a reset token is invalid or expired", async () => {
    const confirmSpy = vi
      .spyOn(appDataApi, "confirmPasswordReset")
      .mockRejectedValue(new Error("Invalid or expired reset token"));

    try {
      renderAppRoute("/reset-password?token=expired-token");
      const user = userEvent.setup();

      await user.type(screen.getByLabelText("새 비밀번호"), "new-password123");
      await user.click(screen.getByRole("button", { name: "비밀번호 변경" }));

      await waitFor(() =>
        expect(confirmSpy).toHaveBeenCalledWith({
          token: "expired-token",
          newPassword: "new-password123",
        }),
      );
      expect(
        await screen.findByText("비밀번호를 재설정하지 못했어요. 링크가 만료되었거나 이미 사용되었을 수 있어요."),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "새 재설정 링크를 요청하기" }),
      ).toBeInTheDocument();
    } finally {
      confirmSpy.mockRestore();
    }
  });

  it("links social login buttons to backend OAuth start routes", () => {
    renderAppRoute("/login");

    expect(screen.getByRole("link", { name: "카카오로 시작하기" })).toHaveAttribute(
      "href",
      "/oauth/kakao/start?redirect=%2Fhome",
    );
    expect(screen.getByRole("link", { name: "구글로 시작하기" })).toHaveAttribute(
      "href",
      "/oauth/google/start?redirect=%2Fhome",
    );
  });

  it("shows a local-friendly OAuth start error when a provider is not configured", async () => {
    const oauthSpy = vi
      .spyOn(appDataApi, "getOAuthStartUrl")
      .mockReturnValue("http://127.0.0.1:8000/api/auth/oauth/kakao/start?redirect=%2Fhome");
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "OAuth provider is not configured" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    try {
      renderAppRoute("/oauth/kakao/start?redirect=/home");

      await waitFor(() =>
        expect(fetchSpy).toHaveBeenCalledWith(
          "http://127.0.0.1:8000/api/auth/oauth/kakao/start?redirect=%2Fhome",
          {
            credentials: "include",
            redirect: "manual",
          },
        ),
      );
      expect(await screen.findByText("카카오 로그인을 사용할 수 없어요")).toBeInTheDocument();
      expect(
        screen.getByText(
          "카카오 로그인을 사용할 수 없어요. OAuth provider is not configured",
        ),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "이메일로 로그인하기" })).toBeInTheDocument();
    } finally {
      oauthSpy.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it("uses the server pending social redirect when completing social signup", async () => {
    const pendingSpy = vi.spyOn(appDataApi, "getPendingSocialSignup").mockResolvedValue({
      provider: "google",
      email: "social@example.com",
      nickname: "소셜유저",
      expiresAt: "2026-06-26T10:00:00Z",
      redirectPath: "/invites/server-token/accept",
    });
    const completeSpy = vi.spyOn(appDataApi, "completeSocialSignup").mockResolvedValue({
      accessToken: "social-access-token",
      user: {
        id: "social-user",
        nickname: "소셜유저",
        email: "social@example.com",
        role: "user",
        hasPassword: false,
                        preferredRegions: null,
        persona: "소셜유저님",
        savedAmount: 0,
        onboardingCompleted: true,
        nicknameSetupCompleted: true,
        socialAccounts: [{ provider: "google", providerNickname: "소셜유저", connectedAt: "2026-06-26T00:00:00Z" }],
        createdAt: "2026-06-26T00:00:00Z",
        updatedAt: "2026-06-26T00:00:00Z",
      },
    });
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["서울"],
      style: "휴식",
      budget: "1인 40만원 이하",
    });
    const acceptInviteSpy = vi
      .spyOn(appDataApi, "acceptInvite")
      .mockResolvedValue(makeInviteState({ inviteToken: "server-token", invited: true, acceptedAt: "2026-06-26T00:00:00Z" }));

    try {
      renderAppRoute("/signup/social-agreement?token=pending-social-token&redirect=/home");

      await waitFor(() => expect(screen.getAllByRole("heading", { name: "소셜 가입 약관 동의" }).length).toBeGreaterThan(0));
      expect(await screen.findByText("social@example.com")).toBeInTheDocument();

      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: /전체 동의/ }));
      await user.click(screen.getByRole("button", { name: "동의하고 가입 완료" }));

      await waitFor(() =>
        expect(completeSpy).toHaveBeenCalledWith({ token: "pending-social-token", agreements: acceptedAgreements }),
      );
      await waitFor(() => expect(acceptInviteSpy).toHaveBeenCalledWith("server-token"));
      expect(pendingSpy).toHaveBeenCalledWith("pending-social-token");
    } finally {
      pendingSpy.mockRestore();
      completeSpy.mockRestore();
      getProfileSpy.mockRestore();
      acceptInviteSpy.mockRestore();
    }
  });

  it("shows a local-friendly OAuth callback error", async () => {
    const refreshSpy = vi.spyOn(appDataApi, "refreshSession");

    try {
      renderAppRoute("/oauth/callback?error=email_policy&redirect=/home");

      expect(await screen.findByText("소셜 로그인을 사용할 수 없어요")).toBeInTheDocument();
      expect(screen.getByText("로그인을 완료하지 못했어요")).toBeInTheDocument();
      expect(
        screen.getByText("검증된 이메일이 확인된 소셜 계정만 연결할 수 있어요. 이메일로 로그인해 주세요."),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "로그인으로 돌아가기" })).toBeInTheDocument();
    } finally {
      refreshSpy.mockRestore();
    }
  });

  it("shows an OAuth cancellation message", async () => {
    renderAppRoute("/oauth/callback?error=access_denied&redirect=/home");

    expect(await screen.findByText("소셜 로그인을 사용할 수 없어요")).toBeInTheDocument();
    expect(
      screen.getByText("소셜 로그인 동의가 완료되지 않았어요. 다시 시도하거나 이메일로 로그인해 주세요."),
    ).toBeInTheDocument();
  });

  it("shares the current policy URL through Web Share API", async () => {
    const shareSpy = vi.fn().mockResolvedValue(undefined);
    const navigatorPrototype = Object.getPrototypeOf(
      window.navigator,
    ) as Navigator & { share?: typeof shareSpy };
    const originalShareDescriptor = Object.getOwnPropertyDescriptor(
      navigatorPrototype,
      "share",
    );
    Object.defineProperty(navigatorPrototype, "share", {
      configurable: true,
      value: shareSpy,
    });

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);

      await userEvent
        .setup()
        .click(await screen.findByRole("button", { name: "공유" }));

      expect(
        screen.queryByRole("link", { name: /친구 초대/ }),
      ).not.toBeInTheDocument();
      await waitFor(() => expect(shareSpy).toHaveBeenCalled());
      await waitFor(() =>
        expect(document.body).toHaveTextContent("정책 링크를 공유했어요"),
      );
    } finally {
      if (originalShareDescriptor) {
        Object.defineProperty(
          navigatorPrototype,
          "share",
          originalShareDescriptor,
        );
      } else {
        Reflect.deleteProperty(navigatorPrototype, "share");
      }
    }
  });

  it("renders policy documents as static checklist rows", async () => {
    const getPolicySpy = vi
      .spyOn(appDataApi, "getPolicy")
      .mockResolvedValue(examplePolicyDetail);

    try {
      await login();
      cleanup();
      renderAppRoute(examplePolicyPath);

      await waitFor(() => expect(document.body).toHaveTextContent("필요 서류"));
      expect(document.querySelectorAll(".check-item").length).toBeGreaterThan(0);
      expect(document.querySelector(".check-item")?.tagName).toBe("DIV");
    } finally {
      getPolicySpy.mockRestore();
    }
  });

  it("redirects the legacy AI recommendation route into trip detail", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "초대 테스트 추천 여행",
      days: { 1: [], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    await login();
    cleanup();
    try {
      renderAppRoute("/ai-results?tripId=55");

      await waitFor(() =>
        expect(screen.getAllByText("초대 테스트 추천 여행").length).toBeGreaterThan(0),
      );
      expect(getTripSpy).toHaveBeenCalledWith("55");
      expect(document.querySelector(".ai-results-screen")).toBeNull();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("preserves an invite redirect through login and signup navigation", async () => {
    renderAppRoute("/invites/jeju-3d/accept");

    await waitFor(() =>
      expect(screen.getByText("트래블헌터 일정 초대입니다")).toBeInTheDocument(),
    );

    expect(
      screen.getByText("일정 상세 내용은 로그인 또는 회원가입 후 초대를 수락한 뒤 확인할 수 있습니다."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("초대가 만료됐으면 초대한 사람에게 새 초대 링크를 요청하세요."),
    ).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("link", { name: "회원가입하고 수락하기" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "회원가입" }),
      ).toBeInTheDocument(),
    );
    const loginLink = screen.getByRole("link", { name: "로그인" });
    expect(decodeURIComponent(loginLink.getAttribute("href") ?? "")).toBe(
      "/login?redirect=/invites/jeju-3d/accept",
    );
  });

  it("shares the invite link from the friend invite page", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      currentUserRole: "editor",
      title: "Invite share trip",
    };
    const inviteLinks = makeInviteLinksState();
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const getInviteSpy = vi
      .spyOn(appDataApi, "getInviteState")
      .mockResolvedValue(inviteLinks);

    try {
      await login();
      cleanup();
      renderAppRoute("/friend-invite?tripId=55");

      await waitFor(() => expect(getInviteSpy).toHaveBeenCalledWith("55"));
      await userEvent
        .setup()
        .click(await screen.findByRole("button", { name: "보기만 가능 링크 복사" }));

      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: "복사됨" }),
        ).toBeInTheDocument(),
      );
      await waitFor(() =>
        expect(document.querySelector(".toast")).toBeTruthy(),
      );
    } finally {
      getTripSpy.mockRestore();
      getInviteSpy.mockRestore();
    }
  });

  it("sends an invite email while preserving the fallback invite link", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      currentUserRole: "editor",
      title: "Invite email trip",
    };
    const inviteLinks = makeInviteLinksState();
    const viewerInvite = inviteLinks.viewer ?? makeInviteState({ role: "viewer" });
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const getInviteSpy = vi.spyOn(appDataApi, "getInviteState").mockResolvedValue(inviteLinks);
    const sendInviteEmailSpy = vi.spyOn(appDataApi, "sendInviteEmail").mockResolvedValue({
      invite: { ...viewerInvite, invited: true },
      deliveryStatus: "notConfigured",
      message: "Email delivery is not configured.",
    });

    try {
      await login();
      cleanup();
      renderAppRoute("/friend-invite?tripId=55");
      const user = userEvent.setup();

      await waitFor(() => expect(getInviteSpy).toHaveBeenCalledWith("55"));
      await user.type(screen.getByRole("textbox", { name: "보기만 가능 친구 email" }), "friend@example.com");
      await user.click(screen.getByRole("button", { name: "보기만 가능 email 보내기" }));

      await waitFor(() =>
        expect(sendInviteEmailSpy).toHaveBeenCalledWith("55", {
          email: "friend@example.com",
          role: "viewer",
        }),
      );
      expect(await screen.findByText("email 발송 설정이 아직 없어요. 해당 권한 링크를 복사해 직접 보내 주세요.")).toBeInTheDocument();
      expect(document.body).toHaveTextContent("http://127.0.0.1:5173/invites/viewer-token/accept");
    } finally {
      getTripSpy.mockRestore();
      getInviteSpy.mockRestore();
      sendInviteEmailSpy.mockRestore();
    }
  });

  it("blocks direct friend invite management for viewer trip members", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      currentUserRole: "viewer",
      title: "Editor member trip",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const getInviteSpy = vi.spyOn(appDataApi, "getInviteState").mockRejectedValue(new Error("Trip not found"));
    const confirmInviteSpy = vi.spyOn(appDataApi, "confirmInviteSent");
    const sendInviteEmailSpy = vi.spyOn(appDataApi, "sendInviteEmail");

    try {
      await login();
      cleanup();
      renderAppRoute("/friend-invite?tripId=55");

      expect(
        await screen.findByText("친구 초대는 일정 owner/editor 멤버만 관리할 수 있어요. 일정 상세로 돌아가 현재 권한을 확인해 주세요."),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "초대 링크 활성화" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "email 초대 보내기" })).not.toBeInTheDocument();
      expect(confirmInviteSpy).not.toHaveBeenCalled();
      expect(sendInviteEmailSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      getInviteSpy.mockRestore();
      confirmInviteSpy.mockRestore();
      sendInviteEmailSpy.mockRestore();
    }
  });

  it("accepts a valid invite after login and links to the joined trip", async () => {
    renderAppRoute("/login?redirect=/invites/jeju-3d/accept");

    const user = userEvent.setup();
    await user.type(
      document.querySelector('input[name="email"]') as HTMLInputElement,
      testEmail,
    );
    await user.type(
      document.querySelector('input[name="password"]') as HTMLInputElement,
      testPassword,
    );
    await user.click(
      document.querySelector('button[type="submit"]') as HTMLButtonElement,
    );

    await waitFor(() =>
      expect(document.body).toHaveTextContent(/초대를 수락했어요|이미 참여 중인 일정입니다/),
    );
    const tripLink = await waitFor(() => {
      const link = document.querySelector('a[href^="/trips/"]');
      expect(link).toBeTruthy();
      return link as HTMLAnchorElement;
    });
    expect(tripLink.getAttribute("href")).toMatch(/^\/trips\/[1-9][0-9]*$/);
  });

  it("accepts a valid invite after signup when a redirect is present", async () => {
    const email = `invite-${Date.now()}@example.com`;
    const signupSpy = vi
      .spyOn(appDataApi, "requestSignupVerification")
      .mockResolvedValue({ verificationRequired: true, email });
    const verifySpy = vi
      .spyOn(appDataApi, "verifySignup")
      .mockResolvedValue({ verified: true, email });
    const completeSpy = vi.spyOn(appDataApi, "completeSignup").mockResolvedValue({
      accessToken: "signup-access-token",
      user: {
        id: "signup-user",
        nickname: "초대테스트",
        email,
        role: "user",
        hasPassword: true,
                            preferredRegions: null,
        persona: "초대테스트님",
        savedAmount: 0,
        onboardingCompleted: true,
        nicknameSetupCompleted: true,
        socialAccounts: [],
        createdAt: "2026-06-15T00:00:00Z",
        updatedAt: "2026-06-15T00:00:00Z",
      },
    });
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: ["제주"],
      style: "휴식",
      budget: "1인 40만원 이하",
    });
    const acceptInviteSpy = vi
      .spyOn(appDataApi, "acceptInvite")
      .mockResolvedValue(makeInviteState({ invited: true, acceptedAt: "2026-06-15T00:00:00Z" }));

    try {
      renderAppRoute("/signup?redirect=/invites/jeju-3d/accept");
      expect(document.querySelector("main")).toHaveClass(
        "prototype-login-layout",
      );
      expect(document.querySelector(".prototype-auth-screen")).toBeTruthy();
      expect(document.querySelector(".ds-auth-form-shell")).toBeTruthy();

      const user = userEvent.setup();
      await user.type(
        document.querySelector('input[name="email"]') as HTMLInputElement,
        email,
      );
      expect(document.querySelector('input[name="password"]')).toBeNull();
      await user.click(screen.getByRole("button", { name: /전체 동의/ }));
      await user.click(
        document.querySelector('button[type="submit"]') as HTMLButtonElement,
      );

      await waitFor(() => expect(document.body).toHaveTextContent("인증 메일을 보냈어요"));
      expect(signupSpy).toHaveBeenCalledWith({ email, agreements: acceptedAgreements });

      cleanup();
      renderAppRoute("/signup/verify?token=valid-token&redirect=/invites/jeju-3d/accept");
      await waitFor(() => expect(document.body).toHaveTextContent("이메일 인증이 완료됐어요"));
      await user.type(
        document.querySelector('input[name="password"]') as HTMLInputElement,
        "password123",
      );
      await user.click(
        document.querySelector('button[type="submit"]') as HTMLButtonElement,
      );

      await waitFor(() => expect(verifySpy).toHaveBeenCalledWith({ token: "valid-token" }));
      await waitFor(() => expect(completeSpy).toHaveBeenCalledWith({ token: "valid-token", password: "password123" }));
      await waitFor(() => expect(acceptInviteSpy).toHaveBeenCalledWith("jeju-3d"));
      await waitFor(() =>
        expect(document.body).toHaveTextContent("초대를 수락했어요"),
      );
      const tripLink = await waitFor(() => {
        const link = document.querySelector('a[href^="/trips/"]');
        expect(link).toBeTruthy();
        return link as HTMLAnchorElement;
      });
      expect(tripLink.getAttribute("href")).toMatch(/^\/trips\/[1-9][0-9]*$/);
    } finally {
      signupSpy.mockRestore();
      verifySpy.mockRestore();
      completeSpy.mockRestore();
      getProfileSpy.mockRestore();
      acceptInviteSpy.mockRestore();
    }
  });

  it("shows an invite error state for an unknown invite token", async () => {
    await login();
    cleanup();
    renderAppRoute("/invites/unknown-token/accept");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("초대 링크를 찾을 수 없어요"),
    );
    expect(document.body).toHaveTextContent("초대한 친구에게 새 초대 링크를 요청해 주세요.");
  });
});
