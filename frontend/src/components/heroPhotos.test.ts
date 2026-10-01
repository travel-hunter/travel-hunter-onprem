import { describe, expect, it } from "vitest";
import { BENEFIT_TYPES, type BenefitType } from "./benefitTile";
import { HERO_PHOTOS, heroThemeOf } from "./heroPhotos";

describe("home banner photos", () => {
  it("has a photo with a credit for every benefit theme the deadline slide can ask for", () => {
    const kinds = Object.keys(BENEFIT_TYPES).filter((kind) => kind !== "nation") as BenefitType[];
    for (const kind of kinds) {
      const photo = HERO_PHOTOS[`theme:${heroThemeOf(kind)}`];
      expect(photo, kind).toBeDefined();
      // 출처(사진 · 작가 · 라이선스)는 CC BY · CC BY-SA 조건 - 세 조각이 다 있어야 한다
      expect(photo.credit.split(" · "), kind).toHaveLength(3);
    }
    expect(heroThemeOf("stay")).toBe("stay");
    expect(heroThemeOf("trip")).toBe("refund");
    expect(heroThemeOf("ship")).toBe("move");
  });
});
