const DRAFT_STORAGE_PREFIX = "travel-hunter:draft:";
/** 판을 올리면 예전 판 초안은 읽지 않고(readDraft) 앱을 켤 때 지운다(purgeStaleDrafts).
    2판 = 장소 수정 초안에서 카카오 이름 · 메모(1판 label · meta)를 뺀 모양(설계 2026-10-03 3절 6번) */
export const DRAFT_VERSION = 2;
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

/** 앱을 켤 때 한 번 - 현재 판이 아닌(또는 읽을 수 없는) 초안 키를 지운다. 1판 장소 수정 초안에는 카카오 이름 · 메모가 들어 있을 수 있다.
    지우면 색인이 당겨지므로 뒤에서부터 돈다. 저장소를 못 쓰면 조용히 넘어간다 - readDraft 가 예전 판을 읽지 않는 것으로 충분하다 */
export function purgeStaleDrafts(storage: Storage | null = getDraftStorage()): void {
  if (!storage) return;
  try {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (!key?.startsWith(DRAFT_STORAGE_PREFIX)) continue;
      if (draftVersionOf(storage.getItem(key)) !== DRAFT_VERSION) storage.removeItem(key);
    }
  } catch {
    // 초안 정리는 최선만 한다.
  }
}

function draftVersionOf(rawValue: string | null): unknown {
  try {
    return (JSON.parse(rawValue ?? "null") as { version?: unknown } | null)?.version;
  } catch {
    return undefined;
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
