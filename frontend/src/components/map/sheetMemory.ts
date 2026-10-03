/* 목록 시트의 화면(scopeKey)마다 스크롤 자리와 여닫은 묶음. 휴대폰은 정책 상세가 다른 주소라 시트가 사라졌다 다시 생기고
   필터 창이 떠도 목록을 내린다 - 시트 안에만 두면 돌아올 때 목록이 맨 위 · 다 접힌 채가 됐다(10/3 사용자 지적). */
export const sheetMemory: {
  scrolls: Map<string, number>;
  opened: ReadonlySet<string>;
  shut: { scope: string; keys: ReadonlySet<string> };
} = { scrolls: new Map(), opened: new Set(), shut: { scope: "", keys: new Set() } };

/** 시험끼리 새지 않게 비운다 */
export function forgetSheetMemory() {
  sheetMemory.scrolls.clear();
  sheetMemory.opened = new Set();
  sheetMemory.shut = { scope: "", keys: new Set() };
}
