import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PublicPlaceItem, TripPlaceAddItem } from "../../../api";
import type { CustomStart } from "./CustomPlaceForm";
import { basketItemPayload, customBasketItem } from "./placeBasket";
import { PlaceMatchPanel } from "./PlaceMatchPanel";
import { usePlaceMatch, type PlaceMatchState } from "./usePlaceMatch";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  distanceMeters: 12,
};
const EMPTY_START: CustomStart = { typedName: "", fill: null, openAt: null };

afterEach(() => {
  vi.unstubAllEnvs();
});

function renderPanel(state: PlaceMatchState) {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
  const handlers = {
    onChooseCandidate: vi.fn(),
    onChooseCustom: vi.fn(),
    onStartDirect: vi.fn(),
    onSubmitCustom: vi.fn(),
    onCancel: vi.fn(),
  };
  render(<PlaceMatchPanel {...handlers} fallbackCenter={null} state={state} tripId="7" />);
  return handlers;
}

describe("PlaceMatchPanel", () => {
  it("shows only the direct entry while idle", async () => {
    const { onStartDirect } = renderPanel({ status: "idle" });

    await userEvent.click(screen.getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));

    expect(onStartDirect).toHaveBeenCalledTimes(1);
    expect(onStartDirect).toHaveBeenCalledWith();   // 클릭 이벤트를 typedQuery 로 넘기지 않는다
    expect(screen.queryByLabelText("장소 이름")).not.toBeInTheDocument();
  });

  it("says it is matching", () => {
    renderPanel({ status: "matching" });

    expect(screen.getByRole("status")).toHaveTextContent("맞춰 보는 중");
    expect(screen.queryByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" })).not.toBeInTheDocument();
  });

  it("shows the candidates and passes the choices through", async () => {
    const { onChooseCandidate, onChooseCustom } = renderPanel({
      status: "choose",
      kakaoPlaceId: "8193468",
      candidates: [odongdo],
      fallback: EMPTY_START,
    });

    await userEvent.click(screen.getByRole("button", { name: "오동도 선택" }));
    await userEvent.click(screen.getByRole("button", { name: "아니요, 다른 곳이에요" }));

    expect(onChooseCandidate).toHaveBeenCalledExactlyOnceWith(odongdo);
    expect(onChooseCustom).toHaveBeenCalledTimes(1);
  });

  it("shows the custom place form and passes the typed place and the cancel through", async () => {
    const { onSubmitCustom, onCancel } = renderPanel({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: 1, start: EMPTY_START });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("장소 이름"), "숙소");
    await user.click(screen.getByRole("button", { name: "담기" }));
    await user.click(screen.getByRole("button", { name: "취소" }));

    expect(onSubmitCustom).toHaveBeenCalledExactlyOnceWith({ name: "숙소", address: null, geoRef: null, latitude: null, longitude: null });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("opens a fresh custom place form for a new pick, so the name typed for the previous place does not stay", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const handlers = {
      onChooseCandidate: vi.fn(),
      onChooseCustom: vi.fn(),
      onStartDirect: vi.fn(),
      onSubmitCustom: vi.fn(),
      onCancel: vi.fn(),
    };
    const panel = (state: PlaceMatchState) => <PlaceMatchPanel {...handlers} fallbackCenter={null} state={state} tripId="7" />;
    const { rerender } = render(panel({ status: "custom", kakaoPlaceId: "1", reason: "noCoords", pickId: 1, start: EMPTY_START }));
    await userEvent.type(screen.getByLabelText("장소 이름"), "앞 장소에 적던 이름");

    // 위치가 없는 결과를 연달아 고르면 상태가 곧바로 custom 에서 custom 으로 바뀐다 - 같은 칸이 남으면 안 된다
    rerender(panel({ status: "custom", kakaoPlaceId: "2", reason: "noCoords", pickId: 2, start: EMPTY_START }));

    expect(screen.getByLabelText("장소 이름")).toHaveValue("");
  });

  it("never saves the name typed for one Kakao place under the Kakao id of the next one", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const added = vi.fn<(payload: TripPlaceAddItem) => void>();
    const withoutPoint = (id: string, title: string) => ({ id: `kakao:${id}`, title, latitude: null, longitude: null });
    // 일정 화면의 연결과 같다: 이름은 칸에서, 카카오 ID 는 지금 상태에서 꺼내 바구니 항목을 만든다
    function Harness() {
      const match = usePlaceMatch({ onMatched: () => undefined });
      return (
        <>
          <button onClick={() => void match.pick(withoutPoint("1", "첫째"))} type="button">
            첫째 고르기
          </button>
          <button onClick={() => void match.pick(withoutPoint("2", "둘째"))} type="button">
            둘째 고르기
          </button>
          <PlaceMatchPanel
            fallbackCenter={null}
            onCancel={match.reset}
            onChooseCandidate={match.chooseCandidate}
            onChooseCustom={match.chooseCustom}
            onStartDirect={match.startDirect}
            onSubmitCustom={(input) => {
              if (match.state.status === "custom") added(basketItemPayload(customBasketItem(input, match.state.kakaoPlaceId)));
            }}
            state={match.state}
            tripId="7"
          />
        </>
      );
    }
    render(<Harness />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "첫째 고르기" }));
    await user.type(await screen.findByLabelText("장소 이름"), "첫째 장소 이름");
    await user.click(screen.getByRole("button", { name: "둘째 고르기" }));

    expect(await screen.findByLabelText("장소 이름")).toHaveValue("");
    await user.type(screen.getByLabelText("장소 이름"), "둘째 장소 이름");
    await user.click(screen.getByRole("button", { name: "담기" }));

    expect(added).toHaveBeenCalledExactlyOnceWith({ customPlace: { name: "둘째 장소 이름" }, kakaoPlaceId: "2" });
  });
});
