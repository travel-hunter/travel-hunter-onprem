import { describe, expect, it } from "vitest";
import { BENEFIT_TYPES, type BenefitType } from "./benefitTile";
import { HERO_PHOTOS, heroCredit, heroThemeOf } from "./heroPhotos";

describe("home banner photos", () => {
  it("has a photo with a credit for every benefit theme the deadline slide can ask for", () => {
    const kinds = Object.keys(BENEFIT_TYPES).filter((kind) => kind !== "nation") as BenefitType[];
    for (const kind of kinds) {
      const photo = HERO_PHOTOS[`theme:${heroThemeOf(kind)}`];
      expect(photo, kind).toBeDefined();
      // 출처(사진 · 작가 · 라이선스)는 CC BY · CC BY-SA 조건 - 세 조각이 다 있어야 한다
      expect(heroCredit(photo).split(" · "), kind).toHaveLength(3);
    }
    for (const photo of Object.values(HERO_PHOTOS)) {
      // CC 는 라이선스 본문 링크까지, 원본은 위키미디어 공용 파일 페이지
      expect(Boolean(photo.licenseUrl), photo.subject).toBe(photo.license.startsWith("CC"));
      expect(photo.page.startsWith("https://commons.wikimedia.org/wiki/File:"), photo.subject).toBe(true);
    }
    expect(heroThemeOf("stay")).toBe("stay");
    expect(heroThemeOf("trip")).toBe("refund");
    expect(heroThemeOf("ship")).toBe("move");
  });
});
