import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type PlaceMatchResult,
  type PlaceSearchCandidate,
  type PublicPlaceItem,
  type Trip,
} from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { installAppKakaoSdkMock } from "../../test/kakaoMock";
import { login, renderAppRoute } from "../../test/renderAppRoute";

/* 카카오가 준 값과 공공데이터 값을 일부러 다르게 둔다 - 바구니 · 요청에 카카오 값이 새면 바로 드러난다 */
function kakaoCandidate(id: string, title: string, overrides: Partial<PlaceSearchCandidate> = {}): PlaceSearchCandidate {
  return {
    id: `kakao:${id}`,
    label: "📍",
    title,
    meta: `카카오 주소 ${title}`,
    address: `카카오 주소 ${title}`,
    categoryName: "카카오 분류",
    categoryCode: "CE7",
    latitude: 34.7443,
    longitude: 127.7663,
    placeUrl: `https://place.map.kakao.com/${id}`,
    sourceProvider: "kakao",
    externalPlaceId: id,
    ...overrides,
  };
}

function publicPlace(name: string, sourceId: string, overrides: Partial<PublicPlaceItem> = {}): PublicPlaceItem {
  return {
    source: "tourapi",
    sourceId,
    name,
    address: `공공데이터 주소 ${name}`,
    latitude: 34.74,
    longitude: 127.76,
    category: "cafe",
    distanceMeters: 30,
    ...overrides,
  };
}

function addTrip(id: string, revision = 3): Trip {
  return {
    ...getPreviewTrip(),
    id,
    title: "담는 흐름 여행",
    revision,
    days: { 1: [], 2: [] },
    currentUserRole: "owner",
  };
}

async function openAddSheet(trip: Trip) {
  vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  await login();
  cleanup();
  renderAppRoute(`/trips/${trip.id}?day=1`);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /장소 추가/ }));
  const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
  return { user, dialog };
}

async function searchAndPick(user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, query: string, title: string) {
  fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: query } });
  await user.click(await within(dialog).findByRole("button", { name: `${title} 선택` }));
}

function mockSearch(...candidates: PlaceSearchCandidate[]) {
  return vi
    .spyOn(appDataApi, "searchTripPlaces")
    .mockImplementation(async (_tripId, request) => candidates.filter((candidate) => request.query.includes(candidate.title.slice(0, 2))));
}

/** 담기 요청 본문에 카카오가 준 이름 · 주소 · 분류가 한 글자도 없어야 한다 */
function expectNoKakaoValues(body: unknown) {
  const text = JSON.stringify(body);
  expect(text).not.toContain("카카오");
  expect(text).not.toContain("34.7443");
  expect(text).not.toContain("7663");
  expect(text).not.toContain("address");
  expect(text).not.toContain("label");
  expect(text).not.toContain("meta");
}

const BUILDING_FILL = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 };

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  delete window.kakao;
});

