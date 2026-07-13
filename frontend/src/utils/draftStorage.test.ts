import { beforeEach, describe, expect, it } from "vitest";
import { clearDraft, createDraftKey, readDraft, saveDraft } from "./draftStorage";

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
        version: 1,
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
});
