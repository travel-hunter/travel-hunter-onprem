import { expect, Page, test } from "@playwright/test";

const seedUser = {
  email: "test.user@example.com",
  password: "password123",
};

const numericTripId = /^[1-9][0-9]*$/;
const apiBaseUrl = process.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";
const examplePolicySlug = "dgtour-\uC601\uAD11-8";
const examplePolicyPath = `/policies/${encodeURIComponent(examplePolicySlug)}`;
const examplePolicyOfficialUrl = "https://www.yeonggwang.go.kr/travel/";

async function login(page: Page) {
  await page.goto("/login");
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await page.locator('input[type="email"]').fill(seedUser.email);
  await page.locator('input[type="password"]').fill(seedUser.password);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/home$/);
}

async function seedStoredAuth(page: Page) {
  const response = await page.request.post(`${apiBaseUrl}/api/auth/login`, {
    data: seedUser,
  });
  expect(response.ok()).toBeTruthy();
  const auth = await response.json();
  await page.addInitScript((storedAuth) => {
    window.localStorage.setItem("travel-hunter-production-auth", JSON.stringify(storedAuth));
  }, auth);
  return auth as { accessToken: string };
}

test.describe.configure({ mode: "serial" });

test("backend data source requires login for protected routes", async ({ page }) => {
  await page.goto("/home");

  await expect(page).toHaveURL(/\/login\?redirect=%2Fhome$/);
  await expect(page.locator('input[type="email"]')).toBeVisible();
});

test("backend data source persists profile setup choices", async ({ page }) => {
  await login(page);

  await page.goto("/profile-setup");
  await page.getByRole("button", { name: "부산" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "맛집" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "1인 30만원 이하" }).click();
  await page.getByRole("button", { name: "추천 홈 보기" }).click();

  await expect(page).toHaveURL(/\/home$/);
  const homeAiCard = page.locator(".prototype-home-ai-card", { hasText: "맛집 코스 만들기" }).first();
  await expect(homeAiCard).toBeVisible();
  await expect(homeAiCard).toContainText("맛집 코스 만들기");

  await page.reload();
  await expect(homeAiCard).toContainText("맛집 코스 만들기");
});

