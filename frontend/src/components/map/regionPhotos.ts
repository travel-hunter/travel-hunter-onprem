/* 지역 카드 배경 사진. 원본(관광명소 PNG 2~3MB)을 560x420 WebP 로 줄여 담았다 -
   카드가 모바일에서 176x132(4:3)라 3배 화면까지 이 크기면 충분하다.
   import 로 들고 와야 Vite 가 해시를 붙여 캐시를 관리한다 - public/ 에 두면 그게 안 된다. */
import chungbuk from "../../assets/regions/chungbuk.webp";
import chungnam from "../../assets/regions/chungnam.webp";
import daegu from "../../assets/regions/daegu.webp";
import daejeon from "../../assets/regions/daejeon.webp";
import gangwon from "../../assets/regions/gangwon.webp";
import gwangju from "../../assets/regions/gwangju.webp";
import gyeonggi from "../../assets/regions/gyeonggi.webp";
import gyeongbuk from "../../assets/regions/gyeongbuk.webp";
import gyeongnam from "../../assets/regions/gyeongnam.webp";
import incheon from "../../assets/regions/incheon.webp";
import jeju from "../../assets/regions/jeju.webp";
import jeonbuk from "../../assets/regions/jeonbuk.webp";
import jeonnam from "../../assets/regions/jeonnam.webp";
import busan from "../../assets/regions/busan.webp";
import sejong from "../../assets/regions/sejong.webp";
import seoul from "../../assets/regions/seoul.webp";
import ulsan from "../../assets/regions/ulsan.webp";

/* 표에 없는 지역은 사진 없이 글자 카드로 나온다. */
export const REGION_PHOTOS: Record<string, string> = {
  서울: seoul,
  인천: incheon,
  경기: gyeonggi,
  강원: gangwon,
  충북: chungbuk,
  충남: chungnam,
  세종: sejong,
  대전: daejeon,
  전북: jeonbuk,
  전남: jeonnam,
  광주: gwangju,
  대구: daegu,
  경북: gyeongbuk,
  울산: ulsan,
  경남: gyeongnam,
  부산: busan,
  제주: jeju,
};
