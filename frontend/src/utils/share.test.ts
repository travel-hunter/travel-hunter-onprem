import { describe, expect, it, vi } from "vitest";
import { shareLinkWithFallback } from "./share";

describe("shareLinkWithFallback", () => {
  it("uses clipboard fallback when share is unavailable", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);

    const method = await shareLinkWithFallback(
      {
        title: "Travel Hunter",
        text: "Travel Hunter link",
        url: "https://example.com/share",
      },
      {
        navigator: {
          share: undefined,
          clipboard: { writeText },
        } as never,
      },
    );

    expect(method).toBe("clipboard");
    expect(writeText).toHaveBeenCalledWith("https://example.com/share");
  });

  it("falls back to legacy copy when share and clipboard are unavailable", async () => {
    const execCommand = vi.fn().mockReturnValue(true);
    const documentLike = {
      body: document.body,
      createElement: document.createElement.bind(document),
      execCommand,
    };

    const method = await shareLinkWithFallback(
      {
        title: "Travel Hunter",
        text: "Travel Hunter link",
        url: "https://example.com/share",
      },
      {
        navigator: {
          share: undefined,
          clipboard: undefined,
        } as never,
        document: documentLike as never,
      },
    );

    expect(method).toBe("legacy");
    expect(execCommand).toHaveBeenCalledWith("copy");
  });
});