test("backend data source drives policy, trip, recommendation, invite, and logout flow", async ({ page }) => {
  await login(page);

  await page.goto(examplePolicyPath);
  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.getByRole("link", { name: "혜택 안내 보기" })).toHaveAttribute(
    "href",
    examplePolicyOfficialUrl,
  );
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.locator(".toast")).toContainText("관심 정책");
  await expect(page.locator(".sticky-cta button").first()).toBeVisible();
  await page.locator(".sticky-cta button").first().click();
  const policyTripSheet = page.locator(".trip-select-sheet");
  await expect(policyTripSheet).toBeVisible();
  const policyTripRow = policyTripSheet.locator(".trip-select-row").first();
  const policyTripLabel = await policyTripRow.textContent();
  expect(policyTripLabel).toBeTruthy();
  await policyTripRow.click();
  await expect(page.locator(".toast")).toBeVisible();
  await policyTripSheet.locator("button", { hasText: "일정에서 보기" }).click();
  await expect(page).toHaveURL(/\/trips\/[1-9][0-9]*$/);

  await page.goto("/trips");
  const firstTrip = page.locator("article.itinerary-card").first();
  await expect(firstTrip).toBeVisible();
  const firstTripLink = firstTrip.locator('a[href^="/trips/"]').first();
  const tripHref = await firstTripLink.getAttribute("href");
  expect(tripHref).toMatch(/^\/trips\/[1-9][0-9]*$/);
  const tripId = tripHref?.split("/").pop() ?? "";
  expect(tripId).toMatch(numericTripId);

  await firstTripLink.click();
  await expect(page).toHaveURL(new RegExp(`/trips/${tripId}$`));
  await expect(page.locator(".prototype-trip-action-ai")).toBeVisible();
  await page.locator(".prototype-trip-action-ai").click();
  await expect(page.locator(".recommendation-preview-banner")).toBeVisible();
  const previewLayout = await page.evaluate(() => {
    const actions = document.querySelector(".trip-primary-actions");
    const preview = document.querySelector(".recommendation-preview-banner");
    const dayTabs = document.querySelector(".day-tabs");
    if (!actions || !preview || !dayTabs) return null;
    const actionsRect = actions.getBoundingClientRect();
    const previewRect = preview.getBoundingClientRect();
    const dayTabsRect = dayTabs.getBoundingClientRect();
    const actionsStyle = window.getComputedStyle(actions);
    const previewStyle = window.getComputedStyle(preview);
    return {
      orderIsActionsPreviewTabs:
        actionsRect.bottom <= previewRect.top && previewRect.bottom <= dayTabsRect.top,
      alignedLeft: Math.round(actionsRect.left) === Math.round(previewRect.left),
      alignedRight: Math.round(actionsRect.right) === Math.round(previewRect.right),
      actionMarginLeft: actionsStyle.marginLeft,
      previewMarginLeft: previewStyle.marginLeft,
      previewRadius: previewStyle.borderRadius,
    };
  });
  expect(previewLayout).toMatchObject({
    orderIsActionsPreviewTabs: true,
    alignedLeft: true,
    alignedRight: true,
    actionMarginLeft: "16px",
    previewMarginLeft: "16px",
    previewRadius: "10px",
  });
  await page.goto(`/trips/${tripId}`);

  await page.goto(`/friend-invite?tripId=${tripId}`);
  const ownerInviteLink = page.locator(".invite-link").first();
  await expect(ownerInviteLink).toBeVisible();
  await expect(ownerInviteLink.locator("span")).toContainText(`/invites/`);
  await expect(ownerInviteLink.locator("span")).toContainText(`/accept`);
  const copyInviteLinkButton = page.getByRole("button", { name: /링크 복사/ }).first();
  await expect(copyInviteLinkButton).toBeVisible();
  await copyInviteLinkButton.click();
  await expect(page.getByRole("button", { name: "보기만 가능 링크 준비 완료" })).toBeVisible();

  await page.goto("/mypage");
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("policy filter toolbar stays usable within the mobile list screen", async ({ page }) => {
  await seedStoredAuth(page);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/policies");
  const listScreen = page.locator(".prototype-policy-list-screen");
  const toolbar = listScreen.locator(".prototype-policy-toolbar");
  const searchRow = listScreen.locator(".prototype-policy-search-row");
  const resultRow = listScreen.locator(".prototype-policy-result-row");

  await expect(toolbar).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "정책 검색" })).toBeVisible();
  await expect(page.getByRole("button", { name: "필터 열기" })).toBeVisible();
  await expect(resultRow).toBeVisible();

  const layout = await searchRow.evaluate((element) => {
    const screen = element.closest(".prototype-policy-list-screen");
    const style = window.getComputedStyle(element);
    return {
      display: style.display,
      screenClientWidth: screen?.clientWidth ?? 0,
      screenScrollWidth: screen?.scrollWidth ?? 0,
      searchRowClientWidth: element.clientWidth,
      searchRowScrollWidth: element.scrollWidth,
    };
  });

  expect(layout.display).toBe("grid");
  expect(layout.screenScrollWidth - layout.screenClientWidth).toBeLessThanOrEqual(1);
  expect(layout.searchRowScrollWidth - layout.searchRowClientWidth).toBeLessThanOrEqual(1);
});

test("policy detail sticky CTA stays attached above bottom tabs while scrolling", async ({ page }) => {
  await seedStoredAuth(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(examplePolicyPath);
  const cta = page.locator(".prototype-policy-detail-screen .sticky-cta");
  const bottomTabs = page.locator(".bottom-tabs");
  await expect(cta).toBeVisible();
  await expect(bottomTabs).toBeVisible();

  await page.locator(".app-container").evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });

  const layout = await page.evaluate(() => {
    const ctaElement = document.querySelector(".prototype-policy-detail-screen .sticky-cta");
    const bottomTabsElement = document.querySelector(".bottom-tabs");
    if (!ctaElement || !bottomTabsElement) return null;
    const ctaRect = ctaElement.getBoundingClientRect();
    const bottomTabsRect = bottomTabsElement.getBoundingClientRect();
    return {
      gap: Math.round(bottomTabsRect.top - ctaRect.bottom),
    };
  });

  expect(Math.abs(layout?.gap ?? Number.POSITIVE_INFINITY)).toBeLessThanOrEqual(1);
});

