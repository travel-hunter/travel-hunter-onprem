# Codex 인계 — 커밋과 push

작성: 2026-09-05 / 작성자: Claude 세션
브랜치: `feature/itinerary-day-strip`
마지막 코드 커밋: `3235fd6` (이 문서를 담은 커밋이 그 뒤에 온다)
작업 트리: **깨끗함.** 스테이지된 것 없음.

push / PR / merge 는 네 몫이다. 나는 커밋까지만 했다.

---

## 1. 먼저 알아야 할 것 — 원격에 사본이 없다

개발서버(`192.168.32.15:~/travel-hunter-onprem`)는 `develop = a7f0c05` 로
`origin/develop` 과 정확히 같다. **개발서버에 있는데 로컬에 없는 커밋은 없다.**

문제는 반대다. **이 컴퓨터에만 있는 커밋이 35개다.** 8개 가지가 어디에도 push 되지 않았다.
`git cherry origin/develop <branch>` 로 확인했고 전부 patch-id 기준 미반영이다.

이 컴퓨터가 죽으면 그대로 사라진다. 병합은 나중에 정해도 되지만
**push 만이라도 하면 사본이 생긴다.**

여덟 가지 모두 `.env` / secret / credential / `.pem` / `.key` 로 보이는 파일을
추가하지 않는다. 확인했다.

---

## 2. 이번에 만든 커밋

아래는 코드 커밋이고, 문서 커밋이 그 뒤로 몇 개 더 붙는다.

```
3235fd6 fix(travel-areas): 행정지역 버튼의 도시 되풀이를 없앤다
9815c30 feat(travel-areas): 세부 지역을 권역으로 접어 보여준다
ef5a3c4 docs: 인계문의 남은 작업을 Task 8 로 좁힌다
b8d51ce docs(contract): 지역 카탈로그와 일정 지역 수정을 계약 문서에 반영한다
de1c315 docs: 일정 화면 후속 조정의 계획서를 남긴다
8583c0b docs: 지역·달력 통합 설계와 두 세션 사이의 인계 기록을 남긴다
ec41c2e test(policy): 마이페이지·정책 테스트를 실제 DB 상태에서 떼어낸다
6e5b4ee feat(itinerary): 세 화면의 날짜·지역 선택을 통일하고 day 스트립을 다듬는다
388a2e4 feat(trip): 지역 선택기와 범위 달력을 공용 컴포넌트로 만든다
f31ae58 feat(travel-areas): 전국 행정지역 카탈로그와 일정 지역 수정 계약을 추가한다
d0f77a8 feat(itinerary): day 선택을 한 줄 스트립과 가장자리 이동영역으로 바꾼다
```

`d0f77a8` 은 09-01 커밋인데 아직 원격에 없다. 나머지는 09-04~09-05 작업이다.

### 커밋 직전 게이트

| 항목 | 결과 |
|---|---|
| `npm run typecheck` | PASS |
| `npx vitest run` | **348 passed / 0 failed** (28 files) |
| `npm run build` | PASS |
| `npm run test:mojibake` | 없음 |
| `git diff --check` | 깨끗 |
| `pytest` | **701 passed / 1 failed** |

백엔드 실패 1건은 `test_restricted_atomic_artifact_and_sidecar_round_trip` 이다.
Windows 임시 디렉터리 권한에 걸리는 간헐적 환경 이슈로, 통과할 때도 있다.
2026-08-27 기록에도 같은 이름으로 남아 있다. **이 브랜치가 만든 것이 아니다.**

### 나눈 기준과 한계

파일 단위로 나눴다. `git add -p` 가 이 환경에서 대화형으로 돌지 않아
헝크 단위로는 못 갈랐다. 그래서 `6e5b4ee` 하나에 네 갈래가 섞여 있다 —
공용 달력 적용 / 공용 지역 선택기 적용 / day 스트립 / 상세 헤더.
커밋 메시지에 네 갈래를 나눠 적어 뒀다.

`.env`, `backend/.env`, `backend/.env.local` 은 gitignore 대상이라 담기지 않았다.
값은 로컬에만 바뀐 채로 있다(`TRAVEL_HUNTER_PUBLIC_BASE_URL` → 5173).

---

## 3. push 우선순위

### 1순위 `feature/itinerary-day-strip`

지금 작업. 테스트 전부 초록. 계획서
`docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md` 의 Task 1~6 과
`docs/superpowers/plans/2026-09-04-itinerary-day-strip-followups.md   (Task 1~10)` 전부를 담는다.

Task 7(계약 문서 동기화)은 끝냈다 — 커밋 `b8d51ce`, `group` 필드까지 반영.
**남은 것은 Task 8 의 5173 수동 확인뿐이다.** 자동 게이트는 전부 통과한 상태다.

09-05 에 세부 지역 권역 접기를 더했다(`9815c30`, `3235fd6`). 시·군·구가 13개를
넘는 9개 시도(서울 25, 경기 31, 전남·경북 22 …)를 권역으로 접는다. 배정은 판단이
갈릴 수 있어 **빠짐·중복만 테스트로 막았다** — 9개 시도 190개 단위가 정확히 분할된다.
배정을 옮기려면 `backend/app/data/administrative_areas.py` 의
`ADMINISTRATIVE_GROUPS_BY_SIDO` 한 곳만 고치면 되고, 옮기다 빠뜨리면 테스트가 잡는다.

### 2순위 `feature/dgtour-canonical-slug` (+8, 08-27)

