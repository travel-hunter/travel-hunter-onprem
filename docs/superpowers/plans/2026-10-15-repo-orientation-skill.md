# repo orientation 스킬 정비 · /repo 연결

> 진행 기록을 이 문서에 계속 적는다(사용자 지시 2026-10-15).

- 브랜치: `feature/repo-orientation-skill`(워크트리 `.superpowers/worktrees/repo-skill`, develop `d870650` = #97 머지 뒤)
- 사용자 결정(2026-10-15): "repo orientation 을 프로젝트 절차를 작동시키는 명령어로 쓰고 있다 → 스킬화, /repo". 방식은 **공용 스킬을 고치고 `/repo` 는 연결만**.

## 0. 배경

- 공용 스킬 `.agent/skills/repo-orientation/SKILL.md`(코덱스와 같이 씀, 저장소에 들어 있음)는 작업 시작 체크리스트 수준이고, 없어진 문서 `docs/current-work-spec.md` 를 가리킨다.
- 사용자가 "repo orientation" 이라고 하면 실제로 해 온 일: fetch · develop 상태, 방금 머지된 PR 커밋이 develop 에 다 들어갔는지, 열린 PR, 워크트리를 머지됨 / 남은 커밋 / 작업 중 파일로 분류, 루트 체크아웃 상태, 로컬 런타임 출처(세 컨테이너 working_dir · 4173 · 5173), CHECKLIST 가 최신 머지를 반영하는지, 남은 서버 작업 → 다음 작업을 묻기.

### 0.1 사용자 추가 요구(2026-10-15): "로컬 서버 버전은 개발서버랑 맞추는 작업도 있어야 함"

- 판정(읽기만, 메모리 prod-vs-dev-build-hash-is-not-drift): 프론트는 `/assets/index-*.css` 해시(JS 해시는 API 주소가 박혀 늘 다름), 백엔드는 `/openapi.json` 바이트 비교, DB 는 `alembic_version`(로컬은 컨테이너 안, 개발서버는 접근 경로가 있을 때만 - 승인 뒤).
- 맞추기(바깥에 영향 - 사용자 승인 뒤): 로컬 백엔드 · 프론트를 develop 으로 다시 빌드 → `alembic upgrade head` → 정책 데이터는 저장소 밖 `D:/travel-hunter-tools/sync-local-policies-from-dev.sh <로컬 db 컨테이너>`(메모리 local-policy-sync-from-dev, alembic 이 같아야 돈다).
- 2026-10-15 실측: 개발서버와 로컬 4173 CSS `index-C7IfHjxj.css` 같음, `/openapi.json` 135,148바이트 같음 → 코드 버전은 일치. DB · 정책 데이터 일치는 아직 확인 안 함.

## 1. 바꿀 것

1. `.agent/skills/repo-orientation/SKILL.md` 를 위 절차(0.1 버전 판정 · 맞추기 제안 포함)로 고친다(읽기만 하는 점검, 보고는 한국어, 끝에 다음 작업 질문). 없어진 문서 참조를 지금 문서(`docs/implemented-feature-spec.md` · `docs/next-work-plan.md` · `docs/mvp-api-contract.md`)로 바꾼다. 영어 본문 · 500단어 안쪽(다른 `.agent/skills` 와 같은 꼴).
2. Claude Code 용 `/repo`: 이 PC 의 `.claude/skills/repo/SKILL.md`(저장소 `.gitignore` 의 `.claude/` - 커밋되지 않음). 공용 스킬을 읽어 그대로 돌리라는 연결만 둔다.
3. CHECKLIST(PR 마다 반영 규칙): Current Status 에 이 PR 머지 준비 한 줄, Recent Validation 에 스킬 시험 결과.

## 2. 시험(스킬 = 문서의 TDD, superpowers:writing-skills)

- RED: 새 에이전트(Sonnet)에게 지금 공용 스킬만 주고 "repo orientation 해 줘"(읽기만) → 1절의 점검 항목 중 무엇을 빠뜨리는지 적는다.
- GREEN: 고친 스킬로 같은 요청 → 빠뜨림이 없어지는지.
- 빠뜨림이 남으면 문구를 고쳐 다시.

## 3. 검증 · 마무리

- `git diff --check`, U+FFFD 0.
- 최종 검토 Opus 1회(리뷰 SHA = PR HEAD).
- 커밋 → 사용자 지시 뒤 푸시 · PR(최종 게이트), PR 본문에 `/repo` 로컬 파일은 저장소 밖이라는 점을 적는다.

## 4. 기록

- 2026-10-15 계획서 작성. RED(옛 스킬, Sonnet): 문서 읽기 · 없어진 문서 지적은 했으나 빠뜨림 - git fetch 안 함(읽기 전용이 아니라고 봄), 머지 커밋이 develop 에 들어갔는지, 워크트리를 머지됨 / 남은 커밋 / 작업 중으로 분류, 로컬 런타임 출처(세 컨테이너 · 4173 · 5173), CHECKLIST 최신 여부, 개발서버 버전 비교, 남은 서버 작업, 다음 작업 질문. 스킬 머리말(YAML ---)도 없었다.
- 2026-10-15 GREEN 용 스킬 작성(491단어, YAML 머리말, 체크리스트 9단계 · 보고 순서 · 다음 작업 선택지 · 흔한 실수) → 같은 요청으로 GREEN 시험.
- 2026-10-15 GREEN(새 스킬, Sonnet): 9단계 모두 수행 - fetch, #97 커밋 2개 develop 확인, 열린 PR 0, 워크트리 분류(머지됨 11 · 남은 커밋 6 · 작업 중 1), CHECKLIST 빠진 PR 없음, 세 컨테이너 working_dir 일치 · 8000/4173/5173 200, 개발서버와 CSS · openapi 같음 · 로컬 alembic 0054, 남은 서버 작업, 못 한 점검과 이유, 다음 작업 선택지. 빠뜨림 없음 → 문구 그대로.
- 2026-10-15 CHECKLIST 반영(PR 마다 규칙): Current Status 머지 준비 줄 · #97 머지, Recent Validation 스킬 시험.
- 2026-10-15 커밋 91d0c83 검토(Opus, d870650 → 91d0c83): Critical 0, Important 2 - /repo 연결 파일의 git show 경로가 Git Bash 에서 깨짐(./ 로) · 머지 전엔 develop 의 옛 스킬을 조용히 읽음(첫 줄 --- 확인 뒤 브랜치 쪽으로), 런타임 출처 명령 미기재(docker ps --format 라벨만으로 명시). Minor 3 - local-workflow 는 루트 체크아웃에만, gh pr view 에 commits, alembic upgrade 는 docker exec. 모두 반영(공용 스킬 522단어).
- 2026-10-15 사용자 추가 요구(0.1) 반영, 개발서버 · 로컬 버전 실측.
