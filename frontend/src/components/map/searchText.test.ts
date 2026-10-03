import { describe, expect, it } from "vitest";
import { choseongOf, filterOfWord, nameHas, nameWords, searchWords, textMatches } from "./searchText";

describe("사람이 치는 말", () => {
  it("splits words and also tries them stuck together", () => {
    expect(searchWords("숙박 세일")).toEqual(["숙박", "세일", "숙박세일"]);
    expect(searchWords("  여수  ")).toEqual(["여수"]);
    // 이름 찾기에서는 낱말이 여럿이면 흔한 말 · 한 자 낱말을 뺀다
    expect(nameWords("KTX 할인")).toEqual(["ktx", "ktx할인"]);
    expect(nameWords("할인")).toEqual(["할인"]);
    expect(nameWords("완도 의")).toEqual(["완도", "완도의"]);
  });

  it("matches names ignoring spaces and by initial consonants", () => {
    expect(nameHas("대한민국 반값여행 지원", "반 값")).toBe(true);
    expect(nameHas("부산영도", "영도")).toBe(true);
    expect(choseongOf("부산광역시")).toBe("ㅂㅅㄱㅇㅅ");
    expect(nameHas("부산", "ㅂㅅ")).toBe(true);
    expect(nameHas("여수", "ㅂㅅ")).toBe(false);
    expect(nameHas("부산", "ㅂ")).toBe(false);   // 초성 한 자는 너무 많이 걸린다 - 이름에 'ㅂ' 글자가 있어야 맞는다
    expect(nameHas("서울특별시", "ㅂㅅ")).toBe(false);   // 초성은 이름 앞부분만 - '특별시'에 걸리지 않게
  });

  it("reads everyday words for kinds of benefits", () => {
    expect(filterOfWord("숙소")).toBe("stay");
    expect(filterOfWord("숙박할인")).toBe("stay");
    expect(filterOfWord("KTX")).toBe("move");
    expect(filterOfWord("배")).toBe("move");
    expect(filterOfWord("배낭")).toBeNull();   // 한 자 별칭은 그 낱말일 때만
    expect(filterOfWord("가족")).toBeNull();
  });

  it("matches text when every word (or its everyday alias) is in it", () => {
    const text = "[여수] 대한민국 숙박세일 페스타 전남 숙박 할인";
    expect(textMatches(text, "여수 숙박세일")).toBe(true);
    expect(textMatches(text, "숙박 세일")).toBe(true);
    expect(textMatches(text, "여수 숙소")).toBe(true);
    expect(textMatches(text, "여수 기차")).toBe(false);
    expect(textMatches(text, "")).toBe(true);
  });
});
