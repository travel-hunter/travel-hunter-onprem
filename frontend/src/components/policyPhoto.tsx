import { useState } from "react";

import { mediaUrl } from "../api/client";
import type { PolicyPhoto } from "../api/types";

/**
 * 정책 상세 hero용 지역 사진 레이어.
 *
 * 사진은 기존 그라디언트를 대체하지 않고 위에 얹는다. URL이 죽으면
 * onError로 스스로 숨어서 아래 그라디언트+이모지가 그대로 드러난다.
 * 공공누리 1유형 출처표시는 사진과 항상 붙어 다니는 크레딧 칩으로 렌더한다.
 */
export function PolicyHeroPhoto({ photo }: { photo: PolicyPhoto }) {
  const [isBroken, setIsBroken] = useState(false);
  if (isBroken) return null;
  return (
    <>
      <img
        alt={photo.alt}
        className="policy-hero-photo"
        loading="lazy"
        onError={() => setIsBroken(true)}
        src={mediaUrl(photo.imageUrl)}
      />
      <span className="policy-hero-credit">{photo.attribution}</span>
    </>
  );
}
