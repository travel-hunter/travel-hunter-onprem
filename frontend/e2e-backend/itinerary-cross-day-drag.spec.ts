import { expect, Page, test } from "@playwright/test";

const seedUser = {
  email: "test.user@example.com",
  password: "password123",
};

const apiBaseUrl = process.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";
const placeLabel = "날짜이동 e2e 장소";

async function seedStoredAuth(page: Page) {
  const response = await page.request.post(`${apiBaseUrl}/api/auth/login`, {
    data: seedUser,
  });
  expect(response.ok()).toBeTruthy();
  const auth = await response.json();
  await page.addInitScript((storedAuth) => {
    window.localStorage.setItem(
      "travel-hunter-production-auth",
      JSON.stringify(storedAuth),
    );
  }, auth);
  return auth as { accessToken: string };
}

/**
 * Day 1 에 장소 하나가 있는 3일짜리 일정을 API 로 만든다.
 *
 * 장소 추가 시트는 검색 후보를 명시적으로 고를 것을 요구하므로 UI 로 픽스처를
 * 구성하면 무거워지고, 그건 이 테스트의 대상이 아니다.
 */
async function createTripWithOnePlaceOnDayOne(page: Page, accessToken: string) {
  const createResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: {
      title: "날짜 간 드래그 e2e 여행",
      region: "부산",
      style: "맛집",
      startDate: "2026-07-12",
      endDate: "2026-07-14",
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const tripId = String((await createResponse.json()).id);

  const addPlaceResponse = await page.request.post(
    `${apiBaseUrl}/api/trips/${tripId}/days/1/places`,
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: {
        expectedRevision: 1,
        time: "10:00",
        label: placeLabel,
        meta: "Day 1 에서 Day 2 로 옮길 카드",
      },
    },
  );
  expect(addPlaceResponse.ok()).toBeTruthy();

  return tripId;
}

/**
 * dnd-kit 드래그를 실제 마우스 입력으로 구동한다.
 *
 * MouseSensor 의 activationConstraint 가 { distance: 8 } 이라 8px 를 넘겨야
 * 드래그가 시작된다 (ItineraryDetailPage.tsx:1770). 한 번에 목적지로
 * 순간이동하면 시작 자체가 안 되므로 steps 로 나눠 움직인다.
 */
async function dragTo(page: Page, from: { x: number; y: number }, to: { x: number; y: number }) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(from.x, from.y - 24, { steps: 6 });
  await page.mouse.move(to.x, to.y, { steps: 24 });
  await page.mouse.move(to.x, to.y, { steps: 2 });
  await page.mouse.up();
}

/**
 * 뷰포트 안으로 끌어온 뒤 중심 좌표를 잰다.
 *
 * 뷰포트가 390x844 라 장소 카드는 대개 화면 아래에 있다. 스크롤 없이 재면
 * boundingBox 는 뷰포트 밖 좌표를 주고, 그 지점에는 아무 요소도 없어서
 * mouse.down 이 손잡이에 닿지 않는다 (elementFromPoint 가 null 을 준다).
 * 드래그가 시작조차 안 되므로 반드시 먼저 스크롤한다.
 */
async function centerOf(target: ReturnType<Page["locator"]>) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) throw new Error("드래그 대상의 위치를 잴 수 없다");
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test("장소 카드를 Day 2 탭에 떨어뜨리면 그 날짜로 옮겨진다", async ({ page }) => {
  const auth = await seedStoredAuth(page);
  const tripId = await createTripWithOnePlaceOnDayOne(page, auth.accessToken);

  await page.goto(`/trips/${tripId}`);

  const handle = page.getByRole("button", { name: `${placeLabel} 순서 이동` });
  await expect(handle).toBeVisible();

  const dayTabs = page.locator("[data-day-drop-id]");
  await expect(dayTabs).toHaveCount(3);
  const dayTwoTab = dayTabs.nth(1);

  // 손잡이를 먼저 재고 스크롤한 뒤에 탭 좌표를 잰다. 순서를 바꾸면
  // 스크롤 때문에 탭 좌표가 어긋난다.
  const from = await centerOf(handle);
  const to = await centerOf(dayTwoTab);
  await dragTo(page, from, to);

  // getByText 는 지도 핀 라벨(span)까지 잡으므로 타임라인 카드 제목만 본다.
  const cardTitle = page.getByRole("heading", { name: placeLabel });

  // 1) 화면이 Day 2 로 넘어가고 카드가 거기에 있다
  await expect(dayTwoTab).toHaveClass(/\bactive\b/);
  await expect(cardTitle).toBeVisible();

  // 2) Day 1 에는 더 이상 없다
  await dayTabs.nth(0).click();
  await expect(dayTabs.nth(0)).toHaveClass(/\bactive\b/);
  await expect(cardTitle).toHaveCount(0);

  // 3) 새로고침해도 유지된다 — 화면만 바뀌고 서버에 저장 안 되는 것이 실제 버그였다
  await page.reload();
  await expect(page.locator("[data-day-drop-id]").nth(1)).toBeVisible();
  await page.locator("[data-day-drop-id]").nth(1).click();
  await expect(page.getByRole("heading", { name: placeLabel })).toBeVisible();
});
