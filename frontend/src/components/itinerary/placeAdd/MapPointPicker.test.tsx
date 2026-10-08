import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type ItineraryPlace, type LocateResult } from "../../../api";
import { installAppKakaoSdkMock } from "../../../test/kakaoMock";
import { KOREA_CENTER, MapPointPicker, firstPublicPlacePoint, pickerStart, spotFromLocate, type PickerStart } from "./MapPointPicker";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.kakao;
});

const BUILDING = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 };
const FAR = { kind: "parcel" as const, id: 77, pnu: "4215011500100010000", address: "강릉시 견소동 1", latitude: 37.77, longitude: 128.95, distanceMeters: 85 };
/** 건물에 찍으면 onPick 이 받는 값 - 찍은 좌표가 아니라 공공데이터 중심이다 */
const BUILDING_SPOT = { address: BUILDING.address, geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 };

function openPicker(
  area: { latitude: number | null; longitude: number | null } | Error,
  fallbackCenter = null as null | { latitude: number; longitude: number },
  start: PickerStart | null = null,
) {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  const spy = vi.spyOn(appDataApi, "getTripAreaCenter");
  if (area instanceof Error) spy.mockRejectedValue(area);
  else spy.mockResolvedValue(area);
  const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: BUILDING, nearCenter: true });
  const onPick = vi.fn();
  const onCancel = vi.fn();
  render(<MapPointPicker fallbackCenter={fallbackCenter} onCancel={onCancel} onPick={onPick} start={start} tripId="7" />);
  return { kakao, onPick, onCancel, spy, locate };
}

