import { vi } from "vitest";

type MockLatLng = { lat: number; lng: number; getLat: () => number; getLng: () => number };
type MockMarker = { setMap: ReturnType<typeof vi.fn> };
type MockMap = {
  setBounds: ReturnType<typeof vi.fn>;
  setCenter: ReturnType<typeof vi.fn>;
  getCenter: ReturnType<typeof vi.fn>;
  panBy: ReturnType<typeof vi.fn>;
  getLevel: ReturnType<typeof vi.fn>;
  setLevel: ReturnType<typeof vi.fn>;
};

const makeLatLng = (lat: number, lng: number): MockLatLng => ({ lat, lng, getLat: () => lat, getLng: () => lng });

export function installAppKakaoSdkMock({
  resolvedLatitude = "35.096",
  resolvedLongitude = "129.03",
}: {
  resolvedLatitude?: string;
  resolvedLongitude?: string;
} = {}) {
  const addressQueries: string[] = [];
  const keywordQueries: string[] = [];
  const mapInstances: Array<{
    container: HTMLElement;
    options: Record<string, unknown>;
    map: MockMap;
    /** 사용자가 지도를 끌어 가운데를 옮긴 것을 흉내 낸다 - setCenter 를 부르지 않는다 */
    moveCenter: (latitude: number, longitude: number) => void;
  }> = [];
  const markerInstances: Array<{ marker: MockMarker; options: Record<string, unknown> }> = [];
  const customOverlayInstances: Array<{
    overlay: { setMap: ReturnType<typeof vi.fn> };
    options: Record<string, unknown>;
  }> = [];
  const eventListeners: Array<{ target: unknown; eventName: string; handler: (event: unknown) => void }> = [];

  function LatLng(this: MockLatLng, lat: number, lng: number) {
    Object.assign(this, makeLatLng(lat, lng));
  }

  function LatLngBounds(this: { extend: ReturnType<typeof vi.fn> }) {
    this.extend = vi.fn();
  }

  /* 가운데와 확대 수준을 기억하는 지도 - setCenter · setLevel 로 바꾸고 getCenter · getLevel 로 읽는다. panBy 는 부른 것만 기록한다(픽셀을 좌표로 바꾸지 않는다) */
  function Map(this: MockMap, container: HTMLElement, options: Record<string, unknown>) {
    let center = (options.center as MockLatLng | undefined) ?? makeLatLng(0, 0);
    this.setBounds = vi.fn();
    this.setCenter = vi.fn((next: MockLatLng) => {
      center = next;
    });
    this.getCenter = vi.fn(() => center);
    this.panBy = vi.fn();
    let level = (options.level as number | undefined) ?? 3;
    this.getLevel = vi.fn(() => level);
    this.setLevel = vi.fn((next: number) => {
      level = next;
    });
    mapInstances.push({
      container,
      options,
      map: this,
      moveCenter: (latitude, longitude) => {
        center = makeLatLng(latitude, longitude);
      },
    });
  }

  function Marker(this: MockMarker, options: Record<string, unknown>) {
    this.setMap = vi.fn();
    markerInstances.push({ marker: this, options });
  }

  function CustomOverlay(
    this: { setMap: ReturnType<typeof vi.fn> },
    options: Record<string, unknown>,
  ) {
    this.setMap = vi.fn();
    customOverlayInstances.push({ overlay: this, options });
  }

  const addressSearch = vi.fn(
    (
      query: string,
      callback: (
        results: Array<{ x: string; y: string }>,
        status: string,
      ) => void,
    ) => {
      addressQueries.push(query);
      callback([], "ZERO_RESULT");
    },
  );
  const keywordSearch = vi.fn(
    (
      query: string,
      callback: (
        results: Array<{ x: string; y: string }>,
        status: string,
      ) => void,
    ) => {
      keywordQueries.push(query);
      callback([{ x: resolvedLongitude, y: resolvedLatitude }], "OK");
    },
  );

  window.kakao = {
    maps: {
      LatLng,
      LatLngBounds,
      Map,
      Marker,
      CustomOverlay,
      event: {
        addListener: vi.fn((target: unknown, eventName: string, handler: (event: unknown) => void) => {
          eventListeners.push({ target, eventName, handler });
        }),
      },
      services: {
        Status: { OK: "OK" },
        Geocoder: function Geocoder(this: {
          addressSearch: typeof addressSearch;
        }) {
          this.addressSearch = addressSearch;
        },
        Places: function Places(this: { keywordSearch: typeof keywordSearch }) {
          this.keywordSearch = keywordSearch;
        },
      },
      load: vi.fn((callback: () => void) => callback()),
    },
  } as unknown as Window["kakao"];

  /** 지도(마커가 아니다)를 눌렀을 때를 흉내 낸다 - 위치 찍기 시험용. 상태를 바꾸므로 act 로 감싸 부른다 */
  function emitMapClick(latitude: number, longitude: number) {
    const event = { latLng: makeLatLng(latitude, longitude) };
    for (const listener of eventListeners) {
      const onMap = mapInstances.some((entry) => entry.map === listener.target);
      if (listener.eventName === "click" && onMap) listener.handler(event);
    }
  }

  /** 가장 나중에 만든 지도를 끌어 가운데가 이 자리로 온 것처럼 만든다(setCenter 를 거치지 않는다) */
  function dragMapTo(latitude: number, longitude: number) {
    mapInstances[mapInstances.length - 1]?.moveCenter(latitude, longitude);
  }

  /** 지도가 옮겨 가거나 확대 수준이 바뀐 뒤 멈춘 것(idle)을 흉내 낸다 - 위치 찍기 알림 시험용. 상태를 바꾸므로 act 로 감싸 부른다 */
  function emitMapIdle() {
    for (const listener of eventListeners) {
      const onMap = mapInstances.some((entry) => entry.map === listener.target);
      if (listener.eventName === "idle" && onMap) listener.handler(undefined);
    }
  }

  return {
    addressQueries,
    addressSearch,
    customOverlayInstances,
    dragMapTo,
    emitMapClick,
    emitMapIdle,
    eventListeners,
    keywordQueries,
    keywordSearch,
    mapInstances,
    markerInstances,
  };
}
