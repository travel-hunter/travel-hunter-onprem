import { describe, expect, it } from "vitest";
import { BENEFIT_TYPES, type BenefitType } from "./benefitTile";
import { HERO_PHOTOS, heroThemeOf, LOGIN_PHOTOS } from "./heroPhotos";

describe("home banner photos", () => {
  it("has a photo with a credit for every benefit theme the deadline slide can ask for", () => {
    const kinds = Object.keys(BENEFIT_TYPES).filter((kind) => kind !== "nation") as BenefitType[];
    for (const kind of kinds) {
      const photo = HERO_PHOTOS[`theme:${heroThemeOf(kind)}`];
      expect(photo, kind).toBeDefined();
    }
    // 출처(사진 · 작가 · 라이선스)는 CC BY · CC BY-SA 조건 - '사진 출처' 창이 세 조각을 다 적는다
    for (const photo of [...Object.values(HERO_PHOTOS), ...LOGIN_PHOTOS]) {
      expect([photo.subject, photo.author, photo.license].every(Boolean), photo.subject).toBe(true);
      // CC 는 라이선스 본문 링크까지, 원본은 위키미디어 공용 파일 페이지
      expect(Boolean(photo.licenseUrl), photo.subject).toBe(photo.license.startsWith("CC"));
      expect(photo.page.startsWith("https://commons.wikimedia.org/wiki/File:"), photo.subject).toBe(true);
    }
    expect(heroThemeOf("stay")).toBe("stay");
    expect(heroThemeOf("trip")).toBe("refund");
    expect(heroThemeOf("ship")).toBe("move");
  });

  it("rotates the login screen through regional photos that need no credit on the photo", () => {
    // 로그인 화면은 사진 위에 출처를 적지 않는다 - 출처 표시 의무가 없는 CC0 · 퍼블릭 도메인만(시안 v54)
    expect(LOGIN_PHOTOS).toHaveLength(8);
    expect(LOGIN_PHOTOS.every((photo) => photo.license === "CC0" || photo.license === "퍼블릭 도메인")).toBe(true);
    expect(new Set(LOGIN_PHOTOS.map((photo) => photo.region)).size).toBe(8);
  });
});
