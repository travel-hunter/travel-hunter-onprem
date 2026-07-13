import { afterEach, describe, expect, it, vi } from "vitest";

async function importKakaoMapModule() {
  vi.resetModules();
  return import("./kakaoMap");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  delete window.kakao;
  document.querySelectorAll("script[data-kakao-map-sdk]").forEach((script) => script.remove());
});

describe("kakaoMap loader", () => {
  it("reports whether the Kakao JavaScript key is configured", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const withoutKey = await importKakaoMapModule();
    expect(withoutKey.hasKakaoMapKey()).toBe(false);

    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const withKey = await importKakaoMapModule();
    expect(withKey.hasKakaoMapKey()).toBe(true);
  });

  it("injects the Kakao SDK script and resolves after maps.load", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const { loadKakaoMaps } = await importKakaoMapModule();

    const loading = loadKakaoMaps();
    const script = document.querySelector<HTMLScriptElement>("script[data-kakao-map-sdk]");
    expect(script).toBeTruthy();
    expect(script?.src).toContain("https://dapi.kakao.com/v2/maps/sdk.js");
    expect(script?.src).toContain("appkey=test-js-key");
    expect(script?.src).toContain("autoload=false");
    expect(script?.src).toContain("libraries=services");

    const load = vi.fn((callback: () => void) => callback());
    window.kakao = { maps: { load } } as unknown as Window["kakao"];
    script?.dispatchEvent(new Event("load"));

    await expect(loading).resolves.toBe(window.kakao);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("rejects when the Kakao SDK script fails to load", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const { loadKakaoMaps } = await importKakaoMapModule();

    const loading = loadKakaoMaps();
    document.querySelector<HTMLScriptElement>("script[data-kakao-map-sdk]")?.dispatchEvent(new Event("error"));

    await expect(loading).rejects.toThrow("Failed to load Kakao Maps SDK");
  });
});
