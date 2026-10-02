/* 홈 배너 사진(시안 v48). 위키미디어 공용에서 이용 조건을 확인한 사진만 쓴다 - 고른 기준·원본 주소·후보 전부는
   docs/photo-sourcing/2026-10-01-home-banner-photos.md, 다시 받기는 docs/photo-sourcing/tools/hero_photos.py --out-dir.
   열쇠는 장의 성격: region:<도>(지역 장) · theme:<refund|stay|partner|move>(마감 장의 혜택 종류, 전국 장은 move).
   열쇠에 사진이 없으면 그 장은 혜택 형태 색 바탕 그대로 - 어울리지 않는 사진보다 낫다.
   출처(사진 · 작가 · 라이선스)는 CC BY · CC BY-SA 의 조건이다. 사진 위마다 적지 않고 앱 전체 '사진 출처' 창(PhotoCredits.tsx)에
   모은다(시안 v53 · v54) - 라이선스 본문 · 원본 링크까지 둔다. 홈 배너 아래와 내 정보 메뉴에서 연다. */
import bukchonHanok from "../assets/login/bukchon-hanok.webp";
import gwanganBridge from "../assets/login/gwangan-bridge.webp";
import hahoeVillage from "../assets/login/hahoe-village.webp";
import hwaseongFortress from "../assets/login/hwaseong-fortress.webp";
import jeonjuHanokMaeul from "../assets/login/jeonju-hanok-maeul.webp";
import seongsanJeju from "../assets/login/seongsan-jeju.webp";
import seoraksanCableCar from "../assets/login/seoraksan-cable-car.webp";
import suncheonBayReeds from "../assets/login/suncheon-bay-reeds.webp";
import boseongGreenTea from "../assets/hero/boseong-green-tea.webp";
import gwangjangMarketJeon from "../assets/hero/gwangjang-market-jeon.webp";
import hwangnamguanHanokStay from "../assets/hero/hwangnamguan-hanok-stay.webp";
import jeonjuHanok from "../assets/hero/jeonju-hanok.webp";
import ktxSancheon from "../assets/hero/ktx-sancheon.webp";
import type { BenefitType } from "./benefitTile";

export type HeroPhoto = {
  src: string;
  subject: string;
  author: string;
  license: string;
  /** 라이선스 본문. 퍼블릭 도메인은 없다 */
  licenseUrl: string | null;
  /** 원본(위키미디어 공용 파일 페이지) */
  page: string;
  /** 로그인 사진만: 어느 지역 풍경인지(출처 창에 '서울 · 북촌 한옥마을') */
  region?: string;
};

const CC_BY_3 = "https://creativecommons.org/licenses/by/3.0/deed.ko";
const CC_BY_SA_3 = "https://creativecommons.org/licenses/by-sa/3.0/deed.ko";
const CC_BY_SA_4 = "https://creativecommons.org/licenses/by-sa/4.0/deed.ko";
const CC0 = "https://creativecommons.org/publicdomain/zero/1.0/deed.ko";
const COMMONS = "https://commons.wikimedia.org/wiki/File:";

export const HERO_PHOTOS: Readonly<Record<string, HeroPhoto>> = {
  "region:전남": {
    src: boseongGreenTea, subject: "보성 녹차밭", author: "Giuseppe Milo", license: "CC BY 3.0", licenseUrl: CC_BY_3,
    page: `${COMMONS}Boseong_Green_Tea_Field_South_Korea_Travel_Photography_(253061695).jpeg`,
  },
  "theme:refund": {
    src: jeonjuHanok, subject: "전주 한옥마을", author: "lumoplank", license: "CC0", licenseUrl: CC0,
    page: `${COMMONS}Jeonju-_Part_II_-_Jeonju3094.jpg`,
  },
  "theme:move": {
    src: ktxSancheon, subject: "KTX-산천", author: "Minseong Kim", license: "CC BY-SA 4.0", licenseUrl: CC_BY_SA_4,
    page: `${COMMONS}KTX-Sancheon.jpg`,
  },
  "theme:stay": {
    src: hwangnamguanHanokStay, subject: "경주 황남관 한옥 숙소", author: "Choi2451", license: "CC BY-SA 3.0", licenseUrl: CC_BY_SA_3,
    page: `${COMMONS}Hwangnamguan_Hotel_at_night.jpg`,
  },
  "theme:partner": {
    src: gwangjangMarketJeon, subject: "광장시장 전", author: "Bo Park(US Army)", license: "퍼블릭 도메인", licenseUrl: null,
    page: `${COMMONS}Korean_pancakes_and_pan-fried_foods_at_Gwangjang_Market.jpg`,
  },
};

/* 로그인 사진(시안 v54): 지역 8곳 풍경을 무작위로 시작해 6초마다 바꾼다. 출처 표시 의무가 없는 CC0 · 퍼블릭 도메인만 골라
   로그인 화면에는 출처를 적지 않는다 - '사진 출처' 창에만. 다시 받기는 docs/photo-sourcing/tools/login_photos.py --out-dir. */
export const LOGIN_PHOTOS: readonly HeroPhoto[] = [
  { region: "서울", src: bukchonHanok, subject: "북촌 한옥마을", author: "Bgag", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Bukchon_Hanok_Village_03.jpg` },
  { region: "경기", src: hwaseongFortress, subject: "수원 화성", author: "Bernard Gagnon", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Hwaseong_Fortress_01.jpg` },
  { region: "강원", src: seoraksanCableCar, subject: "설악산 케이블카", author: "Bernard Gagnon", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Seoraksan_Cable_Car_04.jpg` },
  { region: "전북", src: jeonjuHanokMaeul, subject: "전주 한옥마을", author: "Bernard Gagnon", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Jeonju_Hanok_Maeul_02.jpg` },
  { region: "전남", src: suncheonBayReeds, subject: "순천만 갈대밭", author: "Bandoche", license: "퍼블릭 도메인", licenseUrl: null, page: `${COMMONS}Panorama_of_Reed_fields_in_Suncheon_bay.jpg` },
  { region: "경북", src: hahoeVillage, subject: "안동 하회마을", author: "Bernard Gagnon", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Hahoe_Folk_Village_02.jpg` },
  { region: "부산", src: gwanganBridge, subject: "광안대교와 광안리", author: "lumoplank", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Gwangan_Bridge_and_Gwangalli_Beach_-_Gwangalli2721.jpg` },
  { region: "제주", src: seongsanJeju, subject: "성산일출봉 일대", author: "Bernard Gagnon", license: "CC0", licenseUrl: CC0, page: `${COMMONS}Seongsan,_Jeju_Island.jpg` },
];

/* 혜택 종류 → 사진 주제. 여행상품은 여행지 풍경(환급과 같은 주제), 기차·항공·자동차·배는 교통 */
export function heroThemeOf(kind: BenefitType): "refund" | "stay" | "partner" | "move" {
  if (kind === "stay" || kind === "partner" || kind === "refund") return kind;
  return kind === "trip" ? "refund" : "move";
}
