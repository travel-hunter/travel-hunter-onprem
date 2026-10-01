import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type AdminPhotoReviewCandidate,
  type AdminPhotoReviewTarget,
  type AdminPhotoReviewTargetDetail,
  type User,
} from "../../api";
import { getPreviewUser } from "../../test/fixtures";
import { renderAppRoute } from "../../test/renderAppRoute";

function installAdmin() {
  const user: User & { role: "admin" } = { ...getPreviewUser(), role: "admin" };
  vi.stubEnv("VITE_ADMIN_BASE_URL", "");
  window.localStorage.setItem("travel-hunter-production-auth", JSON.stringify({ accessToken: "test-token", user }));
  vi.spyOn(appDataApi, "getCurrentUser").mockResolvedValue(user);
  vi.spyOn(appDataApi, "getProfile").mockResolvedValue({ preferredRegions: null, style: "Food", budget: "400000 KRW" });
  vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);
  vi.spyOn(appDataApi, "getAdminPhotoReviewCollect").mockResolvedValue(idleCollect);
}

const idleCollect = {
  running: false,
  startedAt: null,
  finishedAt: null,
  done: 0,
  total: 0,
  candidatesAdded: 0,
  targetsCreated: 0,
  targetsEmpty: 0,
  error: null,
  lastRun: { at: "2026-10-01T15:31:00Z", candidatesAdded: 899 },
};

function candidate(id: string, overrides: Partial<AdminPhotoReviewCandidate> = {}): AdminPhotoReviewCandidate {
  return {
    id,
    title: `관광지 ${id}`,
    kind: "관광지",
    contentTypeId: "12",
    imageUrl: `https://tong.example/${id}.jpg`,
    thumbnailUrl: null,
    copyrightType: "Type1",
    width: 940,
    height: 626,
    address: "전남 담양군",
    source: "collect",
    searchKeyword: null,
    ...overrides,
  };
}

function target(id: string, overrides: Partial<AdminPhotoReviewTarget> = {}): AdminPhotoReviewTarget {
  return {
    id,
    unit: "region",
    status: "pending",
    sido: "전남",
    city: "담양",
    policySlug: null,
    policyTitle: null,
    policyCategory: null,
    benefitCount: 3,
    candidateCount: 2,
    photo: null,
    inheritedPhoto: null,
    decidedAt: null,
    ...overrides,
  };
}

function detail(base: AdminPhotoReviewTarget, candidates: AdminPhotoReviewCandidate[]): AdminPhotoReviewTargetDetail {
  return { ...base, candidates };
}

const counts = { pending: 2, approved: 0, none: 0, all: 2 };
const extra = { newTargets: 0, shortTargets: 0 };

