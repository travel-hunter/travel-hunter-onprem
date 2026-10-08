import { useState } from "react";
import { mediaUrl } from "../../api";
import { photoCredit } from "./placeAdd/publicPlaceText";

/* 공공데이터(한국관광공사) 사진 한 장과 출처 칩. url 이 비면 아무것도 그리지 않는다.
   사진이 죽으면 출처 글도 함께 숨는다 - 사진 없이 출처만 남지 않게. 다른 url 이 오면 다시 시도한다 */
export function PlacePhoto({
  url,
  license,
  alt,
  compact = false,
}: {
  url?: string | null;
  license?: string | null;
  alt: string;
  compact?: boolean;
}) {
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);
  if (!url || brokenUrl === url) return null;
  return (
    <span className={compact ? "place-photo place-photo--compact" : "place-photo"}>
      <img alt={alt} loading="lazy" onError={() => setBrokenUrl(url)} src={mediaUrl(url)} />
      <span className="place-photo-credit">{photoCredit(license)}</span>
    </span>
  );
}
