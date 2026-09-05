# E2E backend-mode 스모크 복구 계획

**목표:** `frontend/e2e-backend/backend-mode.spec.ts`의 12개를 다시 전부 통과시켜, 이후 드래그 E2E를 얹을 수 있는 상태로 만든다.

**배경:** 이 저장소는 legacy `travel-hunter-app`의 파일 스냅샷으로 만들어졌고(`dfa5667`), 그때 **GitHub Actions 워크플로만 의도적으로 제외**됐다. Jenkins 파이프라인(`deploy/jenkins/dev/Jenkinsfile`)에는 테스트 단계가 하나도 없다 — `vitest`·`pytest`·`tsc`·`playwright` 전부 0건. 그래서 E2E가 몇 달째 안 돌았고 조용히 낡았다.

---

## 실측 결과 (2026-08-28, 격리 DB `travelhunter_e2e`)

```
1차 (12개 전체)   3 통과 · 1 실패 · 8 미실행
2차 (#4 제외)     6 통과 · 1 실패 · 4 미실행
누적 통과 9 · 실패 2 · 미확인 4
```

`test.describe.configure({ mode: "serial" })`(`:35`) 때문에 **하나가 실패하면 뒤가 전부 중단**된다. 그래서 12개를 초록으로 만들기 전까지는 이 스위트의 가치가 사실상 0이다.

---

## 실패 ① — 낡은 기대값 (기계적 수정)

`backend-mode.spec.ts:12`

```ts
const examplePolicyOfficialUrl = "https://www.yeonggwang.go.kr/travel/";
```

```
기대  https://www.yeonggwang.go.kr/travel/
실제  https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12830
```

시드 데이터가 `f12efc2` "Align digital tourism policies with official region links"에서 VisitKorea 지역 상세 URL로 바뀌었는데 테스트만 안 따라갔다. **앱이 옳고 테스트가 틀렸다.**

> **주의:** 이 상수를 시드 파일에서 읽어오게 바꾸고 싶은 유혹이 있으나 하지 않는다. 테스트가 프로덕션 데이터를 그대로 읽으면 "무엇이든 통과하는" 검증이 된다. 값을 명시적으로 적되, 시드가 또 바뀌면 여기서 걸리게 둔다.

---

## 실패 ② — 제품 판단 필요 (구현 보류)

`backend-mode.spec.ts:272` `empty trip detail saves a manual label-only place through the backend`

```
45초 타임아웃
locator('.trip-select-sheet').locator('input[name="place-label"]')
```

**셀렉터 이름이 바뀐 게 아니다. 그 흐름 자체가 사라졌다.**

`ItineraryDetailPage.tsx:5031`

```tsx
{mode === "edit" ? (
  <label className="field">
    장소명
    <input name="place-label" … />
  </label>
) : null}
```

`place-label` / `place-meta`가 이제 **`mode === "edit"`에서만** 렌더된다. "장소 추가"가 여는 `mode === "add"`에는 대신 `PlacePreviewMapCard`가 들어가고, 저장은 검색 후보를 명시적으로 고를 것을 요구한다.

`ItineraryDetailPage.tsx:2588`

```ts
setPlaceSaveEligibility("requiresExplicitCandidate");
// helper: "검색 결과를 지도에 미리 표시했어요. 저장하려면 후보를 직접 선택해 주세요."
```

### 판단이 갈리는 지점

| 근거 | 방향 |
|---|---|
| `PlaceSaveEligibility` 3상태 + 헬퍼 문구 + 지도 미리보기 카드 — 설계된 기능이다 | 의도된 제거 |
| 카카오 지도 연동상 좌표 없는 장소는 지도에 못 띄운다 | 의도된 제거 |
| **백엔드는 여전히 `latitude: float \| None = None`** — 좌표 없는 장소를 받는다 (`schemas/trip.py:24,95,114,167,181`) | 유실 가능성 |
| 제거된 커밋이 `fcf797f` **"Restore itinerary day drag and gutter scroll"** — 드래그 수정 커밋에 저장 경로 제거가 섞여 있다 | 유실 가능성 |
| `place-edit.test.tsx`는 **edit 모드만** 덮는다. add 모드 수동 입력을 지키는 단위 테스트가 없다 | 유실 가능성 |

