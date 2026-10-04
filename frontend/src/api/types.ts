export type User = {
  id: string;
  nickname: string;
  email: string;
  role: "user" | "admin";
  hasPassword: boolean;
  preferredRegions: string[] | null;
  persona: string;
  savedAmount: number;
  onboardingCompleted: boolean;
  nicknameSetupCompleted: boolean;
  socialAccounts: SocialAccount[];
  createdAt: string;
  updatedAt: string;
};

export type SocialAccount = {
  provider: string;
  providerNickname: string | null;
  connectedAt: string;
};

export type Profile = {
  preferredRegions: string[] | null;
  style: string | null;
  budget: string | null;
};

export type ProfileSkipResponse = {
  skipped: boolean;
  onboardingCompleted: boolean;
};

export type PolicyCategory = "교통" | "숙박" | "여행상품" | "지역할인" | "이벤트" | "기타";

export type PolicyStructuredDetailItem = {
  title?: string;
  label?: string;
  description?: string;
  amount?: string;
  value?: string;
  url?: string;
  startDate?: string;
  endDate?: string;
  type?: string;
};

export type PolicyStructuredDetail = {
  supportContent: PolicyStructuredDetailItem[];
  periods: PolicyStructuredDetailItem[];
  applicationTarget: PolicyStructuredDetailItem[];
  requiredDocuments: PolicyStructuredDetailItem[];
  notes: PolicyStructuredDetailItem[];
};

export type ApplicationGuideRound = {
  key: string;
  label: string;
  status: "past" | "current" | "upcoming";
  applyStart: string | null;
  applyUntil: string | null;
  travelStart: string | null;
  travelEnd: string | null;
  documentsDueBy: string | null;
  applicationFormUrl: string | null;
  documentFormUrl: string | null;
};

export type ApplicationGuide = {
  rounds: ApplicationGuideRound[];
  currentRoundKey: string | null;
  applyFormUrl: string | null;
  documentDeadlineDaysAfterTrip: number | null;
  minNights: number | null;
  minPaymentKrw: number | null;
  requiredDocuments: string[];
  photoRequirement: string | null;
  exclusions: string[];
  contacts: { email: string | null; phones: string[] };
};

export type PolicyPhoto = {
  imageUrl: string;
  thumbnailUrl?: string | null;
  alt: string;
  attribution: string;
};

export type Policy = {
  id: string;
  slug: string;
  label: string;
  tag: string;
  title: string;
  org: string;
  region: string;
  startDate?: string | null;
  deadline: string;
  amount: string;
  /** 카드에만 쓰는 짧은 혜택 문구. 승인값이거나 품질 검사를 통과한 amount. null 이면 카드가 알약을 비운다. */
  cardSummary?: string | null;
  summary: string;
  match: number;
  category: PolicyCategory;
  requirements: string[];
  documents: string[];
  structuredDetail?: PolicyStructuredDetail | null;
  officialUrl: string | null;
  applyUrl: string | null;
  sourceType?: "internal" | "external";
  actionStatus?: "infoOnly";
  photo?: PolicyPhoto | null;
  eligibleIslandCount?: number | null;
  eligibleIslandsOfficialUrl?: string | null;
  applicationGuide?: ApplicationGuide | null;
};

export type TripPolicyApplicationStatus =
  | "not_started"
  | "applied"
  | "selected"
  | "not_selected"
  | "traveled"
  | "documents_submitted"
  | "paid";

export type TripPolicyApplication = {
  status: TripPolicyApplicationStatus;
  roundKey: string | null;
  checklist: { key: string; label: string; checked: boolean }[];
  checks: {
    inTravelWindow: boolean | null;
    meetsMinNights: boolean;
    eligibleIslandMatched: boolean | null;
    applyDeadline: string | null;
    documentsDueDate: string | null;
  };
  updatedAt: string | null;
  updatedBy: string | null;
};

export type TripPolicyApplicationUpdate = {
  status?: TripPolicyApplicationStatus;
  checklist?: Record<string, boolean>;
};

export type AppliedPolicyLinkedTrip = {
  id: string;
  title: string;
  region: string;
  startDate: string | null;
  endDate: string | null;
  applicationStatus?: TripPolicyApplicationStatus | null;
};

export type AppliedPolicyLink = {
  policy: Policy;
  linkedTrips: AppliedPolicyLinkedTrip[];
};

