# 날짜 간 장소 이동 E2E 테스트

**목표:** 장소 카드를 Day 1에서 Day 2로 끌어 옮기는 동작을 Playwright로 자동 검증한다. 지금까지 매 세션 손으로 반복 확인하던 것을 대체한다.

**범위:** 새 스펙 파일 하나. **기존 `backend-mode.spec.ts`는 건드리지 않는다.**

---

## 왜 기존 스펙을 안 건드리는가

`test.describe.configure({ mode: "serial" })`는 **파일 단위**로 적용된다. 실측으로 확인했다 — 임시 스펙을 추가해 함께 돌리니 `backend-mode.spec.ts`가 실패하는 상태에서도 새 파일은 정상 실행·통과했다.

```
[1/13] __probe.spec.ts › probe: a new spec file runs …
4 passed · 1 failed · 8 did not run     ← probe 는 4 passed 안에 포함
```

따라서 옛 스펙의 낡음 3건(정책 URL, 초대 문구, 장소 수동 입력)을 먼저 고칠 필요가 없다. 그대로 두면 통과 중인 9개와 "백엔드에는 있는데 UI에서 사라진 기능" 신호도 함께 보존된다.

---

## 확인된 DOM

| 대상 | 셀렉터 |
|---|---|
| 드래그 손잡이 | `button.drag-handle`, `aria-label="{장소명} 순서 이동"` (`:4447`) |
| Day 탭 | `button.day-tab`, `aria-label="Day {n} {날짜}"`, `data-day-drop-id` (`:4211`) |
| Day 탭 영역 | `[data-itinerary-day-tabs]` (`:3527`) |
| 타임라인 | `[data-itinerary-timeline]` |
| 장소 추가 버튼 영역 | `[data-itinerary-actions]` |

### 센서 활성화 조건 — 테스트 성패를 가른다

`ItineraryDetailPage.tsx:1769`

```ts
useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 8 } }),
```

**마우스를 8px 넘게 움직여야 드래그가 시작된다.** `mouse.down()` 직후 `mouse.up()`을 하거나 한 번에 목적지로 순간이동하면 드래그가 아예 시작되지 않는다. `steps` 옵션으로 여러 번에 나눠 움직여야 한다.

> 이전 세션에서 브라우저 검증에 실패했던 이유가 여기다. 그때는 백그라운드 Chrome에서 `requestAnimationFrame`이 멈춰 드래그가 시작조차 안 됐고, 합성 이벤트를 `window`에 보냈는데 dnd-kit은 `document`에서 듣고 있었다. Playwright는 실제 브라우저에 신뢰된 이벤트를 보내므로 두 문제 모두 해당 없다.

---

## 파일

```
frontend/e2e-backend/itinerary-cross-day-drag.spec.ts   (신규)
```

`playwright.backend.config.ts`의 `testDir: "./e2e-backend"`가 이미 이 디렉터리를 잡으므로 설정 변경은 없다.

---

## Task 1: 픽스처 — 2일짜리 일정에 Day 1 장소 하나

**인터페이스 (기존 스펙에서 확인된 것 재사용)**

- 로그인: `test.user@example.com` / `password123`
- `POST {api}/api/auth/login` → `{ accessToken }`
- `POST {api}/api/trips` → 일정 생성
- `POST {api}/api/trips/{id}/days/1/places` → 장소 추가

- [ ] **Step 1: 기존 스펙의 헬퍼를 그대로 옮긴다**

`backend-mode.spec.ts`의 `login()` / `seedStoredAuth()`를 복사해 쓴다. **새로 짜지 않는다** — 이미 도는 것이 검증돼 있다.

- [ ] **Step 2: API로 일정과 장소를 만든다**

UI로 만들지 않는다. 장소 추가 시트는 지금 검색 후보 선택을 요구해 픽스처 구성이 무거워지고, **이번 테스트의 대상이 아니다.** `backend-mode.spec.ts:247`이 쓰는 방식(`page.request.post`)을 따른다.

---

## Task 2: 드래그 실행과 검증

- [ ] **Step 1: 실패 테스트 작성**