test("confirmed trip detail keeps owner editing controls available", async ({ page }) => {
  const auth = await seedStoredAuth(page);
  const createResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
    headers: { Authorization: `Bearer ${auth.accessToken}` },
    data: {
      title: "확정 잠금 e2e 여행",
      region: "부산",
      style: "맛집",
      startDate: "2026-07-12",
      endDate: "2026-07-14",
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const createdTrip = await createResponse.json();
  const tripId = String(createdTrip.id);
  expect(tripId).toMatch(numericTripId);

  const addPlaceResponse = await page.request.post(`${apiBaseUrl}/api/trips/${tripId}/days/1/places`, {
    headers: { Authorization: `Bearer ${auth.accessToken}` },
    data: {
      expectedRevision: 1,
      time: "10:00",
      label: "광안리 테스트 장소",
      meta: "E2E 편집 컨트롤 확인",
    },
  });
  expect(addPlaceResponse.ok()).toBeTruthy();

  const confirmResponse = await page.request.patch(`${apiBaseUrl}/api/trips/${tripId}/status`, {
    headers: { Authorization: `Bearer ${auth.accessToken}` },
    data: { status: "confirmed" },
  });
  expect(confirmResponse.ok()).toBeTruthy();
  const confirmedTrip = await confirmResponse.json();
  expect(confirmedTrip.status).toBe("confirmed");

  await page.goto(`/trips/${tripId}`);
  await expect(page.locator(".trip-status-panel")).toHaveCount(0);
  await expect(page.locator(".prototype-trip-action-add")).toBeVisible();
  await expect(page.locator(".drag-handle").first()).toBeVisible();
});

test("empty trip detail saves a manual label-only place through the backend", async ({ page }) => {
  const auth = await seedStoredAuth(page);
  const authHeaders = { Authorization: `Bearer ${auth.accessToken}` };
  const manualPlaceLabel = `수동 저장 e2e 장소 ${Date.now()}`;
  const createResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
    headers: authHeaders,
    data: {
      title: "빈 일정 수동 저장 e2e 여행",
      region: "제주",
      style: "휴식",
      startDate: "2026-08-11",
      endDate: "2026-08-13",
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const tripId = String((await createResponse.json()).id);
  expect(tripId).toMatch(numericTripId);

  await page.route(`**/api/trips/${tripId}/place-search**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    });
  });

  for (const width of [390, 1024]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 768 });
    await page.goto(`/trips/${tripId}`);
    await expect(page.getByText("아직 표시할 장소가 없어요")).toBeVisible();
    await expectNoDocumentOverflow(page);
  }

  for (const width of [360, 390, 430, 1024, 1440]) {
    await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
    await page.goto(`/trips/${tripId}`);
    await page.getByRole("button", { name: /장소 추가/ }).click();
    const responsiveSheet = page.locator(".trip-select-sheet");
    await expect(responsiveSheet).toBeVisible();
    await expect(responsiveSheet.getByLabel("장소 지도 미리보기")).toBeVisible();
    await expectNoDocumentOverflow(page);
    await responsiveSheet.getByRole("button", { name: "닫기" }).click();
    await expect(responsiveSheet).toHaveCount(0);
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/trips/${tripId}`);
  await page.getByRole("button", { name: /장소 추가/ }).click();
  const sheet = page.locator(".trip-select-sheet");
  await expect(sheet).toBeVisible();
  await sheet.locator('input[name="place-search"]').fill("후보없는수동장소");
  await expect(sheet.getByText("검색 결과가 없어요")).toBeVisible();
  await expectNoDocumentOverflow(page);

  await sheet.locator('input[name="place-label"]').fill(manualPlaceLabel);
  await sheet.locator('textarea[name="place-meta"]').fill("좌표 없이 리스트에 저장");
  await sheet.getByRole("button", { name: "저장하기" }).click();

  await expect(sheet).toHaveCount(0);
  await expect(page.getByText(manualPlaceLabel).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText(manualPlaceLabel).first()).toBeVisible();
  await expectNoDocumentOverflow(page);
});

test("core app screens do not horizontally overflow at common responsive widths", async ({ page }) => {
  await seedStoredAuth(page);

  const widths = [360, 390, 430, 1024, 1440];
  const staticScreens = [
    { path: "/home", selector: ".prototype-home-screen" },
    { path: "/policies", selector: ".prototype-policy-list-screen" },
    { path: "/trips/new", selector: ".prototype-create-content" },
    { path: "/mypage", selector: ".prototype-mypage-screen" },
  ];

  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });

    for (const screen of staticScreens) {
      await page.goto(screen.path);
      await expect(page.locator(screen.selector)).toBeVisible();
      await expectNoDocumentOverflow(page);
    }

    await page.goto("/trips");
    const firstTripLink = page.locator('article.itinerary-card a[href^="/trips/"]').first();
    await expect(firstTripLink).toBeVisible();
    const tripHref = await firstTripLink.getAttribute("href");
    expect(tripHref).toMatch(/^\/trips\/[1-9][0-9]*$/);
    await page.goto(tripHref ?? "/trips");
    await expect(page.locator(".prototype-trip-detail-screen")).toBeVisible();
    await expectNoDocumentOverflow(page);
  }
});

