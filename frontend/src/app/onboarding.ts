import type { User } from "../api";

export function getSafeRedirect(searchParams: URLSearchParams): string | null {
  return safePath(searchParams.get("redirect"));
}

export function safePath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  return value;
}

export function withRedirect(path: string, redirect: string | null): string {
  const safeRedirect = safePath(redirect);
  if (!safeRedirect) return path;
  return `${path}?redirect=${encodeURIComponent(safeRedirect)}`;
}

export function isOnboardingRoute(pathname: string): boolean {
  return pathname === "/nickname-setup" || pathname === "/profile-setup";
}

export function getOnboardingPath(user: User): string | null {
  if (user.onboardingCompleted) return null;
  const hasNickname = user.nickname.trim().length > 0;
  if (!user.nicknameSetupCompleted || !hasNickname) return "/nickname-setup";
  return "/profile-setup";
}

export function getPostAuthPath(user: User, redirect: string | null): string {
  const onboardingPath = getOnboardingPath(user);
  if (onboardingPath) return withRedirect(onboardingPath, redirect);
  return safePath(redirect) ?? "/home";
}