```ts
test("장소 카드를 Day 2 탭에 떨어뜨리면 그 날짜로 옮겨진다", async ({ page }) => {
  await page.goto(`/trips/${tripId}`);

  const card = page.getByRole("button", { name: `${placeLabel} 순서 이동` });
  await expect(card).toBeVisible();

  const dayTwoTab = page.locator('[data-day-drop-id]').nth(1);
  await expect(dayTwoTab).toBeVisible();

  const from = await card.boundingBox();
  const to = await dayTwoTab.boundingBox();
  if (!from || !to) throw new Error("드래그 대상의 위치를 잴 수 없다");

  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  // activationConstraint distance 8 을 넘겨야 드래그가 시작된다.
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2 - 20, { steps: 5 });
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 20 });
  await page.mouse.up();

  // Day 2 로 전환되고 그 날짜에 카드가 있어야 한다
  await expect(page.getByText(placeLabel)).toBeVisible();
});
```

- [ ] **Step 2: 실행해 실제 동작을 본다**

**이 단계가 이 계획의 핵심이다.** 위 코드가 첫 시도에 통과할 것으로 가정하지 않는다. dnd-kit 드래그는 마우스 경로·중간 지점·타이밍에 민감하다.

```bash
cd frontend
SKIP_E2E_DB_START=1 \
DATABASE_URL="postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter_e2e" \
E2E_API_PORT=8001 E2E_FRONTEND_PORT=5174 \
PYTHON="<repo>/backend/.venv/Scripts/python.exe" \
node scripts/run-backend-e2e.cjs itinerary-cross-day-drag --reporter=line
```

실패하면 **추측으로 좌표를 바꾸지 않는다.** 순서대로:

1. `--headed`로 눈으로 본다 (드래그가 시작은 되는가, 오버레이가 따라오는가)
2. `trace: "on-first-retry"`가 이미 켜져 있으니 `--retries=1`로 trace를 받아 이벤트를 확인한다
3. 그래도 안 되면 중간 경유점을 추가한다 (Day 탭 영역까지 위로 올린 뒤 가로 이동)

- [ ] **Step 3: 검증을 실제 상태로 강화한다**

`getByText(placeLabel)` 만으로는 약하다 — 드래그가 실패해도 Day 1에 그대로 있으면 통과할 수 있다. 통과가 확인되면 아래로 바꾼다.

- Day 2가 활성 탭인지 (`button.day-tab.active`가 Day 2)
- Day 1로 돌아가면 카드가 **없는지**
- 새로고침 후에도 유지되는지 (백엔드에 반영됐는지)

**세 번째가 가장 중요하다.** 화면만 바뀌고 서버에 저장이 안 되는 것이 실제로 있었던 버그다.

- [ ] **Step 4: 커밋**

```bash
git add frontend/e2e-backend/itinerary-cross-day-drag.spec.ts
git commit -m "Cover cross-day place drag with a backend-mode e2e test"
```

---

## 검증

```bash
cd frontend
npx tsc --noEmit
… node scripts/run-backend-e2e.cjs itinerary-cross-day-drag --reporter=line
```

기대: 1 passed. **기존 `backend-mode.spec.ts`의 결과는 이 작업 전후로 달라지지 않아야 한다** (3 passed / 1 failed / 8 did not run 유지).

### 격리 유지

| | |
|---|---|
| DB | `travelhunter_e2e` — 기존 `travelhunter` 무영향 |
| 포트 | 8001 / 5174 — 상시 런타임 8000 / 4173 무영향 |
| `SKIP_E2E_DB_START=1` | 안 하면 러너가 **돌고 있는 db 컨테이너를 재생성**할 수 있다 |
| `DATABASE_URL` 덮어쓰기 | 안 하면 러너가 **본 DB `travelhunter`에 시딩**한다 |

---

## 하지 않을 것

- `backend-mode.spec.ts` 수정 또는 삭제
- 옛 스펙의 낡음 3건 판단 (별도 사안으로 남긴다)
- 같은 날짜 안 순서 변경 / Day 탭 자동 전환 — 이번 것이 통과한 뒤
- Jenkins 파이프라인 수정
- WebKit / Firefox 추가
- 프로덕션 코드 수정
- 개발서버 조작, push / PR / merge
