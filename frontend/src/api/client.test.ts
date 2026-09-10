import { afterEach, describe, expect, it, vi } from "vitest";
import {
  apiClient,
  setApiAccessToken,
  setApiTokenRefresher,
} from "./client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authHeaderOf(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

describe("apiClient 401 재발급", () => {
  afterEach(() => {
    setApiTokenRefresher(null);
    setApiAccessToken(null);
    vi.restoreAllMocks();
  });

  it("401 을 만나면 토큰을 다시 받아 같은 요청을 한 번 재시도한다", async () => {
    setApiAccessToken("stale-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse([{ id: "1" }]));
    const refresher = vi.fn(async () => {
      setApiAccessToken("fresh-token");
      return "fresh-token";
    });
    setApiTokenRefresher(refresher);

    await expect(apiClient.get("/api/trips")).resolves.toEqual([{ id: "1" }]);

    expect(refresher).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(authHeaderOf(fetchSpy.mock.calls[0])).toBe("Bearer stale-token");
    // 재시도가 낡은 토큰을 그대로 다시 보내면 아무것도 고쳐지지 않는다.
    expect(authHeaderOf(fetchSpy.mock.calls[1])).toBe("Bearer fresh-token");
  });

  it("재시도도 401 이면 원래 오류를 그대로 올린다", async () => {
    setApiAccessToken("stale-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Not authenticated" }, 401));
    setApiTokenRefresher(async () => "fresh-token");

    await expect(apiClient.get("/api/trips")).rejects.toMatchObject({
      status: 401,
    });
    // 한 번만 재시도한다. 무한 반복이면 호출이 계속 늘어난다.
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("재발급이 실패하면 재시도하지 않는다", async () => {
    setApiAccessToken("stale-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Not authenticated" }, 401));
    setApiTokenRefresher(async () => null);

    await expect(apiClient.get("/api/trips")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("인증 경로의 401 은 재발급을 시도하지 않는다", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Invalid credentials" }, 401));
    const refresher = vi.fn(async () => "fresh-token");
    setApiTokenRefresher(refresher);

    // 비밀번호가 틀린 로그인까지 재발급을 돌리면 멀쩡한 세션을 건드린다.
    await expect(apiClient.post("/api/auth/login", {})).rejects.toMatchObject({
      status: 401,
    });
    expect(refresher).not.toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("동시에 401 을 맞은 요청들이 재발급을 한 번만 부른다", async () => {
    setApiAccessToken("stale-token");
    let tokenIsFresh = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      tokenIsFresh
        ? jsonResponse({ ok: true })
        : jsonResponse({ detail: "Not authenticated" }, 401),
    );
    /* 리프레시 토큰은 쓰는 순간 회전한다. 두 번 부르면 두 번째는 폐기된 쿠키를 보내고
       멀쩡한 세션이 끊긴다. 그래서 "한 번"이 이 테스트의 요점이다. */
    let resolveRefresh: (token: string) => void = () => undefined;
    const refresher = vi.fn(
      () =>
        new Promise<string | null>((resolve) => {
          resolveRefresh = (token) => {
            tokenIsFresh = true;
            setApiAccessToken(token);
            resolve(token);
          };
        }),
    );
    setApiTokenRefresher(refresher);

    const inFlight = Promise.all([
      apiClient.get("/api/trips"),
      apiClient.get("/api/me"),
      apiClient.get("/api/policies"),
    ]);
    // 세 요청이 모두 401 을 맞고 재발급을 기다리는 시점에 풀어 준다.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    resolveRefresh("fresh-token");

    await expect(inFlight).resolves.toEqual([
      { ok: true },
      { ok: true },
      { ok: true },
    ]);
    expect(refresher).toHaveBeenCalledTimes(1);
  });

  it("재발급이 끝난 뒤 다시 401 을 만나면 새로 재발급한다", async () => {
    setApiAccessToken("stale-token");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: 1 }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: 2 }));
    const refresher = vi.fn(async () => "fresh-token");
    setApiTokenRefresher(refresher);

    await apiClient.get("/api/trips");
    await apiClient.get("/api/trips");

    // 묶음이 한 번 끝나면 풀려야 한다. 안 풀리면 다음 만료를 영영 못 넘긴다.
    expect(refresher).toHaveBeenCalledTimes(2);
  });
});