**이건 "검색에 안 잡히는 장소를 사용자가 직접 적어 넣을 수 있어야 하는가"라는 제품 결정이다. 코드만으로는 결론이 안 난다.**

### 답에 따른 작업

- **A. 의도된 제거였다** → 이 테스트를 현재 흐름(후보 선택 후 저장)에 맞게 다시 쓴다. 테스트 1개 수정
- **B. 유실이었다** → add 모드에 수동 입력 경로를 되살린다. 프로덕션 코드 변경 + 단위 테스트 추가. 별도 계획으로 분리해야 할 규모

**답을 받기 전까지 ②는 손대지 않는다.** 추측으로 테스트를 지우면 유실 신호가 사라지고, 추측으로 기능을 되살리면 요청받지 않은 제품 변경이 된다.

---

## 작업 순서

### Task 1: 실패 ① 수정

- [ ] **Step 1: 현재 값 확인** — 격리 DB에서 실제 `officialUrl`을 조회해 상수와 대조한다

  ```bash
  curl -s "http://127.0.0.1:8001/api/policies/dgtour-%EC%98%81%EA%B4%91-8" \
    | python -c "import json,sys; print(json.load(sys.stdin).get('officialUrl'))"
  ```

- [ ] **Step 2: 상수 교체** — `backend-mode.spec.ts:12`

  ```ts
  const examplePolicyOfficialUrl =
    "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12830";
  ```

- [ ] **Step 3: #4 단독 실행으로 확인**

  ```bash
  cd frontend
  SKIP_E2E_DB_START=1 \
  DATABASE_URL="postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter_e2e" \
  E2E_API_PORT=8001 E2E_FRONTEND_PORT=5174 \
  PYTHON="<repo>/backend/.venv/Scripts/python.exe" \
  node scripts/run-backend-e2e.cjs --grep "drives policy, trip, recommendation" --reporter=line
  ```

  기대: 1 passed

- [ ] **Step 4: ② 제외하고 전체 실행** — ①만 고친 상태에서 #5~#12 중 **아직 못 본 #9~#12**의 실태를 드러낸다

  ```bash
  … node scripts/run-backend-e2e.cjs --grep-invert "manual label-only place" --reporter=line
  ```

  기대: 11개 중 실패 0. **새 실패가 나오면 멈추고 보고한다** — #9~12는 이번에 처음 도는 것이라 추가로 낡았을 수 있다

- [ ] **Step 5: 커밋**

  ```bash
  git add frontend/e2e-backend/backend-mode.spec.ts
  git commit -m "Update the dgtour official URL expectation in the backend e2e smoke"
  ```

### Task 2: 실패 ② — 사용자 답변 대기

- [ ] 위 "판단이 갈리는 지점"을 사용자에게 제시하고 A/B 중 선택을 받는다
- [ ] A면 이 계획에서 테스트를 다시 쓴다. B면 **별도 계획**을 새로 쓴다

---

## 검증

```bash
cd frontend
npx tsc --noEmit                     # 스펙도 타입 검사 대상이다
… node scripts/run-backend-e2e.cjs   # 최종적으로 12 passed
```

**격리 환경을 벗어나지 않는다.**

| | |
|---|---|
| DB | `travelhunter_e2e` — 기존 `travelhunter` 무영향 |
| 포트 | 8001 / 5174 — 상시 런타임 8000 / 4173 무영향 |
| `SKIP_E2E_DB_START=1` | 러너의 `compose up -d db` 를 건너뛴다. 안 하면 **돌고 있는 db 컨테이너를 재생성**할 수 있다 |
| `DATABASE_URL` 덮어쓰기 | 안 하면 러너가 **`travelhunter` 본 DB에 시딩**한다 |

---

## 하지 않을 것

- Jenkins 파이프라인 수정 — 다음 단계이고 별도 작업이다
- 드래그 E2E 신규 작성 — 12개가 초록이 된 뒤
- WebKit / Firefox 추가
- 프로덕션 코드 수정 (②가 B로 결론나기 전까지)
- 개발서버 조작, push / PR / merge
