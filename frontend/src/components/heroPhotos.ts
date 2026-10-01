/* 홈 배너 사진(시안 v48). 위키미디어 공용에서 이용 조건을 확인한 사진만 쓴다 - 고른 기준·원본 주소·후보 전부는
   docs/photo-sourcing/2026-10-01-home-banner-photos.md, 다시 받기는 docs/photo-sourcing/tools/hero_photos.py --out-dir.
   열쇠는 장의 성격: region:<도>(지역 장) · theme:<refund|stay|partner|move>(마감 장의 혜택 종류, 전국 장은 move).
   열쇠에 사진이 없으면 그 장은 혜택 형태 색 바탕 그대로 - 어울리지 않는 사진보다 낫다.
   출처 문구(사진 · 작가 · 라이선스)는 CC BY · CC BY-SA 의 조건이라 화면에서 빼지 않는다. */
import boseongGreenTea from "../assets/hero/boseong-green-tea.webp";
import gwangjangMarketJeon from "../assets/hero/gwangjang-market-jeon.webp";
import hwangnamguanHanokStay from "../assets/hero/hwangnamguan-hanok-stay.webp";
import jeonjuHanok from "../assets/hero/jeonju-hanok.webp";
import ktxSancheon from "../assets/hero/ktx-sancheon.webp";
import type { BenefitType } from "./benefitTile";

export type HeroPhoto = { src: string; credit: string };

export const HERO_PHOTOS: Readonly<Record<string, HeroPhoto>> = {
  "region:전남": { src: boseongGreenTea, credit: "보성 녹차밭 · Giuseppe Milo · CC BY 3.0" },
  "theme:refund": { src: jeonjuHanok, credit: "전주 한옥마을 · lumoplank · CC0" },
  "theme:move": { src: ktxSancheon, credit: "KTX-산천 · Minseong Kim · CC BY-SA 4.0" },
  "theme:stay": { src: hwangnamguanHanokStay, credit: "경주 황남관 한옥 숙소 · Choi2451 · CC BY-SA 3.0" },
  "theme:partner": { src: gwangjangMarketJeon, credit: "광장시장 전 · Bo Park(US Army) · 퍼블릭 도메인" },
};

/* 혜택 종류 → 사진 주제. 여행상품은 여행지 풍경(환급과 같은 주제), 기차·항공·자동차·배는 교통 */
export function heroThemeOf(kind: BenefitType): "refund" | "stay" | "partner" | "move" {
  if (kind === "stay" || kind === "partner" || kind === "refund") return kind;
  return kind === "trip" ? "refund" : "move";
}
