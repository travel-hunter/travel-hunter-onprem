import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KakaoMapView, type KakaoMapMarker } from "./KakaoMapView";

type MockKakaoMapObject = { options: Record<string, unknown>; setMap: ReturnType<typeof vi.fn>; setZIndex?: ReturnType<typeof vi.fn> };

type MockKakaoMaps = NonNullable<Window["kakao"]>["maps"];

function installKakaoSdkMock() {
  const markerClickHandlers: Array<() => void> = [];
  const mapInstances: unknown[] = [];
  const markerInstances: MockKakaoMapObject[] = [];
  const customOverlayInstances: MockKakaoMapObject[] = [];
  const boundsExtends: unknown[] = [];

  function LatLng(this: { lat: number; lng: number }, lat: number, lng: number) {
    this.lat = lat;
    this.lng = lng;
  }

  function LatLngBounds(this: { extend: (latLng: unknown) => void }) {
    this.extend = vi.fn((latLng: unknown) => boundsExtends.push(latLng));
  }

  function Map(
    this: { setBounds: ReturnType<typeof vi.fn>; setCenter: ReturnType<typeof vi.fn> },
    container: HTMLElement,
    options: Record<string, unknown>,
  ) {
    this.setBounds = vi.fn();
    this.setCenter = vi.fn();
    mapInstances.push({ container, options, setBounds: this.setBounds, setCenter: this.setCenter });
  }

  function Marker(this: MockKakaoMapObject, options: Record<string, unknown>) {
    this.setMap = vi.fn();
    this.options = options;
    markerInstances.push(Object.assign(this, { options }));
  }

  function CustomOverlay(this: MockKakaoMapObject, options: Record<string, unknown>) {
    this.setMap = vi.fn();
    this.setZIndex = vi.fn();
    this.options = options;
    customOverlayInstances.push(Object.assign(this, { options }));
  }

  const event = {
    addListener: vi.fn((_target: unknown, eventName: string, handler: () => void) => {
      if (eventName === "click") markerClickHandlers.push(handler);
    }),
  };
  const load = vi.fn((callback: () => void) => callback());

  const maps = { CustomOverlay, LatLng, LatLngBounds, Map, Marker, event, load } as unknown as MockKakaoMaps;
  window.kakao = { maps };

  return { boundsExtends, customOverlayInstances, event, load, mapInstances, markerClickHandlers, markerInstances };
}

function renderMap(markers: KakaoMapMarker[], onSelectMarker = vi.fn(), selectedMarkerId: string | null = null) {
  render(
    <KakaoMapView
      ariaLabel="추천 후보 지도"
      fallback={<p>좌표가 없어 지도를 표시할 수 없어요.</p>}
      markers={markers}
      onSelectMarker={onSelectMarker}
      selectedMarkerId={selectedMarkerId}
    />,
  );
  return onSelectMarker;
}

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.kakao;
  document.querySelectorAll("script[data-kakao-map-sdk]").forEach((script) => script.remove());
});

