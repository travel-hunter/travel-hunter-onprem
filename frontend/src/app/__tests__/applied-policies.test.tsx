import { cleanup, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { appDataApi, type Policy } from "../../api";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — applied policy links", () => {
  it("shows each linked trip's island support progress", async () => {
    const policy: Policy = {
      id: "travelmonth-81",
      slug: "travelmonth-81",
      label: "섬",
      tag: "10만원",
      title: "2026 섬 여행비 지원",
      org: "섬 방문의 해 추진위원회",
      region: "전국",
      deadline: "2026-09-21",
      amount: "최대 10만원",
      summary: "여행비 10만원",
      match: 80,
      category: "여행상품",
      requirements: [],
      documents: [],
      officialUrl: "https://www.visitisland.kr/promotion2",
      applyUrl: null,
    };
    const listSpy = vi.spyOn(appDataApi, "listAppliedPolicyLinks").mockResolvedValue([
      {
        policy,
        linkedTrips: [
          { id: "201", title: "가거도 섬 여행", region: "전남", startDate: "2026-10-03", endDate: "2026-10-04", applicationStatus: "traveled" },
          { id: "202", title: "부산 주말", region: "부산", startDate: null, endDate: null, applicationStatus: null },
        ],
      },
    ]);

    try {
      await login();
      cleanup();
      renderAppRoute("/applied-policies");

      expect(await screen.findByText("신청 진행 · 여행 완료")).toBeInTheDocument();
      expect(screen.getAllByText(/^신청 진행 ·/)).toHaveLength(1);
    } finally {
      listSpy.mockRestore();
    }
  });
});