**이건 이미 대가를 치렀다.** 크롤러가 슬러그에 페이지 순번을 붙이는 근본 문제를
고치는 가지인데(`backend/scripts/crawl_dgtourcard.py:217`), 병합되지 않아
2026-09-03 정책 수집이 돌자 `dgtour-영광` 이 hidden 으로 내려가고
`dgtour-영광-8` 이 active 가 되면서 프론트 테스트 6건이 한꺼번에 깨졌다.

조사 문서가 그 가지 안에 있다.

```
feature/dgtour-canonical-slug:docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md
```

이번에 `ec41c2e` 로 테스트를 DB 에서 떼어냈지만 그건 증상 차단이다.
**원인은 이 가지가 병합돼야 사라진다.**

### 3순위 나머지 여섯

내용 중복이 있어 그대로 병합하면 충돌한다. push 로 사본만 먼저 만들고
병합 여부는 따로 판단할 것을 권한다.

| 가지 | 커밋 | 최종 | 비고 |
|---|---|---|---|
| `feature/e2e-backend-mode-repair` | 6 | 08-28 | 개발 파이프라인 백엔드 테스트 단계 + 교차일 드래그 e2e |
| `feature/local-remediation-integration` | 6 | 08-22 | 드래그 오버플로 수정 + 테스트 안정화 |
| `feature/trip-place-drag-overflow` | 4 | 08-22 | 위와 커밋이 겹친다 |
| `feature/prod-db-cutover-record` | 1 | 08-30 | 운영 DB 이전 기록 + 비밀값 취급 규칙 |
| `feature/local-dev-runtime-docs` | 1 | 08-25 | 로컬 런타임 문서 |
| `feature/frontend-test-stability` | 1 | 08-22 | `213619c` 가 여러 가지에 중복 존재 |

`backup/itinerary-drag-preview-unified-698f06c` 는 이름 그대로 백업이다.
내용은 PR #44(`8d72d66`)로 형태를 바꿔 이미 들어갔다. push 대상이 아니다.

---

## 4. 알아둘 것

### main 이 develop 보다 8커밋 앞선다

전부 운영 Jenkins 파이프라인 설정이다(`ci: add production jenkins pipeline` 외).
반대로 **develop 에만 있고 main 에 없는 커밋은 0개** — develop 이 main 에 완전히 포함된다.
즉 develop 은 운영 파이프라인 설정을 모르는 상태다. 의도된 것인지 확인이 필요하다.

### 건드리면 안 되는 것

- `frontend/src/test/fixtures.ts` 의 `examplePolicySlug = "dgtour-영광"`.
  `feature/dgtour-canonical-slug` 가 정한 정식 계약이고, 병합되면 DB 도 이 값으로 돌아온다.
- 로컬 DB 에 정책 수집을 돌리는 것. 프론트 테스트가 또 흔들린다.

### 설정

백엔드는 저장소 루트 `.env` 를 읽지 않는다.

```python
# backend/app/core/config.py
32  load_env_file(BACKEND_DIR / ".env")
33  load_env_file(BACKEND_DIR / ".env.local", override=True)
```

`backend/.env.local` 이 최종값이다. 여기를 안 고치면 반영되지 않는다.
포트로 깨지던 백엔드 테스트 5건은 이 값을 5173 으로 맞춰 해소했다.

백엔드 컨테이너는 소스를 이미지에 COPY 해서 굽는다. 소스를 고쳐도
`docker compose -f compose.local.yaml build backend` 없이는 반영되지 않는다.
09-04 에 한 번 재빌드했다.

### 검사기에 제어문자 검사가 붙었다

CSS `content` 에 유니코드 이스케이프를 쓰려다 8진으로 풀려 0x15 가 파일에 박혔고
화면에 정체불명 글자로 보였는데, `npm run test:mojibake` 는 통과했었다.
이제 제어문자도 잡는다. 정규식 리터럴로 검사하면 검사기 자신에게 제어문자를 박게 되므로
`charCodeAt` 으로 센다. 탐침 파일로 실제 검출을 확인했다.

**CSS 에 유니코드 이스케이프를 쓰지 마라.** 실제 문자를 넣는 편이 안전하다.

### 미해결 버그 하나

카드를 잡고 좌우 이동영역으로 날짜를 옮긴 뒤 위로 올리면 스크롤 고정이 듣지 않는다.
자동 스크롤 제동은 `autoScrollBrakedRef` 로 한 번만 `autoScrollBrakeTick` 을 올려
dnd-kit 의 `canScroll` 정체성을 바꾸는 구조다. 날짜 전환 시 그 상태가 어떻게 되는지가
다음 확인 지점이다 — `ItineraryDetailPage.tsx:2439` 의 타이머 effect 와 `:2149` 의 `canScroll`.

### 실기기 확인 미완

`docs/superpowers/plans/2026-09-04-itinerary-day-strip-followups.md` 의 "남은 것" 절과
`2026-09-03-trip-region-calendar-unification.md` 의 Task 8 Step 4 를 따른다.

---

## 5. 함께 읽을 문서

```
docs/2026-09-04-codex-handoff.md               세션 밖에서 바뀐 설정과 기준선
docs/2026-09-04-working-tree-attribution.md    누구 작업이 어디 있는지 (커밋 전 기준)
docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md
docs/superpowers/plans/2026-09-04-itinerary-day-strip-followups.md
.superpowers/sdd/2026-09-03-trip-region-calendar-unification/progress.md   (추적 제외)
```
