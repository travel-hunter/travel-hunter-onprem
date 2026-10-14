import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  appDataApi,
  AuthResponse,
  CompleteSocialSignupRequest,
  LoginRequest,
  setApiAccessToken,
  refreshApiAccessToken,
  setApiTokenRefresher,
  SignupCompleteRequest,
  SignupRequest,
  SignupVerificationResponse,
  SignupVerifyResponse,
  Profile,
  User,
} from "../api";
import { forgetPlaces } from "../components/map/placeMemory";
import { NO_CONDITIONS, setPolicyConditions } from "../components/map/policyConditions";

type SessionContextValue = {
  currentUser: User | null;
  isSessionBootstrapping: boolean;
  profile: Profile;
  addedPolicySlugs: Set<string>;
  login: (request?: LoginRequest) => Promise<void>;
  signup: (request?: SignupRequest) => Promise<SignupVerificationResponse>;
  verifySignup: (token: string) => Promise<SignupVerifyResponse>;
  completeSignup: (request: SignupCompleteRequest) => Promise<User>;
  completeSocialSignup: (request: CompleteSocialSignupRequest) => Promise<User>;
  completeOAuthSession: () => Promise<User>;
  logout: () => Promise<void>;
  saveNickname: (nickname: string) => Promise<User>;
  updateProfile: <K extends keyof Profile>(key: K, value: Profile[K]) => void;
  saveProfile: (profile?: Partial<Profile>) => Promise<Profile>;
  skipProfileSetup: () => Promise<void>;
  addPolicy: (slug?: string) => void;
  removeAddedPolicy: (slug: string) => void;
  isPolicyAdded: (slug: string) => boolean;
  /** 서버에서 내 일정에 담긴 정책을 다시 읽는다. 다른 일정 · 다른 기기에서 빼거나 일정을 지운 것을 따라간다 */
  refreshAddedPolicies: () => void;
  savedSlugs: Set<string>;
  addSavedSlug: (slug: string) => void;
  removeSavedSlug: (slug: string) => void;
};

const AUTH_STORAGE_KEY = "travel-hunter-production-auth";
const PROFILE_PROMPT_DISMISSAL_PREFIX = "travel-hunter-profile-completion-dismissed:";

const SessionContext = createContext<SessionContextValue | null>(null);

function readStoredAuth(): AuthResponse | null {
  try {
    const saved = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!saved) return null;
    const parsed = JSON.parse(saved) as Partial<AuthResponse>;
    if (!parsed.accessToken || !parsed.user) return null;
    return { accessToken: parsed.accessToken, user: parsed.user };
  } catch {
    return null;
  }
}

function persistAuth(auth: AuthResponse) {
  setApiAccessToken(auth.accessToken);
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

/* 재발급은 client 한 곳으로 모은다. 거기서 동시 요청을 한 번으로 묶는다
   — 리프레시 토큰이 회전하므로 두 번 부르면 두 번째가 세션을 끊는다. */
async function refreshSessionOnce(): Promise<AuthResponse | null> {
  const token = await refreshApiAccessToken();
  if (!token) return null;
  return readStoredAuth();
}

function clearAuth() {
  // 정책 탭 좁히기 조건(관심 정책만 · 검색어)은 그 사람의 것이다 - 같은 탭에서 다른 사람이 로그인할 때 남지 않게
  setPolicyConditions(NO_CONDITIONS);
  forgetPlaces();   // 본 카카오 장소 메모리도 그 사람의 것이다
  setApiAccessToken(null);
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  clearProfileCompletionPromptDismissals();
}

function clearProfileCompletionPromptDismissals() {
  for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = window.sessionStorage.key(index);
    if (key?.startsWith(PROFILE_PROMPT_DISMISSAL_PREFIX)) {
      window.sessionStorage.removeItem(key);
    }
  }
}

async function readRemoteProfile(): Promise<Profile> {
  return appDataApi.getProfile();
}