describe("Travel Hunter app trip place add flow", () => {
  it("puts a place that matches our data straight into the basket and saves only its reference", async () => {
    const trip = addTrip("92");
    mockSearch(kakaoCandidate("8001", "스타벅스 여수점"));
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("스타벅스 여수오동도점", "T-1")],
    });
    const savedTrip: Trip = { ...trip, revision: 4 };
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue(savedTrip);
    const addSingleSpy = vi.spyOn(appDataApi, "addTripPlace");
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "스타", "스타벅스 여수점");

    // 맞춰 보기에는 이름 · 좌표 · 분류만 간다
    await waitFor(() =>
      expect(matchSpy).toHaveBeenCalledWith({ name: "스타벅스 여수점", latitude: 34.7443, longitude: 127.7663, categoryCode: "CE7" }),
    );
    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("스타벅스 여수오동도점");
    expect(basket).toHaveTextContent("카페");
    expect(basket).toHaveTextContent("공공데이터 주소 스타벅스 여수오동도점");
    expect(basket).not.toHaveTextContent("카카오");
    expect(within(dialog).queryByLabelText("장소 이름")).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    const request = addBatchSpy.mock.calls[0][2];
    expect(addBatchSpy).toHaveBeenCalledWith("92", 1, {
      expectedRevision: 3,
      places: [{ publicPlace: { source: "tourapi", sourceId: "T-1" }, kakaoPlaceId: "8001" }],
    });
    expectNoKakaoValues(request);
    expect(addSingleSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 추가" })).not.toBeInTheDocument());
  });

  it("asks which place is right when candidates come back and adds the one the user chooses", async () => {
    const trip = addTrip("93");
    mockSearch(kakaoCandidate("8002", "오동도"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "candidates",
      places: [
        publicPlace("오동도", "T-10", { category: "sight", distanceMeters: 0 }),
        publicPlace("오동도 공원", "S-11", { source: "sangga", category: "culture", distanceMeters: 220 }),
      ],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "오동", "오동도");

    const choices = await within(dialog).findByRole("region", { name: "이 장소가 맞나요?" });
    expect(within(choices).getByRole("button", { name: "오동도 선택" })).toHaveTextContent("고른 곳과 같은 자리");
    expect(within(choices).getByRole("button", { name: "오동도 공원 선택" })).toHaveTextContent("고른 곳에서 약 220m");
    // 맞춰 보는 동안과 후보를 묻는 동안은 지도 미리보기를 접는다(카카오 이름이 칸 옆에 남지 않게)
    expect(within(dialog).queryByLabelText("장소 지도 미리보기")).not.toBeInTheDocument();

    await user.click(within(choices).getByRole("button", { name: "오동도 공원 선택" }));

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("오동도 공원");
    expect(basket).toHaveTextContent("문화시설");
    expect(within(dialog).queryByRole("region", { name: "이 장소가 맞나요?" })).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("장소 지도 미리보기")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() =>
      expect(addBatchSpy).toHaveBeenCalledWith("93", 1, {
        expectedRevision: 3,
        places: [{ publicPlace: { source: "sangga", sourceId: "S-11" }, kakaoPlaceId: "8002" }],
      }),
    );
  });

  it("lets the user say none of the candidates is right and write the place by hand, starting from the typed words", async () => {
    const trip = addTrip("94");
    mockSearch(kakaoCandidate("8003", "바다횟집 본점"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "candidates",
      places: [publicPlace("바다횟집", "S-20", { source: "sangga", category: "food" })],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "바다", "바다횟집 본점");
    await user.click(await within(dialog).findByRole("button", { name: "아니요, 다른 곳이에요" }));

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    const name = within(form).getByLabelText("장소 이름");
    // 이름 칸은 검색 칸에 친 글로 미리 찬다 - 카카오 이름은 채우지도, 옆에 보이지도 않는다
    expect(name).toHaveValue("바다");
    expect(form).toHaveTextContent("주소를 바로 채우지 못했어요");
    expect(dialog).not.toHaveTextContent("바다횟집 본점");
    expect(within(dialog).queryByDisplayValue("바다횟집 본점")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("장소 지도 미리보기")).not.toBeInTheDocument();

    await user.clear(name);
    await user.type(name, "  우리가 가던 횟집  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("우리가 가던 횟집");
    expect(basket).toHaveTextContent("직접 적은 장소");
    expect(within(dialog).queryByRole("form", { name: "나만의 장소" })).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("94", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "우리가 가던 횟집" }, kakaoPlaceId: "8003" }],
    });
    expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
  });

  it("opens the custom place form straight away when nothing matches", async () => {
    const trip = addTrip("95");
    mockSearch(kakaoCandidate("8004", "새로 생긴 가게"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "새로", "새로 생긴 가게");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("새로");
    expect(form).toHaveTextContent("주소를 바로 채우지 못했어요");
    expect(dialog).not.toHaveTextContent("새로 생긴 가게");
  });

  it("asks for a name without calling match when the picked place has no coordinates", async () => {
    const trip = addTrip("96");
    mockSearch(kakaoCandidate("8005", "좌표없는곳", { latitude: null, longitude: null }));
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "좌표", "좌표없는곳");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(form).toHaveTextContent("위치 정보가 없어서");
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("좌표");
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("falls back to the custom place form when matching fails", async () => {
    const trip = addTrip("97");
    mockSearch(kakaoCandidate("8006", "맞춰보기실패"));
    vi.spyOn(appDataApi, "matchPlace").mockRejectedValue(
      new ApiError("server error", { status: 500, statusText: "Internal Server Error" }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "맞춰", "맞춰보기실패");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(form).toHaveTextContent("맞춰 보지 못했어요");
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("맞춰");
  });

  it("lets the user write a place by hand without searching, and saves it together with a matched one", async () => {
    const trip = addTrip("98");
    mockSearch(kakaoCandidate("8007", "해변카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("해변 카페", "T-30")],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "해변", "해변카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "친구네 집");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    await waitFor(() =>
      expect(within(dialog).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 2개"),
    );
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 2개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("98", 1, {
      expectedRevision: 3,
      places: [
        { publicPlace: { source: "tourapi", sourceId: "T-30" }, kakaoPlaceId: "8007" },
        // 직접 적기로 연 칸은 카카오 장소가 없으므로 ID 도 없다
        { customPlace: { name: "친구네 집" } },
      ],
    });
  });

  it("saves the jibun of the spot picked on the map, never the picked coordinates", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const trip = addTrip("99");
    mockSearch(kakaoCandidate("8008", "동네 쉼터", { latitude: 33.4584, longitude: 126.9425 }));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    // 일정 지역 중심(옛 시험과 같은 값): 지도는 이 응답을 기다린 뒤 열리므로 지우지 않는다. 열리는 자리는 이 값(35.5, 127.7)이 아니라 카카오 결과 자리여야 한다
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 35.5, longitude: 127.7 });
    const locateSpy = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: BUILDING_FILL, nearCenter: true });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "동네", "동네 쉼터");
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    // 지번이 없는 줄(fill 없음)은 위치 찍기 - 단추를 누르지 않아도 지도가 열려 있고, 카카오 결과 자리(33.4584, 126.9425)에서 열린다(보여 주기만)
    expect(within(form).queryByRole("button", { name: "지도에서 찾아 위치 찍기" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(kakao.mapInstances[kakao.mapInstances.length - 1].options).toMatchObject({ center: { lat: 33.4584, lng: 126.9425 } }),
    );
    const name = within(form).getByLabelText("장소 이름");
    expect(name).toHaveValue("동네");   // 친 검색어 - 카카오 이름("동네 쉼터")이 아니다
    await user.clear(name);
    await user.type(name, "우리 쉼터");

    act(() => kakao.emitMapClick(35.51, 127.71));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    // 찍은 좌표는 우리 서버에 지번을 묻는 데만 쓰고, 고른 뒤에는 지번 주소만 보인다
    await waitFor(() => expect(locateSpy).toHaveBeenCalledWith(35.51, 127.71));
    expect(await within(form).findByText(BUILDING_FILL.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("99", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "우리 쉼터", geoRef: { kind: "building", id: 501, pin: true } }, kakaoPlaceId: "8008" }],
    });
    // 찍은 좌표도 카카오 결과 좌표도 요청에 없다
    expect(JSON.stringify(addBatchSpy.mock.calls[0][2])).not.toMatch(/35\.51|127\.71|33\.4584|126\.9425/);
    expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
  });

  it("drops a pending match when the user starts a new search", async () => {
    const trip = addTrip("100");
    mockSearch(kakaoCandidate("8009", "느린곳"), kakaoCandidate("8010", "빠른곳"));
    let finishFirst!: (answer: PlaceMatchResult) => void;
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(
      new Promise<PlaceMatchResult>((resolve) => {
        finishFirst = resolve;
      }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "느린", "느린곳");
    expect(await within(dialog).findByRole("status")).toHaveTextContent("맞춰 보는 중");

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "빠른" } });
    await within(dialog).findByRole("button", { name: "빠른곳 선택" });
    expect(within(dialog).queryByText(/맞춰 보는 중/)).not.toBeInTheDocument();

    await act(async () => {
      finishFirst({ result: "match", places: [publicPlace("느린 곳", "T-40")] });
    });

    expect(within(dialog).queryByRole("region", { name: "추가할 장소 목록" })).not.toBeInTheDocument();
  });

  it("starts the custom place form from the words typed for each picked result, even when two results without coordinates come in a row", async () => {
    const trip = addTrip("101");
    mockSearch(
      kakaoCandidate("8021", "첫째좌표없음", { latitude: null, longitude: null }),
      kakaoCandidate("8022", "둘째좌표없음", { latitude: null, longitude: null }),
    );
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "첫째", "첫째좌표없음");
    const first = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(first).getByLabelText("장소 이름")).toHaveValue("첫째");
    await user.type(within(first).getByLabelText("장소 이름"), "첫째에 적은 이름");

    await searchAndPick(user, dialog, "둘째", "둘째좌표없음");
    const second = await within(dialog).findByRole("form", { name: "나만의 장소" });
    // 앞 줄에 적던 글이 남지 않고 이 줄을 고를 때의 검색어로 새로 채워진다
    expect(within(second).getByLabelText("장소 이름")).toHaveValue("둘째");
    await user.clear(within(second).getByLabelText("장소 이름"));
    await user.type(within(second).getByLabelText("장소 이름"), "둘째에 적은 이름");
    await user.click(within(second).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    // 저장 요청에는 둘째 장소의 카카오 ID 와 방금 적은 이름뿐이다
    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("101", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "둘째에 적은 이름" }, kakaoPlaceId: "8022" }],
    });
    expect(JSON.stringify(addBatchSpy.mock.calls[0][2])).not.toContain("첫째");
  });

  it("asks for a refresh instead of the generic message when saving the basket is refused with 422", async () => {
    const trip = addTrip("102");
    mockSearch(kakaoCandidate("8031", "오래된화면카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("오래된 화면 카페", "T-60")],
    });
    const addBatchSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValue(
        new ApiError("Unprocessable Entity", {
          status: 422,
          statusText: "Unprocessable Entity",
          // 옛 화면이 보낸 모양 - 서버가 모르는 필드(예전 카카오 이름 칸)를 거절했다
          detail: [{ type: "extra_forbidden", loc: ["body", "places", 0, "label"], msg: "Extra inputs are not permitted" }],
        }),
      );
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "오래", "오래된화면카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/입력값을 확인하고 다시 시도해 주세요/)).not.toBeInTheDocument();
    // 담아 둔 장소는 그대로 남는다
    expect(within(dialog).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오래된 화면 카페");
    expect(reload).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "새로 고침" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("keeps the generic message and no refresh button for other save failures", async () => {
    const trip = addTrip("103");
    mockSearch(kakaoCandidate("8032", "그냥실패카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("그냥 실패 카페", "T-61")],
    });
    vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(
      new ApiError("Internal Server Error", { status: 500, statusText: "Internal Server Error" }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "그냥", "그냥실패카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText(/입력값을 확인하고 다시 시도해 주세요/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "새로 고침" })).not.toBeInTheDocument();
  });

  it("keeps the generic message for a 422 about a value rather than the request shape", async () => {
    const trip = addTrip("106");
    mockSearch(kakaoCandidate("8034", "값오류카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("값 오류 카페", "T-63")],
    });
    vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(
      new ApiError("Unprocessable Entity", {
        status: 422,
        statusText: "Unprocessable Entity",
        // 값 오류 - 새로 고쳐도 그대로라 새로 고침을 권하지 않는다
        detail: [{ type: "string_too_long", loc: ["body", "places", 0, "customPlace", "name"], msg: "String should have at most 100 characters" }],
      }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "값오류", "값오류카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText(/입력값을 확인하고 다시 시도해 주세요/)).toBeInTheDocument();
    expect(within(dialog).queryByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "새로 고침" })).not.toBeInTheDocument();
  });

  it("says the place search is unavailable on a 503, not that nothing was found, and the direct entry still saves a place", async () => {
    const trip = addTrip("104");
    vi.spyOn(appDataApi, "searchTripPlaces").mockRejectedValue(
      new ApiError("Place search is unavailable", {
        status: 503,
        statusText: "Service Unavailable",
        detail: "Place search is unavailable",
      }),
    );
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "여수" } });

    expect(await within(dialog).findByText("장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.")).toBeInTheDocument();
    // '결과 없음'이나 일반 실패 문구와 다른 상태다
    expect(within(dialog).queryByText(/검색 결과가 없어요/)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/불러오지 못했어요/)).not.toBeInTheDocument();
    // 직접 적기 입구는 그대로 쓸 수 있다
    await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    // 검색이 실패해도 칸의 글이 직접 적기의 이름으로 미리 찬다
    const name = within(form).getByLabelText("장소 이름");
    expect(name).toHaveValue("여수");
    await user.clear(name);
    await user.type(name, "여수 밤바다 쉼터");
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() =>
      expect(addBatchSpy).toHaveBeenCalledWith("104", 1, {
        expectedRevision: 3,
        places: [{ customPlace: { name: "여수 밤바다 쉼터" } }],
      }),
    );
  });

  it("keeps the generic search failure message for other search errors", async () => {
    const trip = addTrip("105");
    vi.spyOn(appDataApi, "searchTripPlaces").mockRejectedValue(new Error("offline"));
    const { dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "여수" } });

    expect(await within(dialog).findByText("장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/지금 쓸 수 없어요/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" })).toBeInTheDocument();
  });

  it("marks each row with its prematched path and adds a ready row without asking again (시안 v62)", async () => {
    const trip = addTrip("97");
    mockSearch(
      kakaoCandidate("8101", "죽녹원", { categoryCode: "AT4", publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31", { category: "sight" })] } }),
      kakaoCandidate("8102", "죽녹원 대숲길", {
        publicMatch: { result: "candidates", places: [publicPlace("죽녹원", "T-31"), publicPlace("죽녹원 후문", "S-2", { source: "sangga" })] },
      }),
      kakaoCandidate("8103", "죽녹원 앞 노점", { publicMatch: { result: "none", places: [] } }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    const ready = await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" });
    expect(within(dialog).getByRole("button", { name: "죽녹원 대숲길 선택, 비슷한 곳 2" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "죽녹원 앞 노점 선택, 위치 찍기" })).toBeInTheDocument();
    // 지도 미리보기 배지는 첫 줄의 갈래와 같다(결정 25)
    expect(within(dialog).getByRole("region", { name: "장소 지도 미리보기" })).toHaveTextContent("바로 담기");

    await user.click(ready);

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("공공데이터 주소 죽녹원");
    expect(matchSpy).not.toHaveBeenCalled();
    expect(within(dialog).queryByText("우리 장소 목록과 맞춰 보는 중이에요.")).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("장소 검색")).toHaveFocus();
    // 담은 뒤 미리보기는 '저장 가능'(결정 25)
    expect(within(dialog).getByRole("region", { name: "장소 지도 미리보기" })).toHaveTextContent("저장 가능");
  });

  it("opens the candidates or the own-place form right away for the other rows (시안 v62)", async () => {
    const trip = addTrip("98");
    mockSearch(
      kakaoCandidate("8102", "죽녹원 대숲길", {
        publicMatch: { result: "candidates", places: [publicPlace("죽녹원", "T-31"), publicPlace("죽녹원 후문", "S-2", { source: "sangga" })] },
      }),
      kakaoCandidate("8103", "죽녹원 앞 노점", { publicMatch: { result: "none", places: [] } }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 대숲길 선택, 비슷한 곳 2" }));
    expect(within(dialog).getByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원 앞" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 앞 노점 선택, 위치 찍기" }));
    const form = within(dialog).getByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("죽녹원 앞");
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("keeps a row without a prematch on the old path: no mark, matched after the pick (코덱스 검토)", async () => {
    const trip = addTrip("102");
    mockSearch(
      kakaoCandidate("8501", "죽녹원", { publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31")] } }),
      kakaoCandidate("8502", "죽녹원길 카페", { publicMatch: null }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    expect(await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" })).toBeInTheDocument();
    const plain = within(dialog).getByRole("button", { name: "죽녹원길 카페 선택" });
    expect(plain.querySelector(".place-search-result-state")).toBeNull();

    await user.click(plain);

    await waitFor(() => expect(matchSpy).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
  });

  it("keeps the server's results for a two-word query (시안 v61)", async () => {
    const trip = addTrip("99");
    vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([kakaoCandidate("8201", "죽녹원")]);
    const { dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "담양 죽녹원" } });

    expect(await within(dialog).findByRole("button", { name: "죽녹원 선택" })).toBeInTheDocument();
  });

  it("keeps the earlier results dimmed and unclickable inside a fixed area while the next search loads (시안 v61 · 코덱스 검토)", async () => {
    const trip = addTrip("100");
    let release!: (rows: PlaceSearchCandidate[]) => void;
    vi.spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValueOnce([kakaoCandidate("8301", "오동도", { publicMatch: { result: "match", places: [publicPlace("오동도", "T-41")] } })])
      .mockImplementationOnce(() => new Promise<PlaceSearchCandidate[]>((resolve) => { release = resolve; }));
    const { dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");

    fireEvent.change(input, { target: { value: "오동도" } });
    await within(dialog).findByRole("button", { name: "오동도 선택, 바로 담기" });
    fireEvent.change(input, { target: { value: "오동도 등대" } });

    await within(dialog).findByText("장소 검색 결과를 불러오는 중입니다.");
    const list = within(dialog).getByRole("list", { name: "장소 검색 결과" });
    expect(list).toHaveAttribute("aria-busy", "true");
    expect(list).toHaveClass("is-stale");
    expect(list.closest(".place-search-area")).not.toBeNull();
    const stale = within(list).getByRole("button", { name: "오동도 선택, 바로 담기" });
    expect(stale).toBeDisabled();
    fireEvent.click(stale);
    expect(within(dialog).queryByRole("region", { name: "추가할 장소 목록" })).not.toBeInTheDocument();

    // 칠 때의 350ms 대기가 끝나 두 번째 검색이 실제로 나가야 풀 약속이 생긴다
    await waitFor(() => expect(release).toBeTypeOf("function"));
    await act(async () => release([kakaoCandidate("8302", "오동도 등대")]));

    expect(await within(dialog).findByRole("button", { name: "오동도 등대 선택" })).toBeEnabled();
    expect(within(dialog).getByRole("list", { name: "장소 검색 결과" })).toHaveAttribute("aria-busy", "false");
  });

  it("lists the results as list items and announces how many came, keeping focus in the search box (코덱스 검토)", async () => {
    const trip = addTrip("103");
    mockSearch(kakaoCandidate("8601", "오동도"), kakaoCandidate("8602", "오동도 등대"), kakaoCandidate("8603", "오동도 유람선"));
    const { dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");
    input.focus();

    fireEvent.change(input, { target: { value: "오동도" } });

    await within(dialog).findByText("검색 결과 3곳");
    const list = within(dialog).getByRole("list", { name: "장소 검색 결과" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(input).toHaveFocus();
  });

  it("shows 'no results' inside the fixed area even with places in the basket (코덱스 검토)", async () => {
    const trip = addTrip("104");
    vi.spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValueOnce([kakaoCandidate("8701", "죽녹원", { publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31")] } })])
      .mockResolvedValueOnce([]);
    const { user, dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");

    fireEvent.change(input, { target: { value: "죽녹원" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" }));
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    fireEvent.change(input, { target: { value: "없는 장소" } });

    const empty = await within(dialog).findByText("검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.");
    expect(empty.closest(".place-search-area")).not.toBeNull();
  });

  it("fills a no-match row from its jibun, names it by the typed query and saves only the reference (시안 v64)", async () => {
    const trip = addTrip("120");
    mockSearch(kakaoCandidate("8601", "해운대 공영주차장", { categoryCode: "PK6", publicMatch: { result: "none", places: [], fill: BUILDING_FILL } }));
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "해운대 공영" } });
    await user.click(await within(dialog).findByRole("button", { name: "해운대 공영주차장 선택, 주소 채움" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("해운대 공영");   // 친 검색어 - 카카오 이름이 아니다
    expect(form).toHaveTextContent(BUILDING_FILL.address);
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("120", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "해운대 공영", geoRef: { kind: "building", id: 501, pin: true } }, kakaoPlaceId: "8601" }],
    });
    expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
  });

  it("opens the last-resort form with the search text as the name even when pressed before the search fires, and keeps it open after the search runs", async () => {
    const trip = addTrip("121");
    const searchSpy = mockSearch();
    const { user, dialog } = await openAddSheet(trip);
    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "친구네 펜션" } });
    // 350ms 대기 안에 누른다 - 아직 검색이 나가지 않았고 페이지의 검색어 상태는 비어 있다. 칸의 글을 넘겨야 이름이 찬다
    expect(searchSpy).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("친구네 펜션");
    // 대기가 끝나 검색이 나가도 열어 둔 칸을 닫지 않는다(칠 때 이미 맞춰 보던 것을 놓았다)
    await waitFor(() => expect(searchSpy).toHaveBeenCalledTimes(1));
    expect(within(dialog).getByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
    expect(within(dialog).getByLabelText("장소 이름")).toHaveValue("친구네 펜션");
  });

  it("turns geo-filled basket rows into names only when their jibun disappeared in the monthly refresh", async () => {
    const trip = addTrip("122");
    mockSearch(kakaoCandidate("8602", "해운대 공영주차장", { categoryCode: "PK6", publicMatch: { result: "none", places: [], fill: BUILDING_FILL } }));
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValueOnce(new ApiError("Address reference not found", { status: 404, statusText: "Not Found", detail: "Address reference not found" }))
      .mockResolvedValueOnce({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);
    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "해운대 공영" } });
    await user.click(await within(dialog).findByRole("button", { name: "해운대 공영주차장 선택, 주소 채움" }));
    await user.click(within(await within(dialog).findByRole("form", { name: "나만의 장소" })).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText("주소 정보가 바뀌어 위치를 뺐어요. 위치가 필요하면 다시 찾아 담아 주세요.")).toBeInTheDocument();   // 시트의 저장 오류 줄(form-error)에는 역할이 없다
    expect(dialog).toHaveTextContent("위치 없이 이름만");
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));
    expect(addBatchSpy).toHaveBeenLastCalledWith("122", 1, { expectedRevision: 3, places: [{ customPlace: { name: "해운대 공영" }, kakaoPlaceId: "8602" }] });
  });

  it("keeps the basket as it is and asks to save again later when the address lookup is unavailable", async () => {
    const trip = addTrip("123");
    mockSearch(kakaoCandidate("8603", "해운대 공영주차장", { categoryCode: "PK6", publicMatch: { result: "none", places: [], fill: BUILDING_FILL } }));
    vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(
      new ApiError("Address lookup is unavailable", { status: 503, statusText: "Service Unavailable", detail: "Address lookup is unavailable" }),
    );
    const { user, dialog } = await openAddSheet(trip);
    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "해운대 공영" } });
    await user.click(await within(dialog).findByRole("button", { name: "해운대 공영주차장 선택, 주소 채움" }));
    await user.click(within(await within(dialog).findByRole("form", { name: "나만의 장소" })).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText("지금 주소를 확인할 수 없어요. 잠시 뒤 다시 저장해 주세요.")).toBeInTheDocument();
    // 지번은 그대로 - 위치를 빼지 않는다
    expect(within(dialog).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent(BUILDING_FILL.address);
  });
});
