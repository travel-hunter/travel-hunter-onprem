import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
} from "../../api";
import { AppRoot } from "../AppRoot";
import {
  examplePolicyPath,
} from "../../test/fixtures";
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — auth & routing", () => {
  it("renders the browser app root on a direct login entry", () => {
    window.history.pushState({}, "", "/login");
    render(<AppRoot />);

    expect(document.querySelector('input[type="email"]')).toBeTruthy();
    expect(document.querySelector('button[type="submit"]')).toBeTruthy();
    expect(document.querySelector("main")).toHaveClass(
      "prototype-login-layout",
    );
    expect(document.querySelector(".prototype-login-screen")).toBeTruthy();
  });

  it("renders the prototype login screen as the first entry page", () => {
    renderAppRoute("/");

    expect(
      screen.getByRole("heading", { name: "트래블헌터" }),
    ).toBeInTheDocument();
    expect(screen.getByText("숨은 여행 혜택을 사냥하세요")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "카카오로 시작하기" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "구글로 시작하기" }),
    ).toBeInTheDocument();
    expect(document.querySelector(".ds-auth-form-shell")).toBeTruthy();
    // 시안 v49 · v54: 로고 칸 대신 여러 지역 사진(한 장씩 보임) + 브랜드 글자, 가입·찾기 입구.
    // 사진 위에 출처를 적지 않는다 - CC0 · 퍼블릭 도메인이고 앱 안 '사진 출처'에 있다
    expect(document.querySelectorAll(".lg-photo .lg-ph")).toHaveLength(8);
    expect(document.querySelectorAll(".lg-photo .lg-ph.on")).toHaveLength(1);
    expect(document.querySelector(".lg-photo")).not.toHaveTextContent(/CC0|퍼블릭 도메인|Bernard/);
    expect(screen.getByRole("button", { name: "회원가입" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "비밀번호 찾기" })).toBeInTheDocument();
    expect(document.querySelector("main")).toHaveClass(
      "prototype-login-layout",
    );
    expect(
      screen.queryByText(`Travel Hunter ${["Pro", "duction"].join("")}`),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("9:41")).not.toBeInTheDocument();
    expect(screen.queryByText("5G")).not.toBeInTheDocument();
    expect(screen.queryByText("WiFi")).not.toBeInTheDocument();
    expect(screen.queryByText("85%")).not.toBeInTheDocument();
  });

  it("redirects the removed onboarding route to the login entry", () => {
    renderAppRoute("/onboarding");

    expect(
      screen.getByRole("heading", { name: "트래블헌터" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "로그인" })).toBeInTheDocument();
    expect(document.querySelector("main")).toHaveClass(
      "prototype-login-layout",
    );
  });

  it("logs in and reaches the authenticated home route", async () => {
    await login();

    expect(getLink("/trips")).toBeInTheDocument();
  });

  it("waits for refresh-cookie session bootstrap before redirecting protected routes", async () => {
    const refreshSpy = vi
      .spyOn(appDataApi, "refreshSession")
      .mockImplementation(() => new Promise(() => {}));

    try {
      renderAppRoute("/home");

      expect(screen.getByText("세션을 확인하는 중입니다")).toBeInTheDocument();
      expect(document.querySelector('input[type="email"]')).toBeNull();
      expect(document.body.textContent).not.toContain("redirect=");
    } finally {
      refreshSpy.mockRestore();
    }
  });

  it("protects authenticated app routes after session bootstrap fails", async () => {
    const refreshSpy = vi
      .spyOn(appDataApi, "refreshSession")
      .mockRejectedValue(new Error("missing refresh cookie"));

    try {
      renderAppRoute("/home");

      await waitFor(() =>
        expect(document.querySelector('input[type="email"]')).toBeTruthy(),
      );
      expect(document.querySelector('button[type="submit"]')).toBeTruthy();
    } finally {
      refreshSpy.mockRestore();
    }
  });

  it("protects authenticated app routes", async () => {
    renderAppRoute("/home");

    await waitFor(() =>
      expect(document.querySelector('input[type="email"]')).toBeTruthy(),
    );
    expect(document.querySelector('button[type="submit"]')).toBeTruthy();
  });

  it("keeps signup verification progressing when session bootstrap rerenders mid-request", async () => {
    let resolveVerify: (result: { verified: true; email: string }) => void = () => {};
    const verifyPromise = new Promise<{ verified: true; email: string }>((resolve) => {
      resolveVerify = resolve;
    });
    const refreshSpy = vi
      .spyOn(appDataApi, "refreshSession")
      .mockRejectedValue(new Error("missing refresh cookie"));
    const verifySpy = vi
      .spyOn(appDataApi, "verifySignup")
      .mockReturnValue(verifyPromise);

    try {
      renderAppRoute("/signup/verify?token=valid-token");

      await waitFor(() => expect(verifySpy).toHaveBeenCalledWith({ token: "valid-token" }));
      await waitFor(() => expect(refreshSpy).toHaveBeenCalled());
      await act(async () => {
        await Promise.resolve();
      });
      expect(verifySpy).toHaveBeenCalledTimes(1);

      resolveVerify({ verified: true, email: "signup-progress@example.com" });

      await waitFor(() =>
        expect(screen.getByRole("button", { name: "비밀번호 설정하고 가입 완료" })).toBeInTheDocument(),
      );
      expect(verifySpy).toHaveBeenCalledTimes(1);
      expect(document.querySelector('input[name="password"]')).toBeTruthy();
      expect(document.body).toHaveTextContent("이메일 인증이 완료됐어요");
    } finally {
      refreshSpy.mockRestore();
      verifySpy.mockRestore();
    }
  });

  it("clears signup verification cache after signup completes", async () => {
    const email = "signup-cache-clear@example.com";
    const refreshSpy = vi
      .spyOn(appDataApi, "refreshSession")
      .mockRejectedValue(new Error("missing refresh cookie"));
    const verifySpy = vi
      .spyOn(appDataApi, "verifySignup")
      .mockResolvedValue({ verified: true, email });
    const completeSpy = vi.spyOn(appDataApi, "completeSignup").mockResolvedValue({
      accessToken: "signup-cache-clear-access-token",
      user: {
        id: "signup-cache-clear-user",
        nickname: "캐시정리",
        email,
        role: "user",
        hasPassword: true,
        preferredRegions: null,
        persona: "캐시정리님",
        savedAmount: 0,
        onboardingCompleted: true,
        nicknameSetupCompleted: true,
        socialAccounts: [],
        createdAt: "2026-06-15T00:00:00Z",
        updatedAt: "2026-06-15T00:00:00Z",
      },
    });
    const getProfileSpy = vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: null,
      budget: null,
    });

    try {
      renderAppRoute("/signup/verify?token=cache-clear-token");

      await waitFor(() => expect(refreshSpy).toHaveBeenCalled());
      await act(async () => {
        await Promise.resolve();
      });
      await waitFor(() => {
        const input = document.querySelector('input[name="password"]') as HTMLInputElement | null;
        expect(input).toBeTruthy();
      });
      const passwordInput = document.querySelector('input[name="password"]') as HTMLInputElement;
      fireEvent.change(passwordInput, { target: { value: "password123" } });
      expect(passwordInput.value).toBe("password123");
      fireEvent.click(screen.getByRole("button", { name: "비밀번호 설정하고 가입 완료" }));
      await waitFor(() =>
        expect(completeSpy).toHaveBeenCalledWith({ token: "cache-clear-token", password: "password123" }),
      );

      cleanup();
      window.localStorage.clear();
      renderAppRoute("/signup/verify?token=cache-clear-token");

      await waitFor(() => expect(verifySpy).toHaveBeenCalledTimes(2));
    } finally {
      refreshSpy.mockRestore();
      verifySpy.mockRestore();
      completeSpy.mockRestore();
      getProfileSpy.mockRestore();
    }
  });

  it("opens core authenticated routes", async () => {
    await login();

    const routes = [
      "/profile-setup",
      "/home",
      "/policies",
      examplePolicyPath,
      "/trips",
      "/trips/new",
      "/trips/1",
      "/ai-results?tripId=1",
      "/friend-invite?tripId=1",
      "/invites/jeju-3d/accept",
      "/mypage",
    ];

    for (const route of routes) {
      cleanup();
      renderAppRoute(route);
      expect(document.body.textContent?.trim().length).toBeGreaterThan(0);
    }
  });
});
