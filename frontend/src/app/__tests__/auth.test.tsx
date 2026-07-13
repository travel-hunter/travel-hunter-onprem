import {
  cleanup,
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
    expect(document.querySelector(".brand-mark-compass")).toBeTruthy();
    expect(
      document.querySelector(".prototype-login-logo"),
    ).not.toHaveTextContent("TH");
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
