# CHECKLIST 를 #93 ~ #96 머지 뒤 상태로 맞추기

> 진행 기록을 이 문서에 계속 적는다(사용자 지시 2026-10-15).

- 브랜치: `docs/checklist-sync`(워크트리 `.superpowers/worktrees/checklist-sync`, develop `66e5b44` = #96 머지 뒤에서 땀)
- 사용자 결정(2026-10-15): repo orientation 뒤 다음 작업으로 "CHECKLIST 맞추기".

## 0. 배경

- AGENTS.md: CHECKLIST 는 한 가지 현재 상태만 적는다(Current Status · Recent Validation · Active Risks). 브랜치마다 고치면 같은 줄이 충돌하므로 머지 준비 때만 고치고, 브랜치 이야기는 PR 본문에 둔다.
- #94 · #95 · #96 은 충돌을 피하려고 CHECKLIST 를 고치지 않았다. 그래서 develop 의 CHECKLIST 는 #93 을 아직 'Merge-ready' 로 적고 있고, #94 ~ #96 과 그 배포 뒤 할 일이 빠져 있다.

## 1. 바꿀 것 (문서만, 코드 변경 없음)

| 절 | 지금 | 바꿀 것 |
|---|---|---|
| Current Status | #93 Merge-ready 4줄 | #93 · #94 · #95 · #96 머지 한 줄씩(머지 커밋 포함), 다음 일(정책 본문 번역체 정리 - 새 브랜치 · 계획 예정) |
| Recent Validation | #93 검증 | 마지막 머지(#96)와 #95 데이터 마이그레이션 실측(로컬 Postgres 0053 · 0054)만 짧게 |
| Active Risks | #93 절 제목이 브랜치 이름 | 'PR #93, 머지됨'으로. 새 절: #95 교통 혜택 링크 · 배너(배포 뒤 검토 대기열 승인, 0053 · 0054 가 배포 때 돈다, 민간 운영사 막는 목록 · 코레일 탭 주소는 손으로 관리, 태안 반값여행 중복 서버 정리 · 근본 원인), #94 사진 출처(관광공사 사진은 창에서 한 칸), #96 문구(본문 정리 남음, 링크 점검에서 확인 못 한 곳) |

- 남은 위험만 적고 지나간 연대기는 넣지 않는다. 다른 절(#92 이하)은 건드리지 않는다.
- 사실 출처: 각 PR 본문(#93 ~ #96), 계획서 `2026-10-15-qa-detail-copy.md`, 이 세션 실측.

## 2. 검증

- `git diff --check -- CHECKLIST.md`, 바뀐 줄 U+FFFD 0건(AGENTS Done Criteria).
- 머지 커밋 해시를 `git log origin/develop` 와 대조.
- 최종 검토 1회(Opus): 사실 · 해시가 맞는지, 비밀값 없는지, 남은 위험이 빠지지 않았는지.
- 커밋은 검증 · 검토 뒤, 푸시 · PR 은 사용자 지시 뒤(`.codex/local-workflow.md` 최종 게이트대로).

## 3. 기록

- 2026-10-15 계획서 작성 → CHECKLIST 수정(`git diff --check` 통과, U+FFFD 0).
- 2026-10-15 검토(Opus, BASE 66e5b44, 커밋 전 작업 트리): Critical 0, Important 1(PR 참고의 남은 위험 누락 - 관리자 고친 정책은 링크 규칙 밖, PR 별 브라우저 확인 항목), Minor 3(막는 목록 이름 구분, 0053 · 0054 옮기는 곳 구분, #94 출처 조건 단서). 모두 반영.
