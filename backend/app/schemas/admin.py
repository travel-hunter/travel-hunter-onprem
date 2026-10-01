from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AdminRole = Literal["user", "admin"]
PolicyStatus = Literal["active", "hidden"]


class AdminUserListItem(BaseModel):
    id: str
    email: str
    nickname: str
    role: AdminRole
    onboardingCompleted: bool
    createdAt: str
    updatedAt: str


class AdminUserDetail(AdminUserListItem):
    preferredRegions: str | None = None
    travelStyle: str | None = None
    travelBudget: str | None = None


class AdminUserUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=20)
    preferredRegions: str | None = Field(default=None, max_length=255)
    travelStyle: str | None = Field(default=None, max_length=50)
    travelBudget: str | None = Field(default=None, max_length=50)
    onboardingCompleted: bool | None = None
    role: AdminRole | None = None

    model_config = {"extra": "forbid"}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    limit: int
    offset: int


class AdminPolicyListItem(BaseModel):
    id: str
    slug: str
    title: str
    organization: str | None = None
    policyType: str | None = None
    region: str
    status: PolicyStatus
    sourceType: str
    sourceCategory: str | None = None
    sourceLabel: str
    updatedAt: str


class AdminPolicyDetail(AdminPolicyListItem):
    startDate: date | None = None
    endDate: date | None = None
    benefitAmount: int | None = None
    benefitDetail: str | None = None
    description: str | None = None
    requirements: list[str]
    documents: list[str]
    officialUrl: str | None = None
    applyUrl: str | None = None
    policyComment: str | None = None
    policyPeriod: str | None = None
    adminOverrideEnabled: bool
    createdAt: str


class _AdminPolicyWriteRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    organization: str | None = Field(default=None, max_length=100)
    policyType: str | None = Field(default=None, max_length=30)
    region: str | None = Field(default=None, max_length=50)
    startDate: date | None = None
    endDate: date | None = None
    benefitAmount: int | None = Field(default=None, ge=0)
    benefitDetail: str | None = None
    description: str | None = None
    targetCondition: str | None = None
    requirements: list[str] | None = None
    documents: list[str] | None = None
    officialUrl: str | None = Field(default=None, max_length=500)
    applyUrl: str | None = Field(default=None, max_length=500)
    policyComment: str | None = Field(default=None, max_length=300)
    policyPeriod: str | None = Field(default=None, max_length=100)
    status: PolicyStatus | None = None

    model_config = {"extra": "forbid"}

    @field_validator("officialUrl", "applyUrl")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return value


class AdminPolicyCreateRequest(_AdminPolicyWriteRequest):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    policyType: str = Field(min_length=1, max_length=30)
    region: str = Field(min_length=1, max_length=50)
    status: PolicyStatus = "active"


class AdminPolicyUpdateRequest(_AdminPolicyWriteRequest):
    pass


class AdminPolicyListResponse(BaseModel):
    items: list[AdminPolicyListItem]
    total: int
    limit: int
    offset: int


class AdminAuditLogListItem(BaseModel):
    id: str
    adminUserId: str
    adminEmail: str
    action: str
    targetType: str
    targetId: str
    summary: str | None = None
    beforeJson: dict[str, Any] | None = None
    afterJson: dict[str, Any] | None = None
    createdAt: str


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogListItem]
    total: int
    limit: int
    offset: int


class AdminExternalSourceSummaryItem(BaseModel):
    sourceCategory: str
    label: str
    sourceName: str
    totalRecords: int
    activeRecords: int
    scheduledRecords: int
    endedRecords: int
    unknownRecords: int
    freshRecords: int
    promotedPolicyCount: int
    activePromotedPolicyCount: int
    latestFetchedAt: str | None = None
    latestVerifiedAt: str | None = None


class AdminExternalSourceSummaryResponse(BaseModel):
    items: list[AdminExternalSourceSummaryItem]
    totalRecords: int
    activeRecords: int
    freshRecords: int
    promotedPolicyCount: int
    latestFetchedAt: str | None = None


class AdminPolicyCardPreview(BaseModel):
    amount: str
    evidence: str
    issues: list[str] = Field(default_factory=list)


class AdminPolicyReviewCandidateItem(BaseModel):
    id: str
    externalSourceRecordId: str
    reviewStatus: Literal["pending", "approved", "rejected", "superseded"]
    changeKind: Literal["new", "material_change"]
    title: str
    sourceCategory: str
    officialUrl: str
    benefitText: str
    region: str | None = None
    city: str | None = None
    status: str
    startDate: date | None = None
    endDate: date | None = None
    createdAt: str
    reviewReason: str | None = None
    # full_policy: 승인하면 정책 전체가 승격된다. card_copy_only: 카드 문구만 바뀐 후보 - 승인해도 card_summary 만 바뀐다.
    reviewScope: Literal["full_policy", "card_copy_only"] = "full_policy"
    cardPreview: AdminPolicyCardPreview


