import { describe, expect, it } from "vitest";
import { buildPreviewAllowedHosts } from "../../../vite.config";

describe("Vite preview host configuration", () => {
  it("allows the configured administrator subdomain", () => {
    expect(
      buildPreviewAllowedHosts({
        STAGING_DOMAIN: "dev.travel-hunter.co.kr",
        ADMIN_DOMAIN: "admin.travel-hunter.co.kr",
      })
    ).toContain("admin.travel-hunter.co.kr");
  });
});