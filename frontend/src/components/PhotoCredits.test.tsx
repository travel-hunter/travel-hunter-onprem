import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HERO_PHOTOS, LOGIN_PHOTOS } from "./heroPhotos";
import { usePhotoCredits } from "./PhotoCredits";

function Opener() {
  const credits = usePhotoCredits();
  return (
    <>
      <button onClick={credits.open} type="button">
        사진 출처
      </button>
      {credits.dialog}
    </>
  );
}

describe("앱 전체 사진 출처 창", () => {
  it("lists the banner and login photos, the tourism photos' license types, and closes back to the opener", () => {
    render(<Opener />);
    const open = screen.getByRole("button", { name: "사진 출처" });
    fireEvent.click(open);

    const dialog = screen.getByRole("dialog", { name: "사진 출처" });
    const banner = within(dialog).getByRole("region", { name: "홈 배너" });
    const login = within(dialog).getByRole("region", { name: "로그인 화면" });
    expect(banner.querySelectorAll("li")).toHaveLength(Object.keys(HERO_PHOTOS).length);
    expect(login.querySelectorAll("li")).toHaveLength(LOGIN_PHOTOS.length);
    expect(login).toHaveTextContent("서울 · 북촌 한옥마을");
    expect(within(login).getAllByRole("link", { name: "CC0" })[0]).toHaveAttribute("href", LOGIN_PHOTOS[0].licenseUrl);
    expect(within(login).getAllByRole("link", { name: "원본 보기(위키미디어 공용)" })[0]).toHaveAttribute("href", LOGIN_PHOTOS[0].page);
    expect(login).toHaveTextContent("Bandoche · 퍼블릭 도메인"); // 라이선스 본문이 없으면 글자만
    // 관광공사 사진은 사진 위에 '사진: 한국관광공사' 만 - 공공누리 유형은 이 창에 모은다
    const kto = within(dialog).getByRole("region", { name: "한국관광공사 사진" });
    expect(kto).toHaveTextContent("공공누리 제1유형");
    expect(kto).toHaveTextContent("제3유형(변경금지)");
    expect(within(kto).getByRole("link", { name: "공공누리 이용조건" })).toHaveAttribute("href", "https://www.kogl.or.kr/info/license.do");
    expect(screen.getByRole("button", { name: "닫기" })).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(open).toHaveFocus();
  });
});
