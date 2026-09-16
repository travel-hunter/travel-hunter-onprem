const configuredAdminBaseUrl = () => (import.meta.env.VITE_ADMIN_BASE_URL ?? "").replace(/\/$/, "");

function safePath(path: string): string {
  return path.startsWith("/") && !path.startsWith("//") ? path : "/admin";
}

export function adminUrl(path: string): string {
  const adminBaseUrl = configuredAdminBaseUrl();
  return adminBaseUrl ? `${adminBaseUrl}${safePath(path)}` : safePath(path);
}

export function isAdminHost(origin = window.location.origin): boolean {
  const adminBaseUrl = configuredAdminBaseUrl();
  return !adminBaseUrl || origin === adminBaseUrl;
}

export function shouldShowPublicAuthActions(origin = window.location.origin): boolean {
  const adminBaseUrl = configuredAdminBaseUrl();
  return !adminBaseUrl || origin !== adminBaseUrl;
}