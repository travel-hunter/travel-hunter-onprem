import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.getByRole("img", { name: "두륜산 케이블카" })).toBeInTheDocument();
    expect(screen.getAllByText("사진: 한국관광공사")).toHaveLength(1);
  });

  it("omits the list attribution line when no policy has a photo", async () => {
    vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([
      makePolicy({ photo: null }),
    ]);
    vi.spyOn(appDataApi, "listSavedPolicies").mockResolvedValue([]);

    await login();
    cleanup();
    renderAppRoute("/policies");

    await waitFor(() => {
      expect(screen.getByText("해남 공식 할인")).toBeInTheDocument();
    });
    expect(screen.queryByText("사진: 한국관광공사")).not.toBeInTheDocument();
  });

  it("falls back to the emoji tile when the thumbnail image fails to load", () => {
    render(<PolicyThumbPhoto fallback={<span>💸</span>} photo={photo} />);
    const image = screen.getByRole("img", { name: "두륜산 케이블카" });
    fireEvent.error(image);
    expect(screen.queryByRole("img", { name: "두륜산 케이블카" })).not.toBeInTheDocument();
    expect(screen.getByText("💸")).toBeInTheDocument();
  });
});
