import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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
    expect(screen.queryByRole("group", { name: "시·군·구" })).toBeNull();
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

  it("행정 시·군·구는 그리지 않고, 다른 시도의 선택도 남기지 않는다", async () => {
    const catalog = gyeonggiCatalog();
    vi.spyOn(appDataApi, "getTravelAreaCatalog").mockResolvedValue(catalog);
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

    expect(await screen.findByRole("group", { name: "전체" })).toBeInTheDocument();
    // 22개 행정지역은 응답에 그대로 있지만 목록에는 안 나온다.
    expect(screen.queryByRole("button", { name: "경기 22" })).toBeNull();
    expect(screen.queryByRole("group", { name: "시·군·구" })).toBeNull();
    expect(screen.getByRole("button", { name: "제주", pressed: false })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "경기", pressed: true })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "제주 동부 제주시, 서귀포시" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "부산" }));

    expect(onSidoChange).toHaveBeenCalledWith("부산");
  });
});

describe("TripRegionSelector 기본값과 목록 밖 선택", () => {
  const jeju: TravelAreaCatalog = {
    sido: "제주",
    sourceAsOf: "2026-09-10",
    wholeArea: {
      travelAreaId: "whole:jeju",
      travelAreaName: "제주 전체",
      sido: "제주",
      areaType: "whole",
      includedCities: ["제주", "서귀포"],
    },
    recommendedAreas: [jejuEast],
    administrativeAreas: [
      {
        travelAreaId: "admin:jeju:jejusi",
        travelAreaName: "제주시",
        sido: "제주",
        areaType: "administrative",
        includedCities: ["제주"],
      },
    ],
  };

  /* 실제 화면은 선택을 부모가 들고 되먹인다. 그 왕복이 있어야
     자동 선택과 복원이 화면에 반영되는지 볼 수 있다. */
  function Controlled({
    restoreAreaId,
    onChange,
    onRestore,
  }: {
    restoreAreaId?: string;
    onChange?: (area: TravelAreaOption) => void;
    onRestore?: (area: TravelAreaOption) => void;
  }) {
    const [value, setValue] = useState<TravelAreaOption | null>(null);
    return (
      <TripRegionSelector
        selectedSido="제주"
        value={value}
        onSidoChange={vi.fn()}
        onChange={(area) => {
          setValue(area);
          onChange?.(area);
        }}
        onRestore={(area) => {
          setValue(area);
          onRestore?.(area);
        }}
        restoreAreaId={restoreAreaId}
      />
    );
  }

  it("시도를 고르면 세부 지역을 건드리지 않아도 전체가 선택된다", async () => {
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jeju);
    const onChange = vi.fn();
    const onRestore = vi.fn();
    try {
      render(<Controlled onChange={onChange} onRestore={onRestore} />);

      expect(
        await screen.findByRole("button", { name: /제주 전체/ }),
      ).toHaveAttribute("aria-pressed", "true");
      /* 기본값은 사용자가 고른 것이 아니다. onChange 로 흘리면 생성 화면은
         URL 에 `whole:` id 를 쓰고(새로고침하면 못 읽는다), 편집 화면은
         "지역을 바꿨다"로 보고 저장 때 원래 지역을 덮는다. */
      expect(onRestore).toHaveBeenCalledWith(jeju.wholeArea);
      expect(onChange).not.toHaveBeenCalled();
      // 추천 권역은 대안으로 남는다.
      expect(
        screen.getByRole("button", { name: /제주 동부/ }),
      ).toHaveAttribute("aria-pressed", "false");
    } finally {
      catalogSpy.mockRestore();
    }
  });

  it("시·군·구로 저장된 일정을 열면 그 선택이 목록 밖에라도 남는다", async () => {
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jeju);
    const onChange = vi.fn();
    try {
      render(<Controlled restoreAreaId="admin:jeju:jejusi" onChange={onChange} />);

      const restored = await screen.findByRole("button", { name: "제주시" });
      expect(restored).toHaveAttribute("aria-pressed", "true");
      expect(
        screen.getByRole("group", { name: "현재 선택" }),
      ).toBeInTheDocument();
      // 행정지역 이름 아래에 포함 도시를 또 붙이지 않는다.
      expect(restored.textContent).toBe("제주시");
      // 복원이 "전체" 로 덮이면 저장 때 지역이 조용히 바뀐다.
      expect(
        screen.getByRole("button", { name: /제주 전체/ }),
      ).toHaveAttribute("aria-pressed", "false");
      expect(onChange).not.toHaveBeenCalled();
    } finally {
      catalogSpy.mockRestore();
    }
  });

  it("목록에 있는 선택은 현재 선택으로 겹쳐 그리지 않는다", async () => {
    const catalogSpy = vi
      .spyOn(appDataApi, "getTravelAreaCatalog")
      .mockResolvedValue(jeju);
    try {
      render(<Controlled />);

      await screen.findByRole("group", { name: "전체" });
      expect(screen.queryByRole("group", { name: "현재 선택" })).toBeNull();
      // 추천 권역은 어느 도시를 아우르는지가 정보라 그대로 둔다.
      const recommended = screen.getByRole("button", { name: /제주 동부/ });
      expect(recommended.textContent).toContain("제주");
      expect(recommended.textContent).toContain("서귀포");
    } finally {
      catalogSpy.mockRestore();
    }
  });
});
