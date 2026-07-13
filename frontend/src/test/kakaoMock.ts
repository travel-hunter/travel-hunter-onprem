import { vi } from "vitest";

export function installAppKakaoSdkMock({
  resolvedLatitude = "35.096",
  resolvedLongitude = "129.03",
}: {
  resolvedLatitude?: string;
  resolvedLongitude?: string;
} = {}) {
  const addressQueries: string[] = [];
  const keywordQueries: string[] = [];
  const mapInstances: unknown[] = [];
  const markerInstances: unknown[] = [];
  const customOverlayInstances: Array<{
    overlay: { setMap: ReturnType<typeof vi.fn> };
    options: Record<string, unknown>;
  }> = [];

  function LatLng(
    this: { lat: number; lng: number },
    lat: number,
    lng: number,
  ) {
    this.lat = lat;
    this.lng = lng;
  }

  function LatLngBounds(this: { extend: ReturnType<typeof vi.fn> }) {
    this.extend = vi.fn();
  }

  function Map(
    this: {
      setBounds: ReturnType<typeof vi.fn>;
      setCenter: ReturnType<typeof vi.fn>;
    },
    container: HTMLElement,
    options: Record<string, unknown>,
  ) {
    this.setBounds = vi.fn();
    this.setCenter = vi.fn();
    mapInstances.push({ container, options });
  }

  function Marker(
    this: { setMap: ReturnType<typeof vi.fn> },
    options: Record<string, unknown>,
  ) {
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
      event: { addListener: vi.fn() },
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

  return {
    addressQueries,
    addressSearch,
    customOverlayInstances,
    keywordQueries,
    keywordSearch,
    mapInstances,
    markerInstances,
  };
}
