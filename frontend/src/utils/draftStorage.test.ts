import { beforeEach, describe, expect, it } from "vitest";
import { DRAFT_VERSION, clearDraft, createDraftKey, purgeStaleDrafts, readDraft, saveDraft } from "./draftStorage";

describe("draftStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("saves, reads, and clears a draft", () => {
    const key = createDraftKey("example");

    saveDraft(key, { label: "Cafe stop" });

    expect(readDraft<{ label: string }>(key)).toEqual({ label: "Cafe stop" });

    clearDraft(key);
    expect(readDraft(key)).toBeNull();
  });

  it("ignores expired drafts", () => {
    const key = createDraftKey("expired");
    window.localStorage.setItem(
      key,
      JSON.stringify({
        version: DRAFT_VERSION,
        savedAt: Date.now() - 10_000,
        value: { label: "Old draft" },
      }),
    );

    expect(readDraft(key, 1)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("ignores malformed draft payloads", () => {
    const key = createDraftKey("broken");
    window.localStorage.setItem(key, "{not-json");

    expect(readDraft(key)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("is on version 2 and ignores and removes a draft that version 1 wrote", () => {
    expect(DRAFT_VERSION).toBe(2);
    const key = createDraftKey("trip-place:55:edit:1");
    window.localStorage.setItem(
      key,
      JSON.stringify({ version: 1, savedAt: Date.now(), value: { placeId: "1", label: "카카오 예전 식당", meta: "음식점 · 부산 중구 카카오로 1" } }),
    );

    expect(readDraft(key)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });
});

describe("purgeStaleDrafts", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("removes every draft key that is not on the current version, including unreadable ones, and nothing else", () => {
    const old = { version: 1, savedAt: Date.now(), value: { label: "카카오 예전 식당", meta: "음식점 · 부산 중구 카카오로 1" } };
    // 이웃한 키 셋 - 지우면 색인이 당겨지므로 앞에서부터 지우면 하나를 건너뛴다
    for (const name of ["a", "b", "c"]) window.localStorage.setItem(createDraftKey(`trip-place:55:edit:${name}`), JSON.stringify(old));
    window.localStorage.setItem(createDraftKey("broken"), "{not-json");
    window.localStorage.setItem(createDraftKey("no-version"), JSON.stringify({ savedAt: Date.now(), value: {} }));
    const current = createDraftKey("trip-place:55:edit:9");
    saveDraft(current, { placeId: "9", time: "10:00" });
    window.localStorage.setItem("travel-hunter-production-auth", "keep");

    purgeStaleDrafts();

    const left = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index)).sort();
    expect(left).toEqual([current, "travel-hunter-production-auth"].sort());
    expect(readDraft(current)).toEqual({ placeId: "9", time: "10:00" });
  });

  it("does nothing when storage is unavailable", () => {
    expect(() => purgeStaleDrafts(null)).not.toThrow();
  });
});
