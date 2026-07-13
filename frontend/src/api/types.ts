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
};

export type PolicyStructuredDetail = {
  benefits: PolicyStructuredDetailItem[];
  conditions: PolicyStructuredDetailItem[];
  periods: PolicyStructuredDetailItem[];
  links: PolicyStructuredDetailItem[];
  documents: PolicyStructuredDetailItem[];
  notices: PolicyStructuredDetailItem[];
};

export type Policy = {
  id: string;
  slug: string;
  label: string;
  tag: string;
  title: string;
  org: string;
  region: string;
  deadline: string;
  amount: string;
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
};

export type AppliedPolicyLinkedTrip = {
  id: string;
  title: string;
  region: string;
  startDate: string | null;
  endDate: string | null;
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
  dates: string;
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

export type InviteRole = "viewer" | "editor";
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

export type InviteLinksState = {
  tripId: string;
  viewer: InviteState | null;
  editor: InviteState | null;
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