describe("MapPointPicker", () => {
  it("opens on the trip area center with a fixed crosshair and asks for the jibun of the point the crosshair ends on", async () => {
    const { kakao, onPick, spy, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(spy).toHaveBeenCalledWith("7");
    expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 34.76, lng: 127.66 }, level: 6 });
    // 핀을 꽂지 않는다 - 십자선은 지도 가운데에 고정돼 있고 스크린 리더에는 숨긴다
    expect(document.querySelector(".map-point-picker-pin")).toHaveAttribute("aria-hidden", "true");
    expect(kakao.markerInstances).toHaveLength(0);
    // 가운데는 늘 있으므로 지도가 뜨면 바로 고를 수 있다
    const confirm = screen.getByRole("button", { name: "이 위치로" });
    await waitFor(() => expect(confirm).toBeEnabled());

    kakao.dragMapTo(34.7443123456, 127.7663987654);
    await userEvent.click(confirm);

    // 찍은 좌표는 소수 여섯 자리까지만 남겨 지번을 묻는 데만 쓰고, onPick 에는 지번과 공공데이터 중심이 실린다
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(BUILDING_SPOT));
    expect(locate).toHaveBeenCalledWith(34.744312, 127.766399);
  });

  it("moves the center to the clicked point instead of dropping a pin", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));

    act(() => kakao.emitMapClick(34.7, 127.6));
    act(() => kakao.emitMapClick(34.8, 127.7));

    const { setCenter } = kakao.mapInstances[0].map;
    expect(setCenter).toHaveBeenCalledTimes(2);
    expect(setCenter.mock.calls[1][0].getLat()).toBe(34.8);
    expect(kakao.markerInstances).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "이 위치로" }));
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(BUILDING_SPOT));
    expect(locate).toHaveBeenCalledExactlyOnceWith(34.8, 127.7);
  });

  it("is a labelled map the keyboard can use: focus on open, arrow keys pan, Enter picks the center", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const user = userEvent.setup();

    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    expect(map).toHaveAttribute("tabindex", "0");
    expect(map).toHaveAccessibleDescription(/방향키/);
    await waitFor(() => expect(map).toHaveFocus());

    await user.keyboard("{ArrowRight}{ArrowDown}{ArrowLeft}{ArrowUp}");
    expect(kakao.mapInstances[0].map.panBy.mock.calls).toEqual([
      [60, 0],
      [0, 60],
      [-60, 0],
      [0, -60],
    ]);

    // 지도가 옮겨 간 자리를 Enter 가 고른다 - 단추를 누른 것과 같다
    kakao.dragMapTo(34.771, 127.672);
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(BUILDING_SPOT));
    expect(locate).toHaveBeenCalledExactlyOnceWith(34.771, 127.672);
  });

  it("keeps the page from scrolling on handled keys and leaves browser shortcuts alone", async () => {
    const { kakao } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const { panBy } = kakao.mapInstances[0].map;

    // fireEvent 는 기본 동작을 막았으면 false 를 돌려준다
    expect(fireEvent.keyDown(map, { key: "ArrowDown" })).toBe(false);
    expect(panBy).toHaveBeenCalledTimes(1);
    expect(fireEvent.keyDown(map, { key: "ArrowLeft", altKey: true })).toBe(true);
    expect(fireEvent.keyDown(map, { key: "a" })).toBe(true);
    expect(panBy).toHaveBeenCalledTimes(1);
  });

  it("zooms one level per + (or =) and -, and stops at the widest level", async () => {
    const { kakao } = openPicker(new Error("offline"));   // 대한민국 전체(수준 13)에서 연다
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const { setLevel } = kakao.mapInstances[0].map;

    // fireEvent 는 기본 동작을 막았으면 false 를 돌려준다 - 키가 쪽으로 새지 않는다
    expect(fireEvent.keyDown(map, { key: "+" })).toBe(false);
    fireEvent.keyDown(map, { key: "=" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });   // 14 가 가장 넓다 - 더 부르지 않는다
    // Ctrl + - 는 브라우저 화면 축소라 건드리지 않는다
    expect(fireEvent.keyDown(map, { key: "-", ctrlKey: true })).toBe(true);
    expect(setLevel.mock.calls.map(([level]) => level)).toEqual([12, 11, 12, 13, 14]);
  });

  it("tells a screen reader where the center is each time the map stops, and will not pick outside Korea", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const user = userEvent.setup();
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(map).toHaveFocus());
    const status = screen.getAllByRole("status").slice(-1)[0];   // 알림 칸이 둘(지도에서 찾기 · 가운데) - 가운데 알림이 마지막이다
    expect(status).toHaveTextContent("지도 가운데 위도 34.7600, 경도 127.6600");

    // 방향키로 옮긴 지도가 멈추면(idle) 새 가운데를 알린다
    await user.keyboard("{ArrowUp}");
    kakao.dragMapTo(34.79, 127.66);
    act(() => kakao.emitMapIdle());
    expect(status).toHaveTextContent("지도 가운데 위도 34.7900, 경도 127.6600");

    // 가운데가 대한민국 밖(위도 39 너머)이면 그렇게 알리고, '이 위치로'도 Enter 도 고르지 않는다
    kakao.dragMapTo(40.2, 127.66);
    act(() => kakao.emitMapIdle());
    expect(status).toHaveTextContent("대한민국 밖이에요. 대한민국 안으로 옮겨 주세요.");
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(onPick).not.toHaveBeenCalled();
    expect(locate).not.toHaveBeenCalled();   // 대한민국 밖은 지번도 묻지 않는다

    // 다시 안으로 옮기면 고를 수 있다
    kakao.dragMapTo(34.79, 127.66);
    act(() => kakao.emitMapIdle());
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeEnabled();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(BUILDING_SPOT));
    expect(locate).toHaveBeenCalledExactlyOnceWith(34.79, 127.66);
  });

  it("opens on the first public place of the trip when the area has no center", async () => {
    const { kakao } = openPicker({ latitude: null, longitude: null }, { latitude: 35.1, longitude: 129.03 });

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 35.1, lng: 129.03 }, level: 6 });
  });

  it("opens on the middle of Korea when nothing else is known, and still opens if the center request fails", async () => {
    const { kakao } = openPicker(new Error("offline"));

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(kakao.mapInstances[0].options).toMatchObject({
      center: { lat: KOREA_CENTER.latitude, lng: KOREA_CENTER.longitude },
      level: 13,
    });
  });

  it("closes with cancel and says so when the map cannot load", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");   // 키가 없어 SDK 를 불러올 수 없다
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const onCancel = vi.fn();
    render(<MapPointPicker fallbackCenter={null} onCancel={onCancel} onPick={vi.fn()} tripId="7" />);

    expect(await screen.findByText(/지도를 불러오지 못했어요/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeDisabled();
  });
});

describe("spotFromLocate", () => {
  it("keeps the public center for a building or a near parcel, only the address for a wide parcel, nothing without a jibun", () => {
    expect(spotFromLocate({ fill: BUILDING, nearCenter: true })).toEqual({ address: BUILDING.address, geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 });
    expect(spotFromLocate({ fill: FAR, nearCenter: false })).toEqual({ address: "강릉시 견소동 1", geoRef: { kind: "parcel", id: 77, pin: false }, latitude: null, longitude: null });
    expect(spotFromLocate({ fill: null, nearCenter: false })).toBeNull();
  });
});

