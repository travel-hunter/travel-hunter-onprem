import { apiClient, apiConfig } from "./client";
import type { ProfileSkipResponse } from "./types";
import {
  AppDataApi,
  AuthResponse,
  ChangePasswordRequest,
  ChangePasswordResponse,
  CompleteSocialSignupRequest,
  CreateTripRequest,
  DeleteTripResponse,
  EmailAvailabilityRequest,
  EmailAvailabilityResponse,
  LoginRequest,
  LogoutResponse,
  NicknameSuggestionResponse,
  NicknameUpdateRequest,
  OAuthProvider,
  PasswordResetConfirmRequest,
  PasswordResetConfirmResponse,
  PasswordResetRequest,
  PasswordResetResponse,
  PendingSocialSignupResponse,
  SavePolicyResponse,
  SendInviteEmailRequest,
  SignupRequest,
  SignupCompleteRequest,
  SignupVerificationResponse,
  SignupVerifyRequest,
  SignupVerifyResponse,
  TripPlaceMoveRequest,
  TripPlaceMutationRequest,
  TripPlaceSearchOptions,
  TripPlaceUpdateRequest,
  TripPolicyResponse,
  TripStatusUpdateRequest,
  TravelAreaRecommendationOptions,
  WithdrawRequest,
  WithdrawResponse,
} from "./dataApi";
import {
  AdminAuditLogListResponse,
  AdminExternalSourceSummaryResponse,
  AdminPolicyDetail,
  AdminPolicyListResponse,
  AdminUserDetail,
  AdminUserListResponse,
  AppliedPolicyLink,
  ExternalCollectionOpsHealth,
  ExternalCollectionRunResponse,
  InviteEmailResult,
  InviteLinksState,
  InviteRole,
  InviteState,
  PlaceSearchCandidate,
  Policy,
  Profile,
  ProfileOptions,
  Recommendation,
  RegionRecommendation,
  TravelAreaRecommendationResponse,
  Trip,
  User,
} from "./types";

const makeDefaultLogin = (request: LoginRequest | undefined): LoginRequest => {
  if (!request || !request.email || !request.password) {
    throw new Error("TRAVEL_HUNTER: login request must include email and password.");
  }
  return request;
};

const makeDefaultSignup = (request: SignupRequest | undefined): SignupRequest => {
  if (!request || !request.email || !request.agreements) {
    throw new Error("TRAVEL_HUNTER: signup request must include email and agreements.");
  }
  return request;
};

function queryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const backendApi: AppDataApi = {
  getProfileOptions: (): Promise<ProfileOptions> => apiClient.get<ProfileOptions>("/api/profile-options"),
  login: (request?: LoginRequest): Promise<AuthResponse> => apiClient.post<AuthResponse>("/api/auth/login", makeDefaultLogin(request)),
  signup: (request?: SignupRequest): Promise<SignupVerificationResponse> => apiClient.post<SignupVerificationResponse>("/api/auth/signup", makeDefaultSignup(request)),
  requestSignupVerification: (request?: SignupRequest): Promise<SignupVerificationResponse> => apiClient.post<SignupVerificationResponse>("/api/auth/signup", makeDefaultSignup(request)),
  verifySignup: (request: SignupVerifyRequest): Promise<SignupVerifyResponse> => apiClient.post<SignupVerifyResponse>("/api/auth/signup/verify", request),
  completeSignup: (request: SignupCompleteRequest): Promise<AuthResponse> => apiClient.post<AuthResponse>("/api/auth/signup/complete", request),
  getPendingSocialSignup: (token: string): Promise<PendingSocialSignupResponse> =>
    apiClient.get<PendingSocialSignupResponse>(`/api/auth/oauth/pending-signup?token=${encodeURIComponent(token)}`),
  completeSocialSignup: (request: CompleteSocialSignupRequest): Promise<AuthResponse> =>
    apiClient.post<AuthResponse>("/api/auth/oauth/pending-signup/complete", request),
  checkEmailAvailability: (request: EmailAvailabilityRequest): Promise<EmailAvailabilityResponse> => apiClient.post<EmailAvailabilityResponse>("/api/auth/email-check", request),
  getNicknameSuggestion: (): Promise<NicknameSuggestionResponse> => apiClient.get<NicknameSuggestionResponse>("/api/me/nickname-suggestion"),
  updateNickname: (request: NicknameUpdateRequest): Promise<User> => apiClient.patch<User>("/api/me/nickname", request),
  refreshSession: (): Promise<AuthResponse> => apiClient.post<AuthResponse>("/api/auth/refresh"),
  logout: (): Promise<LogoutResponse> => apiClient.post<LogoutResponse>("/api/auth/logout"),
  changePassword: (request: ChangePasswordRequest): Promise<ChangePasswordResponse> => apiClient.post<ChangePasswordResponse>("/api/auth/password/change", request),
  withdraw: (request: WithdrawRequest): Promise<WithdrawResponse> => apiClient.post<WithdrawResponse>("/api/auth/withdraw", request),
  requestPasswordReset: (request: PasswordResetRequest): Promise<PasswordResetResponse> => apiClient.post<PasswordResetResponse>("/api/auth/password-reset/request", request),
  confirmPasswordReset: (request: PasswordResetConfirmRequest): Promise<PasswordResetConfirmResponse> => apiClient.post<PasswordResetConfirmResponse>("/api/auth/password-reset/confirm", request),
  getOAuthStartUrl: (provider: OAuthProvider, redirect?: string | null): string => {
    const query = redirect ? `?redirect=${encodeURIComponent(redirect)}` : "";
    return `${apiConfig.baseUrl}/api/auth/oauth/${provider}/start${query}`;
  },
  getCurrentUser: (): Promise<User> => apiClient.get<User>("/api/me"),
  getProfile: (): Promise<Profile> => apiClient.get<Profile>("/api/me/profile"),
  updateProfile: (profile: Partial<Profile>): Promise<Profile> => apiClient.patch<Profile>("/api/me/profile", profile),
  skipProfileSetup: (): Promise<ProfileSkipResponse> => apiClient.post<ProfileSkipResponse>("/api/me/profile/skip"),
  listPolicies: (): Promise<Policy[]> => apiClient.get<Policy[]>("/api/policies"),
  listRegionRecommendations: (options?: { style?: string | null; region?: string | null; preferredRegions?: string[] | null; limit?: number }): Promise<RegionRecommendation[]> => {
    const params = new URLSearchParams();
    if (options?.style) params.set("style", options.style);
    if (options?.region) params.set("region", options.region);
    for (const preferredRegion of options?.preferredRegions ?? []) {
      if (preferredRegion) params.append("preferredRegions", preferredRegion);
    }
    if (options?.limit !== undefined) params.set("limit", String(options.limit));
    const query = params.toString();
    return apiClient.get<RegionRecommendation[]>(`/api/recommendations/regions${query ? `?${query}` : ""}`);
  },
  listTravelAreaRecommendations: (options?: TravelAreaRecommendationOptions): Promise<TravelAreaRecommendationResponse> => {
    const params = new URLSearchParams();
    if (options?.sido) params.set("sido", options.sido);
    if (options?.query) params.set("query", options.query);
    if (options?.mode) params.set("mode", options.mode);
    if (options?.style) params.set("style", options.style);
    if (options?.limit !== undefined) params.set("limit", String(options.limit));
    const query = params.toString();
    return apiClient.get<TravelAreaRecommendationResponse>(`/api/recommendations/travel-areas${query ? `?${query}` : ""}`);
  },
  getPolicy: (policySlug = ""): Promise<Policy> => apiClient.get<Policy>(`/api/policies/${policySlug}`),
  savePolicy: (policySlug: string): Promise<SavePolicyResponse> => apiClient.post<SavePolicyResponse>(`/api/me/saved-policies/${policySlug}`),
  listSavedPolicies: (): Promise<Policy[]> => apiClient.get<Policy[]>("/api/me/saved-policies"),
  listAppliedPolicies: (): Promise<Policy[]> => apiClient.get<Policy[]>("/api/me/applied-policies"),
  listAppliedPolicyLinks: (): Promise<AppliedPolicyLink[]> => apiClient.get<AppliedPolicyLink[]>("/api/me/applied-policy-links"),
  removeSavedPolicy: (policySlug: string): Promise<SavePolicyResponse> => apiClient.delete<SavePolicyResponse>(`/api/me/saved-policies/${policySlug}`),
  listTrips: (): Promise<Trip[]> => apiClient.get<Trip[]>("/api/trips"),
  createTrip: (trip?: CreateTripRequest): Promise<Trip> => apiClient.post<Trip>("/api/trips", trip),
  deleteTrip: (tripId: string): Promise<DeleteTripResponse> => apiClient.delete<DeleteTripResponse>(`/api/trips/${tripId}`),
  getTrip: (tripId: string): Promise<Trip> => apiClient.get<Trip>(`/api/trips/${tripId}`),
  updateTripStatus: (tripId: string, status: TripStatusUpdateRequest): Promise<Trip> => apiClient.patch<Trip>(`/api/trips/${tripId}/status`, status),
  addTripPlace: (tripId: string, dayNumber: number, place: TripPlaceMutationRequest): Promise<Trip> => apiClient.post<Trip>(`/api/trips/${tripId}/days/${dayNumber}/places`, place),
  updateTripPlace: (tripId: string, placeId: string, place: TripPlaceUpdateRequest): Promise<Trip> => apiClient.patch<Trip>(`/api/trips/${tripId}/places/${placeId}`, place),
  moveTripPlace: (tripId: string, placeId: string, move: TripPlaceMoveRequest): Promise<Trip> => apiClient.patch<Trip>(`/api/trips/${tripId}/places/${placeId}/move`, move),
  deleteTripPlace: (tripId: string, placeId: string, expectedRevision: number): Promise<Trip> =>
    apiClient.delete<Trip>(`/api/trips/${tripId}/places/${placeId}${queryString({ expectedRevision })}`),
  addPolicyToTrip: (tripId: string, policySlug: string): Promise<TripPolicyResponse> => apiClient.post<TripPolicyResponse>(`/api/trips/${tripId}/policies/${policySlug}`),
  removePolicyFromTrip: (tripId: string, policySlug: string): Promise<TripPolicyResponse> => apiClient.delete<TripPolicyResponse>(`/api/trips/${tripId}/policies/${policySlug}`),
  listRecommendations: (tripId: string): Promise<Recommendation[]> => apiClient.get<Recommendation[]>(`/api/trips/${tripId}/recommendations`),
  searchTripPlaces: (tripId: string, options: TripPlaceSearchOptions): Promise<PlaceSearchCandidate[]> =>
    apiClient.get<PlaceSearchCandidate[]>(`/api/trips/${tripId}/place-search${queryString(options)}`),
  getInviteState: (tripId: string): Promise<InviteLinksState> => apiClient.get<InviteLinksState>(`/api/trips/${tripId}/invite`),
  confirmInviteSent: (tripId: string, role?: InviteRole): Promise<InviteState> => apiClient.post<InviteState>(`/api/trips/${tripId}/invite`, role ? { role } : undefined),
  sendInviteEmail: (tripId: string, request: SendInviteEmailRequest): Promise<InviteEmailResult> => apiClient.post<InviteEmailResult>(`/api/trips/${tripId}/invite/email`, request),
  acceptInvite: (inviteToken: string): Promise<InviteState> => apiClient.post<InviteState>(`/api/invites/${inviteToken}/accept`),
  listAdminUsers: (options): Promise<AdminUserListResponse> =>
    apiClient.get<AdminUserListResponse>(`/api/admin/users${queryString(options ?? {})}`),
  getAdminUser: (userId: string): Promise<AdminUserDetail> => apiClient.get<AdminUserDetail>(`/api/admin/users/${userId}`),
  updateAdminUser: (userId: string, user): Promise<AdminUserDetail> => apiClient.patch<AdminUserDetail>(`/api/admin/users/${userId}`, user),
  listAdminPolicies: (options): Promise<AdminPolicyListResponse> =>
    apiClient.get<AdminPolicyListResponse>(`/api/admin/policies${queryString(options ?? {})}`),
  getAdminExternalSourceSummary: (): Promise<AdminExternalSourceSummaryResponse> =>
    apiClient.get<AdminExternalSourceSummaryResponse>("/api/admin/external-sources/summary"),
  getExternalCollectionOpsHealth: (): Promise<ExternalCollectionOpsHealth> =>
    apiClient.get<ExternalCollectionOpsHealth>("/api/ops/external-collection"),
  runExternalCollection: (): Promise<ExternalCollectionRunResponse> =>
    apiClient.post<ExternalCollectionRunResponse>("/api/ops/external-collection/run"),
  getAdminPolicy: (policyId: string): Promise<AdminPolicyDetail> => apiClient.get<AdminPolicyDetail>(`/api/admin/policies/${policyId}`),
  createAdminPolicy: (policy): Promise<AdminPolicyDetail> => apiClient.post<AdminPolicyDetail>("/api/admin/policies", policy),
  updateAdminPolicy: (policyId: string, policy): Promise<AdminPolicyDetail> => apiClient.patch<AdminPolicyDetail>(`/api/admin/policies/${policyId}`, policy),
  listAdminAuditLogs: (options): Promise<AdminAuditLogListResponse> =>
    apiClient.get<AdminAuditLogListResponse>(`/api/admin/audit-logs${queryString(options ?? {})}`),
};
