import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type Policy,
  type Trip,
  type User,
} from "../../api";
import { App } from "../App";
import { AppProviders } from "../AppRoot";
import {
  examplePolicyDetail,
  examplePolicyPath,
  examplePolicySlug,
  examplePolicyTitle,
  getUpcomingPreviewTrip,
  getPreviewUser,
  testEmail,
} from "../../test/fixtures";
import { getLink, login, renderAppRoute } from "../../test/renderAppRoute";

function installStoredUser(user: User) {
  window.localStorage.setItem(
    "travel-hunter-production-auth",
    JSON.stringify({ accessToken: "test-token", user }),
  );
}

function mockMyPageAccountLoad(user: User) {
  return [
    vi.spyOn(appDataApi, "getCurrentUser").mockResolvedValue(user),
    vi.spyOn(appDataApi, "getProfile").mockResolvedValue({ preferredRegions: null, style: null, budget: null }),
    vi.spyOn(appDataApi, "getProfileOptions").mockResolvedValue({ regions: [], travelStyles: [], budgets: [] }),
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]),
    vi.spyOn(appDataApi, "listTrips").mockResolvedValue([]),
    vi.spyOn(appDataApi, "listAppliedPolicies").mockResolvedValue([]),
  ];
}

/* 이 스위트는 목이 아니라 127.0.0.1:8000 실제 백엔드를 친다.
   정책 수집이 한 번 돌면 DB 슬러그가 바뀌어(dgtour-영광 -> dgtour-영광-8)
   화면이 그리는 링크가 픽스처와 어긋난다. 정책 조회·찜 경로만 붙잡아
   화면이 픽스처 슬러그를 쓰도록 고정한다. 흐름 자체는 그대로 돈다. */
const installedPolicyApiSpies: { mockRestore: () => void }[] = [];

function installExamplePolicyApi({ saved = false }: { saved?: boolean } = {}) {
  const savedSlugs = new Set<string>(saved ? [examplePolicySlug] : []);
  const spies = [
    vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail),
    vi
      .spyOn(appDataApi, "listPolicies")
      .mockResolvedValue([examplePolicyDetail]),
    vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockImplementation(async () =>
        savedSlugs.has(examplePolicySlug) ? [examplePolicyDetail] : [],
      ),
    vi.spyOn(appDataApi, "savePolicy").mockImplementation(async (slug) => {
      savedSlugs.add(slug);
      return { policyId: slug, saved: true };
    }),
    vi
      .spyOn(appDataApi, "removeSavedPolicy")
      .mockImplementation(async (slug) => {
        savedSlugs.delete(slug);
        return { policyId: slug, saved: false };
      }),
  ];
  // 도중에 실패해도 다음 테스트로 새지 않도록 등록해 두고 afterEach 에서 되돌린다.
  installedPolicyApiSpies.push(...spies);
  return { savedSlugs };
}

