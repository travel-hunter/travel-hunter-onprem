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
    vi.stubEnv("VITE_ADMIN_BASE_URL", "");
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

  it("renders review candidates separately from official source controls", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const approveSpy = vi.spyOn(appDataApi as any, "approveAdminPolicyReviewCandidate").mockResolvedValue({});
    const confirmSpy = vi.spyOn(window, "confirm").mockReset().mockReturnValueOnce(false).mockReturnValueOnce(true);
    const sourcesSpy = vi.spyOn(appDataApi as any, "listAdminCollectionSources").mockResolvedValue({ items: [{ key: "island_visit", displayName: "Island Visit support", officialUrl: "https://www.visitisland.kr/promotion2", sourceCategory: "island_visit", enabled: false, publicationMode: "review", lastOutcome: null, lastCollectedAt: null, lastError: null }] });
    vi.spyOn(appDataApi as any, "listAdminPolicyReviewCandidates").mockResolvedValue({ items: [{ id: "candidate-1", externalSourceRecordId: "record-1", reviewStatus: "pending", changeKind: "new", title: "Island travel support", sourceCategory: "island_visit", officialUrl: "https://www.visitisland.kr/promotion2", benefitText: "travel support", region: null, city: null, status: "scheduled", startDate: "2026-10-01", endDate: "2026-10-31", createdAt: "2026-09-13T00:00:00", reviewReason: "card_quality_review", cardPreview: { amount: "혜택 상세 확인", evidence: "신청하러 가기", issues: ["benefit_navigation_text"] } }] });
    const updateSpy = vi.spyOn(appDataApi as any, "updateAdminCollectionSource").mockResolvedValue({ key: "island_visit", displayName: "Island Visit support", officialUrl: "https://www.visitisland.kr/promotion2", sourceCategory: "island_visit", enabled: true, publicationMode: "review", lastOutcome: null, lastCollectedAt: null, lastError: null });

    renderAppRoute("/admin/policy-review");

    await waitFor(() => expect(document.body).toHaveTextContent("Island Visit support"));
    expect(document.body).toHaveTextContent("Island travel support");
    expect(screen.getByLabelText("카드 표시 예정")).toBeTruthy();
    expect(document.body).toHaveTextContent("혜택 상세 확인");
    expect(document.body).toHaveTextContent("원문 일부");
    expect(document.body).toHaveTextContent("버튼 문구가 포함되어 있어요");
    await userEvent.click(screen.getByRole("button", { name: "\uC2B9\uC778\uD558\uACE0 \uACF5\uAC1C" }));
    expect(approveSpy).not.toHaveBeenCalled();
    expect(confirmSpy.mock.calls[0][0]).toContain("혜택 상세 확인");
    await userEvent.click(screen.getByRole("button", { name: "\uC2B9\uC778\uD558\uACE0 \uACF5\uAC1C" }));
    await waitFor(() => expect(approveSpy).toHaveBeenCalledWith("candidate-1"));
    expect(confirmSpy.mock.calls[1][0]).toContain("혜택 상세 확인");
    await userEvent.click(screen.getByRole("button", { name: "\uC218\uC9D1 \uD65C\uC131\uD654" }));
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("island_visit", { enabled: true }));
    expect(sourcesSpy).toHaveBeenCalledTimes(2);
    confirmSpy.mockRestore();
  });

  it("toggles auto-publish per source and labels why candidates wait", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    const source = { key: "local_half_trip", displayName: "Korea Half-Price Travel", officialUrl: "https://official.example/half", sourceCategory: "local_half_trip", enabled: true, publicationMode: "review", expectedMinRecords: 11, lastParsedCount: 22, autoApprovedLast24h: 0, lastOutcome: "success", lastCollectedAt: "2026-09-14T09:00:00", lastError: null };
    vi.spyOn(appDataApi as any, "listAdminCollectionSources").mockResolvedValue({ items: [source] });
    vi.spyOn(appDataApi as any, "listAdminPolicyReviewCandidates").mockResolvedValue({
      items: [{ ...makeCandidate(1), title: "Renamed support", changeKind: "material_change", reviewReason: "identity_changed" }],
      total: 1, limit: 50, offset: 0,
    });
    vi.spyOn(appDataApi as any, "listAdminEligibleIslandSnapshots").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0, approvedSnapshotId: null, approvedEntryCount: 0 });
    const updateSpy = vi.spyOn(appDataApi as any, "updateAdminCollectionSource").mockReset().mockResolvedValue({ ...source, publicationMode: "auto_after_reviewed_baseline", autoApprovedLast24h: 3 });
    const confirmSpy = vi.spyOn(window, "confirm").mockReset().mockReturnValue(true);

    renderAppRoute("/admin/policy-review");

    await waitFor(() => expect(document.body).toHaveTextContent("Renamed support"));
    expect(document.body).toHaveTextContent("\uC81C\uBAA9\u00B7\uC9C0\uC5ED \uBCC0\uACBD");
    expect(document.body).toHaveTextContent("\uC804\uAC74 \uAC80\uD1A0");
    expect(document.body).toHaveTextContent("\uAE30\uC900 \uAC74\uC218 11 (\uCD5C\uADFC 22\uAC74)");
    await userEvent.click(screen.getByRole("button", { name: "\uC790\uB3D9 \uBC1C\uD589 \uCF1C\uAE30" }));
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("local_half_trip", { publicationMode: "auto_after_reviewed_baseline" }));
    expect(confirmSpy.mock.calls[0][0]).toContain("\uC790\uB3D9 \uBC1C\uD589");
    await waitFor(() => expect(document.body).toHaveTextContent("\uC790\uB3D9 \uBC1C\uD589 \uC911"));
    expect(document.body).toHaveTextContent("\uCD5C\uADFC 24\uC2DC\uAC04 \uC790\uB3D9 \uBC1C\uD589 3\uAC74");
    expect(screen.getByRole("button", { name: "\uAC80\uD1A0\uB85C \uB418\uB3CC\uB9AC\uAE30" })).toBeVisible();
    confirmSpy.mockRestore();
  });

  function makeCandidate(id: number) {
    return { id: String(id), externalSourceRecordId: `record-${id}`, reviewStatus: "pending", changeKind: "new", title: `Candidate ${id}`, sourceCategory: "island_visit", officialUrl: "https://official.example/island", benefitText: "support", region: null, city: null, status: "scheduled", startDate: null, endDate: null, createdAt: "2026-09-13T00:00:00" };
  }

  function installBatchReviewPage() {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    vi.spyOn(appDataApi as any, "listAdminCollectionSources").mockResolvedValue({ items: [] });
    vi.spyOn(appDataApi as any, "listAdminEligibleIslandSnapshots").mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0, approvedSnapshotId: null, approvedEntryCount: 0 });
    const listSpy = vi.spyOn(appDataApi as any, "listAdminPolicyReviewCandidates").mockImplementation(async (...args: unknown[]) => {
      const offset = (args[0] as { offset?: number } | undefined)?.offset ?? 0;
      const items = offset >= 50 ? [makeCandidate(51)] : Array.from({ length: 50 }, (_, index) => makeCandidate(index + 1));
      return { items, total: 71, limit: 50, offset };
    });
    const batchSpy = vi.spyOn(appDataApi as any, "approveAdminPolicyReviewCandidates").mockReset().mockResolvedValue({ approvedCount: 1, approvedCandidateIds: ["1"] });
    return { listSpy, batchSpy };
  }

  it("pages review candidates by 50 and approves only the selected ones", async () => {
    const { listSpy, batchSpy } = installBatchReviewPage();
    const confirmSpy = vi.spyOn(window, "confirm").mockReset().mockReturnValue(true);

    renderAppRoute("/admin/policy-review");

    await waitFor(() => expect(document.body).toHaveTextContent("Candidate 50"));
    expect(document.body).toHaveTextContent("1 / 2");
    expect(screen.getByRole("button", { name: "선택 승인" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Candidate 1 선택" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Candidate 3 선택" }));
    await userEvent.click(screen.getByRole("button", { name: "선택 승인" }));
    await waitFor(() => expect(batchSpy).toHaveBeenCalledWith({ candidateIds: ["1", "3"], approveAll: false }));
    expect(confirmSpy.mock.calls[0][0]).toContain("2건");
    expect(confirmSpy.mock.calls[0][0]).toContain("\uD61C\uD0DD \uC0C1\uC138 \uD655\uC778");

    await userEvent.click(screen.getByRole("button", { name: "다음" }));
    await waitFor(() => expect(document.body).toHaveTextContent("Candidate 51"));
    expect(document.body).toHaveTextContent("2 / 2");
    expect(listSpy).toHaveBeenLastCalledWith({ limit: 50, offset: 50 });
    confirmSpy.mockRestore();
  });

  it("approves all pending candidates only after a confirmation that states the total", async () => {
    const { batchSpy } = installBatchReviewPage();
    const confirmSpy = vi.spyOn(window, "confirm").mockReset().mockReturnValueOnce(false).mockReturnValueOnce(true);

    renderAppRoute("/admin/policy-review");

    await waitFor(() => expect(document.body).toHaveTextContent("Candidate 1"));
    await userEvent.click(screen.getByRole("button", { name: "전체 승인" }));
    expect(batchSpy).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "전체 승인" }));
    await waitFor(() => expect(batchSpy).toHaveBeenCalledWith({ candidateIds: [], approveAll: true }));
    expect(confirmSpy.mock.calls[1][0]).toContain("71건");
    expect(confirmSpy.mock.calls[1][0]).toContain("\uD61C\uD0DD \uC0C1\uC138 \uD655\uC778");
    confirmSpy.mockRestore();
  });

  it("shows catalog changes separately from policy review candidates", async () => {
    installStoredUser({ ...getPreviewUser(), role: "admin" });
    vi.spyOn(appDataApi as any, "listAdminCollectionSources").mockResolvedValue({ items: [] });
    vi.spyOn(appDataApi as any, "listAdminPolicyReviewCandidates").mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    const snapshot = {
      id: "3", reviewStatus: "pending", isCurrentApproved: false, entryCount: 42, addedCount: 3, removedCount: 1, changedCount: 0,
      sourceNoticeUrl: "https://www.visitisland.kr/notice/12", sourceNoticeTitle: "2026 대상 섬 목록 안내",
      attachmentFiles: [{ url: "https://www.visitisland.kr/files/south.xlsx", filename: "south.xlsx", sha256: "a".repeat(64) }],
      attachmentFingerprint: "b".repeat(64), parserVersion: "xlsx-v1", fetchedAt: "2026-09-14T09:00:00", reviewedAt: null, reviewNote: null, createdAt: "2026-09-14T09:00:00",
    };
    vi.spyOn(appDataApi as any, "listAdminEligibleIslandSnapshots").mockResolvedValue({ items: [snapshot], total: 1, limit: 20, offset: 0, approvedSnapshotId: null, approvedEntryCount: 0 });
    const approveSpy = vi.spyOn(appDataApi as any, "approveAdminEligibleIslandSnapshot").mockResolvedValue({ ...snapshot, reviewStatus: "approved", isCurrentApproved: true });
    const confirmSpy = vi.spyOn(window, "confirm").mockReset().mockReturnValue(true);

    renderAppRoute("/admin/policy-review");

    expect(await screen.findByRole("heading", { name: "대상 섬 목록 갱신" })).toBeVisible();
    expect(screen.getByText("추가 3 · 삭제 1 · 변경 0")).toBeVisible();
    expect(screen.getByRole("link", { name: "south.xlsx" })).toHaveAttribute("href", "https://www.visitisland.kr/files/south.xlsx");
    expect(document.body).not.toHaveTextContent("승인하고 공개");
    await userEvent.click(screen.getByRole("button", { name: "카탈로그 승인" }));
    await waitFor(() => expect(approveSpy).toHaveBeenCalledWith("3"));
    expect(confirmSpy.mock.calls[0][0]).toContain("추가 3");
    expect(confirmSpy.mock.calls[0][0]).toContain("삭제 1");
    confirmSpy.mockRestore();
  });
});