test("home recommendation starts a new trip and reaches policy navigation", async ({ page }) => {
  await seedStoredAuth(page);

  await page.goto("/home");
  const aiTripCard = page.getByRole("link", { name: /맛집 코스 만들기/ }).first();
  await expect(aiTripCard).toBeVisible();
  await expect(aiTripCard).toHaveAttribute("href", /\/trips\/new\?region=/);

  await aiTripCard.click();
  await expect(page).toHaveURL(/\/trips\/new\?region=/);
  await expect(page.getByRole("heading", { name: "여행 지역 선택" })).toBeVisible();
  const firstTravelArea = page.locator(".prototype-travel-area-card").first();
  await expect(firstTravelArea).toBeVisible();
  await firstTravelArea.click();
  await page.getByRole("button", { name: "다음" }).click();

  await expect(page.getByRole("heading", { name: "여행 정보를 한 번에 확인해요" })).toBeVisible();
  await page.locator('input[name="trip-title"]').fill("홈 추천 smoke 여행");
  await page.locator('input[type="date"]').nth(0).fill("2026-07-12");
  await page.locator('input[type="date"]').nth(1).fill("2026-07-14");
  await page.getByRole("button", { name: "확인하고 만들기" }).click();

  await expect(page).toHaveURL(/\/trips\/[1-9][0-9]*$/);
  await expect(page.locator(".day-tab").first()).toBeVisible();
  const policyNavigationLink = page.locator('.prototype-matching-policy-card[href^="/policies"]').first();
  await expect(policyNavigationLink).toBeVisible();
  const policyHref = await policyNavigationLink.getAttribute("href");
  expect(policyHref).toMatch(/^\/policies(?:\/.+)?$/);
  await policyNavigationLink.click();
  await expect(page).toHaveURL(/\/policies(?:\/.+)?$/);
  await expect(page.locator("#root")).not.toBeEmpty();
});

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => Math.ceil(document.documentElement.scrollWidth - document.documentElement.clientWidth));
  expect(overflow).toBeLessThanOrEqual(1);
}

test("backend data source creates a trip with selected profile values and policy slug", async ({ page }) => {
  await login(page);

  const travelAreaResponse = await page.request.get(
    `${apiBaseUrl}/api/recommendations/travel-areas?sido=${encodeURIComponent("부산")}&limit=1`,
  );
  expect(travelAreaResponse.ok()).toBeTruthy();
  const travelAreaItems = ((await travelAreaResponse.json()) as {
    items: { travelAreaId: string }[];
  }).items;
  expect(travelAreaItems.length).toBeGreaterThan(0);
  const travelAreaId = travelAreaItems[0].travelAreaId;

  await page.goto(
    `/trips/new?policySlug=${encodeURIComponent(examplePolicySlug)}&region=${encodeURIComponent("부산")}&travelAreaId=${encodeURIComponent(travelAreaId)}`,
  );
  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.getByRole("heading", { name: "여행 정보를 한 번에 확인해요" })).toBeVisible();
  await page.locator('input[name="trip-title"]').fill("부산 e2e 여행");
  await page.locator('input[type="date"]').nth(0).fill("2026-07-12");
  await page.locator('input[type="date"]').nth(1).fill("2026-07-15");
  await page.getByRole("button", { name: "확인하고 만들기" }).click();
  await expect(page).toHaveURL(/\/trips\/[1-9][0-9]*$/);
  const createdTripId = page.url().split("/").pop() ?? "";
  expect(createdTripId).toMatch(numericTripId);
  await expect(page.locator(".day-tab").first()).toBeVisible();
  await expect(page.locator("body")).toContainText("영광 디지털관광주민증 혜택");
  await expect(page.getByText("아직 표시할 장소가 없어요")).toBeVisible();
  await expect(page.getByRole("button", { name: /추천 일정만들기/ })).toBeVisible();
  await expect(page.locator(".timeline-item")).toHaveCount(0);

  await page.goto(`/ai-results?tripId=${createdTripId}`);
  await expect(page.locator(".prototype-trip-detail-screen")).toBeVisible();
  await expect(page.locator(".prototype-trip-action-ai")).toBeVisible();

  await page.goto(`/friend-invite?tripId=${createdTripId}`);
  await expect(page.locator(".invite-link").first()).toBeVisible();
});

