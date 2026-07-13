const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export type ApiHealth = {
  status: "ok";
  service: string;
  environment: string;
  database: "connected" | "unavailable" | "not_configured";
};

export const apiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, ""),
};

let accessToken: string | null = null;

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;
  body: unknown;

  constructor(message: string, options: { status: number; statusText: string; detail?: unknown; body?: unknown }) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.statusText = options.statusText;
    this.detail = options.detail;
    this.body = options.body;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function setApiAccessToken(token: string | null) {
  accessToken = token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${apiConfig.baseUrl}${path}`, {
    credentials: "include",
    headers,
    ...init,
  });

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
    });
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
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
