import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, appDataApi, type ItineraryPlace, type PublicPlaceItem, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

// jsdom 에는 scrollIntoView 가 없다. 이동 후 카드로 스크롤하는 코드가 여기서 터진다.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

const kakaoName = "카카오 예전 식당";
const kakaoAddress = "부산 중구 카카오로 1";
const legacyPlace: ItineraryPlace = {
  id: "9",
  time: "09:00",
  label: kakaoName,
  meta: `음식점 · ${kakaoAddress}`,
  address: kakaoAddress,
  latitude: 35.1,
  longitude: 129.03,
  category: "음식점 > 한식",
  categoryCode: "FD6",
  placeUrl: "http://place.map.kakao.com/777",
  sourceProvider: "kakao",
  externalPlaceId: "777",
  needsConfirmation: true,
};
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

function tripWith(places: ItineraryPlace[], role: Trip["currentUserRole"] = "owner"): Trip {
  return { ...getPreviewTrip(), id: "70", revision: 4, title: "예전 행 확인 여행", currentUserRole: role, days: { 1: places, 2: [] } };
}

async function openLegacyRow(trip: Trip) {
  vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  await login();
  cleanup();
  renderAppRoute(`/trips/${trip.id}?day=1`);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: `${kakaoName} 상세 열기` }));
  return user;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Travel Hunter app — old Kakao place rows", () => {
  it("opens the confirm screen instead of the edit form and keeps the old Kakao values out of it", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    await openLegacyRow(tripWith([legacyPlace]));

    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });
    expect(within(sheet).getByText("장소 이름을 다시 적어 주세요")).toBeInTheDocument();
    // 결정 26: 예전 이름 대신 어느 행인지 알려 주는 단서
    expect(within(sheet).getByText("Day 1 · 1번째 장소 · 09:00")).toBeInTheDocument();
    expect(listSpy).toHaveBeenCalledWith("70", "9");
    expect(await within(sheet).findByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();
    // 수정 창의 장소명 · 메모 칸은 없다 - 예전 이름 · 주소 · 메모를 폼에 옮기지 않는다
    expect(sheet.querySelector('input[name="place-label"]')).toBeNull();
    expect(sheet.querySelector('textarea[name="place-meta"]')).toBeNull();
    expect(sheet).not.toHaveTextContent(kakaoName);
    expect(sheet).not.toHaveTextContent(kakaoAddress);
    expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute("href", "http://place.map.kakao.com/777");
    // 시간 바꾸기는 그대로
    expect(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" })).toBeInTheDocument();
  });

  it("replaces the old row with the picked public place by reference only", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: {
        1: [{ id: "9", time: "09:00", label: "자갈치시장", meta: "부산 중구 자갈치해안로 52", address: "부산 중구 자갈치해안로 52", placeOrigin: "public", publicSource: "tourapi", publicSourceId: "126508" }],
        2: [],
      },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(await within(sheet).findByRole("button", { name: "자갈치시장 선택" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("70", "9", { expectedRevision: 4, publicPlace: { source: "tourapi", sourceId: "126508" } }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 확인" })).not.toBeInTheDocument());
    expect(document.body).toHaveTextContent("자갈치시장");
    expect(document.body).not.toHaveTextContent(kakaoName);
  });

  it("replaces the old row with a name the user typed", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: { 1: [{ id: "9", time: "09:00", label: "내가 아는 식당", meta: "", placeOrigin: "custom" }], 2: [] },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    const form = await within(sheet).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "내가 아는 식당");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("70", "9", {
        expectedRevision: 4,
        customPlace: { name: "내가 아는 식당" },
      }),
    );
    await waitFor(() => expect(document.body).toHaveTextContent("내가 아는 식당"));
  });

  it("changes only the time of an old row", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: { 1: [{ ...legacyPlace, time: "10:00" }], 2: [] },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" }));
    await user.click(within(sheet).getByRole("button", { name: "시간만 저장" }));

    // 이름 · 메모 · 주소 · 좌표 · 분류는 한 글자도 보내지 않는다
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("70", "9", { time: "10:00", expectedRevision: 4 }));
  });

  it("keeps the old Kakao name and address out of local drafts", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const user = await openLegacyRow(tripWith([legacyPlace]));
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" }));

    const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index) ?? "");
    const draftKeys = keys.filter((key) => key.startsWith("travel-hunter:draft:"));
    expect(draftKeys).toEqual([]);
    expect(keys.map((key) => window.localStorage.getItem(key) ?? "").join("\n")).not.toContain(kakaoName);
  });

  it("keeps the read-only detail for viewers", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    await openLegacyRow(tripWith([legacyPlace], "viewer"));

    const sheet = await screen.findByRole("dialog", { name: "장소 상세" });
    expect(within(sheet).getByText(kakaoAddress)).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "장소 확인" })).not.toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
  });

  it("asks for a refresh when replacing the old row is refused with 422", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockRejectedValue(
        new ApiError("Unprocessable Entity", {
          status: 422,
          statusText: "Unprocessable Entity",
          // 옛 화면이 보낸 모양 - 서버가 모르는 필드(예전 메모 칸 meta)를 거절했다
          detail: [{ type: "extra_forbidden", loc: ["body", "meta"], msg: "Extra inputs are not permitted" }],
        }),
      );
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const user = await openLegacyRow(tripWith([legacyPlace]));
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(await within(sheet).findByRole("button", { name: "자갈치시장 선택" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1));
    expect(await within(sheet).findByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(sheet).queryByText(/입력값을 확인하고 다시 시도해 주세요/)).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "새로 고침" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("tells the user to find the location again when the address reference is gone", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockRejectedValue(
        new ApiError("Address reference not found", { status: 404, statusText: "Not Found", detail: "Address reference not found" }),
      );
    const user = await openLegacyRow(tripWith([legacyPlace]));
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(await within(sheet).findByRole("button", { name: "자갈치시장 선택" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1));
    expect(await within(sheet).findByText("주소 정보가 바뀌었어요. 지도에서 위치를 다시 찾아 담아 주세요.")).toBeInTheDocument();
  });
});
