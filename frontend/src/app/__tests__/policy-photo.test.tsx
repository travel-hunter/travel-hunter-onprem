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

/* 정책 사진은 목록 카드(검색·필터 목록)와 상세에만 있다. 지도 뒤 목록 시트의 줄은 혜택 형태 그림을 쓴다.
   지역 필터(region=)를 걸면 목록 카드 화면이 된다. */
const listRoute = "/policies?region=전남";

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
    renderAppRoute(listRoute);

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
    renderAppRoute(listRoute);

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
    renderAppRoute(listRoute);

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.queryByText("사진: 한국관광공사")).not.toBeInTheDocument();
  });

  it("keeps policy photos off the map list - rows show the benefit kind instead, so no credit line", async () => {
    // 사진은 상세에만(시안 결정). 사진을 안 보이는 목록에 출처 줄만 남으면 안 된다
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo }),
      makePolicy({ id: "p2", slug: "p2", title: "[완도] 디지털관광주민증 혜택", photo: { ...photo, alt: "완도 타워" } }),
      makePolicy({
        id: "gangwon-photo",
        slug: "gangwon-photo",
        title: "강원 관광 혜택",
        region: "강원",
        photo: { ...photo, alt: "강원 관광지", attribution: "사진: 강원관광재단" },
      }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies?place=전남");
    const sheet = await waitFor(() => {
      const element = document.querySelector(".thmap-sheet") as HTMLElement | null;
      expect(element?.querySelector(".thmap-title")).toHaveTextContent("전남 2건");
      return element as HTMLElement;
    });
    expect(within(sheet).getByText("해남 공식 할인")).toBeInTheDocument();
    expect(within(sheet).getAllByRole("img", { name: "제휴 할인" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("img", { name: "두륜산 케이블카" })).not.toBeInTheDocument();
    expect(screen.queryByText("사진: 한국관광공사")).not.toBeInTheDocument();
    expect(screen.queryByText("사진: 강원관광재단")).not.toBeInTheDocument();
  });

  it("falls back to the emoji tile when the thumbnail image fails to load", () => {
    render(<PolicyThumbPhoto fallback={<span>💸</span>} photo={photo} />);
    const image = screen.getByRole("img", { name: "두륜산 케이블카" });
    fireEvent.error(image);
    expect(screen.queryByRole("img", { name: "두륜산 케이블카" })).not.toBeInTheDocument();
    expect(screen.getByText("💸")).toBeInTheDocument();
  });
});
