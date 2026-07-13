import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { appDataApi, type User } from "../../api";
import { getPreviewUser } from "../../test/fixtures";
import { renderAppRoute } from "../../test/renderAppRoute";

describe("admin pages", () => {
  const NO_ACCESS = "\uC811\uADFC \uAD8C\uD55C\uC774 \uC5C6\uC2B5\uB2C8\uB2E4";
  const ADMIN_ONLY =
    "\uC774 \uD398\uC774\uC9C0\uB294 \uAD00\uB9AC\uC790\uB9CC \uC811\uADFC\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
  const USER_MANAGEMENT = "\uD68C\uC6D0 \uAD00\uB9AC";
  const POLICY_TITLE = "\uC815\uCC45 \uC81C\uBAA9";
  const SAVE = "\uC800\uC7A5";

  function installStoredUser(user: User & { role?: "user" | "admin" }) {
    window.localStorage.setItem(
      "travel-hunter-production-auth",
      JSON.stringify({ accessToken: "test-token", user }),
    );
    vi.spyOn(appDataApi, "getCurrentUser").mockResolvedValue(user);
    vi.spyOn(appDataApi, "getProfile").mockResolvedValue({
      preferredRegions: null,
      style: "Food",
      budget: "400000 KRW",
    });
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);
  }

  it("shows a dedicated 403 page for logged-in non-admin users", async () => {
    installStoredUser({ ...getPreviewUser(), role: "user" });

    renderAppRoute("/admin");

    await waitFor(() => expect(document.body).toHaveTextContent(NO_ACCESS));
    expect(document.body).toHaveTextContent(ADMIN_ONLY);
  });

  it("renders the admin user list for admin users", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    vi.spyOn(appDataApi as any, "listAdminUsers").mockResolvedValue({
      items: [
        {
          id: "2",
          email: "user@example.com",
          nickname: "traveler",
          role: "user",
          onboardingCompleted: true,
          createdAt: "2026-05-27T00:00:00",
          updatedAt: "2026-05-27T00:00:00",
        },
      ],
      total: 1,
      limit: 30,
      offset: 0,
    });

    renderAppRoute("/admin/users");

    await waitFor(() =>
      expect(document.body).toHaveTextContent(USER_MANAGEMENT),
    );
    await waitFor(() =>
      expect(document.body).toHaveTextContent("user@example.com"),
    );
  });

  it("renders admin user counts and pagination controls", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const listSpy = vi
      .spyOn(appDataApi as any, "listAdminUsers")
      .mockResolvedValueOnce({
        items: Array.from({ length: 30 }, (_, index) => ({
          id: String(index + 1),
          email: `user-${index + 1}@example.com`,
          nickname: `traveler-${index + 1}`,
          role: "user",
          onboardingCompleted: true,
          createdAt: "2026-05-27T00:00:00",
          updatedAt: "2026-05-27T00:00:00",
        })),
        total: 226,
        limit: 30,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: "31",
            email: "user-31@example.com",
            nickname: "traveler-31",
            role: "user",
            onboardingCompleted: true,
            createdAt: "2026-05-27T00:00:00",
            updatedAt: "2026-05-27T00:00:00",
          },
        ],
        total: 226,
        limit: 30,
        offset: 30,
      });

    renderAppRoute("/admin/users");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("총 226명 중 1-30명 표시"),
    );
    expect(screen.getByRole("button", { name: "이전" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "다음" })).not.toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "다음" }));

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith({ limit: 30, offset: 30 }),
    );
  });

  it("renders admin policy status tabs, counts, and pagination controls", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const listSpy = vi
      .spyOn(appDataApi as any, "listAdminPolicies")
      .mockResolvedValueOnce({
        items: Array.from({ length: 30 }, (_, index) => ({
          id: String(index + 1),
          slug: `policy-${index + 1}`,
          title: `정책 ${index + 1}`,
          organization: null,
          policyType: "교통",
          region: "충남",
          status: "active",
          sourceType: "external",
          sourceCategory: "local_half_trip",
          sourceLabel: "반값여행",
          updatedAt: "2026-05-27T00:00:00",
        })),
        total: 71,
        limit: 30,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 30,
        offset: 0,
      });

    renderAppRoute("/admin/policies");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("총 71개 중 1-30개 표시"),
    );
    expect(document.body).toHaveTextContent("반값여행");
    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "노출중" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "숨김" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "이전" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "다음" })).not.toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "숨김" }));

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith({
        limit: 30,
        offset: 0,
        status: "hidden",
      }),
    );
  });

  it("renders admin audit log counts and pagination controls", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const listSpy = vi
      .spyOn(appDataApi as any, "listAdminAuditLogs")
      .mockResolvedValueOnce({
        items: Array.from({ length: 30 }, (_, index) => ({
          id: String(index + 1),
          adminUserId: "1",
          adminEmail: "admin@example.com",
          action: "policy.update",
          targetType: "policy",
          targetId: String(index + 1),
          summary: "Updated policy",
          beforeJson: null,
          afterJson: null,
          createdAt: "2026-05-27T00:00:00",
        })),
        total: 45,
        limit: 30,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 45,
        limit: 30,
        offset: 30,
      });

    renderAppRoute("/admin/audit-logs");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("총 45개 중 1-30개 표시"),
    );
    expect(screen.getByRole("button", { name: "이전" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "다음" })).not.toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "다음" }));

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith({ limit: 30, offset: 30 }),
    );
  });

  it("shows the admin entry in desktop and mobile service navigation", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });

    renderAppRoute("/home");

    await waitFor(() => expect(screen.getAllByText("관리자").length).toBe(2));
    expect(
      document.querySelector(".top-tabs a[href='/admin'] span")?.textContent,
    ).toBe("관리자");
    expect(
      document.querySelector(".bottom-tabs a[href='/admin'] span")?.textContent,
    ).toBe("관리자");
    expect(
      document.querySelector(".bottom-tabs")?.classList.contains("admin-tabs"),
    ).toBe(true);
  });

  it("submits admin policy edits without slug or sourceType", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    vi.spyOn(appDataApi as any, "getAdminPolicy").mockResolvedValue({
      id: "10",
      slug: "fixed-slug",
      title: "Original policy",
      organization: "Travel Hunter",
      policyType: "region-discount",
      region: "Nationwide",
      startDate: null,
      endDate: "2026-12-31",
      benefitAmount: 10000,
      benefitDetail: "10000 KRW discount",
      description: "Policy description",
      requirements: ["Domestic traveler"],
      documents: ["ID card"],
      officialUrl: "https://example.com/official",
      applyUrl: null,
      policyComment: "Comment",
      policyPeriod: null,
      status: "active",
      sourceType: "internal",
      sourceCategory: null,
      sourceLabel: "내부",
      adminOverrideEnabled: false,
      updatedAt: "2026-05-27T00:00:00",
      createdAt: "2026-05-27T00:00:00",
    });
    const updateSpy = vi
      .spyOn(appDataApi as any, "updateAdminPolicy")
      .mockResolvedValue({
        id: "10",
        slug: "fixed-slug",
        title: "Edited policy",
        organization: "Travel Hunter",
        policyType: "region-discount",
        region: "Nationwide",
        startDate: null,
        endDate: "2026-12-31",
        benefitAmount: 10000,
        benefitDetail: "10000 KRW discount",
        description: "Policy description",
        requirements: ["Domestic traveler"],
        documents: ["ID card"],
        officialUrl: "https://example.com/official",
        applyUrl: null,
        policyComment: "Comment",
        policyPeriod: null,
        status: "active",
        sourceType: "internal",
        sourceCategory: null,
        sourceLabel: "내부",
        adminOverrideEnabled: false,
        updatedAt: "2026-05-27T00:00:00",
        createdAt: "2026-05-27T00:00:00",
      });

    renderAppRoute("/admin/policies/10");

    const titleInput = await screen.findByRole("textbox", {
      name: POLICY_TITLE,
    });
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Edited policy");
    await userEvent.click(screen.getByRole("button", { name: SAVE }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalled());
    const payload = updateSpy.mock.calls[0][1] as Record<string, unknown>;
    expect(payload.title).toBe("Edited policy");
    expect(payload.slug).toBeUndefined();
    expect(payload.sourceType).toBeUndefined();
  });

  it("renders external policy source status on the admin dashboard", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    vi.spyOn(
      appDataApi as any,
      "getAdminExternalSourceSummary",
    ).mockResolvedValue({
      items: [
        {
          sourceCategory: "local_half_trip",
          label: "반값여행",
          sourceName: "대한민국 반값여행",
          totalRecords: 16,
          activeRecords: 5,
          scheduledRecords: 7,
          endedRecords: 4,
          unknownRecords: 0,
          freshRecords: 5,
          promotedPolicyCount: 5,
          activePromotedPolicyCount: 5,
          latestFetchedAt: "2026-05-27T09:00:00",
          latestVerifiedAt: "2026-05-27T09:00:00",
        },
      ],
      totalRecords: 16,
      activeRecords: 5,
      freshRecords: 5,
      promotedPolicyCount: 5,
      latestFetchedAt: "2026-05-27T09:00:00",
    });
    vi.spyOn(
      appDataApi as any,
      "getExternalCollectionOpsHealth",
    ).mockResolvedValue({
      schedulerEnabled: false,
      runAt: "03:00",
      pollSeconds: 60,
      minParsedCount: 1,
      lastAttemptedRunDate: null,
      lastSuccessfulRunDate: null,
      lastParsedCount: null,
      lastOutcome: null,
      lastError: null,
    });

    renderAppRoute("/admin");

    await waitFor(() =>
      expect(document.body).toHaveTextContent("외부 정책 수집 상태"),
    );
    expect(document.body).toHaveTextContent("대한민국 반값여행");
    expect(
      screen.getByRole("button", { name: "지금 수집 실행" }),
    ).toBeInTheDocument();
  });

  it("runs external policy collection from the admin dashboard", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const summarySpy = vi
      .spyOn(appDataApi as any, "getAdminExternalSourceSummary")
      .mockResolvedValue({
        items: [],
        totalRecords: 0,
        activeRecords: 0,
        freshRecords: 0,
        promotedPolicyCount: 0,
        latestFetchedAt: null,
      });
    vi.spyOn(
      appDataApi as any,
      "getExternalCollectionOpsHealth",
    ).mockResolvedValue({
      schedulerEnabled: false,
      runAt: "03:00",
      pollSeconds: 60,
      minParsedCount: 1,
      lastAttemptedRunDate: null,
      lastSuccessfulRunDate: null,
      lastParsedCount: null,
      lastOutcome: null,
      lastError: null,
    });
    const runSpy = vi.spyOn(appDataApi as any, "runExternalCollection").mockResolvedValue({
      sourceName: "official external benefits",
      sourceCategory: "multiple",
      parsedCount: 3,
      createdOrUpdatedCount: 2,
      outcome: "success",
      sources: [],
    });

    renderAppRoute("/admin");

    await userEvent.click(await screen.findByRole("button", { name: "지금 수집 실행" }));

    await waitFor(() => expect(runSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(summarySpy.mock.calls.length).toBeGreaterThanOrEqual(2));
    expect(document.body).toHaveTextContent("수집 결과 success");
  });
});