const emptyProfile: Profile = {
  preferredRegions: null,
  style: null,
  budget: null,
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<User | null>(() => {
    const stored = readStoredAuth();
    if (stored) setApiAccessToken(stored.accessToken);
    return stored?.user ?? null;
  });
  const [isSessionBootstrapping, setIsSessionBootstrapping] = useState(true);
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [addedPolicySlugs, setAddedPolicySlugs] = useState<Set<string>>(new Set());
  const [savedSlugs, setSavedSlugs] = useState<Set<string>>(new Set());
  const savedSlugAdditionsRef = useRef<Set<string>>(new Set());
  const savedSlugRemovalsRef = useRef<Set<string>>(new Set());
  /* 이 탭에서 담았지만 서버 목록에서 아직 못 본 정책. 숙박 할인 지역 정책은 서버가 대표 정책으로 담아 끝내 안 보인다.
     서버 목록에 한 번 보이면 그때부터는 서버가 기준이다(일정을 지우면 빠진다). */
  const unconfirmedAddedRef = useRef<Set<string>>(new Set());

  function refreshSavedSlugsFromRemote(isCancelled?: () => boolean) {
    appDataApi
      .listSavedPolicies()
      .then((policies) => {
        if (isCancelled?.()) return;
        const next = new Set(policies.map((policy) => policy.slug));
        savedSlugRemovalsRef.current.forEach((slug) => next.delete(slug));
        savedSlugAdditionsRef.current.forEach((slug) => next.add(slug));
        setSavedSlugs(next);
      })
      .catch(() => {});
  }

  useEffect(() => {
    let cancelled = false;

    async function applyAuth(auth: AuthResponse) {
      if (cancelled) return;
      persistAuth(auth);
      setCurrentUser(auth.user);
      const nextProfile = await readRemoteProfile();
      if (cancelled) return;
      setProfile(nextProfile);
      refreshSavedSlugsFromRemote(() => cancelled);
    }

    async function verifyStoredSession() {
      try {
        const stored = readStoredAuth();
        if (!stored) {
          const refreshed = await refreshSessionOnce();
          if (refreshed) {
            await applyAuth(refreshed);
          } else if (!cancelled && !readStoredAuth()) {
            clearAuth();
          }
          return;
        }

        try {
          const user = await appDataApi.getCurrentUser();
          /* 낡은 토큰이면 위 요청이 401 을 맞고 client 가 조용히 재발급했을 수 있다.
             그때 `stored.accessToken` 을 다시 저장하면 방금 받은 새 토큰을 덮어쓴다. */
          const currentToken = readStoredAuth()?.accessToken ?? stored.accessToken;
          await applyAuth({ accessToken: currentToken, user });
        } catch {
          if (cancelled) return;
          const refreshed = await refreshSessionOnce();
          if (refreshed) {
            await applyAuth(refreshed);
            return;
          }
          if (cancelled) return;
          if (readStoredAuth()?.accessToken === stored.accessToken) {
            clearAuth();
            setCurrentUser(null);
          }
        }
      } finally {
        if (!cancelled) {
          setIsSessionBootstrapping(false);
        }
      }
    }

    setApiTokenRefresher(async () => {
      const auth = await appDataApi.refreshSession();
      persistAuth(auth);
      return auth.accessToken;
    });
    void verifyStoredSession();
    return () => {
      cancelled = true;
      setApiTokenRefresher(null);
    };
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      currentUser,
      isSessionBootstrapping,
      profile,
      addedPolicySlugs,
      login: async (request) => {
        const auth = await appDataApi.login(request);
        persistAuth(auth);
        setCurrentUser(auth.user);
        setProfile(await readRemoteProfile());
        refreshSavedSlugsFromRemote();
      },
      signup: async (request) => {
        const result = await appDataApi.requestSignupVerification(request);
        setSavedSlugs(new Set());
        return result;
      },
      verifySignup: async (token) => appDataApi.verifySignup({ token }),
      completeSignup: async (request) => {
        const auth = await appDataApi.completeSignup(request);
        persistAuth(auth);
        setCurrentUser(auth.user);
        setProfile(await readRemoteProfile());
        savedSlugAdditionsRef.current.clear();
        savedSlugRemovalsRef.current.clear();
        setSavedSlugs(new Set());
        return auth.user;
      },
      completeSocialSignup: async (request) => {
        const auth = await appDataApi.completeSocialSignup(request);
        persistAuth(auth);
        setCurrentUser(auth.user);
        setProfile(await readRemoteProfile());
        savedSlugAdditionsRef.current.clear();
        savedSlugRemovalsRef.current.clear();
        setSavedSlugs(new Set());
        return auth.user;
      },
      completeOAuthSession: async () => {
        const auth = await appDataApi.refreshSession();
        persistAuth(auth);
        setCurrentUser(auth.user);
        setProfile(await readRemoteProfile());
        refreshSavedSlugsFromRemote();
        return auth.user;
      },
      saveNickname: async (nickname) => {
        const user = await appDataApi.updateNickname({ nickname });
        const stored = readStoredAuth();
        if (stored) persistAuth({ accessToken: stored.accessToken, user });
        setCurrentUser(user);
        return user;
      },
      logout: async () => {
        try {
          await appDataApi.logout();
        } finally {
          clearAuth();
          setCurrentUser(null);
          setProfile(emptyProfile);
          savedSlugAdditionsRef.current.clear();
          savedSlugRemovalsRef.current.clear();
          setSavedSlugs(new Set());
          unconfirmedAddedRef.current.clear();
          setAddedPolicySlugs(new Set());
        }
      },
      updateProfile: (key, value) => {
        setProfile((current) => ({ ...current, [key]: value }));
      },
      saveProfile: async (profilePatch) => {
        const savedProfile = await appDataApi.updateProfile({ ...profile, ...profilePatch });
        setProfile(savedProfile);
        try {
          const user = await appDataApi.getCurrentUser();
          const stored = readStoredAuth();
          if (stored) persistAuth({ accessToken: stored.accessToken, user });
          setCurrentUser(user);
        } catch {
          // Profile persistence already succeeded; stale user metadata can refresh on the next session check.
        }
        return savedProfile;
      },
      skipProfileSetup: async () => {
        await appDataApi.skipProfileSetup();
        setProfile(await readRemoteProfile());
        try {
          const user = await appDataApi.getCurrentUser();
          const stored = readStoredAuth();
          if (stored) persistAuth({ accessToken: stored.accessToken, user });
          setCurrentUser(user);
        } catch {
          // Skip persistence already succeeded; stale user metadata can refresh later.
        }
      },
      addPolicy: (slug?: string) => {
        if (slug) {
          unconfirmedAddedRef.current.add(slug);
          setAddedPolicySlugs((prev) => new Set(prev).add(slug));
        }
      },
      removeAddedPolicy: (slug: string) => {
        unconfirmedAddedRef.current.delete(slug);
        setAddedPolicySlugs((prev) => {
          const next = new Set(prev);
          next.delete(slug);
          return next;
        });
      },
      isPolicyAdded: (slug: string) => addedPolicySlugs.has(slug),
      refreshAddedPolicies: () => {
        appDataApi
          .listAppliedPolicies()
          .then((policies) => {
            if (!readStoredAuth()) return; // 그사이 로그아웃했다
            const next = new Set(policies.map((policy) => policy.slug));
            unconfirmedAddedRef.current.forEach((slug) => {
              if (next.has(slug)) unconfirmedAddedRef.current.delete(slug);
              else next.add(slug);
            });
            setAddedPolicySlugs(next);
          })
          .catch(() => {});
      },
      savedSlugs,
      addSavedSlug: (slug: string) => {
        savedSlugRemovalsRef.current.delete(slug);
        savedSlugAdditionsRef.current.add(slug);
        setSavedSlugs((prev) => new Set(prev).add(slug));
      },
      removeSavedSlug: (slug: string) => {
        savedSlugAdditionsRef.current.delete(slug);
        savedSlugRemovalsRef.current.add(slug);
        setSavedSlugs((prev) => {
          const next = new Set(prev);
          next.delete(slug);
          return next;
        });
      },
    }),
    [addedPolicySlugs, currentUser, isSessionBootstrapping, profile, savedSlugs],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used within SessionProvider");
  return value;
}
