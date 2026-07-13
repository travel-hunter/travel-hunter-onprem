import type { Policy, TravelAreaRecommendationResponse, Trip, User } from "../api";

export const testEmail = "test.user@example.com";
export const testPassword = "password123";
export const examplePolicySlug = "dgtour-영광-8";
export const examplePolicyPath = `/policies/${encodeURIComponent(examplePolicySlug)}`;
export const examplePolicyTitle =
  "영광 디지털관광주민증 혜택";
export const examplePolicyDetail: Policy = {
  id: examplePolicySlug,
  slug: examplePolicySlug,
  label: "전남",
  tag: "지역할인",
  title: examplePolicyTitle,
  org: "한국관광공사",
  region: "전남",
  deadline: "2026-08-31",
  amount: "혜택 제공",
  summary: "디지털관광주민증 또는 대한민국 반값여행을 통해 신청 가능한 영광 방문 혜택을 확인할 수 있습니다.",
  match: 75,
  category: "지역할인",
  requirements: [
    "디지털관광주민증 발급 또는 지역별 신청 조건 확인",
    "전남 영광 방문",
  ],
  documents: ["디지털관광주민증 또는 지역별 신청 확인"],
  officialUrl: "https://www.yeonggwang.go.kr/travel/",
  applyUrl: null,
  sourceType: "external",
};

export function testIsoDateFromToday(daysFromToday: number) {
  const date = new Date(Date.now() + daysFromToday * 86_400_000);
  return date.toISOString().slice(0, 10);
}

export function getPreviewTrip(): Trip {
  return {
    id: "21",
    title: "부산 여행 1",
    status: "confirmed",
    revision: 1,
    dates: "2026.06.12 - 06.13",
    people: ["여행자"],
    participantCount: 1,
    expectedSaving: "0원",
    linkedPolicies: [],
    recommendedPolicies: [],
    days: {
      1: [{ id: "101", time: "09:00", label: "도착", meta: "오전" }],
      2: [{ id: "102", time: "10:00", label: "일정", meta: "점심" }],
    },
    currentUserRole: "owner",
  };
}

export function getGangwonTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "sido",
    sido: "강원",
    query: null,
    emptyReason: null,
    items: [
      {
        travelAreaId: "gangwon-sokcho-goseong-yangyang",
        travelAreaName: "속초·고성·양양",
        sido: "강원",
        includedCities: ["속초", "고성", "양양"],
        summary: "바다와 설악산, 감성 카페를 함께 즐기는 동해 북부 권역",
        tags: ["바다", "산", "카페", "2박3일"],
        reason: "강원 지역 혜택과 속초·고성·양양 여행 동선이 잘 맞아요.",
        policyCount: 5,
        localPolicyCount: 4,
        nationwidePolicyCount: 1,
        endingSoonCount: 1,
        estimatedValueKrw: 120000,
        score: 95,
      },
      {
        travelAreaId: "gangwon-gangneung-donghae-samcheok",
        travelAreaName: "강릉·동해·삼척",
        sido: "강원",
        includedCities: ["강릉", "동해", "삼척"],
        summary: "해변과 커피, 드라이브를 함께 즐기는 동해 중부 권역",
        tags: ["바다", "커피", "드라이브"],
        reason: "강릉 중심 동해안 여행에 적합해요.",
        policyCount: 3,
        localPolicyCount: 2,
        nationwidePolicyCount: 1,
        endingSoonCount: 0,
        estimatedValueKrw: 80000,
        score: 88,
      },
    ],
  };
}

export function getSokchoTravelAreaResponse(): TravelAreaRecommendationResponse {
  const response = getGangwonTravelAreaResponse();
  return {
    ...response,
    mode: "search",
    sido: null,
    query: "속초",
    items: [response.items[0]],
  };
}

export function getBusanTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "sido",
    sido: "부산",
    query: null,
    emptyReason: null,
    items: [
      {
        travelAreaId: "busan-all",
        travelAreaName: "부산 전체",
        sido: "부산",
        includedCities: ["부산"],
        summary: "바다와 도시, 미식을 함께 즐기는 부산 대표 권역",
        tags: ["바다", "도시", "맛집"],
        reason: "부산 대표 여행권역으로 바로 일정을 만들 수 있어요.",
        policyCount: 4,
        localPolicyCount: 3,
        nationwidePolicyCount: 1,
        endingSoonCount: 0,
        estimatedValueKrw: 90000,
        score: 92,
      },
    ],
  };
}

export function getJejuTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "sido",
    sido: "제주",
    query: null,
    emptyReason: null,
    items: [
      {
        travelAreaId: "jeju-all",
        travelAreaName: "제주 전체",
        sido: "제주",
        includedCities: ["제주", "서귀포"],
        summary: "제주 전역의 자연, 맛집, 체험을 함께 둘러보는 대표 여행권역",
        tags: ["자연", "맛집", "체험"],
        reason: "기본 프로필 지역에 맞춰 바로 일정을 만들 수 있어요.",
        policyCount: 4,
        localPolicyCount: 3,
        nationwidePolicyCount: 1,
        endingSoonCount: 1,
        estimatedValueKrw: 110000,
        score: 94,
      },
    ],
  };
}