test("normalized policy save, unsave, trip link, and unlink stay consistent on my page", async ({ page }) => {
  const auth = await seedStoredAuth(page);
  const authHeaders = { Authorization: `Bearer ${auth.accessToken}` };

  // Normalize to a known-unsaved baseline so this test is independent of serial order.
  await page.request.delete(
    `${apiBaseUrl}/api/me/saved-policies/${encodeURIComponent(examplePolicySlug)}`,
    { headers: authHeaders },
  );

  // A dedicated, uniquely-named trip isolates the link/unlink legs from other
  // serial tests and from leftover trips in a reused database across runs.
  const tripTitle = `정책 연결 스모크 ${Date.now()}`;
  const tripResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
    headers: authHeaders,
    data: {
      title: tripTitle,
      region: "부산",
      style: "맛집",
      startDate: "2026-08-01",
      endDate: "2026-08-03",
    },
  });
  expect(tripResponse.ok()).toBeTruthy();
  const tripId = String((await tripResponse.json()).id);
  expect(tripId).toMatch(numericTripId);

  // Capture the live policy title to drive title-based selectors below.
  await page.goto(examplePolicyPath);
  await expect(page.locator(".prototype-policy-detail-screen")).toBeVisible();
  const saveToggle = page.getByRole("button", { name: "저장" });
  const heartIcon = saveToggle.locator("svg").first();
  const policyTitle = (
    await page.locator(".prototype-policy-detail-screen h1").first().textContent()
  )?.trim();
  expect(policyTitle).toBeTruthy();
  const linkedTitle = policyTitle as string;

  // Save toggles only once the session has loaded the unsaved baseline.
  await expect(heartIcon).toHaveAttribute("fill", "none");
  await saveToggle.click();
  await expect(page.locator(".toast")).toContainText("관심 정책");

  // My page favorite list reflects the saved policy.
  await page.goto("/mypage");
  await expect(
    page
      .getByRole("region", { name: "즐겨찾기 정책" })
      .locator("article.ds-favorite-policy-card", { hasText: linkedTitle }),
  ).toBeVisible();

  // Unsave toggles only once the session has loaded the saved state.
  await page.goto(examplePolicyPath);
  await expect(heartIcon).toHaveAttribute("fill", "currentColor");
  await saveToggle.click();
  await expect(page.locator(".toast")).toContainText("해제");

  // My page favorite list drops the unsaved policy.
  await page.goto("/mypage");
  await expect(
    page
      .getByRole("region", { name: "즐겨찾기 정책" })
      .locator("article.ds-favorite-policy-card", { hasText: linkedTitle }),
  ).toHaveCount(0);

  // Link the normalized policy to the dedicated trip from the policy detail CTA.
  await page.goto(examplePolicyPath);
  await page.locator(".sticky-cta button").first().click();
  const tripSheet = page.locator(".trip-select-sheet");
  await expect(tripSheet).toBeVisible();
  await tripSheet.locator(".trip-select-row", { hasText: tripTitle }).click();
  const viewTripButton = tripSheet.locator("button", { hasText: "일정에서 보기" });
  await expect(viewTripButton).toBeVisible();
  await viewTripButton.click();
  await expect(page).toHaveURL(new RegExp(`/trips/${tripId}$`));

  // Trip detail shows the linked policy.
  const linkedRegion = page.getByRole("region", { name: "연결된 정책" });
  await expect(linkedRegion.getByText(linkedTitle)).toBeVisible();

  // Unlink removes it from the trip detail linked-policy region.
  await linkedRegion.getByRole("button", { name: `${linkedTitle} 연결 삭제` }).click();
  await expect(
    page.getByRole("region", { name: "연결된 정책" }).getByText(linkedTitle),
  ).toHaveCount(0);
});
