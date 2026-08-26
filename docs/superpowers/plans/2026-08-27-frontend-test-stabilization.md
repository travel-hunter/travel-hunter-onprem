# 프론트엔드 테스트 안정화 (policies / trip-create)

**목표:** `feature/local-remediation-integration`에만 남아 있던 커밋 `213619c` "Stabilize trip and policy frontend tests"의 내용 중, 현재 `develop`에 아직 반영되지 않은 부분만 골라 적용해 상시 실패 테스트를 줄인다.

**범위:** 테스트 파일 2개만 수정한다. **프로덕션 코드는 건드리지 않는다.**

**출처 커밋:** `213619c` (2026-08-22, `feature/local-remediation-integration`)

---

## 배경

`develop`에는 프론트엔드 테스트가 상시 7건 실패하는 상태로 유지돼 왔다. 그 중 일부는 테스트가 실제 백엔드 호출에 의존해서 나는 실패다. `213619c`는 그 의존을 목(mock)으로 끊는 커밋인데, PR로 올라간 적이 없어 develop에 없다.

**단, develop이 그 사이 독립적으로 같은 패턴을 상당 부분 흡수했다.** 실측 결과:

- `trip-create.test.tsx`에는 이미 "스파이를 `try` 밖에서 만들고 `renderAppRoute`를 `try` 안으로 넣는" 형태와 `await waitFor(() => expect(다음).toBeEnabled())` 패턴이 여러 테스트에 들어가 있다 (`:946`, `:998`, `:1043`).
- `policies.test.tsx`의 `"keeps the trip-attached state scoped to the selected policy"`(`:893`)에는 **목이 0건**이다. 여기가 진짜 빈 곳이다.

따라서 커밋 전체를 그대로 cherry-pick하면 이미 반영된 부분과 충돌한다 (`git apply --check`로 확인: `policies.test.tsx`는 offset만으로 통과, `trip-create.test.tsx`는 hunk #2에서 실패).

**결론: cherry-pick을 3-way로 시도하되, 충돌은 develop 쪽 개선을 살리는 방향으로 수동 해소한다. develop이 이미 더 나은 형태를 갖고 있으면 그쪽을 유지한다.**

---

## 확인된 차이

| 파일 | 대상 테스트 | develop 상태 | 커밋이 더하는 것 |
|---|---|---|---|
| `policies.test.tsx` | `keeps the trip-attached state scoped to the selected policy` (`:893`) | 목 0건 — `listTrips` / `addPolicyToTrip` / `getTrip`을 실제 API로 호출 | 세 스파이 + `previewTrip` 픽스처 + `finally`에서 `mockRestore` |
| `trip-create.test.tsx` | `uses the home recommendation region query when creating a trip` (`:243`) | `listTravelAreaRecommendations` 목 없음. `renderAppRoute`가 `try` 밖 | `travelAreasSpy` 추가, `renderAppRoute`를 `try` 안으로, `다음` 버튼 enabled 대기 |
| `trip-create.test.tsx` | 나머지 3개 hunk | **이미 동등하게 반영됨** | 적용 대상 아님 |

`develop`의 `uses the home recommendation region query` 테스트에는 커밋에 없는 `부산 전체` 활성화 대기가 추가돼 있다. **이건 반드시 보존한다.**

---

## 작업 순서

### Task 1: 기준선 기록 (완료)

`npx vitest run` 전체 — **295 tests / 288 passed / 7 failed** (2026-08-27, `d31dc8f` 기준, 백엔드 컨테이너 healthy 상태에서 측정).

```
mypage.test.tsx    :: refreshes the my page applied policy summary after policy linking on another route
mypage.test.tsx    :: refreshes the my page favorite summary after policy detail save and unsave
mypage.test.tsx    :: removes trip detail unlinked policies from the my page applied summary
mypage.test.tsx    :: saves a policy from the policy detail header action
mypage.test.tsx    :: shows saved policies on my page and removes them
policies.test.tsx  :: keeps the trip-attached state scoped to the selected policy   <- 이번 목표
policies.test.tsx  :: shows all saved trips in the policy trip picker
```

**`trip-create.test.tsx`의 실패는 0건이다.** 즉 `213619c`의 trip-create 부분은 develop에 이미 동등하게 반영돼 있고, 이번 작업의 실질 대상은 `policies.test.tsx` 한 곳이다.

실패 "건수"만 보지 않는다. 이 저장소의 프론트 스위트는 타이밍 한계에 걸려 있어 같은 코드로도 7~8건 사이를 오간다 (이전 세션에서 프로덕션 코드 고정 + 테스트 되돌림 실험으로 비논리적 변동임을 확인). **이름 목록의 차이로 판단한다.**

### Task 2: cherry-pick 시도 및 충돌 해소

- [ ] `git cherry-pick 213619c` 실행. 충돌 예상.
- [ ] `policies.test.tsx` — 충돌이 없으면 그대로 둔다.
- [ ] `trip-create.test.tsx` — 충돌 구간에서:
  - develop의 `부산 전체` 활성화 대기를 **남긴다**
  - 커밋의 `travelAreasSpy` + `renderAppRoute` 이동 + enabled 대기를 **더한다**
  - develop이 이미 동등한 개선을 가진 hunk는 develop 쪽을 채택한다
- [ ] 충돌 마커(`<<<<<<<`)가 남아있지 않은지 grep으로 확인한다.

### Task 3: 타입 검사

- [ ] `npm run build` — `tsc` 통과 확인. 스파이 목 값의 타입이 맞는지 여기서 걸린다.

### Task 4: 전체 스위트 재실행

- [ ] `npx vitest run` 전체. **일부 파일만 돌리지 않는다** (이전에 부분 실행 기준선 때문에 `place-edit.test.tsx` 회귀를 놓친 적 있음).
- [ ] Task 1의 실패 이름 목록과 비교한다. 기대: `keeps the trip-attached state scoped to the selected policy`가 목록에서 사라져 **6건 이하**가 된다.
- [ ] `trip-create.test.tsx`의 `preselects a travelAreaId`는 이 저장소에서 코드와 무관하게 나타났다 사라지는 것이 확인된 테스트다. **등장해도 회귀로 보지 않고, 사라져도 성과로 세지 않는다.**
- [ ] 새로 생긴 실패가 있으면 **되돌리고 원인부터 조사한다.**

### Task 5: 커밋

- [ ] `git commit` (cherry-pick 이어서). 원 커밋 저자/메시지를 유지하되, develop과 다르게 해소한 부분을 커밋 메시지에 적는다.
- [ ] **push / PR은 하지 않는다.** Codex 담당.

---

## 검증

```
cd frontend
npx vitest run          # 전체. 실패 이름 목록 비교
npm run build           # tsc + 번들
```

**로컬 런타임 연결은 하지 않는다.** 이번 변경은 테스트 파일 전용이라 4173/8000에 반영될 프로덕션 코드가 없다. 사용자에게 브라우저 확인을 요청할 것도 없다.

---

## 하지 않을 것

- 프로덕션 코드 수정
- 남은 실패 테스트들의 일괄 수정 (범위 밖 — 별도 작업)
- 스위트 타이밍 한계 자체의 해결 (별도 작업)
- push / PR / merge
- 개발서버(192.168.32.15) 조작
