const DRAFT_STORAGE_PREFIX = "travel-hunter:draft:";
const DRAFT_VERSION = 1;
const DEFAULT_DRAFT_TTL_MS = 24 * 60 * 60 * 1000;

type StoredDraft<T> = {
  version: number;
  savedAt: number;
  value: T;
};

export function createDraftKey(scope: string): string {
  return `${DRAFT_STORAGE_PREFIX}${scope}`;
}

export function readDraft<T>(key: string, ttlMs = DEFAULT_DRAFT_TTL_MS): T | null {
  const storage = getDraftStorage();
  if (!storage) return null;

  try {
    const rawValue = storage.getItem(key);
    if (!rawValue) return null;
    const parsed = JSON.parse(rawValue) as Partial<StoredDraft<T>>;
    if (parsed.version !== DRAFT_VERSION || typeof parsed.savedAt !== "number" || !("value" in parsed)) {
      storage.removeItem(key);
      return null;
    }
    if (Date.now() - parsed.savedAt > ttlMs) {
      storage.removeItem(key);
      return null;
    }
    return parsed.value as T;
  } catch {
    try {
      storage.removeItem(key);
    } catch {
      // Ignore unavailable storage.
    }
    return null;
  }
}

export function saveDraft<T>(key: string, value: T): void {
  const storage = getDraftStorage();
  if (!storage) return;

  try {
    const draft: StoredDraft<T> = {
      version: DRAFT_VERSION,
      savedAt: Date.now(),
      value,
    };
    storage.setItem(key, JSON.stringify(draft));
  } catch {
    // Draft persistence is best-effort and must not block form usage.
  }
}

export function clearDraft(key: string): void {
  const storage = getDraftStorage();
  if (!storage) return;

  try {
    storage.removeItem(key);
  } catch {
    // Ignore unavailable storage.
  }
}

function getDraftStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