class AdminPolicyReviewCandidateListResponse(BaseModel):
    items: list[AdminPolicyReviewCandidateItem]
    total: int
    limit: int
    offset: int


class AdminPolicyReviewBatchApproveRequest(BaseModel):
    candidateIds: list[str] = Field(default_factory=list, max_length=100)
    approveAll: bool = False
    note: str | None = Field(default=None, max_length=2000)


class AdminPolicyReviewBatchApproveResponse(BaseModel):
    approvedCount: int
    approvedCandidateIds: list[str]


class AdminPolicyReviewDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class AdminPolicyReviewRejectRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class AdminCollectionSourceItem(BaseModel):
    key: str
    displayName: str
    officialUrl: str
    sourceCategory: str
    enabled: bool
    publicationMode: str
    expectedMinRecords: int = 0
    lastParsedCount: int | None = None
    autoApprovedLast24h: int = 0
    lastOutcome: str | None = None
    lastCollectedAt: str | None = None
    lastError: str | None = None


class AdminCollectionSourceListResponse(BaseModel):
    items: list[AdminCollectionSourceItem]


class AdminCollectionSourceUpdateRequest(BaseModel):
    enabled: bool | None = None
    publicationMode: Literal["review", "auto_after_reviewed_baseline"] | None = None
    expectedMinRecords: int | None = Field(default=None, ge=0)


# Eligible island catalog review — independent of policy review candidates.


class AdminEligibleIslandAttachment(BaseModel):
    url: str
    filename: str
    sha256: str


class AdminEligibleIslandSnapshotItem(BaseModel):
    id: str
    reviewStatus: Literal["pending", "approved", "rejected", "superseded"]
    isCurrentApproved: bool
    entryCount: int
    addedCount: int
    removedCount: int
    changedCount: int
    sourceNoticeUrl: str | None = None
    sourceNoticeTitle: str | None = None
    attachmentFiles: list[AdminEligibleIslandAttachment]
    attachmentFingerprint: str | None = None
    parserVersion: str
    fetchedAt: str
    reviewedAt: str | None = None
    reviewNote: str | None = None
    createdAt: str


class AdminEligibleIslandSnapshotListResponse(BaseModel):
    items: list[AdminEligibleIslandSnapshotItem]
    total: int
    limit: int
    offset: int
    approvedSnapshotId: str | None = None
    approvedEntryCount: int


class AdminEligibleIslandEntry(BaseModel):
    displayName: str
    normalizedName: str
    jurisdictionName: str


class AdminEligibleIslandSnapshotDetail(BaseModel):
    snapshot: AdminEligibleIslandSnapshotItem
    added: list[AdminEligibleIslandEntry]
    removed: list[AdminEligibleIslandEntry]
    unchanged: list[AdminEligibleIslandEntry]
    addedTotal: int
    removedTotal: int
    unchangedTotal: int
    limit: int
    offset: int


class AdminEligibleIslandRejectRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class AdminEligibleIslandCollectResponse(BaseModel):
    outcome: Literal["created", "unchanged", "identical", "suspicious_shrink", "download_failed", "parser_changed"]
    snapshotId: str | None = None
    entryCount: int
    error: str | None = None


PhotoReviewUnit = Literal["region", "policy"]
PhotoReviewStatus = Literal["pending", "approved", "none"]


class AdminPhotoReviewPhoto(BaseModel):
    candidateId: str
    title: str
    imageUrl: str
    thumbnailUrl: str | None = None
    copyrightType: str | None = None


class AdminPhotoReviewTargetItem(BaseModel):
    id: str
    unit: PhotoReviewUnit
    status: PhotoReviewStatus
    sido: str
    city: str
    policySlug: str | None = None
    policyTitle: str | None = None
    policyCategory: str | None = None
    benefitCount: int
    candidateCount: int
    photo: AdminPhotoReviewPhoto | None = None
    inheritedPhoto: AdminPhotoReviewPhoto | None = None
    decidedAt: str | None = None


class AdminPhotoReviewCandidate(BaseModel):
    id: str
    title: str
    kind: str
    contentTypeId: str | None = None
    imageUrl: str
    thumbnailUrl: str | None = None
    copyrightType: str | None = None
    width: int | None = None
    height: int | None = None
    address: str | None = None
    source: Literal["collect", "search"]
    searchKeyword: str | None = None


class AdminPhotoReviewTargetDetail(AdminPhotoReviewTargetItem):
    candidates: list[AdminPhotoReviewCandidate]


class AdminPhotoReviewCounts(BaseModel):
    pending: int
    approved: int
    none: int
    all: int


class AdminPhotoReviewTargetListResponse(BaseModel):
    items: list[AdminPhotoReviewTargetItem]
    counts: AdminPhotoReviewCounts
    pendingTotal: int


class AdminPhotoReviewApproveRequest(BaseModel):
    candidateId: str = Field(min_length=1, max_length=40)


class AdminPhotoReviewSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=50)
