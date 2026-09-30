import { expect, Page, test } from "@playwright/test";

const seedUser = {
  email: "test.user@example.com",
  password: "password123",
};

const numericTripId = /^[1-9][0-9]*$/;
const apiBaseUrl = process.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";
const examplePolicySlug = "dgtour-\uC601\uAD11";
const examplePolicyPath = `/policies/${encodeURIComponent(examplePolicySlug)}`;

function isoDateFromToday(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

async function apiAuthHeaders(page: Page) {
  const response = await page.request.post(`${apiBaseUrl}/api/auth/login`, { data: seedUser });
  expect(response.ok()).toBeTruthy();
  return { Authorization: `Bearer ${(await response.json()).accessToken}` };
}

/* 예시 정책(영광, 전남)은 지역이 맞는 일정에만 담기고(PR #77), 정책 담기 창은 끝나지 않은 일정만 보여 준다.
   그래서 담기를 시험하는 일정은 전남 전체 권역으로, 오늘 기준 앞날로 만든다. 권역 id 는 카탈로그에서 읽는다. */
async function createUpcomingJeonnamTrip(page: Page, authHeaders: Record<string, string>, title: string) {
  const catalogResponse = await page.request.get(
    `${apiBaseUrl}/api/travel-areas?sido=${encodeURIComponent("전남")}`,
    { headers: authHeaders },
  );
  expect(catalogResponse.ok()).toBeTruthy();
  const travelAreaId = (await catalogResponse.json()).wholeArea.travelAreaId as string;
  const tripResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
    headers: authHeaders,
    data: {
      title,
      region: "전남",
      travelAreaId,
      style: "맛집",
      startDate: isoDateFromToday(30),
      endDate: isoDateFromToday(32),
    },
  });
  expect(tripResponse.ok()).toBeTruthy();
  const tripId = String((await tripResponse.json()).id);
  expect(tripId).toMatch(numericTripId);
  return tripId;
}

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

test("login page remains scrollable in short mobile browser viewports", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 560 });
  await page.goto("/login");

  await expect(page.getByRole("button", { name: "로그인" })).toBeVisible();
  await expect(page.getByRole("link", { name: "카카오로 시작하기" })).toBeVisible();

  const scrollBefore = await page.evaluate(() => ({
    documentClientHeight: document.documentElement.clientHeight,
    documentScrollHeight: document.documentElement.scrollHeight,
    mainOverflowY: window.getComputedStyle(document.querySelector(".prototype-login-layout") as Element).overflowY,
    containerOverflowY: window.getComputedStyle(document.querySelector(".prototype-login-container") as Element).overflowY,
    screenOverflowY: window.getComputedStyle(document.querySelector(".prototype-login-screen") as Element).overflowY,
  }));

  expect(scrollBefore.documentScrollHeight).toBeGreaterThan(scrollBefore.documentClientHeight);
  expect(scrollBefore.mainOverflowY).toBe("auto");
  expect(scrollBefore.containerOverflowY).toBe("visible");
  expect(scrollBefore.screenOverflowY).toBe("visible");

  await page.getByRole("link", { name: "구글로 시작하기" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("link", { name: "구글로 시작하기" })).toBeVisible();
});