describe("MapPointPicker jibun", () => {
  it("opens at the result spot when a start is given and still never hands out the picked coordinates", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 }, null, { center: { latitude: 37.7712, longitude: 128.948 }, origin: "kakao" });
    await waitFor(() => expect(kakao.mapInstances[0]?.options).toMatchObject({ center: { lat: 37.7712, lng: 128.948 }, level: 3 }));
    locate.mockResolvedValueOnce({ fill: null, nearCenter: false });
    await userEvent.setup().click(screen.getByRole("button", { name: "이 위치로" }));
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(null));   // 지번 없음 - 카카오 결과 좌표는 담지 않는다(151842-4)
  });

  it("moves the map to a place found in the map search without touching the name and asks for its jibun on pick", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([{ kind: "place", id: "kakao:1", name: "해운대 공영주차장", address: "부산 해운대구 중동", latitude: 35.1602, longitude: 129.1614 }]);
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    await user.type(screen.getByRole("textbox", { name: "지도에서 찾기" }), "해운대");
    const result = await screen.findByRole("button", { name: /해운대 공영주차장/ });
    expect(screen.getByRole("list", { name: "지도에서 찾기 결과" })).toContainElement(result);
    await user.click(result);
    expect(kakao.mapInstances[0].map.setCenter).toHaveBeenLastCalledWith(expect.objectContaining({ lat: 35.1602, lng: 129.1614 }));   // 지도만 옮겼다
    expect(screen.getByText(/‘해운대 공영주차장’ 자리로 옮겼어요/)).toBeInTheDocument();   // 상태 줄이 둘이라 role 로 고르지 않는다
    expect(screen.getByRole("application", { name: "위치 고르기 지도" })).toHaveFocus();   // 고른 뒤 지도로
    await user.click(screen.getByRole("button", { name: "이 위치로" }));
    await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(BUILDING_SPOT));
    expect(locate).toHaveBeenCalledWith(35.1602, 129.1614);
  });

  it("lists at most four map-search results that have a point and closes them with Esc", async () => {
    const { kakao } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const hit = (n: number, point = true) => ({ kind: "place" as const, id: `kakao:${n}`, name: `장소 ${n}`, address: `주소 ${n}`, latitude: point ? 35 + n / 100 : null, longitude: point ? 129 : null });
    vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([hit(1, false), hit(2), hit(3), hit(4), hit(5), hit(6)]);
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    await user.type(screen.getByRole("textbox", { name: "지도에서 찾기" }), "장소");
    const list = await screen.findByRole("list", { name: "지도에서 찾기 결과" });
    expect(within(list).getAllByRole("button").map((button) => button.textContent)).toEqual(["장소 2주소 2", "장소 3주소 3", "장소 4주소 4", "장소 5주소 5"]);   // 좌표 없는 결과는 빼고 넷까지
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("list", { name: "지도에서 찾기 결과" })).not.toBeInTheDocument();
  });

  it("says in a live status line that the map search is running and when it found nothing", async () => {
    const { kakao } = openPicker({ latitude: 34.76, longitude: 127.66 });
    let answer: (items: never[]) => void = () => undefined;
    const search = vi.spyOn(appDataApi, "searchPlaces").mockImplementation(() => new Promise((resolve) => { answer = resolve; }));
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(document.querySelector(".map-point-picker-search [role=status]")).toBeEmptyDOMElement();   // 검색 전에는 비어 있다
    await user.type(screen.getByRole("textbox", { name: "지도에서 찾기" }), "없는곳");
    const status = await screen.findByText("찾는 중…");
    expect(status).toHaveAttribute("role", "status");
    await waitFor(() => expect(search).toHaveBeenCalledTimes(1));   // 300ms 멈춘 뒤에야 묻는다
    await act(async () => answer([]));
    expect(await screen.findByText("결과가 없어요")).toBe(status);   // 같은 알림 칸의 글만 바뀐다
    await user.clear(screen.getByRole("textbox", { name: "지도에서 찾기" }));
    expect(status).toBeEmptyDOMElement();
  });

  it("keeps the focus on the confirm button while asking for the jibun and ignores a second press", async () => {
    const { kakao, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    locate.mockImplementationOnce(() => new Promise<LocateResult>(() => undefined));
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const confirm = screen.getByRole("button", { name: "이 위치로" });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);
    expect(confirm).toHaveFocus();   // disabled 로 끄면 초점이 body 로 떨어진다
    expect(confirm).not.toBeDisabled();
    expect(confirm).toHaveAttribute("aria-disabled", "true");
    await user.click(confirm);
    expect(locate).toHaveBeenCalledTimes(1);
  });

  it("ignores a late jibun answer when the map stopped after asking, lets the user pick again, and tells the user when asking failed", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    let answer: (value: LocateResult) => void = () => undefined;
    locate.mockImplementationOnce(() => new Promise<LocateResult>((resolve) => { answer = resolve; }));
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const confirm = screen.getByRole("button", { name: "이 위치로" });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);
    expect(confirm).toHaveAttribute("aria-disabled", "true");   // 묻는 동안은 꺼 둔다 - disabled 가 아니라 aria-disabled 라 초점을 잃지 않는다
    expect(confirm).toHaveFocus();
    kakao.dragMapTo(34.8, 127.7);   // 묻는 동안 지도를 옮기고
    act(() => kakao.emitMapIdle());   // 멈춘다 - 실제 지도는 끌기가 끝나면 idle 을 낸다. 물음을 무르고 '이 위치로'를 다시 켠다
    expect(confirm).toBeEnabled();
    await act(async () => answer({ fill: BUILDING, nearCenter: true }));
    expect(onPick).not.toHaveBeenCalled();   // 늦은 답은 버린다(코덱스 MEDIUM)
    expect(confirm).toBeEnabled();   // 버린 답이 단추를 다시 잠그지 않는다
    locate.mockRejectedValueOnce(new Error("network"));
    await user.click(confirm);
    expect(await screen.findByRole("alert")).toHaveTextContent("지번을 확인하지 못했어요. 다시 찍거나 취소하고 이름만 담아 주세요.");
    expect(onPick).not.toHaveBeenCalled();
  });

  it("also ignores a late jibun answer for a spot the map already left before it reported idle", async () => {
    const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
    let answer: (value: LocateResult) => void = () => undefined;
    locate.mockImplementationOnce(() => new Promise<LocateResult>((resolve) => { answer = resolve; }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const confirm = screen.getByRole("button", { name: "이 위치로" });
    await waitFor(() => expect(confirm).toBeEnabled());
    await userEvent.setup().click(confirm);
    kakao.dragMapTo(34.8, 127.7);   // idle 은 아직 안 냈다 - 방향키로 옮긴 직후처럼
    await act(async () => answer({ fill: BUILDING, nearCenter: true }));
    expect(onPick).not.toHaveBeenCalled();   // 십자선 밑이 달라졌으니 버린다
    expect(confirm).toBeEnabled();   // 답이 왔으니 다시 누를 수 있다
  });
});

