import type { BrowseFilter } from "./policyBrowse";

/* 사람이 치는 말을 이름 · 글에 맞춰 보는 규칙(10/3 사용자 조사) - 정책 탭 검색 칸 · 홈 검색 · 글 검색('…모두 보기') · 위치로 찾기가
   같이 쓴다. 띄어쓰기는 무시하고('반 값' = 반값), 여러 낱말이면 낱말마다 본다. 일상 별칭과 초성(ㅂㅅ)은 이름(지역 · 시군 · 사업)에만
   붙인다 - 정책 본문에 초성을 맞추면 엉뚱한 것이 너무 많이 걸린다. */
export const squash = (value: string) => value.toLocaleLowerCase("ko-KR").replace(/\s+/g, "");

/** 찾을 말의 낱말들(띄어쓰기로 나누고 같은 것은 하나로). 낱말이 여럿이면 붙인 말도 하나 더 - '숙박 세일'이 '숙박세일'에도 맞게 */
export function searchWords(query: string): string[] {
  const words = query.toLocaleLowerCase("ko-KR").split(/\s+/).filter(Boolean);
  const out = new Set(words);
  if (words.length > 1) out.add(words.join(""));
  return Array.from(out);
}

const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
/** 초성만 친 낱말(두 자 이상) */
export const isChoseong = (word: string) => word.length >= 2 && /^[ㄱ-ㅎ]+$/.test(word);
export function choseongOf(value: string) {
  let out = "";
  for (const char of value) {
    const code = char.charCodeAt(0) - 0xac00;
    if (code >= 0 && code < 11172) out += CHO[Math.floor(code / 588)];
  }
  return out;
}

/** 이름이 낱말을 품는가 - 띄어쓰기 무시. 초성만 친 낱말은 이름 앞부분의 초성으로('ㅂㅅ' = 부산 · 보성, 서울특별시의 '특별시'는 아니다) */
export function nameHas(name: string, word: string) {
  if (!word) return false;
  return isChoseong(word) ? choseongOf(name).startsWith(word) : squash(name).includes(squash(word));
}

/* 낱말이 여럿일 때 이름 찾기에서 빼는 흔한 말 - 'KTX 할인'의 '할인'이 '…할인' 사업을 다 끌어왔다. 한 낱말로만 치면 그대로 찾는다 */
const GENERIC_WORDS = new Set(["할인", "혜택", "지원", "여행", "쿠폰", "이벤트", "정보", "추천"]);

/** 이름(지역 · 시군 · 사업 · 장소)에 맞춰 볼 낱말 - 낱말이 여럿이면 한 자 낱말과 흔한 말은 뺀다(붙인 말은 남긴다) */
export function nameWords(query: string, keep: (word: string) => boolean = () => false): string[] {
  const words = searchWords(query);
  if (words.length === 1) return words;
  const joined = words[words.length - 1];
  return words.filter((word) => word === joined || keep(word) || (word.length >= 2 && !GENERIC_WORDS.has(word)));
}

/** 표에서 그 낱말의 값 - 자기 키만 본다. 'constructor' · '__proto__'를 치면 Object 의 것이 나와 화면이 통째로 멈췄다(10/3 리뷰) */
function own<T>(table: Readonly<Record<string, T>>, key: string): T | undefined {
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : undefined;
}

/* 일상에서 부르는 지역 이름 → 지도 도(짧은 이름) */
const REGION_WORDS: Readonly<Record<string, readonly string[]>> = {
  강원도: ["강원"], 경기도: ["경기"], 제주도: ["제주"],
  충청도: ["충북", "충남"], 충청: ["충북", "충남"], 충청북도: ["충북"], 충청남도: ["충남"],
  전라도: ["전북", "전남"], 전라: ["전북", "전남"], 전라북도: ["전북"], 전라남도: ["전남"],
  경상도: ["경북", "경남"], 경상: ["경북", "경남"], 경상북도: ["경북"], 경상남도: ["경남"],
  수도권: ["서울", "경기", "인천"], 호남: ["광주", "전북", "전남"], 영남: ["부산", "대구", "울산", "경북", "경남"],
  seoul: ["서울"], busan: ["부산"], incheon: ["인천"], daegu: ["대구"], gwangju: ["광주"], daejeon: ["대전"],
  ulsan: ["울산"], sejong: ["세종"], gyeonggi: ["경기"], gangwon: ["강원"], jeju: ["제주"],
};

/** 낱말이 가리키는 지도 도들('수도권' → 서울 · 경기 · 인천) */
export function regionsOfWord(word: string): readonly string[] {
  return own(REGION_WORDS, squash(word)) ?? [];
}

/* 혜택 형태를 가리키는 말 → 위 칩. 두 자 이상은 낱말 안에 들어 있어도(숙박할인 → 숙박), 한 자는 낱말이 그것일 때만 */
const FILTER_WORDS: ReadonlyArray<readonly [string, BrowseFilter]> = [
  ["숙박", "stay"], ["숙소", "stay"], ["호텔", "stay"], ["펜션", "stay"], ["민박", "stay"], ["리조트", "stay"], ["게스트하우스", "stay"],
  ["환급", "refund"], ["페이백", "refund"], ["캐시백", "refund"],
  ["제휴", "partner"], ["가맹점", "partner"],
  ["교통", "move"], ["기차", "move"], ["열차", "move"], ["철도", "move"], ["ktx", "move"], ["srt", "move"], ["itx", "move"],
  ["렌터카", "move"], ["렌트카", "move"], ["항공", "move"], ["비행기", "move"], ["여객선", "move"], ["버스", "move"], ["배", "move"],
];
export function filterOfWord(word: string): BrowseFilter | null {
  const w = squash(word);
  for (const [alias, key] of FILTER_WORDS) if (alias.length >= 2 ? w.includes(alias) : w === alias) return key;
  return null;
}

/* 글 검색에서 낱말 대신 찾아볼 말 - 정책 글은 '숙박' · '열차' · '강원'처럼 적는다 */
const TEXT_WORDS: Readonly<Record<string, readonly string[]>> = {
  숙소: ["숙박"], 호텔: ["숙박"], 펜션: ["숙박"], 렌트카: ["렌터카"], 비행기: ["항공"],
  기차: ["열차", "철도", "코레일"], ktx: ["열차", "철도", "코레일"], srt: ["열차", "철도"],
  강원도: ["강원"], 제주도: ["제주"], 경기도: ["경기"], 수도권: ["서울", "경기", "인천"],
};

/** 글(정책 본문 등)이 찾을 말에 맞는가 - 붙여서 맞거나, 낱말이 모두(별칭 포함) 들어 있어야 한다. 띄어쓰기 무시 */
export function textMatches(text: string, query: string) {
  const words = query.toLocaleLowerCase("ko-KR").split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = squash(text);
  if (hay.includes(words.join(""))) return true;
  return words.every((word) => hay.includes(word) || (own(TEXT_WORDS, word) ?? []).some((alt) => hay.includes(alt)));
}