describe("admin photo review", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    window.localStorage.clear();
  });

  it("approves the picked photo and moves on to the next pending city", async () => {
    installAdmin();
    const damyang = target("1");
    const namwon = target("2", { city: "남원", sido: "전북" });
    vi.spyOn(appDataApi, "listAdminPhotoReviewTargets").mockResolvedValue({ items: [damyang, namwon], counts, pendingTotal: 5, ...extra });
    const getSpy = vi
      .spyOn(appDataApi, "getAdminPhotoReviewTarget")
      .mockImplementation(async (id) => (id === "1" ? detail(damyang, [candidate("11"), candidate("12")]) : detail(namwon, [candidate("21")])));
    const approveSpy = vi.spyOn(appDataApi, "approveAdminPhotoReviewTarget").mockResolvedValue(
      detail({ ...damyang, status: "approved", photo: { candidateId: "12", title: "관광지 12", imageUrl: "https://tong.example/12.jpg", thumbnailUrl: null, copyrightType: "Type1" } }, [candidate("11"), candidate("12")]),
    );

    renderAppRoute("/admin/photo-review");

    await screen.findByRole("heading", { name: "담양" });
    const confirm = screen.getByRole("button", { name: "이 사진으로 확정" });
    expect(confirm).toBeDisabled();
    expect(screen.getByText("확정 전에는 혜택 그림이 나갑니다")).toBeInTheDocument();
    // 사진 검토 대기 수가 왼쪽 메뉴에 붙는다
    expect(screen.getByLabelText("검토 대기 5건")).toHaveTextContent("5");

    await userEvent.click(screen.getByRole("radio", { name: /관광지 12/ }));
    expect(document.querySelector(".photo-review-credit")).toHaveTextContent("사진: 한국관광공사공공누리 제1유형");
    await userEvent.click(confirm);

    expect(approveSpy).toHaveBeenCalledWith("1", "12");
    await screen.findByRole("heading", { name: "남원" });
    expect(getSpy).toHaveBeenLastCalledWith("2");
    expect(screen.getByRole("status")).toHaveTextContent("담양: 사진을 확정했습니다 · 다음 남원");
  });

  it("shows a policy's inherited city photo and switches units", async () => {
    installAdmin();
    const listSpy = vi.spyOn(appDataApi, "listAdminPhotoReviewTargets").mockImplementation(async ({ unit }) =>
      unit === "region"
        ? { items: [target("1")], counts: { pending: 1, approved: 0, none: 0, all: 1 }, pendingTotal: 2, ...extra }
        : {
            items: [
              target("5", {
                unit: "policy",
                policySlug: "dgtour-damyang",
                policyTitle: "[담양] 디지털관광주민증 혜택",
                policyCategory: "할인",
                inheritedPhoto: { candidateId: "9", title: "죽녹원", imageUrl: "https://tong.example/9.jpg", thumbnailUrl: null, copyrightType: "Type1" },
              }),
            ],
            counts: { pending: 1, approved: 0, none: 0, all: 1 },
            pendingTotal: 2,
            ...extra,
          },
    );
    vi.spyOn(appDataApi, "getAdminPhotoReviewTarget").mockImplementation(async (id) =>
      id === "1"
        ? detail(target("1"), [candidate("11")])
        : detail(
            target("5", {
              unit: "policy",
              policyTitle: "[담양] 디지털관광주민증 혜택",
              policyCategory: "할인",
              inheritedPhoto: { candidateId: "9", title: "죽녹원", imageUrl: "https://tong.example/9.jpg", thumbnailUrl: null, copyrightType: "Type1" },
            }),
            [candidate("51")],
          ),
    );
    const noneSpy = vi.spyOn(appDataApi, "markAdminPhotoReviewTargetNone").mockResolvedValue(
      detail(target("5", { unit: "policy", status: "none", policyTitle: "[담양] 디지털관광주민증 혜택" }), [candidate("51")]),
    );

    renderAppRoute("/admin/photo-review");
    await screen.findByRole("heading", { name: "담양" });
    await userEvent.click(screen.getByRole("button", { name: /정책 사진/ }));

    await screen.findByRole("heading", { name: "디지털관광주민증 혜택" });
    expect(listSpy).toHaveBeenLastCalledWith({ unit: "policy", status: "pending" });
    expect(screen.getByText("시군 사진(죽녹원)을 그대로 씁니다")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "상태로 거르기" })).toHaveTextContent("시군 사진");

    await userEvent.click(screen.getByRole("button", { name: "시군 사진 그대로 쓰기" }));
    expect(noneSpy).toHaveBeenCalledWith("5");
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("시군 사진을 그대로 씁니다"));
  });

  it("finds a landmark by name and says so when nothing new turns up", async () => {
    installAdmin();
    const damyang = target("1");
    vi.spyOn(appDataApi, "listAdminPhotoReviewTargets").mockResolvedValue({ items: [damyang], counts: { pending: 1, approved: 0, none: 0, all: 1 }, pendingTotal: 1, ...extra });
    vi.spyOn(appDataApi, "getAdminPhotoReviewTarget").mockResolvedValue(detail(damyang, [candidate("11")]));
    const found = candidate("31", { title: "죽녹원", source: "search", searchKeyword: "죽녹원" });
    const searchSpy = vi
      .spyOn(appDataApi, "searchAdminPhotoReviewCandidates")
      .mockResolvedValueOnce(detail(damyang, [candidate("11"), found]))
      .mockResolvedValueOnce(detail(damyang, [candidate("11"), found]));

    renderAppRoute("/admin/photo-review");
    await screen.findByRole("heading", { name: "담양" });

    await userEvent.type(screen.getByLabelText("이름으로 찾기"), "죽녹원");
    await userEvent.click(screen.getByRole("button", { name: "찾기" }));

    expect(searchSpy).toHaveBeenCalledWith("1", "죽녹원");
    const group = await screen.findByRole("group", { name: /찾은 사진/ });
    expect(within(group).getByRole("radio", { name: /죽녹원/ })).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("이름으로 찾기"));
    await userEvent.type(screen.getByLabelText("이름으로 찾기"), "없는곳");
    await userEvent.click(screen.getByRole("button", { name: "찾기" }));
    expect(await screen.findByText(/‘없는곳’\(으\)로 새로 찾은 사진이 없습니다/)).toBeInTheDocument();
  });

  it("explains a TourAPI outage instead of failing silently", async () => {
    installAdmin();
    const damyang = target("1");
    vi.spyOn(appDataApi, "listAdminPhotoReviewTargets").mockResolvedValue({ items: [damyang], counts: { pending: 1, approved: 0, none: 0, all: 1 }, pendingTotal: 1, ...extra });
    vi.spyOn(appDataApi, "getAdminPhotoReviewTarget").mockResolvedValue(detail(damyang, []));
    vi.spyOn(appDataApi, "fetchMoreAdminPhotoReviewCandidates").mockRejectedValue(
      new ApiError("TourAPI is disabled", { status: 503, statusText: "Service Unavailable" }),
    );

    renderAppRoute("/admin/photo-review");
    await screen.findByRole("heading", { name: "담양" });
    expect(screen.getByText(/후보가 아직 없습니다/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "후보 6장 더 받기" }));
    expect(await screen.findByText("관광공사 API 가 꺼져 있어 사진을 받을 수 없습니다.")).toBeInTheDocument();
  });

  it("fills candidates in the background and reloads when the run ends", async () => {
    installAdmin();
    const damyang = target("1");
    const listSpy = vi
      .spyOn(appDataApi, "listAdminPhotoReviewTargets")
      .mockResolvedValue({ items: [damyang], counts: { pending: 1, approved: 0, none: 0, all: 1 }, pendingTotal: 1, newTargets: 3, shortTargets: 1 });
    vi.spyOn(appDataApi, "getAdminPhotoReviewTarget").mockResolvedValue(detail(damyang, [candidate("11")]));
    const running = { ...idleCollect, running: true, startedAt: "2026-10-01T16:00:00Z", done: 1, total: 4, candidatesAdded: 6 };
    const finished = { ...running, running: false, finishedAt: "2026-10-01T16:01:00Z", done: 4, candidatesAdded: 18, targetsCreated: 3, targetsEmpty: 1 };
    const startSpy = vi.spyOn(appDataApi, "startAdminPhotoReviewCollect").mockResolvedValue(running);
    vi.mocked(appDataApi.getAdminPhotoReviewCollect).mockResolvedValueOnce(idleCollect).mockResolvedValue(finished);

    renderAppRoute("/admin/photo-review");
    await screen.findByRole("heading", { name: "담양" });
    const box = document.querySelector(".photo-review-collect") as HTMLElement;
    await waitFor(() => expect(box).toHaveTextContent("마지막 수집"));
    expect(box).toHaveTextContent("새로 들어올 대상 3곳");
    expect(box).toHaveTextContent("후보가 모자란 대상 1곳");
    expect(box).toHaveTextContent("899장");

    const listCalls = listSpy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "후보 채우기" }));
    expect(startSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("button", { name: "후보 받는 중…" })).toBeDisabled();
    expect(document.querySelector(".photo-review-collect")).toHaveTextContent("1/4곳 · 후보 6장");

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("후보 18장을 넣었습니다 · 새 대상 3곳 · 못 채운 1곳은 이름으로 찾아 주세요"), { timeout: 4000 });
    expect(screen.getByRole("button", { name: "후보 채우기" })).toBeEnabled();
    expect(listSpy.mock.calls.length).toBeGreaterThan(listCalls);
  });

  it("says a run is already going instead of starting a second one", async () => {
    installAdmin();
    const damyang = target("1");
    vi.spyOn(appDataApi, "listAdminPhotoReviewTargets").mockResolvedValue({ items: [damyang], counts: { pending: 1, approved: 0, none: 0, all: 1 }, pendingTotal: 1, ...extra });
    vi.spyOn(appDataApi, "getAdminPhotoReviewTarget").mockResolvedValue(detail(damyang, [candidate("11")]));
    vi.spyOn(appDataApi, "startAdminPhotoReviewCollect").mockRejectedValue(
      new ApiError("Photo candidate collection is already running", { status: 409, statusText: "Conflict" }),
    );

    renderAppRoute("/admin/photo-review");
    await screen.findByRole("heading", { name: "담양" });
    await userEvent.click(screen.getByRole("button", { name: "후보 채우기" }));
    expect(await screen.findByText("이미 후보를 받는 중입니다.")).toBeInTheDocument();
  });
});
