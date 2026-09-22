const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export type ApiHealth = {
  status: "ok";
  service: string;
  environment: string;
  database: "connected" | "unavailable" | "not_configured";
};

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const apiConfig = {
  baseUrl: configuredApiBaseUrl === "same-origin"
    ? ""
    : (configuredApiBaseUrl || DEFAULT_API_BASE_URL).replace(/\/$/, ""),
};

let accessToken: string | null = null;

/* 401 을 만났을 때 토큰을 다시 받아 오는 통로. 세션 쪽이 등록한다.
   client 가 appDataApi 를 직접 부르면 import 가 순환한다. */
type TokenRefresher = () => Promise<string | null>;
let refreshAccessToken: TokenRefresher | null = null;
let pendingRefresh: Promise<string | null> | null = null;

export function setApiTokenRefresher(refresher: TokenRefresher | null) {
  refreshAccessToken = refresher;
  pendingRefresh = null;
}

/* 리프레시 토큰은 쓰는 순간 회전한다 — 백엔드 `auth_service.refresh` 가 기존 토큰을 revoke 한다.
   그래서 동시에 두 번 부르면 두 번째는 이미 폐기된 쿠키를 보내 401 이 되고,
   멀쩡한 세션이 끊긴 것처럼 보인다. 몇 개가 몰리든 한 번만 흐르게 묶는다. */
export function refreshApiAccessToken(): Promise<string | null> {
  const refresher = refreshAccessToken;
  if (!refresher) return Promise.resolve(null);
  if (!pendingRefresh) {
    pendingRefresh = refresher()
      .catch(() => null)
      .finally(() => {
        pendingRefresh = null;
      });
  }
  return pendingRefresh;
}

/* 재발급을 시도해선 안 되는 경로. `/api/auth/refresh` 는 자기 자신을 다시 부르고,
   로그인·회원가입의 401 은 "비밀번호가 틀렸다"는 뜻이라 재발급할 세션이 없다.
   `/api/me` 는 낡은 토큰으로 부르는 첫 요청이라 오히려 재발급이 필요하다. */
function skipsTokenRefresh(path: string): boolean {
  return path.startsWith("/api/auth/");
}

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;
  body: unknown;
  /** 백엔드가 응답 헤더 X-Request-Id 로 준 요청 ID. 문의 코드로 보여 주면 서버 로그를 바로 찾을 수 있다. */
  requestId: string | null;

  constructor(
    message: string,
    options: { status: number; statusText: string; detail?: unknown; body?: unknown; requestId?: string | null },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.statusText = options.statusText;
    this.detail = options.detail;
    this.body = options.body;
    this.requestId = options.requestId ?? null;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** 오류 문구 뒤에 문의 코드를 붙인다. 응답이 없던 오류(네트워크 단절)는 코드가 없다. */
export function withInquiryCode(message: string, error: unknown): string {
  return isApiError(error) && error.requestId ? `${message} (문의 코드: ${error.requestId})` : message;
}

export function setApiAccessToken(token: string | null) {
  accessToken = token;
}

async function sendRequest(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  return fetch(`${apiConfig.baseUrl}${path}`, {
    credentials: "include",
    headers,
    ...init,
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await sendRequest(path, init);

  /* 액세스 토큰은 짧게 산다. 탭을 열어 둔 채 방치하면 다음 요청이 401 로 떨어지는데,
     여기서 되살리지 않으면 화면마다 "불러오지 못했어요"가 뜨고 새로고침으로만 풀린다.
     재시도는 요청당 한 번이다. 두 번째도 401 이면 정말로 세션이 끝난 것이다. */
  if (
    response.status === 401 &&
    refreshAccessToken &&
    !skipsTokenRefresh(path)
  ) {
    const nextToken = await refreshApiAccessToken();
    if (nextToken) {
      response = await sendRequest(path, init);
    }
  }

  if (!response.ok) {
    let detail: unknown;
    let body: unknown;
    try {
      body = await response.clone().json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = (body as { detail?: unknown }).detail;
      }
    } catch {
      // Keep the generic message when the backend does not return a JSON error payload.
    }
    const message = typeof detail === "string" && detail
      ? detail
      : `API request failed: ${response.status} ${response.statusText}`;
    throw new ApiError(message, {
      status: response.status,
      statusText: response.statusText,
      detail,
      body,
      requestId: response.headers.get("X-Request-Id"),
    });
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, init?: RequestInit) => request<T>(path, init),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) =>
    request<T>(path, {
      method: "DELETE",
    }),
  getHealth: () => request<ApiHealth>("/api/health"),
};
