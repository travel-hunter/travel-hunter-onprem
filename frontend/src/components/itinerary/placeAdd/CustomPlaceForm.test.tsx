import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi } from "../../../api";
import { installAppKakaoSdkMock } from "../../../test/kakaoMock";
import { CustomPlaceForm, type CustomPlaceReason, type CustomStart } from "./CustomPlaceForm";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.kakao;
});

const EMPTY_START: CustomStart = { typedName: "", fill: null, openAt: null };
const FILL = { kind: "parcel" as const, id: 4401, pnu: "1213010200100010006", address: "전남광주통합특별시 여수시 수정동 1-6", latitude: 34.744764, longitude: 127.767783, distanceMeters: 2 };

function renderForm(reason: CustomPlaceReason = "none", start: CustomStart = EMPTY_START) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(<CustomPlaceForm fallbackCenter={null} onCancel={onCancel} onSubmit={onSubmit} reason={reason} start={start} tripId="7" />);
  return { onSubmit, onCancel, form: screen.getByRole("form", { name: "나만의 장소" }) };
}

describe("CustomPlaceForm", () => {
  it("starts with an empty name field that is not pre-filled or hinted with any place name", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form } = renderForm();

    const name = within(form).getByLabelText("장소 이름");
    expect(name).toHaveValue("");
    expect(name).toHaveAttribute("name", "custom-place-name");
    expect(within(form).getByRole("button", { name: "담기" })).toBeDisabled();
  });

  it("explains why it opened", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const expected: Record<CustomPlaceReason, RegExp> = {
      none: /같은 곳을 찾지 못했어요/,
      noCoords: /위치 정보가 없어서/,
      failed: /맞춰 보지 못했어요/,
      direct: /이름을 적고, 지도에서 찾아/,
      building: /건물의 지번으로 주소와 위치를/,
      parcel: /땅의 지번으로 주소와 위치를/,
      pin: /주소를 바로 채우지 못했어요/,
    };
    for (const [reason, text] of Object.entries(expected)) {
      const { form } = renderForm(reason as CustomPlaceReason);
      expect(within(form).getByText(text)).toBeInTheDocument();
      cleanup();
    }
  });

  it("submits the trimmed name without a point when no point was picked", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "  할머니 댁  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "할머니 댁", address: null, geoRef: null, latitude: null, longitude: null });
  });

  it("submits with Enter and ignores a blank name", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onSubmit } = renderForm("direct");
    const user = userEvent.setup();
    const name = within(form).getByLabelText("장소 이름");

    await user.type(name, "   {Enter}");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.clear(name);
    await user.type(name, "숙소{Enter}");
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "숙소", address: null, geoRef: null, latitude: null, longitude: null });
  });

  it("hides the map pin button when there is no map key", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form } = renderForm();

    expect(within(form).queryByRole("button", { name: "지도에서 찾아 위치 찍기" })).not.toBeInTheDocument();
  });

  it("hides its own cancel and add buttons while the map is open, and Enter does not save (결정 26)", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "내 쉼터");
    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));

    // 지도의 취소 · 이 위치로만 보인다 - 칸의 취소 · 담기가 둘씩 보이지 않게
    expect(within(form).getAllByRole("button", { name: "취소" })).toHaveLength(1);
    expect(within(form).queryByRole("button", { name: "담기" })).not.toBeInTheDocument();
    // 찍는 중에 이름 칸에서 Enter 를 눌러도 위치 없이 담기지 않는다
    await user.type(within(form).getByLabelText("장소 이름"), "{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("lets the user pick the spot with the keyboard alone and puts the focus on the add button", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    // 지도가 열리면 지도에 초점이 있어 바로 방향키를 쓴다
    const map = await within(form).findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(map).toHaveFocus());
    await user.keyboard("{ArrowRight}");
    expect(kakao.mapInstances[0].map.panBy).toHaveBeenCalledWith(60, 0);
    kakao.dragMapTo(34.77, 127.67);
    await user.keyboard("{Enter}");

    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    expect(locate).toHaveBeenCalledWith(34.77, 127.67);
    // 이름이 있어 담기가 켜져 있다 - 지도가 닫힌 뒤 초점은 담기로
    await waitFor(() => expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus());
    await user.click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
  });

  it("puts the focus back on the open-map button when the map is cancelled", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form } = renderForm();
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await within(form).findByRole("application", { name: "위치 고르기 지도" });
    // 양식 자체의 취소와 지도의 취소가 둘 다 있다 - 지도 쪽을 누른다
    await user.click(within(within(form).getByRole("region", { name: "지도에서 위치 찍기" })).getByRole("button", { name: "취소" }));

    expect(within(form).queryByRole("application")).not.toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" })).toHaveFocus();
  });

  it("lets the user clear a picked point before submitting", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "지우기" }));
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: null, geoRef: null, latitude: null, longitude: null });
  });

  it("cancels", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onCancel } = renderForm();

    await userEvent.click(within(form).getByRole("button", { name: "취소" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("prefills the typed query, shows the public jibun and submits its reference with a pin", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onSubmit } = renderForm("parcel", { typedName: "오동도 선착장", fill: FILL, openAt: null });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("오동도 선착장");
    expect(within(form).getByText("내가 친 검색어로 채웠어요 · 고칠 수 있어요")).toBeInTheDocument();
    expect(within(form).getByText(FILL.address)).toBeInTheDocument();
    expect(within(form).getByText("땅 지번 · 국토교통부 공공데이터")).toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus();   // 이름 · 주소가 이미 있다
    await userEvent.setup().click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "오동도 선착장", address: FILL.address, geoRef: { kind: "parcel", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
  });

  it("keeps the filled spot's small map when the name is edited", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const { form } = renderForm("building", { typedName: "스타벅스", fill: { ...FILL, kind: "building" }, openAt: null });
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));

    await user.type(within(form).getByLabelText("장소 이름"), " 강남역점");
    await act(async () => {});

    // 마커 라벨이 이름을 따라가면 글자마다 지도를 새로 만든다
    expect(kakao.mapInstances).toHaveLength(1);
  });

  it("cuts a long typed query to 100 characters and keeps the button off for an empty one", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const long = renderForm("direct", { typedName: "가".repeat(130), fill: null, openAt: null });
    expect((within(long.form).getByLabelText("장소 이름") as HTMLInputElement).value).toHaveLength(100);
    cleanup();
    const empty = renderForm("direct", { typedName: "", fill: null, openAt: null });
    expect(within(empty.form).getByRole("button", { name: "담기" })).toBeDisabled();
    expect(within(empty.form).queryByText("내가 친 검색어로 채웠어요 · 고칠 수 있어요")).not.toBeInTheDocument();
  });

  it("opens the picker right away at the result spot for a pin row and hides its own buttons", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form } = renderForm("pin", { typedName: "안목해변", fill: null, openAt: { latitude: 37.7712, longitude: 128.948 } });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 37.7712, lng: 128.948 } });   // 결과 자리에서 연다(보여 주기만)
    expect(within(form).queryByRole("button", { name: "담기" })).not.toBeInTheDocument();   // 결정 26
  });

  it("reopens the picker at the result spot when a cancelled pin row asks for the map again", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form } = renderForm("pin", { typedName: "안목해변", fill: null, openAt: { latitude: 37.7712, longitude: 128.948 } });
    const user = userEvent.setup();
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    await user.click(within(within(form).getByRole("region", { name: "지도에서 위치 찍기" })).getByRole("button", { name: "취소" }));
    expect(within(form).queryByRole("application")).not.toBeInTheDocument();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(2));
    // 처음 자동으로 열린 자리와 같은 자리에서 다시 연다 - 일정 지역 가운데(34.76, 127.66)가 아니다
    expect(kakao.mapInstances[1].options).toMatchObject({ center: { lat: 37.7712, lng: 128.948 } });
  });

  it("fills the address and the public center from the jibun of the picked spot", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();
    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(locate).toHaveBeenCalledWith(34.75, 127.65);
    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    // 찍은 좌표(34.75, 127.65)는 어디에도 없다 - 좌표는 공공데이터 중심
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
  });

  it("keeps only the address for a wide parcel and only the name where there is no jibun", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValueOnce({ fill: { ...FILL, distanceMeters: 85 }, nearCenter: false });
    const { form, onSubmit } = renderForm("direct", { typedName: "넓은 공원", fill: null, openAt: null });
    const user = userEvent.setup();
    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(await within(form).findByText("이 땅은 넓어서 핀 없이 주소만 담겨요")).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenLastCalledWith({ name: "넓은 공원", address: FILL.address, geoRef: { kind: "parcel", id: 4401, pin: false }, latitude: null, longitude: null });

    locate.mockResolvedValueOnce({ fill: null, nearCenter: false });
    await user.click(within(form).getByRole("button", { name: "다시 찍기" }));
    await user.click(await within(form).findByRole("button", { name: "이 위치로" }));
    expect(await within(form).findByText("이 자리는 지번이 없어 위치 없이 이름만 담겨요")).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenLastCalledWith({ name: "넓은 공원", address: null, geoRef: null, latitude: null, longitude: null });
  });

  it("puts the focus on the add button when the map is cancelled with a name filled in", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await within(form).findByRole("application", { name: "위치 고르기 지도" });
    // 양식 자체의 취소와 지도의 취소가 둘 다 있다 - 지도 쪽을 누른다
    await user.click(within(within(form).getByRole("region", { name: "지도에서 위치 찍기" })).getByRole("button", { name: "취소" }));

    expect(within(form).queryByRole("application")).not.toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus();   // 담기가 켜져 있으면 담기로
  });

  it("puts the focus on the fix-position button when a spot was picked but the name is still empty", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form } = renderForm("direct");
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));

    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    // 이름이 비어 담기가 꺼져 있다 - 꺼진 단추로 보내면 초점이 body 로 떨어지니 지도를 다시 여는 단추로
    expect(within(form).getByRole("button", { name: "담기" })).toBeDisabled();
    await waitFor(() => expect(within(form).getByRole("button", { name: "위치 고치기" })).toHaveFocus());
  });

  it("keeps the typed name when a place found in the map search only moves the map", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([{ kind: "place", id: "kakao:1", name: "해운대 공영주차장", address: "부산 해운대구 중동", latitude: 35.1602, longitude: 129.1614 }]);
    const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    await user.type(within(form).getByRole("textbox", { name: "지도에서 찾기" }), "해운대");
    await user.click(await within(form).findByRole("button", { name: /해운대 공영주차장/ }));

    expect(kakao.mapInstances[0].map.setCenter).toHaveBeenCalledWith(expect.objectContaining({ lat: 35.1602, lng: 129.1614 }));   // 지도만 옮겼다
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("내 쉼터");   // 이름 칸은 그대로
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(locate).toHaveBeenCalledWith(35.1602, 129.1614);
    await user.click(await within(form).findByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
    expect(JSON.stringify(onSubmit.mock.calls)).not.toContain("해운대 공영주차장");   // 카카오 이름은 어디에도 실리지 않는다
  });
});