test("backend data source persists profile setup choices", async ({ page }) => {
  await login(page);

  await page.goto("/profile-setup");
  // 지역 칸은 누를 때마다 켜고 끈다. 앞선 실행(또는 같은 DB 를 쓰는 vitest)이 부산을 이미 저장해 두었으면
  // 한 번 더 누르는 순간 빠진다 - 꺼져 있을 때만 누른다.
  const busanButton = page.getByRole("button", { name: "부산" });
  await expect(busanButton).toBeVisible();
  if ((await busanButton.getAttribute("aria-pressed")) !== "true") await busanButton.click();
  await expect(busanButton).toHaveAttribute("aria-pressed", "true");
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
  const authHeaders = await apiAuthHeaders(page);
  // 로컬 DB 는 개발서버 수집본이라 시드와 공식 주소가 다를 수 있다. 화면은 API 가 준 주소를 그대로 걸어야 한다.
  const policyResponse = await page.request.get(
    `${apiBaseUrl}/api/policies/${encodeURIComponent(examplePolicySlug)}`,
  );
  expect(policyResponse.ok()).toBeTruthy();
  const examplePolicyOfficialUrl = (await policyResponse.json()).officialUrl as string;
  const tripTitle = `정책 담기 e2e ${Date.now()}`;
  await createUpcomingJeonnamTrip(page, authHeaders, tripTitle);

  await page.goto(examplePolicyPath);
  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.getByRole("link", { name: "혜택 안내 보기" })).toHaveAttribute(
    "href",
    examplePolicyOfficialUrl,
  );
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.locator(".toast")).toContainText("관심 정책");
  const policyTripButton = page.getByRole("button", { name: /내 일정에 담기|일정에 담김/ });
  await expect(policyTripButton).toBeVisible();
  await policyTripButton.click();
  const policyTripSheet = page.locator(".trip-select-sheet");
  await expect(policyTripSheet).toBeVisible();
  await policyTripSheet.locator(".trip-select-row", { hasText: tripTitle }).click();
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
  // 초대는 함께 편집 링크 하나다(1a007ee Make friend invites editor-only)
  await expect(page.getByRole("button", { name: "함께 편집 링크 준비 완료" })).toBeVisible();

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
  /* 지도 화면은 건수 줄 대신 혜택 형태 칩 줄과 지도 뒤 목록 시트(머리가 건수를 말한다) */
  const chipRow = page.getByRole("group", { name: "혜택 형태" });

  await expect(toolbar).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "정책 검색" })).toBeVisible();
  await expect(page.getByRole("button", { name: "필터 열기" })).toBeVisible();
  await expect(chipRow).toBeVisible();
  await expect(page.locator(".thmap-sheet .thmap-title")).toContainText("모든 지역");

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

