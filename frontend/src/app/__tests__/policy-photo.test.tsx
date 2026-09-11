import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appDataApi, type Policy, type PolicyPhoto as PolicyPhotoType } from "../../api";
import { PolicyThumbPhoto } from "../../components/policyPhoto";
import { login, renderAppRoute } from "../../test/renderAppRoute";

const photo: PolicyPhotoType = {
  imageUrl: "https://tong.visitkorea.or.kr/cms/resource/haenam.jpg",
  thumbnailUrl: "https://tong.visitkorea.or.kr/cms/resource/haenam_t.jpg",
  alt: "두륜산 케이블카",
  attribution: "사진: 한국관광공사",
};

function makePolicy(overrides: Partial<Policy> = {}): Policy {
  return {
    id: "travelmonth-77",
    slug: "travelmonth-77",
    label: "전남",
    tag: "최대 2만원",
    title: "해남 공식 할인",
    org: "전라남도",
    region: "전남",
    deadline: "2026-10-31",
    amount: "최대 2만원",
    summary: "해남 관광 할인",
    match: 80,
    category: "지역할인",
    requirements: [],
    documents: [],
    officialUrl: "https://korean.visitkorea.or.kr/",
    applyUrl: null,
    sourceType: "external",
    ...overrides,
  };
}

/* 지도 화면엔 지도 밑 목록이 없다(시안 그대로). 목록 카드는 시트 손잡이 → 지역 타일을 거쳐야 보인다. */
async function openSheetTile(tile: RegExp) {
  const grab = await waitFor(() => {
    const button = document.querySelector(".thmap-grab");
    expect(button).toBeTruthy();
    return button as HTMLButtonElement;
  });
  fireEvent.click(grab);
  const sheet = document.querySelector(".thmap-sheet") as HTMLElement;
  fireEvent.click(within(sheet).getByRole("button", { name: tile }));
}

describe("Travel Hunter app — policy region photos", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  it("renders hero photo with mandatory attribution on the detail screen", async () => {
    vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(makePolicy({ photo }));
    vi.spyOn(appDataApi, "listTrips").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies/travelmonth-77");

    await waitFor(() => {
      expect(screen.getByRole("img", { name: "두륜산 케이블카" })).toBeInTheDocument();
    });
    expect(screen.getByText("사진: 한국관광공사")).toBeInTheDocument();
  });

  it("keeps the emoji hero when the policy has no photo", async () => {
    vi.spyOn(appDataApi, "getPolicy").mockResolvedValue(makePolicy({ photo: null }));
    vi.spyOn(appDataApi, "listTrips").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies/travelmonth-77");

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.queryByText("사진: 한국관광공사")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "두륜산 케이블카" })).not.toBeInTheDocument();
  });

  it("shows list thumbnails and a single attribution line when any photo renders", async () => {
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo }),
      makePolicy({ id: "p2", slug: "p2", title: "사진 없는 정책", photo: null }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies");
    await openSheetTile(/^전남\s*\d/);

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.getByRole("img", { name: "두륜산 케이블카" })).toBeInTheDocument();
    expect(screen.getAllByText("사진: 한국관광공사")).toHaveLength(1);
  });

  it("uses the API attribution for a fallback-provider photo in the list", async () => {
    const pixabayAttribution = "Photo: photographer via Pixabay";
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo: { ...photo, attribution: pixabayAttribution } }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies");
    await openSheetTile(/^전남\s*\d/);

    await waitFor(() => {
      expect(screen.getByText(pixabayAttribution)).toBeInTheDocument();
    });
  });

  it("omits the list attribution line when no policy has a photo", async () => {
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo: null }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies");
    await openSheetTile(/^전남\s*\d/);

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.queryByText("사진: 한국관광공사")).not.toBeInTheDocument();
  });

  it("keeps a single attribution line on the grouped region list behind the map pill", async () => {
    // 지역을 고르고 알약을 누르면 종류별 그룹 목록이다 - 여기도 사진이 보이므로 출처 줄이 붙어야 한다
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo }),
      makePolicy({ id: "p2", slug: "p2", title: "[완도] 디지털관광주민증 혜택", photo: { ...photo, alt: "완도 타워" } }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies");
    // 지도에서 전남을 눌러야 표시가 뜬다 - URL 의 region 은 이제 필터일 뿐 지도를 안 움직인다
    await waitFor(() => expect(document.querySelector('.thmap-rg[data-region="전남"]')).toBeTruthy());
    fireEvent.click(document.querySelector('.thmap-rg[data-region="전남"]') as unknown as Element);

    fireEvent.click(await screen.findByRole("button", { name: "전남 정책 2건 보기" }));
    // 제목이 그룹 헤더에도 한 번 더 있으니 사진으로 카드를 센다
    await waitFor(() => {
      expect(screen.getByRole("img", { name: "완도 타워" })).toBeInTheDocument();
    });
    expect(document.querySelectorAll(".thmap-grp")).toHaveLength(2);
    expect(screen.getByRole("img", { name: "두륜산 케이블카" })).toBeInTheDocument();
    expect(screen.getAllByText("사진: 한국관광공사")).toHaveLength(1);
  });

  it("falls back to the emoji tile when the thumbnail image fails to load", () => {
    render(<PolicyThumbPhoto fallback={<span>💸</span>} photo={photo} />);
    const image = screen.getByRole("img", { name: "두륜산 케이블카" });
    fireEvent.error(image);
    expect(screen.queryByRole("img", { name: "두륜산 케이블카" })).not.toBeInTheDocument();
    expect(screen.getByText("💸")).toBeInTheDocument();
  });
});