export function getNationwideTravelAreaResponse(): TravelAreaRecommendationResponse {
  const broadRegions = [
    ["서울", "seoul-all"],
    ["부산", "busan-all"],
    ["대구", "daegu-all"],
    ["인천", "incheon-ganghwa"],
    ["광주", "gwangju-all"],
    ["대전", "daejeon-all"],
    ["울산", "ulsan-all"],
    ["세종", "sejong-all"],
    ["경기", "gyeonggi-gapyeong-yangpyeong"],
    ["강원", "gangwon-sokcho-goseong-yangyang"],
    ["충북", "chungbuk-danyang-jecheon"],
    ["충남", "chungnam-gongju-buyeo"],
    ["전북", "jeonbuk-jeonju-wanju"],
    ["전남", "jeonnam-yeosu-suncheon"],
    ["경북", "gyeongbuk-gyeongju"],
    ["경남", "gyeongnam-tongyeong-geoje-goseong"],
    ["제주", "jeju-all"],
  ] as const;

  return {
    mode: "nationwide",
    sido: null,
    query: null,
    emptyReason: null,
    items: broadRegions.map(([sido, travelAreaId], index) => ({
      travelAreaId,
      travelAreaName: `${sido} 전체`,
      sido,
      includedCities: [sido],
      summary: `${sido} 대표 여행권역`,
      tags: ["대표", "여행"],
      reason: `${sido} 기본 여행권역`,
      policyCount: 3,
      localPolicyCount: 2,
      nationwidePolicyCount: 1,
      endingSoonCount: 0,
      estimatedValueKrw: 50000 + index * 1000,
      score: 100 - index,
    })),
  };
}

export function getYeonggwangTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "search",
    sido: "전남",
    query: "영광",
    emptyReason: null,
    items: [
      {
        travelAreaId: "policy-region:%EC%A0%84%EB%82%A8:%EC%98%81%EA%B4%91",
        travelAreaName: "영광",
        sido: "전남",
        includedCities: ["영광"],
        summary: "영광 정책 혜택과 연결되는 전남 여행 지역입니다.",
        tags: ["정책 혜택", "지역 여행", "전남"],
        reason: "영광에 포함된 도시 혜택이 있어 여행 동선과 잘 맞아요.",
        policyCount: 1,
        localPolicyCount: 1,
        nationwidePolicyCount: 0,
        endingSoonCount: 0,
        estimatedValueKrw: 200000,
        score: 58,
      },
    ],
  };
}

export function getHapcheonTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "search",
    sido: null,
    query: "합천",
    emptyReason: null,
    items: [
      {
        travelAreaId: "policy-region:%EA%B2%BD%EB%82%A8:%ED%95%A9%EC%B2%9C",
        travelAreaName: "합천",
        sido: "경남",
        includedCities: ["합천"],
        summary: "합천 정책 혜택과 연결되는 경남 여행 지역입니다.",
        tags: ["정책 혜택", "지역 여행", "경남"],
        reason: "합천은 정책 혜택, 지역 여행, 경남 테마에 맞는 대표 여행권역이에요.",
        policyCount: 0,
        localPolicyCount: 0,
        nationwidePolicyCount: 0,
        endingSoonCount: 0,
        estimatedValueKrw: 0,
        score: 12,
      },
    ],
  };
}

export function getGyeongjuTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "search",
    sido: null,
    query: "경주",
    emptyReason: null,
    items: [
      {
        travelAreaId: "gyeongbuk-gyeongju",
        travelAreaName: "경주",
        sido: "경북",
        includedCities: ["경주"],
        summary: "역사와 전통, 산책 코스를 함께 즐기는 경주 대표 권역",
        tags: ["역사", "전통", "산책"],
        reason: "경주 검색어와 정확히 맞는 여행권역이에요.",
        policyCount: 3,
        localPolicyCount: 2,
        nationwidePolicyCount: 1,
        endingSoonCount: 0,
        estimatedValueKrw: 70000,
        score: 90,
      },
    ],
  };
}

export function getGangneungTravelAreaResponse(): TravelAreaRecommendationResponse {
  return {
    mode: "search",
    sido: null,
    query: "강릉",
    emptyReason: null,
    items: [
      {
        travelAreaId: "gangwon-gangneung-donghae-samcheok",
        travelAreaName: "강릉·동해·삼척",
        sido: "강원",
        includedCities: ["강릉", "동해", "삼척"],
        summary: "해변과 커피, 드라이브를 함께 즐기는 동해 중부 권역",
        tags: ["바다", "커피", "드라이브"],
        reason: "강릉 검색어와 맞는 동해안 여행권역이에요.",
        policyCount: 3,
        localPolicyCount: 2,
        nationwidePolicyCount: 1,
        endingSoonCount: 0,
        estimatedValueKrw: 80000,
        score: 88,
      },
    ],
  };
}

export function getPreviewUser(): User {
  return {
    id: "preview-user-id",
    nickname: "여행러",
    email: "preview.user@example.com",
    role: "user",
    hasPassword: true,
    preferredRegions: null,
    persona: "family",
    savedAmount: 0,
    onboardingCompleted: true,
    nicknameSetupCompleted: true,
    socialAccounts: [],
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}