export type ItineraryPlace = {
  id?: string;
  time: string;
  label: string;
  meta: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

export type RecommendationCategoryGroup = "stay" | "food" | "attraction" | "other";
export type RecommendationSourceType = "freshCandidate" | "savedSummary";

export type LinkedTripPolicy = {
  slug: string;
  title: string;
  amount: string;
  region: string;
  status?: "active" | "hidden";
  category?: PolicyCategory;
  tag?: string;
  deadline?: string | null;
  /** 공식 안내·신청 페이지. 일정 화면의 버튼이 정책 상세를 거치지 않고 바로 나간다 */
  officialUrl?: string | null;
  applyUrl?: string | null;
  application?: TripPolicyApplication | null;
};

export type AdminUserListItem = {
  id: string;
  email: string;
  nickname: string;
  role: "user" | "admin";
  onboardingCompleted: boolean;
  createdAt: string;
  updatedAt: string;
};

export type AdminUserDetail = AdminUserListItem & {
  preferredRegions: string | null;
  travelStyle: string | null;
  travelBudget: string | null;
};

export type AdminUserListResponse = {
  items: AdminUserListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminPolicyStatus = "active" | "hidden";

export type AdminPolicyListItem = {
  id: string;
  slug: string;
  title: string;
  organization: string | null;
  policyType: string | null;
  region: string;
  status: AdminPolicyStatus;
  sourceType: string;
  sourceCategory: string | null;
  sourceLabel: string;
  updatedAt: string;
};

export type AdminPolicyDetail = AdminPolicyListItem & {
  startDate: string | null;
  endDate: string | null;
  benefitAmount: number | null;
  benefitDetail: string | null;
  description: string | null;
  requirements: string[];
  documents: string[];
  structuredDetail?: PolicyStructuredDetail | null;
  officialUrl: string | null;
  applyUrl: string | null;
  policyComment: string | null;
  policyPeriod: string | null;
  adminOverrideEnabled: boolean;
  createdAt: string;
};

export type AdminPolicyListResponse = {
  items: AdminPolicyListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminAuditLogListItem = {
  id: string;
  adminUserId: string;
  adminEmail: string;
  action: string;
  targetType: string;
  targetId: string;
  summary: string | null;
  beforeJson: Record<string, unknown> | null;
  afterJson: Record<string, unknown> | null;
  createdAt: string;
};

export type AdminAuditLogListResponse = {
  items: AdminAuditLogListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminExternalSourceSummaryItem = {
  sourceCategory: string;
  label: string;
  sourceName: string;
  totalRecords: number;
  activeRecords: number;
  scheduledRecords: number;
  endedRecords: number;
  unknownRecords: number;
  freshRecords: number;
  promotedPolicyCount: number;
  activePromotedPolicyCount: number;
  latestFetchedAt: string | null;
  latestVerifiedAt: string | null;
};

export type AdminExternalSourceSummaryResponse = {
  items: AdminExternalSourceSummaryItem[];
  totalRecords: number;
  activeRecords: number;
  freshRecords: number;
  promotedPolicyCount: number;
  latestFetchedAt: string | null;
};

export type ExternalCollectionOpsHealth = {
  schedulerEnabled: boolean;
  runAt: string;
  pollSeconds: number;
  minParsedCount: number;
  lastAttemptedRunDate: string | null;
  lastSuccessfulRunDate: string | null;
  lastParsedCount: number | null;
  lastOutcome: string | null;
  lastError: string | null;
};

export type ExternalCollectionSourceRunResult = {
  sourceCategory: string;
  parsedCount: number;
  createdOrUpdatedCount: number;
  outcome: string;
  error: string | null;
};

export type ExternalCollectionRunResponse = {
  sourceName: string;
  sourceCategory: string;
  parsedCount: number;
  createdOrUpdatedCount: number;
  outcome: string;
  sources: ExternalCollectionSourceRunResult[];
};

export type Trip = {
  id: string;
  title: string;
  status: "draft" | "confirmed";
  revision: number;
  region: string;
  travelAreaId: string | null;
  dates: string;
  startDate: string;
  endDate: string;
  people: string[];
  participantCount: number;
  expectedSaving: string;
  linkedPolicies: LinkedTripPolicy[];
  recommendedPolicies: LinkedTripPolicy[];
  days: Record<number, ItineraryPlace[]>;
  currentUserRole: "owner" | "editor" | "viewer";
};

export type Recommendation = {
  id?: string | null;
  label: string;
  title: string;
  meta: string;
  reason: string;
  categoryGroup?: RecommendationCategoryGroup | null;
  categoryCode?: string | null;
  categoryName?: string | null;
  phone?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  placeUrl?: string | null;
  suggestedDay?: number | null;
  aiReview?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
  sourceType?: RecommendationSourceType | null;
};

export type PlaceSearchCandidate = {
  id?: string | null;
  label: string;
  title: string;
  meta: string;
  categoryCode?: string | null;
  categoryName?: string | null;
  phone?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

/** 통합 검색의 장소 한 곳(place) 또는 동 · 읍 · 면 구역(area). sido · city 는 서버가 주소로 가린 지도 도 · 시군 */
export type PlaceSearchItem = {
  kind: "place" | "area";
  id: string;
  name: string;
  category?: string | null;
  categoryCode?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  placeUrl?: string | null;
  sido?: string | null;
  city?: string | null;
  /** 이 근처(GET /places/nearby)일 때만 - 기준 좌표에서의 거리(m) */
  distanceMeters?: number | null;
};

/** 장소 카드 '이 근처'의 분류: 맛집 · 카페 · 숙소 · 볼거리(카카오 분류 코드) */
export type NearbyCategory = "FD6" | "CE7" | "AD5" | "AT4";

/** 맞춰 보기(POST /places/match) - 고른 카카오 장소를 우리 장소 기반과 견준다. 서버는 받은 값을 저장 · 로그에 남기지 않는다(카카오 운영정책) */
export type PlaceMatchRequest = {
  name: string;
  latitude: number;
  longitude: number;
  categoryCode?: string | null;
};

/** 공공데이터 장소 분류 - 서버 public_places.category 와 같은 7개 */
export type PublicPlaceCategory = "sight" | "culture" | "leisure" | "stay" | "shopping" | "food" | "cafe";

/** 우리 장소 기반(public_places)의 한 곳 - 공공데이터 값. source + sourceId 가 담을 때 쓰는 열쇠다(3단계) */
export type PublicPlaceItem = {
  source: "tourapi" | "sangga";
  sourceId: string;
  name: string;
  address?: string | null;
  latitude: number;
  longitude: number;
  category: PublicPlaceCategory;
  sido?: string | null;
  city?: string | null;
  photoUrl?: string | null;
  photoLicense?: string | null;
  distanceMeters: number;
};

/** match = 바로 담기, candidates = '이 장소가 맞나요?' 후보 1~3곳, none = 나만의 장소 */
export type PlaceMatchResult = {
  result: "match" | "candidates" | "none";
  places: PublicPlaceItem[];
};

export type RegionRecommendation = {
  region: string;
  title: string;
  reason: string;
  policyCount: number;
  endingSoonCount: number;
  estimatedValueKrw: number;
  score: number;
  styleMatchedCount: number;
};

export type TravelAreaRecommendation = {
  travelAreaId: string;
  travelAreaName: string;
  sido: string;
  includedCities: string[];
  summary: string;
  tags: string[];
  reason: string;
  policyCount: number;
  localPolicyCount: number;
  nationwidePolicyCount: number;
  endingSoonCount: number;
  estimatedValueKrw: number;
  score: number;
};

export type TravelAreaRecommendationResponse = {
  mode: "sido" | "search" | "nationwide";
  sido: string | null;
  query: string | null;
  items: TravelAreaRecommendation[];
  emptyReason: "unsupported_sido" | "no_match" | null;
};

export type TravelAreaOption = {
  travelAreaId: string;
  travelAreaName: string;
  sido: string;
  areaType: "whole" | "recommended" | "administrative";
  includedCities: string[];
  /* 시·군·구가 많은 광역시도에서만 채워진다. 화면이 이 값으로 접어 보여준다. */
  group?: string | null;
};

export type TravelAreaCatalog = {
  sido: string;
  sourceAsOf: string;
  wholeArea: TravelAreaOption;
  recommendedAreas: TravelAreaOption[];
  administrativeAreas: TravelAreaOption[];
};

export type InviteRole = "editor";
export type InviteEmailDeliveryStatus = "sent" | "notConfigured" | "failed";

export type InviteState = {
  id: string;
  tripId: string;
  inviteToken: string;
  inviteUrl: string;
  expiresAt: string;
  createdAt: string;
  acceptedAt: string | null;
  invited: boolean;
  copied: boolean;
  role: InviteRole;
  alreadyMember: boolean;
};

export type InviteEmailResult = {
  invite: InviteState;
  deliveryStatus: InviteEmailDeliveryStatus;
  message: string;
};

export type ProfileOptions = {
  regions: readonly string[];
  travelStyles: readonly string[];
  budgets: readonly string[];
};


export type AdminPolicyReviewCandidate = {
  id: string;
  externalSourceRecordId: string;
  reviewStatus: "pending" | "approved" | "rejected" | "superseded";
  changeKind: "new" | "material_change";
  title: string;
  sourceCategory: string;
  officialUrl: string;
  benefitText: string;
  region: string | null;
  city: string | null;
  status: string;
  startDate: string | null;
  endDate: string | null;
  createdAt: string;
  reviewReason?: string | null;
  /** card_copy_only: 카드 문구만 바뀐 후보. 승인해도 상세는 그대로고 card_summary 만 바뀐다. */
  reviewScope?: "full_policy" | "card_copy_only";
  cardPreview?: { amount: string; evidence: string; issues: string[] };
};

export type AdminPolicyReviewCandidateListResponse = { items: AdminPolicyReviewCandidate[]; total: number; limit: number; offset: number };

export type AdminPolicyReviewBatchApproveResponse = { approvedCount: number; approvedCandidateIds: string[] };

export type AdminCollectionSource = {
  key: string;
  displayName: string;
  officialUrl: string;
  sourceCategory: string;
  enabled: boolean;
  publicationMode: "review" | "auto_after_reviewed_baseline";
  expectedMinRecords?: number;
  lastParsedCount?: number | null;
  autoApprovedLast24h?: number;
  lastOutcome: string | null;
  lastCollectedAt: string | null;
  lastError: string | null;
};

export type AdminCollectionSourceListResponse = { items: AdminCollectionSource[] };

export type AdminCollectionSourceUpdate = {
  enabled?: boolean;
  publicationMode?: "review" | "auto_after_reviewed_baseline";
  expectedMinRecords?: number;
};

// Eligible island catalog review — separate from policy review candidates.
export type AdminEligibleIslandAttachment = { url: string; filename: string; sha256: string };

export type AdminEligibleIslandSnapshot = {
  id: string;
  reviewStatus: "pending" | "approved" | "rejected" | "superseded";
  isCurrentApproved: boolean;
  entryCount: number;
  addedCount: number;
  removedCount: number;
  changedCount: number;
  sourceNoticeUrl: string | null;
  sourceNoticeTitle: string | null;
  attachmentFiles: AdminEligibleIslandAttachment[];
  attachmentFingerprint: string | null;
  parserVersion: string;
  fetchedAt: string;
  reviewedAt: string | null;
  reviewNote: string | null;
  createdAt: string;
};

export type AdminEligibleIslandSnapshotListResponse = {
  items: AdminEligibleIslandSnapshot[];
  total: number;
  limit: number;
  offset: number;
  approvedSnapshotId: string | null;
  approvedEntryCount: number;
};

export type AdminEligibleIslandEntry = { displayName: string; normalizedName: string; jurisdictionName: string };

export type AdminEligibleIslandSnapshotDetail = {
  snapshot: AdminEligibleIslandSnapshot;
  added: AdminEligibleIslandEntry[];
  removed: AdminEligibleIslandEntry[];
  unchanged: AdminEligibleIslandEntry[];
  addedTotal: number;
  removedTotal: number;
  unchangedTotal: number;
  limit: number;
  offset: number;
};

export type AdminEligibleIslandCollectResponse = {
  outcome: "created" | "unchanged" | "identical" | "suspicious_shrink" | "download_failed" | "parser_changed";
  snapshotId: string | null;
  entryCount: number;
  error: string | null;
};

// 사진 검토(관리자): 수집은 후보만, 관리자가 한 장을 확정해야 앱 사진이 된다
export type AdminPhotoReviewUnit = "region" | "policy";
export type AdminPhotoReviewStatus = "pending" | "approved" | "none";

export type AdminPhotoReviewPhoto = {
  candidateId: string;
  title: string;
  imageUrl: string;
  thumbnailUrl: string | null;
  copyrightType: string | null;
};

export type AdminPhotoReviewTarget = {
  id: string;
  unit: AdminPhotoReviewUnit;
  status: AdminPhotoReviewStatus;
  sido: string;
  city: string;
  policySlug: string | null;
  policyTitle: string | null;
  policyCategory: string | null;
  benefitCount: number;
  candidateCount: number;
  photo: AdminPhotoReviewPhoto | null;
  inheritedPhoto: AdminPhotoReviewPhoto | null;
  decidedAt: string | null;
};

export type AdminPhotoReviewCandidate = {
  id: string;
  title: string;
  kind: string;
  contentTypeId: string | null;
  imageUrl: string;
  thumbnailUrl: string | null;
  copyrightType: string | null;
  width: number | null;
  height: number | null;
  address: string | null;
  source: "collect" | "search";
  searchKeyword: string | null;
};

export type AdminPhotoReviewTargetDetail = AdminPhotoReviewTarget & { candidates: AdminPhotoReviewCandidate[] };

export type AdminPhotoReviewTargetListResponse = {
  items: AdminPhotoReviewTarget[];
  counts: { pending: number; approved: number; none: number; all: number };
  pendingTotal: number;
  /** 다음 '후보 채우기'가 새로 넣을 대상(공개됐지만 아직 대상이 아닌 정책 · 시군 줄) */
  newTargets: number;
  /** 수집 후보('이름으로 찾기' 제외)가 6장이 안 되는 검토 대기 대상 */
  shortTargets: number;
};

/** '후보 채우기' 진행. 시각은 UTC ISO(끝에 Z) */
export type AdminPhotoReviewCollectStatus = {
  running: boolean;
  startedAt: string | null;
  finishedAt: string | null;
  done: number;
  total: number;
  candidatesAdded: number;
  targetsCreated: number;
  targetsEmpty: number;
  error: string | null;
  lastRun: { at: string; candidatesAdded: number } | null;
};