describe("pickerStart", () => {
  it("opens on the area center, then the trip's own public place, when no start is given", () => {
    expect(pickerStart({ latitude: 1, longitude: 2 }, { latitude: 3, longitude: 4 })).toEqual({
      center: { latitude: 1, longitude: 2 },
      level: 6,
    });
    expect(pickerStart({ latitude: null, longitude: null }, { latitude: 3, longitude: 4 })).toEqual({
      center: { latitude: 3, longitude: 4 },
      level: 6,
    });
    expect(pickerStart(null, null)).toEqual({ center: KOREA_CENTER, level: 13 });
  });
});

describe("firstPublicPlacePoint", () => {
  const place = (overrides: Partial<ItineraryPlace>): ItineraryPlace => ({ time: "", label: "장소", meta: "", ...overrides });

  it("takes the first public place with a point, in day order", () => {
    const days = {
      2: [place({ placeOrigin: "public", latitude: 35.2, longitude: 129.2 })],
      1: [
        place({ placeOrigin: "custom", latitude: 37, longitude: 127 }),
        place({ placeOrigin: "public", latitude: null, longitude: null }),
        place({ placeOrigin: "public", latitude: 34.1, longitude: 126.1 }),
      ],
    };

    expect(firstPublicPlacePoint(days)).toEqual({ latitude: 34.1, longitude: 126.1 });
  });

  it("is null when the trip has no public place with a point", () => {
    expect(firstPublicPlacePoint({ 1: [place({ placeOrigin: "custom", latitude: 37, longitude: 127 })] })).toBeNull();
    expect(firstPublicPlacePoint({ 1: [place({})] })).toBeNull();
    expect(firstPublicPlacePoint({})).toBeNull();
  });
});
