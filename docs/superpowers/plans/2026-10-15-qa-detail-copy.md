# QA 10/15 정책 상세 문구 · 전국 카드 · 본문 번역체 정리 계획

> 진행 기록을 이 문서에 계속 적는다(사용자 지시 2026-10-15: "작은 작업이여도 계획은 작성하면서 프로젝트 절차 준수", "기록은 항상 할것").

- 브랜치: `feature/qa-detail-copy`(워크트리 `.superpowers/worktrees/qa-copy`, develop `60eb6a6` = #94 머지 뒤에서 땀)
- 관련 PR: #95(교통 혜택 링크 · 배너 · 추가 혜택 합치기, 아직 Draft) - 링크 문제는 #95 가 맡는다.

## 0. 배경 - QA 보고(2026-10-15)

| # | 보고 | 판단 |
|---|---|---|
| Issue#1 | 사진 출처 링크가 '전체 보기'와 같이 눌린다 | #94(develop 머지됨)가 홈 배너 아래 '사진 출처' 단추를 이미 뺐다. QA 는 예전 4173 빌드로 본 것. **사용자 결정: #94 로 끝, 그대로** |
| Issue#2 | 정책 상세 항목 이름이 번역 어투 | 아래 1절 표대로 바꾼다 |
| Issue#3 | 전국 공통 혜택의 '혜택 안내' 링크가 다른 사이트로 간다 | 여행가는 달 홍보 페이지(5건) · 코레일 FAQ(1건) 탓. **#95 가 고친다**(배포 뒤 검토 대기열 승인 필요). 이 계획은 점검 결과만 기록(5절) |
| 추가 | 전국 카드의 작은 설명 줄이 제목 · 요약과 겹친다(정책 탭 목록) | 전국 공통 줄에서 설명 줄을 뺀다(2절) |
| 추가 | 정책 본문 번역체 | 검토 제안서대로 고친다(**사용자: "시안대로 진행"**) - 3절 |

## 1. 정책 상세 · 일정 이름 바꾸기 (Issue#2)

| 위치 | 이전 | 바꾼 이름 | 상태 |
|---|---|---|---|
| 상세 요약 칸 `<dt>` | 받는 것 | 혜택 | 구현 · 시험 통과(커밋 전) |
| 상세 요약 칸 `<dt>` · 본문 `<h3>` | 받는 방법 | 혜택 사용 방법 | 구현(커밋 전) |
| 본문 섹션 | 받는 혜택 | 혜택 내용 | 구현 · 시험 통과(커밋 전) |
| 본문 섹션 | 받을 수 있는 사람 | 혜택 대상 | 구현 · 시험 통과(커밋 전) |
| 본문 섹션 | 확인할 점 | 확인 사항 | 구현 · 시험 통과(커밋 전) |
| 일정 상태 칩 | 다녀옴 | 지난 여행(사용자 선택) | 구현 · 시험 통과(커밋 전) |

- 요약 칸은 '혜택 내용'이 아니라 '혜택' - 바로 아래 섹션 제목 '혜택 내용'과 같은 말이 두 번 나오지 않게(사용자에게 보고함, 바꾸라면 바꾼다).
- QA 가 쓴 '받을 수 있는 대상'은 코드 · 데이터 어디에도 없다 - 화면의 '받을 수 있는 사람'으로 본다.
- 파일: `frontend/src/components/policyDetailParts.tsx`, `frontend/src/utils.ts`, 시험 `policy-detail.test.tsx` · `trip-detail.test.tsx` · `trips-list.test.tsx` · `utils.test.ts`.
- **기록:** 이 단계는 계획서 없이 먼저 고쳤다(절차 위반, 사용자 지적). 시험은 먼저 바꿔 실패를 본 뒤 고쳤다(policy-detail 15건 RED → 33/33, utils 1건 RED → 6/6).

## 2. 전국 카드 설명 줄 빼기

- 정책 탭 목록 줄(`components/map/policyListText.ts` 의 `otherText`)은 [요약 head, 첫 문장 detail] 을 낸다. 전국 공통(`region === "전국"`)은 detail 을 빈 문자열로 - 제목 · 요약이 곧 내용이라 되풀이다.
- 시험 `policyListText.test.ts` "drops the description line for nationwide benefits" 를 먼저 넣어 RED 확인(4건 중 1 실패).
- **상태:** 구현 반영, 계획 승인 뒤 GREEN 확인(map 컴포넌트 · utils 시험 79/79 통과).
- 홈 화면 전국 카드(`HomePage.tsx` NationwideLineCard)는 별도 구성이라 이번 범위 아님 - QA 사진은 정책 탭 목록이다.

## 2.5 일정에서 연결된 정책을 지울 때 '빼기' → '삭제' (QA 추가 2026-10-15)

- 사용자: "정책을 제거할때도 빼기 라는 버튼도 어색함, 삭제로 변경" - "일정에서 연결된 정책 제거하고 싶을때".
- 위치: `pages/itinerary/ItineraryDetailPage.tsx` 연결된 정책 × 를 누르면 뜨는 확인 창.
  - 단추 `빼기` → `삭제`
  - 제목 "이 정책을 일정에서 뺄까요?" → "이 정책을 일정에서 삭제할까요?" (같은 화면 장소 확인 창 "장소를 삭제할까요?" 와 맞춘다)
  - 본문 "… 연결만 풀려요. 정책은 정책 탭에 그대로 있어 다시 담을 수 있어요." 는 그대로 - 정책 자체가 지워지는 것이 아니라는 안내라 남긴다.
- 시험: `trip-detail.test.tsx`(제목 · 단추 이름 4곳), `mypage.test.tsx`(단추 이름 1곳)를 먼저 바꿔 RED → 구현 → GREEN.
- 기록(2026-10-15): 시험을 먼저 바꿔 RED(trip-detail 정책 시험 3건 실패) → 제목 · 단추 두 줄 수정 → GREEN(정책 시험 10/10).

## 3. 정책 본문 번역체 정리 (사용자: "시안대로 진행") - **이 브랜치 범위 밖**

> 2026-10-15 사용자 결정: 본문 정리는 새 브랜치로 따로 한다. #95 머지 뒤 develop 에서 새 브랜치 · 새 계획서로 진행하고, 이 절은 넘겨줄 내용으로 남긴다.

제안서: 세션 scratchpad `copy-review.md`(사용자에게 파일로 보냄). 우선순위 그대로:

1. 디지털관광주민증 52건 공통 문장 - `backend/app/services/digital_tourism_resident_card.py` · `policy_semantic_mapping.py`
2. 숙박세일 32건 - `backend/app/services/stay_discount_aliases.py`(요약이 조건 3개를 " / " 로 이은 문자열 → 한 문장)
3. 반값여행 8건 - `policy_semantic_mapping.py` · `dgtourcard_parser.py`, 괄호 안 쉼표에서 잘리는 `_split_detail_lines` 결함
4. 교통 6건 - `travelmonth_traffic_detail.py`(#95 와 같은 파일 - 충돌 주의, 6절)
5. 프론트 - `policyDetailText.ts` 제휴 분야 단위 '곳', 라벨 가운뎃점, 문자열로 묶인 판별(아래)

말투: 본문은 합니다체 유지(제안서 기본안). 화면 고정 문구는 해요체 그대로.

### 3.1 같이 움직여야 하는 문자열(제안서 8절)

- 프론트가 데이터 항목 제목으로 판별: `startsWith("받는 방법")` · `"카테고리별 인기 혜택"` · `"혜택 적용 조건"` · `startsWith("대상 지역")` · `"지원내용"/"지원 내용"` · `"핵심 혜택"`.
- 반값여행 spend 정규식 `/^(.+?) 등 지역 여행 지출을 대상으로/`, `PLAIN_DOCUMENT_NOTE` 키, `GENERIC`/`TEMPLATE` 정규식(`최종.{0,30}확인`, `변동될 수 있`).
- 백엔드 문장을 바꾸면 위 판별 · 정규식 · 시험 문구를 같은 커밋에서 바꾼다.

### 3.2 이미 공개된 정책 행에 어떻게 반영할지 - 조사 중

- 상세 문장이 정책 행(`policies.structured_detail` 등)에 저장되는지, 읽을 때(`policy_to_api`) 만들어지는지 출처마다 확인한다(숙박세일 지역 정책은 읽을 때 만드는 부분이 있다).
- 2026-10-15 조사: API 상세는 `policy_structured_detail.structured_detail_for_api` → 검토 증거 상세가 없으면 `policies.structured_detail`(저장값)을 그대로 쓴다. 상세 문장은 승격 때 `policy_semantic_mapping.map_external_source_semantics` 가 만들어 저장한다. 숙박세일 지역 정책만 읽을 때 `stay_discount_aliases.apply_alias_structured_detail` 로 일부를 덧씌운다. → 문장을 바꿔도 공개 행은 다시 승격되기 전까지 옛 문장이다.
- 저장되는 출처는 다음 수집 승격 때 상세 지문이 바뀌어 검토 대기열 후보(material_change)가 대량(최대 92건)으로 생길 수 있다. 선례 `0045_traffic_detail` 처럼 데이터 마이그레이션으로 공개 행을 한 번 다시 채울지, 승격을 기다릴지 정한다 - 조사 결과를 이 절에 적고 사용자 승인 뒤 진행.

## 4. 검증

- 프론트 `npm run typecheck` · `npx vitest run`(mypage 6건은 원래 실패) · `npm run test:mojibake` · `npm run build`, 백엔드 `python -m pytest`(snapshot 1건 제외), 마이그레이션이 생기면 로컬 Postgres 에서 실제로 돌린다.
- `git diff --check`, 바뀐 파일 U+FFFD 0건.
- 최종 검토 Opus 1회(끝에 한 번).
- 브라우저 확인은 사용자(4173 재빌드 뒤): 상세 섹션 이름, 일정 '지난 여행', 정책 탭 전국 줄, 본문 문장.

### 4.1 검증 기록

- 2026-10-15 커밋 전 최종(1 · 2 · 2.5절): `npx vitest run` 742 중 736 통과 - 실패 6건은 모두 mypage(원래 실패). typecheck · mojibake · build · `git diff --check` 통과, U+FFFD 0건.
- 2026-10-15 #95 머지(0b8cc9f) 확인: #93 · #94 · #95 커밋 10개가 모두 develop 에 들어 있다. 이 브랜치와 겹치는 파일은 `policy-detail.test.tsx` 하나(충돌 없음) - develop 을 받은 뒤 해당 시험을 다시 돌린다.
- 2026-10-15 1 · 2절 반영 중 전체 프론트 실행: 742 중 735 통과 - mypage 6건(원래 실패) + 전국 설명 줄 시험 1건(구현 반영 전 시점 실행). typecheck · mojibake · build · diff-check 통과.

### 4.2 PR 절차 기록(`.codex/local-workflow.md` 'PR 생성 전 최종 게이트')

- 2026-10-15 사용자 지적: "pr 내용도 프롬프트 준수 안햇음". #96 을 만들 때 빠뜨린 것 - 코드 리뷰와 BASE/HEAD SHA 대조, 생성 직후 `gh pr view --json commits,files,baseRefName,headRefName,isDraft,state,url` 재확인, 로컬 브라우저 완료 조건(세 컨테이너 같은 working_dir · 5173), Slack 전송 여부 질문. 아래 순서로 채운다.
- 게이트 1~4(2026-10-15): `origin/develop`(0b8cc9f) 기준 behind 0 · ahead 2(be93082 + develop 병합 f0c531b), 바뀐 파일 11개 모두 이 작업 것.
- 로컬 런타임: db · backend · frontend 세 컨테이너를 이 워크트리(qa-copy)에서 다시 만들었다(db 는 `--force-recreate`, 볼륨 보존). working_dir 세 개 모두 qa-copy, 8000 health 200 · API 정책 98 · 전국 6, 4173 200, 5173(Vite, 같은 워크트리) 200 - 새 문구('혜택 대상' · '확인 사항' · '지난 여행')가 나온다.
- 코드 리뷰(Opus, BASE 0b8cc9f → HEAD f0c531b): Critical 0, Important 1, Minor 4.
  - Important: `frontend/e2e-backend/backend-mode.spec.ts` 가 옛 확인 창 이름("뺄까요" · "빼기")을 쓴다 → 고친다.
  - Minor: `policyListText.ts` 가 "전국" 을 직접 씀 → `NATIONWIDE_REGION` 으로(고친다). 계획서 3절 제목 줄 잘림 → 고쳤다. `home.test.tsx` 일정 제목 "지난 여행" 이 새 칩 문구와 겹쳐 읽기 어려움 → 제목을 바꾼다. 옛 이름이 주석에만 남음 → 화면 영향 없어 본문 정리 브랜치에서(기록만).
  - 고친 뒤 같은 검토자가 늘어난 범위를 다시 보고, 리뷰 SHA 와 PR HEAD 를 맞춘다.
- 리뷰 지적 반영 뒤 검증(2026-10-15): map · home 시험 95/95, typecheck 통과, `git diff --check` 통과, `npm run test:e2e:containers`(재빌드한 4173 · 같은 워크트리 컨테이너) 13/13 통과.

## 5. Issue#3 링크 점검 기록(2026-10-15, 로컬 DB 공개 정책 98건 · 링크 63개 실접속)

- 전국 공통 6건: 여행가는 달 교통 페이지 5 · 코레일 FAQ 1 → #95 로 해결(배포 뒤 승인).
- 숙박세일 32건: 모두 ktostay.visitkorea.or.kr 200.
- 반값여행 8건: 6건 200, 고흥 · 장흥은 이 PC 에서 접속 시간 초과(사이트 장애 또는 해외 차단 가능) - QA 가 다른 망에서 확인 필요.
- 디지털관광주민증 52건: 시군별 공식 페이지(visitkorea dgtourcard regnMain)이나 NetFunnel 대기 화면 뒤라 시군 일치를 자동 확인 못 함 - QA 가 몇 곳 브라우저로 확인 필요.

## 6. 순서 · 충돌

1. 2절 GREEN 확인(2026-10-15: map · utils 시험 79/79) → 1 · 2절 커밋(이 계획서 포함) → 푸시 · Draft PR. **이 브랜치는 여기까지.**
2. 본문 정리(3절)는 #95 머지 뒤 develop 에서 새 브랜치 · 새 계획서(3.2 반영 방식 포함, 사용자 승인 뒤 구현).
3. CHECKLIST 는 머지 직전에만(다른 열린 PR 과 충돌 방지).