describe("Travel Hunter app — my page", () => {
  afterEach(() => {
    installedPolicyApiSpies.splice(0).forEach((spy) => spy.mockRestore());
  });

  it("saves a policy from the policy detail header action", async () => {
    installExamplePolicyApi();
    await login();
    cleanup();
    render(
      <MemoryRouter
        initialEntries={["/policies", examplePolicyPath]}
        initialIndex={1}
      >
        <AppProviders>
          <App />
        </AppProviders>
      </MemoryRouter>,
    );

    const saveButton = await screen.findByRole("button", { name: "저장" });
    const user = userEvent.setup();
    await user.click(saveButton);

    await waitFor(() =>
      expect(document.body).toHaveTextContent("관심 정책으로 저장했어요."),
    );
    await user.click(screen.getByRole("button", { name: "뒤로" }));
    // 관심 정책만 보기는 필터 시트로 모았다 - 상단 ♡ 관심 알약은 제목 줄과 함께 걷어냈다
    await user.click(await screen.findByRole("button", { name: "필터 열기" }));
    const filterDialog = screen.getByRole("dialog", { name: "정책 필터" });
    await user.click(within(filterDialog).getByRole("button", { name: "관심 정책만" }));
    await user.click(within(filterDialog).getByRole("button", { name: "필터 적용하기" }));

    await waitFor(() => {
      expect(document.body).toHaveTextContent("전체 1개 중 1개 표시");
      expect(getLink(examplePolicyPath)).toBeInTheDocument();
    });
    await user.click(
      screen.getByRole("button", {
        name: `${examplePolicyTitle} 즐겨찾기 해제`,
      }),
    );
    await waitFor(() =>
      expect(
        document.querySelector(`a[href="${examplePolicyPath}"]`),
      ).toBeFalsy(),
    );
  });

  it("refreshes the my page favorite summary after policy detail save and unsave", async () => {
    const user = userEvent.setup();
    // 정책 상세가 실제 DB 행을 읽으면 그 슬러그가 아래 기대값과 어긋난다.
    vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail);
    const listSavedPoliciesSpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockResolvedValue([]);
    const savePolicySpy = vi
      .spyOn(appDataApi, "savePolicy")
      .mockResolvedValue({ policyId: examplePolicySlug, saved: true });
    const removeSavedPolicySpy = vi
      .spyOn(appDataApi, "removeSavedPolicy")
      .mockResolvedValue({ policyId: examplePolicySlug, saved: false });

    try {
      await login();
      cleanup();
      render(
        <MemoryRouter initialEntries={[examplePolicyPath]}>
          <AppProviders>
            <App />
            <Link to="/mypage">마이페이지 테스트 이동</Link>
            <Link to={examplePolicyPath}>정책 상세 테스트 이동</Link>
          </AppProviders>
        </MemoryRouter>,
      );

      await user.click(await screen.findByRole("button", { name: "저장" }));
      await waitFor(() =>
        expect(savePolicySpy).toHaveBeenCalledWith(examplePolicySlug),
      );
      await screen.findByText("관심 정책으로 저장했어요.");
      await user.click(screen.getByRole("link", { name: "마이페이지 테스트 이동" }));

      const savedSummary = await screen.findByLabelText("나의 활동 요약");
      const favoritePolicyStat = within(savedSummary)
        .getByText("즐겨찾기")
        .closest(".mp-stat") as HTMLElement;
      await waitFor(() =>
        expect(within(favoritePolicyStat).getByText("1")).toBeInTheDocument(),
      );

      await user.click(screen.getByRole("link", { name: "정책 상세 테스트 이동" }));
      await user.click(await screen.findByRole("button", { name: "저장" }));
      await waitFor(() =>
        expect(removeSavedPolicySpy).toHaveBeenCalledWith(examplePolicySlug),
      );
      await screen.findByText("관심 정책에서 해제했어요.");
      await user.click(screen.getByRole("link", { name: "마이페이지 테스트 이동" }));

      const updatedSummary = await screen.findByLabelText("나의 활동 요약");
      const updatedFavoritePolicyStat = within(updatedSummary)
        .getByText("즐겨찾기")
        .closest(".mp-stat") as HTMLElement;
      await waitFor(() =>
        expect(within(updatedFavoritePolicyStat).getByText("0")).toBeInTheDocument(),
      );
    } finally {
      listSavedPoliciesSpy.mockRestore();
      savePolicySpy.mockRestore();
      removeSavedPolicySpy.mockRestore();
    }
  });

  it("shows saved policies on my page and removes them", async () => {
    installExamplePolicyApi();
    await login();
    await appDataApi.savePolicy(examplePolicySlug);
    cleanup();
    renderAppRoute("/mypage");
    await waitFor(() => expect(getLink(examplePolicyPath)).toBeInTheDocument());
    expect(screen.getAllByText("내 정보").length).toBeGreaterThan(0);
    expect(screen.queryByText("프로필")).not.toBeInTheDocument();
    expect(screen.getByText("내 일정")).toBeInTheDocument();
    expect(screen.getByText("즐겨찾기")).toBeInTheDocument();
    // 앱이 세는 것은 일정에 담은 혜택이라 '신청 정책' 대신 '담은 혜택'(시안 v49)
    expect(screen.getByText("담은 혜택")).toBeInTheDocument();
    expect(screen.queryByText("신청 정책")).not.toBeInTheDocument();
    expect(screen.getByText(/즐겨찾기 정책/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /알림 설정/ }),
    ).not.toBeInTheDocument();
    // 이모지 대신 닉네임 첫 글자(홈 머리와 같다)
    const avatar = document.querySelector(".mp-avatar");
    expect(avatar?.textContent?.trim()).toHaveLength(1);
    expect(avatar).not.toHaveTextContent("🧳");
    expect(document.querySelector(".prototype-mypage-screen")).toHaveClass("mp-screen");
    const settingsMenu = document.querySelector(".ds-settings-menu") as HTMLElement;
    // 로그아웃은 보통 줄, 회원 탈퇴는 설정 줄이 아니라 맨 아래 작은 글자
    expect(within(settingsMenu).getAllByRole("button").map((button) => button.textContent?.trim())).toEqual([
      "공지사항 / FAQ",
      "이용약관",
      "개인정보처리방침",
      "비밀번호 관리",
      "로그아웃",
    ]);
    expect(screen.getByRole("button", { name: "회원 탈퇴" })).toHaveClass("mp-quit");
    const favoriteRow = document.querySelector("#my-favorites .mp-pol");
    expect(favoriteRow).toBeTruthy();
    expect(favoriteRow?.querySelector(".benefit-tile")).toBeTruthy();
    expect(favoriteRow?.querySelector(".mp-dday")).toBeTruthy();

    await userEvent.setup().click(
      within(favoriteRow as HTMLElement).getByRole("button", {
        name: `${examplePolicyTitle} 즐겨찾기 해제`,
      }),
    );

    await waitFor(() =>
      expect(
        document.querySelector(`a[href="${examplePolicyPath}"]`),
      ).toBeFalsy(),
    );
  });

  it("shows a compact saved-policy error state with a recovery action on my page", async () => {
    await login();
    const listSavedPoliciesSpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockRejectedValue(new Error("load failed"));

    try {
      cleanup();
      renderAppRoute("/mypage");

      await waitFor(() =>
        expect(document.body).toHaveTextContent(
          "저장한 정책을 불러오지 못했어요.",
        ),
      );
      const savedPolicySection = screen
        .getByText(/즐겨찾기 정책/)
        .closest("section") as HTMLElement;
      expect(savedPolicySection).toBeTruthy();
      const alert = within(savedPolicySection).getByRole("alert");
      expect(alert).toBeInTheDocument();
      expect(
        within(alert).getByRole("link", { name: "정책 찾기" }),
      ).toHaveAttribute("href", "/policies");
    } finally {
      listSavedPoliciesSpy.mockRestore();
    }
  });

  it("shows a lightweight empty state when my page has no favorite policies", async () => {
    await login();
    const listSavedPoliciesSpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockResolvedValue([]);

    try {
      cleanup();
      renderAppRoute("/mypage");

      await waitFor(() =>
        expect(
          screen.getByText("아직 즐겨찾기한 정책이 없어요"),
        ).toBeInTheDocument(),
      );
      expect(
        screen.getByText("혜택 상세에서 하트를 누르면 여기에 모여요."),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "정책 보러 가기" }),
      ).toHaveAttribute("href", "/policies");
      expect(
        document.querySelector(`a[href="${examplePolicyPath}"]`),
      ).toBeFalsy();
    } finally {
      listSavedPoliciesSpy.mockRestore();
    }
  });

  it("deduplicates favorite policies by slug on my page", async () => {
    await login();
    const duplicatePolicy = { ...examplePolicyDetail };
    const listSavedPoliciesSpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockResolvedValue([duplicatePolicy, duplicatePolicy]);

    try {
      cleanup();
      renderAppRoute("/mypage");

      await waitFor(() =>
        expect(document.querySelector("#my-favorites .mp-pol")).toBeTruthy(),
      );
      expect(
        document.querySelectorAll("#my-favorites .mp-pol"),
      ).toHaveLength(1);
      expect(screen.getByRole("heading", { name: "즐겨찾기 정책 1" })).toBeInTheDocument();
    } finally {
      listSavedPoliciesSpy.mockRestore();
    }
  });

  it("refreshes the my page applied policy summary after policy linking on another route", async () => {
    const trip = getUpcomingPreviewTrip();
    const user = userEvent.setup();

    await login();
    cleanup();

    const listSavedPoliciesSpy = vi
      .spyOn(appDataApi, "listSavedPolicies")
      .mockResolvedValue([]);
    // 담은 혜택은 서버 목록으로 센다 - 담은 뒤에는 서버가 그 정책을 돌려준다
    let linked = false;
    const listAppliedPoliciesSpy = vi
      .spyOn(appDataApi, "listAppliedPolicies")
      .mockImplementation(async () => (linked ? [examplePolicyDetail] : []));
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockImplementation(async () => {
        linked = true;
        return { tripId: trip.id, policyId: examplePolicySlug, added: true };
      });

    try {
      // 정책 상세가 실제 DB 행을 읽으면 그 슬러그가 아래 기대값과 어긋난다.
      vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail);
      render(
        <MemoryRouter initialEntries={[examplePolicyPath]}>
          <AppProviders>
            <App />
            <Link to="/mypage">마이페이지 테스트 이동</Link>
          </AppProviders>
        </MemoryRouter>,
      );

      await user.click(await screen.findByRole("button", { name: /내 일정에 담기/ }));
      await user.click(await screen.findByRole("button", { name: /부산 여행 1/ }));
      await waitFor(() =>
        expect(addPolicyToTripSpy).toHaveBeenCalledWith(
          trip.id,
          examplePolicySlug,
        ),
      );
      await user.click(screen.getByRole("link", { name: "마이페이지 테스트 이동" }));

      const summary = await screen.findByLabelText("나의 활동 요약");
      const appliedPolicyStat = within(summary)
        .getByText("담은 혜택")
        .closest(".mp-stat") as HTMLElement;
      await waitFor(() =>
        expect(within(appliedPolicyStat).getByText("1")).toBeInTheDocument(),
      );
    } finally {
      listSavedPoliciesSpy.mockRestore();
      listAppliedPoliciesSpy.mockRestore();
      listTripsSpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
    }
  });

  it("removes trip detail unlinked policies from the my page applied summary", async () => {
    const trip: Trip = {
      ...getUpcomingPreviewTrip(),
      linkedPolicies: [],
    };
    const user = userEvent.setup();

    await login();
    cleanup();

    const listAppliedPoliciesSpy = vi
      .spyOn(appDataApi, "listAppliedPolicies")
      .mockResolvedValue([]);
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const addPolicyToTripSpy = vi
      .spyOn(appDataApi, "addPolicyToTrip")
      .mockResolvedValue({
        policyId: examplePolicySlug,
        tripId: trip.id,
        added: true,
      });
    const removePolicyFromTripSpy = vi
      .spyOn(appDataApi, "removePolicyFromTrip")
      .mockResolvedValue({
        policyId: examplePolicySlug,
        tripId: trip.id,
        added: false,
      });

    try {
      // 정책 상세가 실제 DB 행을 읽으면 그 슬러그가 아래 기대값과 어긋난다.
      vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(examplePolicyDetail);
      render(
        <MemoryRouter initialEntries={[examplePolicyPath]}>
          <AppProviders>
            <App />
            <Link to="/mypage">마이페이지 테스트 이동</Link>
          </AppProviders>
        </MemoryRouter>,
      );

      await user.click(await screen.findByRole("button", { name: /내 일정에 담기/ }));
      await user.click(await screen.findByRole("button", { name: /부산 여행 1/ }));
      await user.click(await screen.findByRole("button", { name: "일정에서 보기" }));
      const linkedRegion = await screen.findByRole("region", {
        name: "연결된 정책",
      });
      await user.click(
        within(linkedRegion).getByRole("button", {
          name: `${examplePolicyTitle} 연결 삭제`,
        }),
      );
      // × 뒤에 확인 창이 한 번 더 있다
      await user.click(
        within(await screen.findByRole("dialog")).getByRole("button", { name: "빼기" }),
      );
      await waitFor(() =>
        expect(removePolicyFromTripSpy).toHaveBeenCalledWith(
          trip.id,
          examplePolicySlug,
        ),
      );
      await waitFor(() =>
        expect(
          within(linkedRegion).queryByRole("button", {
            name: `${examplePolicyTitle} 연결 삭제`,
          }),
        ).not.toBeInTheDocument(),
      );
      await user.click(screen.getByRole("link", { name: "마이페이지 테스트 이동" }));

      const summary = await screen.findByLabelText("나의 활동 요약");
      const appliedPolicyStat = within(summary)
        .getByText("담은 혜택")
        .closest(".mp-stat") as HTMLElement;
      await waitFor(() =>
        expect(within(appliedPolicyStat).getByText("0")).toBeInTheDocument(),
      );
    } finally {
      listAppliedPoliciesSpy.mockRestore();
      listTripsSpy.mockRestore();
      getTripSpy.mockRestore();
      addPolicyToTripSpy.mockRestore();
      removePolicyFromTripSpy.mockRestore();
    }
  });

  it("does not render removed notification/contact controls on my page", async () => {
    await login();
    cleanup();
    renderAppRoute("/mypage");

    await waitFor(() =>
      expect(screen.getAllByText("내 정보").length).toBeGreaterThan(0),
    );
    expect(
      screen.queryByRole("button", { name: /알림 설정/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "전화번호" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("카카오 알림톡 연락처");
  });

  it("opens FAQ, terms, and privacy content from my page settings", async () => {
    await login();
    cleanup();
    renderAppRoute("/mypage");
    const user = userEvent.setup();

    await waitFor(() =>
      expect(screen.getAllByText("내 정보").length).toBeGreaterThan(0),
    );

    await user.click(screen.getByRole("button", { name: /공지사항 \/ FAQ/ }));
    let dialog = await screen.findByRole("dialog", { name: "공지사항 / FAQ" });
    expect(
      within(dialog).getByText("정책 정보는 어떻게 확인하나요?"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "신청 버튼과 혜택 안내 보기 버튼은 무엇이 다른가요?",
      ),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("준비 중이에요.");
    await user.click(within(dialog).getByRole("button", { name: "닫기" }));

    await user.click(screen.getByRole("button", { name: /이용약관/ }));
    dialog = await screen.findByRole("dialog", { name: "이용약관" });
    expect(within(dialog).getByText("서비스 목적")).toBeInTheDocument();
    expect(within(dialog).getByText("정보의 성격")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "닫기" }));

    await user.click(screen.getByRole("button", { name: /개인정보처리방침/ }));
    dialog = await screen.findByRole("dialog", { name: "개인정보처리방침" });
    expect(within(dialog).getByText("수집 항목")).toBeInTheDocument();
    expect(within(dialog).getByText("보호 조치")).toBeInTheDocument();
  });

  it("edits profile preferences from my page", async () => {
    const targetRegion = "강원";
    const nextProfile = {
      preferredRegions: [targetRegion],
      style: "사진",
      budget: "상관없음",
    };
    const nextNickname = `바다${Date.now().toString().slice(-6)}`;
    const nextUser = {
      ...getPreviewUser(),
      email: testEmail,
      nickname: nextNickname,
    };
    const updateProfileSpy = vi
      .spyOn(appDataApi, "updateProfile")
      .mockResolvedValue(nextProfile);
    const updateNicknameSpy = vi
      .spyOn(appDataApi, "updateNickname")
      .mockResolvedValue(nextUser);
    let getCurrentUserSpy: { mockRestore: () => void } | null = null;

    try {
      await login();
      cleanup();
      renderAppRoute("/mypage");
      const user = userEvent.setup();

      // 서버 프로필을 받기 전엔 편집을 못 연다(빈 자리값으로 저장돼 지워지지 않게) - 켜질 때까지 기다린다
      const editButton = await screen.findByRole("button", { name: "편집" });
      await waitFor(() => expect(editButton).toBeEnabled());
      await user.click(editButton);
      const dialog = screen.getByRole("dialog", { name: "프로필 편집" });
      expect(dialog).toBeInTheDocument();
      const nicknameInput = within(dialog).getByRole("textbox", {
        name: "닉네임",
      });
      await user.clear(nicknameInput);
      await user.type(nicknameInput, nextUser.nickname);
      expect(nicknameInput).toHaveValue(nextUser.nickname);
      getCurrentUserSpy = vi
        .spyOn(appDataApi, "getCurrentUser")
        .mockResolvedValue(nextUser);

      const regionButton = await within(dialog).findByRole("button", { name: targetRegion });
      expect(regionButton).toHaveClass("pe-chip");
      await user.click(regionButton);
      expect(regionButton).toHaveAttribute("aria-pressed", "true");
      const styleButton = within(dialog).getByRole("button", { name: nextProfile.style });
      expect(styleButton).toHaveClass("pe-chip");
      await user.click(styleButton);
      const budgetButton = within(dialog).getByRole("button", { name: nextProfile.budget });
      expect(budgetButton).toHaveClass("pe-chip");
      await user.click(budgetButton);
      await user.click(
        within(dialog).getByRole("button", { name: "저장" }),
      );

      await waitFor(() =>
        expect(updateNicknameSpy).toHaveBeenCalledWith({
          nickname: nextUser.nickname,
        }),
      );
      // 편집 창은 서버 프로필을 받은 뒤에 열린다 - 원래 관심 지역에 고른 지역이 더해진다(빈 초안으로 덮지 않는다)
      await waitFor(() =>
        expect(updateProfileSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            preferredRegions: expect.arrayContaining([targetRegion]),
            style: nextProfile.style,
            budget: nextProfile.budget,
          }),
        ),
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: "프로필 편집" }),
        ).not.toBeInTheDocument(),
      );
      expect(screen.getByText(nextUser.nickname)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "편집" })).toBeInTheDocument();
    } finally {
      updateNicknameSpy.mockRestore();
      getCurrentUserSpy?.mockRestore();
      updateProfileSpy.mockRestore();
    }
  });

  it("validates and suggests nicknames from the my page profile editor", async () => {
    await login();
    const updateNicknameSpy = vi.spyOn(appDataApi, "updateNickname");
    const updateProfileSpy = vi.spyOn(appDataApi, "updateProfile");
    const suggestionSpy = vi
      .spyOn(appDataApi, "getNicknameSuggestion")
      .mockResolvedValue({ nickname: "반짝여행자123" });

    try {
      cleanup();
      renderAppRoute("/mypage");
      const user = userEvent.setup();

      // 서버 프로필을 받기 전엔 편집을 못 연다(빈 자리값으로 저장돼 지워지지 않게) - 켜질 때까지 기다린다
      const editButton = await screen.findByRole("button", { name: "편집" });
      await waitFor(() => expect(editButton).toBeEnabled());
      await user.click(editButton);
      const dialog = screen.getByRole("dialog", { name: "프로필 편집" });
      const nicknameInput = within(dialog).getByRole("textbox", {
        name: "닉네임",
      });

      await user.clear(nicknameInput);
      await user.type(nicknameInput, "가");
      await user.click(
        within(dialog).getByRole("button", { name: "저장" }),
      );
      expect(
        await within(dialog).findByText(
          "닉네임은 2자 이상 20자 이하로 입력해 주세요.",
        ),
      ).toBeInTheDocument();
      expect(updateNicknameSpy).not.toHaveBeenCalled();
      expect(updateProfileSpy).not.toHaveBeenCalled();

      await user.click(
        within(dialog).getByRole("button", { name: "추천 받기" }),
      );
      await waitFor(() => expect(nicknameInput).toHaveValue("반짝여행자123"));
    } finally {
      updateNicknameSpy.mockRestore();
      updateProfileSpy.mockRestore();
      suggestionSpy.mockRestore();
    }
  });

  it("shows a nickname suggestion error from the my page profile editor", async () => {
    await login();
    const suggestionSpy = vi
      .spyOn(appDataApi, "getNicknameSuggestion")
      .mockRejectedValue(new Error("suggest failed"));

    try {
      cleanup();
      renderAppRoute("/mypage");
      const user = userEvent.setup();

      // 서버 프로필을 받기 전엔 편집을 못 연다(빈 자리값으로 저장돼 지워지지 않게) - 켜질 때까지 기다린다
      const editButton = await screen.findByRole("button", { name: "편집" });
      await waitFor(() => expect(editButton).toBeEnabled());
      await user.click(editButton);
      const dialog = screen.getByRole("dialog", { name: "프로필 편집" });
      await user.click(
        within(dialog).getByRole("button", { name: "추천 받기" }),
      );

      expect(
        await within(dialog).findByText(
          "닉네임을 추천하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ),
      ).toBeInTheDocument();
    } finally {
      suggestionSpy.mockRestore();
    }
  });

  it("shows one trip title in the my page trip summary", async () => {
    const trip: Trip = {
      ...getUpcomingPreviewTrip(),
      id: "101",
      title: "부산 맛집 여행",
    };

    await login();
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue([trip]);

    try {
      cleanup();
      renderAppRoute("/mypage");

      const summary = await screen.findByLabelText("나의 활동 요약");
      await waitFor(() =>
        expect(within(summary).getByText("내 일정")).toBeInTheDocument(),
      );
      const tripStat = within(summary)
        .getByText("내 일정")
        .closest(".mp-stat");
      expect(tripStat).not.toBeNull();
      await waitFor(() =>
        expect(
          within(tripStat as HTMLElement).getByText("1"),
        ).toBeInTheDocument(),
      );
    } finally {
      listTripsSpy.mockRestore();
    }
  });

  it("shows the trip count in the my page stats", async () => {
    const trips: Trip[] = [
      { ...getUpcomingPreviewTrip(), id: "101", title: "부산 맛집 여행" },
      { ...getUpcomingPreviewTrip(), id: "102", title: "강원 2일 여행" },
      { ...getUpcomingPreviewTrip(), id: "103", title: "제주 3일 여행" },
    ];

    await login();
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockResolvedValue(trips);

    try {
      cleanup();
      renderAppRoute("/mypage");

      const summary = await screen.findByLabelText("나의 활동 요약");
      await waitFor(() =>
        expect(within(summary).getByText("내 일정")).toBeInTheDocument(),
      );
      const tripStat = within(summary)
        .getByText("내 일정")
        .closest(".mp-stat");
      expect(tripStat).not.toBeNull();
      await waitFor(() =>
        expect(
          within(tripStat as HTMLElement).getByText("3"),
        ).toBeInTheDocument(),
      );
    } finally {
      listTripsSpy.mockRestore();
    }
  });

  it("shows the applied policy count in the my page stats", async () => {
    const appliedPolicies: Policy[] = [
      {
        id: examplePolicySlug,
        slug: examplePolicySlug,
        label: "지",
        tag: "최대 30만원 환급",
        title: examplePolicyTitle,
        org: "문화체육관광부",
        region: "전국",
        deadline: "2026-10-31",
        amount: "최대 30만원 환급",
        summary: "국내 여행 지원",
        match: 98,
        category: "지역할인",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
      },
      {
        id: "gangneung-stay",
        slug: "gangneung-stay",
        label: "속",
        tag: "숙박 할인",
        title: "강릉 숙박 할인권",
        org: "강릉시",
        region: "강원",
        deadline: "2026-08-15",
        amount: "숙박비 50% 할인",
        summary: "숙박 할인",
        match: 90,
        category: "숙박",
        requirements: [],
        documents: [],
        officialUrl: null,
        applyUrl: null,
      },
    ];

    await login();
    const listAppliedPoliciesSpy = vi
      .spyOn(appDataApi, "listAppliedPolicies")
      .mockResolvedValue(appliedPolicies);

    try {
      cleanup();
      renderAppRoute("/mypage");

      const summary = await screen.findByLabelText("나의 활동 요약");
      const appliedPolicyStat = within(summary)
        .getByText("담은 혜택")
        .closest(".mp-stat") as HTMLElement;
      expect(appliedPolicyStat).toBeTruthy();
      await waitFor(() =>
        expect(within(appliedPolicyStat).getByText("2")).toBeInTheDocument(),
      );
    } finally {
      listAppliedPoliciesSpy.mockRestore();
    }
  });

  it("keeps the my page stats visible when trips fail to load", async () => {
    await login();
    const listTripsSpy = vi
      .spyOn(appDataApi, "listTrips")
      .mockRejectedValue(new Error("load failed"));

    try {
      cleanup();
      renderAppRoute("/mypage");

      const summary = await screen.findByLabelText("나의 활동 요약");
      await waitFor(() =>
        expect(within(summary).getByText("내 일정")).toBeInTheDocument(),
      );
      const tripStat = within(summary)
        .getByText("내 일정")
        .closest(".mp-stat");
      expect(tripStat).not.toBeNull();
      await waitFor(() =>
        expect(
          within(tripStat as HTMLElement).getByText("0"),
        ).toBeInTheDocument(),
      );
      expect(document.body).not.toHaveTextContent(
        "일정 정보를 불러오지 못했어요",
      );
    } finally {
      listTripsSpy.mockRestore();
    }
  });

  it("keeps account actions as settings menu rows with responsive dialogs", async () => {
    const accountUser = { ...getPreviewUser(), hasPassword: true };
    installStoredUser(accountUser);
    const loadSpies = mockMyPageAccountLoad(accountUser);

    try {
      renderAppRoute("/mypage");
      const user = userEvent.setup();

      const settingsMenu = await screen.findByRole("region", { name: "설정 메뉴" });
      const passwordButton = within(settingsMenu).getByRole("button", {
        name: /비밀번호 관리/,
      });
      // 회원 탈퇴는 설정 줄 밖, 맨 아래 작은 글자(시안 v49) - 빨강은 탈퇴 창 안에서만
      expect(within(settingsMenu).queryByRole("button", { name: /회원 탈퇴/ })).not.toBeInTheDocument();
      const withdrawalButton = screen.getByRole("button", { name: "회원 탈퇴" });

      expect(passwordButton).toHaveClass("mp-row");
      expect(passwordButton).not.toHaveClass("danger");
      expect(withdrawalButton).toHaveClass("mp-quit");
      expect(screen.queryByRole("region", { name: "비밀번호 관리" })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "회원 탈퇴" })).not.toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "비밀번호 관리" })).not.toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "회원 탈퇴" })).not.toBeInTheDocument();

      await user.click(passwordButton);
      const passwordDialog = await screen.findByRole("dialog", { name: "비밀번호 관리" });
      expect(passwordDialog).toHaveClass("prototype-account-dialog");
      expect(passwordDialog.querySelector(".prototype-account-handle")).toBeTruthy();
      expect(within(passwordDialog).getByRole("button", { name: "비밀번호 변경" })).toBeInTheDocument();
      await user.click(within(passwordDialog).getByRole("button", { name: "비밀번호 관리 닫기" }));
      await waitFor(() =>
        expect(screen.queryByRole("dialog", { name: "비밀번호 관리" })).not.toBeInTheDocument(),
      );
      await waitFor(() => expect(passwordButton).toHaveFocus());

      await user.click(withdrawalButton);
      const withdrawalDialog = await screen.findByRole("dialog", { name: "회원 탈퇴" });
      expect(withdrawalDialog).toHaveClass("prototype-account-dialog");
      expect(withdrawalDialog.querySelector(".prototype-account-notice")).toBeTruthy();
      expect(within(withdrawalDialog).getByRole("button", { name: "회원 탈퇴" })).toBeInTheDocument();
    } finally {
      loadSpies.forEach((spy) => spy.mockRestore());
    }
  });

  it("lets password users change password, clears auth, and redirects to login", async () => {
    const accountUser = { ...getPreviewUser(), hasPassword: true };
    installStoredUser(accountUser);
    const loadSpies = mockMyPageAccountLoad(accountUser);
    const changePasswordSpy = vi
      .spyOn(appDataApi, "changePassword")
      .mockResolvedValue({ changed: true });
    const logoutSpy = vi
      .spyOn(appDataApi, "logout")
      .mockResolvedValue({ loggedOut: true });

    try {
      renderAppRoute("/mypage");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /비밀번호 관리/ }));
      const passwordSection = await screen.findByRole("dialog", { name: "비밀번호 관리" });

      await user.click(within(passwordSection).getByRole("button", { name: "비밀번호 변경" }));
      expect(await within(passwordSection).findByRole("alert")).toHaveTextContent(
        "현재 비밀번호를 입력해 주세요.",
      );

      await user.type(within(passwordSection).getByLabelText("현재 비밀번호"), "old-password123");
      await user.type(within(passwordSection).getByLabelText("새 비밀번호"), "new-password123");
      await user.click(within(passwordSection).getByRole("button", { name: "비밀번호 변경" }));

      await waitFor(() =>
        expect(changePasswordSpy).toHaveBeenCalledWith({
          currentPassword: "old-password123",
          newPassword: "new-password123",
        }),
      );
      await waitFor(() => expect(logoutSpy).toHaveBeenCalled());
      await waitFor(() =>
        expect(window.localStorage.getItem("travel-hunter-production-auth")).toBeNull(),
      );
      expect(await screen.findByRole("heading", { name: "트래블헌터" })).toBeInTheDocument();
    } finally {
      changePasswordSpy.mockRestore();
      logoutSpy.mockRestore();
      loadSpies.forEach((spy) => spy.mockRestore());
    }
  });

  it("clears password dialog secrets and restores menu focus after Escape", async () => {
    const accountUser = { ...getPreviewUser(), hasPassword: true };
    installStoredUser(accountUser);
    const loadSpies = mockMyPageAccountLoad(accountUser);

    try {
      renderAppRoute("/mypage");
      const user = userEvent.setup();
      const opener = await screen.findByRole("button", { name: /비밀번호 관리/ });
      await user.click(opener);
      let passwordDialog = await screen.findByRole("dialog", { name: "비밀번호 관리" });
      expect(passwordDialog.querySelector("form")).toBeInTheDocument();

      await user.type(within(passwordDialog).getByLabelText("현재 비밀번호"), "old-password123");
      await user.type(within(passwordDialog).getByLabelText("새 비밀번호"), "short");
      await user.click(within(passwordDialog).getByRole("button", { name: "비밀번호 변경" }));
      expect(await within(passwordDialog).findByRole("alert")).toBeInTheDocument();

      await user.keyboard("{Escape}");
      expect(screen.queryByRole("dialog", { name: "비밀번호 관리" })).not.toBeInTheDocument();
      expect(opener).toHaveFocus();

      await user.click(opener);
      passwordDialog = await screen.findByRole("dialog", { name: "비밀번호 관리" });
      expect(within(passwordDialog).getByLabelText("현재 비밀번호")).toHaveValue("");
      expect(within(passwordDialog).getByLabelText("새 비밀번호")).toHaveValue("");
      expect(within(passwordDialog).queryByRole("alert")).not.toBeInTheDocument();
    } finally {
      loadSpies.forEach((spy) => spy.mockRestore());
    }
  });

  it("uses hasPassword for OAuth-only account guidance and confirmation withdrawal", async () => {
    const oauthOnlyUser = {
      ...getPreviewUser(),
      hasPassword: false,
      socialAccounts: [
        { provider: "google", providerNickname: "소셜유저", connectedAt: "2026-06-26T00:00:00Z" },
      ],
    };
    installStoredUser(oauthOnlyUser);
    const loadSpies = mockMyPageAccountLoad(oauthOnlyUser);
    const withdrawSpy = vi
      .spyOn(appDataApi, "withdraw")
      .mockResolvedValue({ withdrawn: true });
    const logoutSpy = vi
      .spyOn(appDataApi, "logout")
      .mockResolvedValue({ loggedOut: true });

    try {
      renderAppRoute("/mypage");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /비밀번호 관리/ }));
      const passwordSection = await screen.findByRole("dialog", { name: "비밀번호 관리" });
      expect(within(passwordSection).getByText("소셜 로그인 계정입니다")).toBeInTheDocument();
      expect(within(passwordSection).queryByRole("button", { name: "비밀번호 변경" })).not.toBeInTheDocument();
      await user.click(within(passwordSection).getByRole("button", { name: "확인" }));

      await user.click(screen.getByRole("button", { name: /회원 탈퇴/ }));
      const withdrawalSection = await screen.findByRole("dialog", { name: "회원 탈퇴" });
      expect(within(withdrawalSection).getByText("탈퇴 후 계정은 복구할 수 없습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByText("같은 이메일로 다시 가입할 수 있습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByText("새로 가입해도 이전 데이터는 복원되지 않습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByLabelText("확인 문구")).toBeInTheDocument();
      expect(within(withdrawalSection).queryByLabelText("현재 비밀번호")).not.toBeInTheDocument();

      await user.type(within(withdrawalSection).getByLabelText("확인 문구"), "탈퇴할게요");
      await user.click(within(withdrawalSection).getByRole("button", { name: "회원 탈퇴" }));
      expect(await within(withdrawalSection).findByRole("alert")).toHaveTextContent(
        "탈퇴하려면 확인 문구 탈퇴합니다를 정확히 입력해 주세요.",
      );
      expect(withdrawSpy).not.toHaveBeenCalled();

      await user.clear(within(withdrawalSection).getByLabelText("확인 문구"));
      await user.type(within(withdrawalSection).getByLabelText("확인 문구"), "탈퇴합니다");
      await user.click(within(withdrawalSection).getByRole("button", { name: "회원 탈퇴" }));

      const finalDialog = await screen.findByRole("alertdialog", { name: "정말 탈퇴하시겠어요?" });
      expect(withdrawSpy).not.toHaveBeenCalled();
      await user.click(within(finalDialog).getByRole("button", { name: "탈퇴 확정" }));

      await waitFor(() =>
        expect(withdrawSpy).toHaveBeenCalledWith({ confirmationPhrase: "탈퇴합니다" }),
      );
      await waitFor(() => expect(logoutSpy).toHaveBeenCalled());
      expect(await screen.findByRole("heading", { name: "트래블헌터" })).toBeInTheDocument();
    } finally {
      withdrawSpy.mockRestore();
      logoutSpy.mockRestore();
      loadSpies.forEach((spy) => spy.mockRestore());
    }
  });

  it("requires password confirmation for password user withdrawal", async () => {
    const accountUser = { ...getPreviewUser(), hasPassword: true };
    installStoredUser(accountUser);
    const loadSpies = mockMyPageAccountLoad(accountUser);
    const withdrawSpy = vi
      .spyOn(appDataApi, "withdraw")
      .mockResolvedValue({ withdrawn: true });
    const logoutSpy = vi
      .spyOn(appDataApi, "logout")
      .mockResolvedValue({ loggedOut: true });

    try {
      renderAppRoute("/mypage");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /회원 탈퇴/ }));
      const withdrawalSection = await screen.findByRole("dialog", { name: "회원 탈퇴" });
      expect(within(withdrawalSection).getByText("탈퇴 후 계정은 복구할 수 없습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByText("같은 이메일로 다시 가입할 수 있습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByText("새로 가입해도 이전 데이터는 복원되지 않습니다.")).toBeInTheDocument();
      expect(within(withdrawalSection).getByLabelText("현재 비밀번호")).toBeInTheDocument();
      expect(within(withdrawalSection).queryByLabelText("확인 문구")).not.toBeInTheDocument();

      await user.click(within(withdrawalSection).getByRole("button", { name: "회원 탈퇴" }));
      expect(await within(withdrawalSection).findByRole("alert")).toHaveTextContent(
        "탈퇴하려면 현재 비밀번호를 입력해 주세요.",
      );
      expect(withdrawSpy).not.toHaveBeenCalled();

      await user.type(within(withdrawalSection).getByLabelText("현재 비밀번호"), "password123");
      await user.keyboard("{Enter}");
      let finalDialog = await screen.findByRole("alertdialog", { name: "정말 탈퇴하시겠어요?" });
      expect(document.body.style.overflow).toBe("hidden");
      expect(screen.queryByRole("dialog", { name: "회원 탈퇴" })).not.toBeInTheDocument();
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("alertdialog", { name: "정말 탈퇴하시겠어요?" })).not.toBeInTheDocument();
      const returnedWithdrawalSection = await screen.findByRole("dialog", { name: "회원 탈퇴" });
      expect(returnedWithdrawalSection.querySelector("form")).toBeInTheDocument();
      expect(within(returnedWithdrawalSection).getByLabelText("현재 비밀번호")).toHaveValue("password123");
      expect(document.body.style.overflow).toBe("hidden");
      expect(withdrawSpy).not.toHaveBeenCalled();

      await user.click(within(returnedWithdrawalSection).getByRole("button", { name: "취소" }));
      await waitFor(() => expect(document.body.style.overflow).toBe(""));

      await user.click(screen.getByRole("button", { name: /회원 탈퇴/ }));
      const reopenedWithdrawalSection = await screen.findByRole("dialog", { name: "회원 탈퇴" });
      await user.type(within(reopenedWithdrawalSection).getByLabelText("현재 비밀번호"), "password123");
      await user.click(within(reopenedWithdrawalSection).getByRole("button", { name: "회원 탈퇴" }));
      finalDialog = await screen.findByRole("alertdialog", { name: "정말 탈퇴하시겠어요?" });
      expect(withdrawSpy).not.toHaveBeenCalled();
      await user.click(within(finalDialog).getByRole("button", { name: "탈퇴 확정" }));
      await waitFor(() => expect(withdrawSpy).toHaveBeenCalledWith({ password: "password123" }));
      await waitFor(() => expect(logoutSpy).toHaveBeenCalled());
    } finally {
      withdrawSpy.mockRestore();
      logoutSpy.mockRestore();
      loadSpies.forEach((spy) => spy.mockRestore());
    }
  });

});
