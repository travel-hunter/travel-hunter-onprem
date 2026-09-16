# Codex 인계 — 장소 카드 하단 시트 (feature/itinerary-place-sheet)

작성: Claude, 2026-09-16
워크트리: `.superpowers/worktrees/itinerary-place-sheet` · 브랜치 `feature/itinerary-place-sheet` · base `develop@7456708`
스펙: `docs/superpowers/specs/2026-09-16-itinerary-card-management-design.md` (§브랜치 ①)
플랜: `docs/superpowers/plans/2026-09-16-itinerary-place-sheet.md`

## 상태

- 구현 완료, **미커밋**(사용자 승인 대기). 푸시·PR 은 Codex.
- 변경 파일 5개: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`, `frontend/src/app/__tests__/place-edit.test.tsx`, `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/src/app/__tests__/trips-list.test.tsx` (+ 스펙·플랜·이 문서).
- 백엔드·API 계약·골든 JSON 변경 없음(API 변경 없음).

## 무엇이 바뀌었나

| QA | 변경 |
|---|---|
| 3·5 카드 탭 상세/수정 | 카드 본문 클릭 + sr-only 버튼 `"{장소명} 상세 열기"` → 편집 하단 시트. 카드 하단 수정·삭제 버튼 제거. dnd-kit 활성화 제약(마우스 8px/터치 800ms) + `wasDraggedRef` 로 드래그와 분리 |
| 상세 통합 | `PlaceDetailDialog` 삭제 → 시트 상단 `PlaceSheetDetail`(분류·시간·주소·좌표·카카오맵 링크). 지도 핀 "상세 보기" 도 같은 시트 |
| 보기 권한 | 시트 `readOnly`: 제목 "장소 상세", 입력 비활성, Day 칩·저장·삭제 없음 |
| 삭제 | 시트 하단 삭제 → 기존 ConfirmDialog → 성공 시 시트 닫힘 |
| Day 이동 | Day 칩 선택 즉시 `PATCH /places/{id}/move`. 저장은 `PATCH /places` 단독(시간 변경 시 같은 Day 재정렬, 실패하면 토스트 "장소 정보는 저장했지만 순서를 맞추지 못했어요."). 이전의 이동 실패 묵살 제거. 409 시 시트 닫고 새로고침. 이동 중엔 저장·삭제·닫기 비활성 |
| 2 이동 피드백 | 이동 성공 시 목적지 카드 `.just-moved` 1.6초 링 플래시 + `scrollIntoView`. 시트가 열려 있으면 닫힐 때로 미룸. `prefers-reduced-motion` 존중 |

## 검증

- `npx vitest run` 33 files / **400 passed**, `npm run test:mojibake` clean, `npx tsc --noEmit` clean (워크트리 frontend, 2026-09-16).
- `git diff --stat` == `git diff --ignore-space-at-eol --stat` → 줄끝 오염 없음.
- e2e(`frontend/e2e-backend`) **미실행**. grep 상 이 브랜치가 건드린 버튼을 누르는 spec 없음.
- 리뷰: Task 별 리뷰 5회 + 전체 브랜치 리뷰 1회 + 수정 1회 재리뷰. 잔여 minor 는 아래.

## 5173 수동 확인 (사용자)

1. 모바일 폭(390px): 카드 탭 → 시트. 길게 눌러 드래그 → 시트 안 열림.
2. 데스크톱: 클릭 → 시트. 8px 이상 끌기 → 드래그만(드롭 후 시트가 열리면 안 됨).
3. 시트 Day 칩 → 카드가 그 Day 로 이동, 칩 선택 상태 갱신. 시트 닫으면 목적지 카드가 플래시+스크롤.
4. 시트에서 장소명 수정 → 저장 → 네트워크 탭에 `move` 호출 없음.
5. 시트 삭제 → 확인 → 카드 사라지고 시트 닫힘.
6. 보기 권한 계정: 카드 탭 → "장소 상세" 읽기 전용.
7. 지도 뷰 → 핀 → 상세 보기 → 같은 시트.
8. 카드에 수정·삭제 버튼 없음. 추천 미리보기 카드는 이전과 동일.
9. **390px 에서 시트를 연 채 타임라인이 위에 보이는가.** 리뷰어 계산상 남는 공간 ~90-125px 이라 헤더/Day 스트립만 보일 가능성이 높다. 그러면 `PlaceSheetDetail` 을 접이식(`<details>`)으로 바꾸는 후속 결정 필요.
10. Tab 키로 카드 진입 → "{장소명} 상세 열기" 버튼이 포커스 시 보이는가 → Enter 로 시트.

## 잔여 minor (머지 차단 아님)

- 같은 카드를 1.6초 안에 두 번 옮기면 플래시 애니메이션이 재시작되지 않음.
- 드래그 이동 실패 토스트는 자동으로 사라지지 않음(기존 동작).
- `place-edit.test.tsx` 의 `scrollIntoView` 폴리필은 호출부의 `?.` 덕에 없어도 되는 중복.
- 409 시트 닫힘 / 재정렬 실패 토스트 / 이동 중 저장 비활성 — 직접 테스트 없음(수동 3·4 로 확인).

## Codex 가 할 일

1. 사용자 커밋 승인 후(또는 Claude 가 커밋한 뒤) `git push -u origin feature/itinerary-place-sheet`.
2. PR → `develop`. 본문에 위 표와 수동 확인 결과, e2e 미실행 명시.
3. 후속 브랜치 순서: ② `feature/itinerary-edit-mode`(편집 토글·전체 Day 적층·배치 삭제 API) → ③ `feature/trip-date-shrink-confirm`. 스펙 문서 참조.
