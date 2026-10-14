import { mediaUrl } from "../api/client";
import type { PolicyPhoto } from "../api/types";

/**
 * 정책 상세 hero용 지역 사진 레이어.
 *
 * 사진은 그라디언트 위에 얹는다. URL이 죽으면 onError 로 알리고,
 * 부르는 쪽(PolicyDetailHero)이 사진을 빼고 시도 사진이나 그림 칸을 깐다.
 * 공공누리 1유형 출처표시는 사진과 항상 붙어 다니는 크레딧 칩으로 렌더한다.
 */
export function PolicyHeroPhoto({ photo, onError }: { photo: PolicyPhoto; onError: () => void }) {
  return (
    <>
      <img
        alt={photo.alt}
        className="policy-hero-photo"
        onError={onError}
        src={mediaUrl(photo.imageUrl)}
      />
      <span className="policy-hero-credit">{photo.attribution}</span>
    </>
  );
}