describe("KakaoMapView", () => {
  it("initializes the Kakao SDK map, markers, and always-visible place labels for valid coordinate markers", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();
    const onSelectMarker = renderMap([
      { id: "spot-1", label: "속초 전망대", subtitle: "명소", latitude: 38.2, longitude: 128.6 },
      { id: "food-1", label: "속초 로컬 맛집", subtitle: "맛집", latitude: 38.1, longitude: 128.5 },
    ]);

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));

    expect(kakao.markerInstances).toHaveLength(2);
    expect(kakao.customOverlayInstances).toHaveLength(2);
    expect(kakao.boundsExtends).toHaveLength(2);
    expect(kakao.event.addListener).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("좌표가 없어 지도를 표시할 수 없어요.")).not.toBeInTheDocument();

    const firstLabel = kakao.customOverlayInstances[0].options.content as HTMLElement;
    const secondLabel = kakao.customOverlayInstances[1].options.content as HTMLElement;
    expect(firstLabel).toHaveClass("kakao-map-place-label");
    expect(firstLabel).toHaveTextContent("1");
    expect(firstLabel).toHaveTextContent("속초 전망대");
    expect(firstLabel.querySelector("strong")).toHaveAttribute("title", "속초 전망대");
    expect(secondLabel).toHaveTextContent("속초 로컬 맛집");

    fireEvent.click(firstLabel);
    expect(onSelectMarker).toHaveBeenCalledWith("spot-1");

    kakao.markerClickHandlers[1]();
    expect(onSelectMarker).toHaveBeenCalledWith("food-1");
  });

  it("marks the selected place label and lets users clear it from the label", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();
    const onSelectMarker = vi.fn();
    renderMap([{ id: "spot-1", label: "속초 전망대", latitude: 38.2, longitude: 128.6 }], onSelectMarker, "spot-1");

    await waitFor(() => expect(kakao.customOverlayInstances).toHaveLength(1));

    const selectedLabel = kakao.customOverlayInstances[0].options.content as HTMLElement;
    expect(selectedLabel).toHaveClass("kakao-map-place-label", "selected");
    expect(selectedLabel).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(selectedLabel);
    expect(onSelectMarker).toHaveBeenCalledWith(null);
  });

  it("does not rebuild the Kakao map when selection props change", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();
    const markers = [{ id: "spot-1", label: "속초 전망대", latitude: 38.2, longitude: 128.6 }];
    const onSelectMarker = vi.fn();
    const { rerender } = render(
      <KakaoMapView
        ariaLabel="추천 후보 지도"
        fallback={<p>좌표가 없어 지도를 표시할 수 없어요.</p>}
        markers={markers}
        onSelectMarker={onSelectMarker}
        selectedMarkerId={null}
      />,
    );

    await waitFor(() => expect(kakao.customOverlayInstances).toHaveLength(1));
    const label = kakao.customOverlayInstances[0].options.content as HTMLElement;
    expect(label).not.toHaveClass("selected");

    rerender(
      <KakaoMapView
        ariaLabel="추천 후보 지도"
        fallback={<p>좌표가 없어 지도를 표시할 수 없어요.</p>}
        markers={[...markers]}
        onSelectMarker={(markerId) => onSelectMarker(markerId)}
        selectedMarkerId="spot-1"
      />,
    );

    expect(kakao.mapInstances).toHaveLength(1);
    expect(kakao.markerInstances).toHaveLength(1);
    expect(kakao.customOverlayInstances).toHaveLength(1);
    await waitFor(() => expect(label).toHaveClass("selected"));
    expect(label).toHaveAttribute("aria-pressed", "true");
    expect(kakao.customOverlayInstances[0].setZIndex).toHaveBeenCalledWith(20);
  });


  it("resolves marker coordinates from Kakao services when AI candidates only provide a search query", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();
    const addressSearch = vi.fn((_query: string, callback: (results: Array<{ x: string; y: string }>, status: string) => void) => {
      callback([], "ZERO_RESULT");
    });
    const keywordSearch = vi.fn((query: string, callback: (results: Array<{ x: string; y: string }>, status: string) => void) => {
      expect(query).toBe("속초 전망대");
      callback([{ y: "38.2", x: "128.6" }], "OK");
    });
    window.kakao = {
      maps: {
        ...window.kakao!.maps,
        services: {
          Status: { OK: "OK" },
          Geocoder: function Geocoder(this: { addressSearch: typeof addressSearch }) {
            this.addressSearch = addressSearch;
          },
          Places: function Places(this: { keywordSearch: typeof keywordSearch }) {
            this.keywordSearch = keywordSearch;
          },
        },
      },
    } as unknown as Window["kakao"];

    renderMap([{ id: "spot-1", label: "속초 전망대", latitude: null, longitude: null, query: "속초 전망대" }]);

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(addressSearch).toHaveBeenCalledWith("속초 전망대", expect.any(Function));
    expect(keywordSearch).toHaveBeenCalledWith("속초 전망대", expect.any(Function));
    expect(kakao.markerInstances).toHaveLength(1);
    expect(kakao.customOverlayInstances).toHaveLength(1);
    expect(kakao.customOverlayInstances[0].options.content).toHaveTextContent("속초 전망대");
  });

  it("renders fallback content and skips SDK map initialization when no valid coordinates exist", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();

    renderMap([
      { id: "missing", label: "좌표 없는 후보", subtitle: "명소", latitude: null, longitude: null },
      { id: "invalid", label: "잘못된 후보", subtitle: "맛집", latitude: Number.NaN, longitude: 128.5 },
    ]);

    expect(screen.getByText("좌표가 없어 지도를 표시할 수 없어요.")).toBeInTheDocument();
    expect(kakao.mapInstances).toHaveLength(0);
    expect(kakao.markerInstances).toHaveLength(0);
    expect(kakao.customOverlayInstances).toHaveLength(0);
    expect(kakao.event.addListener).not.toHaveBeenCalled();
  });

  it("renders fallback content and skips SDK map initialization when the Kakao key is not configured", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const kakao = installKakaoSdkMock();

    renderMap([{ id: "spot-1", label: "속초 전망대", latitude: 38.2, longitude: 128.6 }]);

    expect(screen.getByText("좌표가 없어 지도를 표시할 수 없어요.")).toBeInTheDocument();
    expect(kakao.mapInstances).toHaveLength(0);
    expect(kakao.markerInstances).toHaveLength(0);
    expect(kakao.customOverlayInstances).toHaveLength(0);
  });

  it("keeps long place labels on the bounded overlay class with a full title", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installKakaoSdkMock();
    const longPlaceName = "공주 공산성 연지 및 주변 문화유산 탐방지";

    renderMap([{ id: "long-spot", label: longPlaceName, latitude: 36.46, longitude: 127.12 }]);

    await waitFor(() => expect(kakao.customOverlayInstances).toHaveLength(1));

    const label = kakao.customOverlayInstances[0].options.content as HTMLElement;
    expect(label).toHaveClass("kakao-map-place-label");
    expect(label.querySelector("strong")).toHaveTextContent(longPlaceName);
    expect(label.querySelector("strong")).toHaveAttribute("title", longPlaceName);
  });
});