test("policy detail action bar replaces the bottom tabs and stays at the bottom while scrolling", async ({ page }) => {
  await seedStoredAuth(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(examplePolicyPath);
  const bar = page.locator(".prototype-policy-detail-screen .policy-detail-bar");
  await expect(bar).toBeVisible();
  await expect(bar.getByRole("button", { name: /내 일정에 담기|일정에 담김/ })).toBeVisible();
  // 상세에서는 탭바를 가리고 그 자리에 버튼 줄을 둔다
  await expect(page.locator(".bottom-tabs")).toBeHidden();

  for (const position of ["top", "bottom"] as const) {
    await page.evaluate((where) => {
      const scroller = document.querySelector(".app-container");
      const top = where === "top" ? 0 : Number.MAX_SAFE_INTEGER;
      scroller?.scrollTo({ top });
      window.scrollTo({ top });
    }, position);
    const gap = await page.evaluate(() => {
      const barElement = document.querySelector(".prototype-policy-detail-screen .policy-detail-bar");
      return barElement ? Math.round(window.innerHeight - barElement.getBoundingClientRect().bottom) : null;
    });
    expect(Math.abs(gap ?? Number.POSITIVE_INFINITY)).toBeLessThanOrEqual(1);
  }
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

test("empty trip detail opens the place sheet at common widths and explains an empty search", async ({ page }) => {
  const auth = await seedStoredAuth(page);
  const authHeaders = { Authorization: `Bearer ${auth.accessToken}` };
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
  // 장소 추가는 검색 후보를 담아 저장하는 방식이다. 이름만 적어 넣는 칸은 편집 모드에만 있다(2026-08-25 fcf797f).
  await expect(sheet.locator('input[name="place-label"]')).toHaveCount(0);
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
  // 지역 고르기는 편집 화면과 같은 선택기(6e5b4ee). 시도 전체가 기본으로 골라져 있다.
  const firstTravelArea = page.locator(".trip-region-selector__area").first();
  await expect(firstTravelArea).toBeVisible();
  await firstTravelArea.click();
  await page.getByRole("button", { name: "다음" }).click();

  await expect(page.getByRole("heading", { name: /여행 정보를 확인해요$/ })).toBeVisible();
  await page.locator('input[name="trip-title"]').fill("홈 추천 smoke 여행");
  await page.locator('input[type="date"]').nth(0).fill(isoDateFromToday(20));
  await page.locator('input[type="date"]').nth(1).fill(isoDateFromToday(22));
  await page.getByRole("button", { name: "일정 생성" }).click();

  await expect(page).toHaveURL(/\/trips\/[1-9][0-9]*$/);
  await expect(page.locator(".day-tab").first()).toBeVisible();
  const policyNavigationLink = page.locator('.prototype-matching-policy-card[href^="/policies"]').first();
  await expect(policyNavigationLink).toBeVisible();
  const policyHref = await policyNavigationLink.getAttribute("href");
  // 정책 탭으로 가는 길은 일정의 시도를 골라 둔 지도(?place=…&sheet=1)일 수 있다
  expect(policyHref).toMatch(/^\/policies(?:\/[^?]+)?(?:\?.*)?$/);
  await policyNavigationLink.click();
  await expect(page).toHaveURL(/\/policies(?:\/[^?]+)?(?:\?.*)?$/);
  await expect(page.locator("#root")).not.toBeEmpty();
});

async function expectNoDocumentOverflow(page: Page) {
  const overflow = await page.evaluate(() => Math.ceil(document.documentElement.scrollWidth - document.documentElement.clientWidth));
  expect(overflow).toBeLessThanOrEqual(1);
}

test("backend data source creates a trip with selected profile values and policy slug", async ({ page }) => {
  await login(page);

  // 정책 상세의 '새 일정에 담기'가 만드는 주소 그대로(영광 정책 → 영광·전남). 지역이 다른 일정은 서버가 거절한다(PR #77).
  await page.goto(
    `/trips/new?policySlug=${encodeURIComponent(examplePolicySlug)}&region=${encodeURIComponent("영광")}&sido=${encodeURIComponent("전남")}`,
  );
  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.getByRole("heading", { name: /여행 정보를 확인해요$/ })).toBeVisible();
  await page.locator('input[name="trip-title"]').fill("영광 e2e 여행");
  await page.locator('input[type="date"]').nth(0).fill(isoDateFromToday(20));
  await page.locator('input[type="date"]').nth(1).fill(isoDateFromToday(23));
  await page.getByRole("button", { name: "일정 생성" }).click();
  await expect(page).toHaveURL(/\/trips\/[1-9][0-9]*$/);
  const createdTripId = page.url().split("/").pop() ?? "";
  expect(createdTripId).toMatch(numericTripId);
  await expect(page.locator(".day-tab").first()).toBeVisible();
  // 시드 제목은 '영광 …', 개발서버 수집본은 '[영광] …'
  await expect(page.locator("body")).toContainText(/영광\]? 디지털관광주민증 혜택/);
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
  const tripId = await createUpcomingJeonnamTrip(page, authHeaders, tripTitle);

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
  await page.getByRole("button", { name: /내 일정에 담기|일정에 담김/ }).click();
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
  // 연결에는 신청 진행 기록이 붙어 있어 바로 지우지 않고 확인 창을 거친다.
  await linkedRegion.getByRole("button", { name: `${linkedTitle} 연결 삭제` }).click();
  await page.getByRole("dialog", { name: "이 정책을 일정에서 뺄까요?" }).getByRole("button", { name: "빼기" }).click();
  await expect(
    page.getByRole("region", { name: "연결된 정책" }).getByText(linkedTitle),
  ).toHaveCount(0);
});
