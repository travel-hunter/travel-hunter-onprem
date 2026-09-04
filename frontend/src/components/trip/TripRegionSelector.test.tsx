import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type TravelAreaCatalog, type TravelAreaOption } from "../../api";
import { TripRegionSelector } from "./TripRegionSelector";

const jejuEast: TravelAreaOption = {
  travelAreaId: "jeju-east",
  travelAreaName: "제주 동부",
  sido: "제주",
  areaType: "recommended",
  includedCities: ["제주시", "서귀포시"],
};

const jejuCatalog: TravelAreaCatalog = {
  sido: "제주",
  sourceAsOf: "2026-09-04",
  wholeArea: {
    travelAreaId: "jeju-all",
    travelAreaName: "제주 전체",
    sido: "제주",
    areaType: "whole",
    includedCities: ["제주시", "서귀포시"],
  },
  recommendedAreas: [
    jejuEast,
    {
      travelAreaId: "jeju-west",
      travelAreaName: "제주 서부",
      sido: "제주",
      areaType: "recommended",
      includedCities: ["제주시"],
    },
  ],
  administrativeAreas: [
    {
      travelAreaId: "jeju-jeju",
      travelAreaName: "제주시",
      sido: "제주",
      areaType: "administrative",
      includedCities: ["제주시"],
    },
  ],
};

function gyeonggiCatalog(): TravelAreaCatalog {
  return {
    sido: "경기",
    sourceAsOf: "2026-09-04",
    wholeArea: {
      travelAreaId: "gyeonggi-all",
      travelAreaName: "경기 전체",
      sido: "경기",
      areaType: "whole",
      includedCities: ["수원시"],
    },
    recommendedAreas: [],
    administrativeAreas: Array.from({ length: 22 }, (_, index) => ({
      travelAreaId: `gyeonggi-city-${index + 1}`,
      travelAreaName: `경기 ${index + 1}`,
      sido: "경기",
      areaType: "administrative",
      includedCities: [`경기 ${index + 1}`],
    })),
  };
}

describe("TripRegionSelector", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders controlled sido buttons and grouped catalog options", async () => {
    vi.spyOn(appDataApi, "getTravelAreaCatalog").mockResolvedValue(jejuCatalog);
    const onSidoChange = vi.fn();
    const onChange = vi.fn();

    render(
      <TripRegionSelector
        selectedSido="제주"
        value={jejuEast}
        onSidoChange={onSidoChange}
        onChange={onChange}
      />,
    );

    expect(screen.getAllByRole("button", { pressed: false })).toHaveLength(16);
    expect(screen.getByRole("button", { name: "제주", pressed: true })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("group", { name: "전체" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "추천 여행권역" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "시·군·구" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "제주 동부 제주시, 서귀포시" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: "제주 서부 제주시" }));

    expect(onChange).toHaveBeenCalledWith(jejuCatalog.recommendedAreas[1]);
    expect(onSidoChange).not.toHaveBeenCalled();
  });

  it("keeps the previous selection while loading and calls retry after an error", async () => {
    let rejectCatalog: (error: Error) => void = () => undefined;
    const pendingCatalog = new Promise<TravelAreaCatalog>((_, reject) => {
      rejectCatalog = reject;
    });
    const getCatalog = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockReturnValueOnce(pendingCatalog)
      .mockResolvedValueOnce(jejuCatalog);
    const onSidoChange = vi.fn();

    render(
      <TripRegionSelector
        selectedSido="제주"
        value={jejuEast}
        onSidoChange={onSidoChange}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "제주 동부 제주시, 서귀포시" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("여행권역을 불러오는 중입니다.")).toBeInTheDocument();

    rejectCatalog(new Error("network"));

    expect(await screen.findByRole("alert")).toHaveTextContent("여행권역을 불러오지 못했습니다.");
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    await screen.findByRole("group", { name: "추천 여행권역" });
    expect(getCatalog).toHaveBeenCalledTimes(2);
    expect(onSidoChange).not.toHaveBeenCalled();
  });

  it("shows more than 20 complete administrative options and does not keep stale selection across sido changes", async () => {
    vi.spyOn(appDataApi, "getTravelAreaCatalog").mockResolvedValue(gyeonggiCatalog());
    const onSidoChange = vi.fn();
    const onChange = vi.fn();

    render(
      <TripRegionSelector
        selectedSido="경기"
        value={jejuEast}
        onSidoChange={onSidoChange}
        onChange={onChange}
      />,
    );

    expect(await screen.findByRole("button", { name: "경기 22 경기 22" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "제주", pressed: false })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "경기", pressed: true })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "제주 동부 제주시, 서귀포시" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "부산" }));

    expect(onSidoChange).toHaveBeenCalledWith("부산");
    expect(onChange).not.toHaveBeenCalled();
  });
});
