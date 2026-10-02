import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { HERO_PHOTOS, LOGIN_PHOTOS, type HeroPhoto } from "./heroPhotos";
import "../styles/photo-credits.css";

/* 앱 전체 '사진 출처'(시안 v54). 홈 배너 아래 '사진 출처'와 내 정보 메뉴 '사진 출처'가 같은 창을 연다.
   open 을 단추의 onClick 에 걸고 dialog 를 그 화면 어디든 그리면 된다 - 닫으면 초점이 연 단추로 돌아간다. */
export function usePhotoCredits() {
  const [opener, setOpener] = useState<HTMLElement | null>(null);
  const open = (event: MouseEvent<HTMLElement>) => setOpener(event.currentTarget);
  const close = useCallback(() => {
    opener?.focus();
    setOpener(null);
  }, [opener]);
  return { open, dialog: opener ? createPortal(<PhotoCreditsDialog onClose={close} />, document.body) : null };
}

/* 사진마다 주제 · 작가 · 라이선스(본문 링크) · 원본 링크. 휴대폰은 아래에서, 넓은 화면은 가운데. Esc · 바깥 · 닫기로 닫는다 */
function PhotoCreditsDialog({ onClose }: { onClose: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeButton.current?.focus();
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="photo-credits" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div aria-labelledby="photo-credits-title" aria-modal="true" className="photo-credits-card" role="dialog">
        <div className="photo-credits-head">
          <h2 id="photo-credits-title">사진 출처</h2>
          <button onClick={onClose} ref={closeButton} type="button">
            닫기
          </button>
        </div>
        <CreditGroup photos={Object.values(HERO_PHOTOS)} title="홈 배너" />
        <CreditGroup photos={LOGIN_PHOTOS} title="로그인 화면" />
        <p className="photo-credits-note">
          위키미디어 공용 사진입니다. CC BY · CC BY-SA 사진은 저작자와 라이선스를 밝히는 것이 이용 조건이고, CC0 · 퍼블릭 도메인
          사진은 의무는 없지만 함께 적습니다. 관광공사 사진(시군 · 정책)은 사진과 함께 출처를 적습니다.
        </p>
      </div>
    </div>
  );
}

function CreditGroup({ title, photos }: { title: string; photos: readonly HeroPhoto[] }) {
  return (
    <section aria-label={title} className="photo-credits-group">
      <h3>{title}</h3>
      <ul className="photo-credits-list">
        {photos.map((photo) => (
          <li key={photo.src}>
            <img alt="" loading="lazy" src={photo.src} />
            <div>
              <b>{photo.region ? `${photo.region} · ${photo.subject}` : photo.subject}</b>
              <span>
                {photo.author} ·{" "}
                {photo.licenseUrl ? (
                  <a href={photo.licenseUrl} rel="noreferrer noopener" target="_blank">
                    {photo.license}
                  </a>
                ) : (
                  photo.license
                )}
              </span>
              <a href={photo.page} rel="noreferrer noopener" target="_blank">
                원본 보기(위키미디어 공용)
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
