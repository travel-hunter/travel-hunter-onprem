export type KakaoMapsNamespace = {
  maps: {
    LatLng: new (lat: number, lng: number) => unknown;
    LatLngBounds: new () => { extend: (latLng: unknown) => void };
    Map: new (container: HTMLElement, options: Record<string, unknown>) => {
      setBounds: (bounds: unknown) => void;
      setCenter: (latLng: unknown) => void;
    };
    Marker: new (options: Record<string, unknown>) => {
      setMap: (map: unknown | null) => void;
    };
    CustomOverlay: new (options: Record<string, unknown>) => {
      setMap: (map: unknown | null) => void;
    };
    event: { addListener: (target: unknown, eventName: string, handler: () => void) => void };
    services?: {
      Status: { OK: string };
      Geocoder: new () => {
        addressSearch: (query: string, callback: (results: Array<{ x: string; y: string }>, status: string) => void) => void;
      };
      Places: new () => {
        keywordSearch: (
          query: string,
          callback: (results: Array<{ x: string; y: string }>, status: string) => void,
        ) => void;
      };
    };
    load: (callback: () => void) => void;
  };
};

declare global {
  interface Window {
    kakao?: KakaoMapsNamespace;
  }
}

let kakaoMapsPromise: Promise<KakaoMapsNamespace> | null = null;

export function hasKakaoMapKey(): boolean {
  return Boolean(import.meta.env.VITE_KAKAO_MAP_JS_KEY?.trim());
}

export function loadKakaoMaps(): Promise<KakaoMapsNamespace> {
  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao);
  }
  if (kakaoMapsPromise) return kakaoMapsPromise;

  const appKey = import.meta.env.VITE_KAKAO_MAP_JS_KEY?.trim();
  if (!appKey) {
    kakaoMapsPromise = Promise.reject(new Error("Kakao Maps JavaScript key is not configured"));
    return kakaoMapsPromise;
  }

  kakaoMapsPromise = new Promise<KakaoMapsNamespace>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>("script[data-kakao-map-sdk]");

    const resolveWhenReady = () => {
      if (!window.kakao?.maps) {
        reject(new Error("Kakao Maps SDK did not expose window.kakao.maps"));
        return;
      }
      window.kakao.maps.load(() => resolve(window.kakao as KakaoMapsNamespace));
    };

    if (existingScript) {
      existingScript.addEventListener("load", resolveWhenReady, { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Kakao Maps SDK")), { once: true });
      if (window.kakao?.maps) resolveWhenReady();
      return;
    }

    const script = document.createElement("script");
    script.async = true;
    script.dataset.kakaoMapSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(appKey)}&autoload=false&libraries=services`;
    script.addEventListener("load", resolveWhenReady, { once: true });
    script.addEventListener("error", () => reject(new Error("Failed to load Kakao Maps SDK")), { once: true });
    document.head.appendChild(script);
  });

  return kakaoMapsPromise;
}
