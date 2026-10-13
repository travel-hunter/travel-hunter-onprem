import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type PublicPlaceItem } from "../../api";
import { installAppKakaoSdkMock } from "../../test/kakaoMock";
import { LegacyPlaceConfirm } from "./LegacyPlaceConfirm";

const jagalchi: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "자갈치시장",
  address: "부산 중구 자갈치해안로 52",
  latitude: 35.0966,
  longitude: 129.0306,
  category: "shopping",
  distanceMeters: 40,
};

const BUILDING = { kind: "building" as const, id: 4401, pnu: "1213010200100010006", address: "전남광주통합특별시 여수시 수정동 1-6", latitude: 34.744764, longitude: 127.767783, distanceMeters: 3 };

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.kakao;
});

function renderConfirm(props: Partial<Parameters<typeof LegacyPlaceConfirm>[0]> = {}) {
  const onReplace = vi.fn();
  render(
    <LegacyPlaceConfirm
      fallbackCenter={null}
      onReplace={onReplace}
      placeId="9"
      placeUrl="http://place.map.kakao.com/777"
      tripId="70"
      {...props}
    />,
  );
  return onReplace;
}

describe("LegacyPlaceConfirm", () => {
  it("asks for the name again and offers the public places the server found for the old row", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const onReplace = renderConfirm();

    expect(screen.getByText("장소 이름을 다시 적어 주세요")).toBeInTheDocument();
    expect(listSpy).toHaveBeenCalledWith("70", "9");
    const choices = await screen.findByRole("region", { name: "이 장소가 맞나요?" });
    const candidate = within(choices).getByRole("button", { name: "자갈치시장 선택" });
    expect(candidate).toHaveTextContent("쇼핑");
    expect(candidate).toHaveTextContent("부산 중구 자갈치해안로 52");

    await userEvent.setup().click(candidate);
    expect(onReplace).toHaveBeenCalledWith({ publicPlace: { source: "tourapi", sourceId: "126508" } });
  });

  it("opens the name field when none of the candidates is right, and turns the name into the user's own place", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const onReplace = renderConfirm();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "아니요, 직접 적을게요" }));
    const form = screen.getByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
    await user.type(within(form).getByLabelText("장소 이름"), "  내가 아는 식당  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onReplace).toHaveBeenCalledWith({ customPlace: { name: "내가 아는 식당" } });
  });

  it("saves a picked spot as the user's own place with its public reference only - no address, no coordinates", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: BUILDING, nearCenter: true });
    const onReplace = renderConfirm();
    const user = userEvent.setup();

    const form = await screen.findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "  내 쉼터  ");
    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(await within(form).findByText(BUILDING.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));

    // 주소 · 좌표는 키째 없다(toStrictEqual) - 서버가 지번 참조(geoRef)로 다시 찾는다
    expect(onReplace).toHaveBeenCalledTimes(1);
    expect(onReplace.mock.calls[0][0]).toStrictEqual({ customPlace: { name: "내 쉼터", geoRef: { kind: "building", id: 4401, pin: true } } });
  });

  it("goes back to the candidates when the name field is cancelled", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    renderConfirm();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "아니요, 직접 적을게요" }));
    await user.click(within(screen.getByRole("form", { name: "나만의 장소" })).getByRole("button", { name: "취소" }));

    expect(await screen.findByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "나만의 장소" })).toBeNull();
  });

  it("shows the name field straight away when the server finds no candidate, and cancel clears what was typed", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    renderConfirm();
    const user = userEvent.setup();

    const form = await screen.findByRole("form", { name: "나만의 장소" });
    expect(screen.queryByRole("region", { name: "이 장소가 맞나요?" })).toBeNull();
    await user.type(within(form).getByLabelText("장소 이름"), "쓰다 만 이름");
    await user.click(within(form).getByRole("button", { name: "취소" }));

    expect(within(screen.getByRole("form", { name: "나만의 장소" })).getByLabelText("장소 이름")).toHaveValue("");
  });

  it("falls back to the name field when the candidate request fails", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockRejectedValue(new Error("network"));
    renderConfirm();

    expect(await screen.findByText("비슷한 장소를 불러오지 못했어요. 이름을 직접 적어 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
  });

  it("never links an old row's place url that is not a Kakao place page (코드 검토)", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    render(<LegacyPlaceConfirm fallbackCenter={null} onReplace={vi.fn()} placeId="9" placeUrl="javascript:alert(1)" tripId="70" />);

    await screen.findByRole("form", { name: "나만의 장소" });
    expect(screen.queryByRole("link", { name: "카카오맵에서 보기" })).not.toBeInTheDocument();
  });

  it("shows which row it is with the clue it is given (결정 26)", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    render(<LegacyPlaceConfirm clue="Day 2 · 3번째 장소" fallbackCenter={null} onReplace={vi.fn()} placeId="9" tripId="70" />);

    expect(await screen.findByText("Day 2 · 3번째 장소")).toBeInTheDocument();
  });

  it("links to Kakao Map only when the row kept a place url", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const { unmount } = render(
      <LegacyPlaceConfirm fallbackCenter={null} onReplace={vi.fn()} placeId="9" placeUrl="http://place.map.kakao.com/777" tripId="70" />,
    );
    const link = screen.getByRole("link", { name: "카카오맵에서 보기" });
    expect(link).toHaveAttribute("href", "http://place.map.kakao.com/777");
    expect(link).toHaveAttribute("target", "_blank");
    unmount();

    render(<LegacyPlaceConfirm fallbackCenter={null} onReplace={vi.fn()} placeId="9" placeUrl={null} tripId="70" />);
    expect(screen.queryByRole("link", { name: "카카오맵에서 보기" })).toBeNull();
  });
});
