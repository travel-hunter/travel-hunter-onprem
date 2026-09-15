from typing import Any, Literal

from pydantic import BaseModel, Field


PolicyCategory = Literal["교통", "숙박", "여행상품", "지역할인", "이벤트", "기타"]
PolicySourceType = Literal["internal", "external"]
PolicyActionStatus = Literal["infoOnly"]


class PolicyStructuredDetail(BaseModel):
    supportContent: list[dict[str, Any]] = Field(default_factory=list)
    periods: list[dict[str, Any]] = Field(default_factory=list)
    applicationTarget: list[dict[str, Any]] = Field(default_factory=list)
    requiredDocuments: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)


class PolicyPhoto(BaseModel):
    imageUrl: str
    thumbnailUrl: str | None = None
    alt: str
    attribution: str


class Policy(BaseModel):
    id: str
    slug: str
    label: str
    tag: str
    title: str
    org: str
    region: str
    startDate: str | None = None
    deadline: str
    amount: str
    summary: str
    match: int
    category: PolicyCategory
    requirements: list[str]
    documents: list[str]
    structuredDetail: PolicyStructuredDetail | None = None
    officialUrl: str | None = None
    applyUrl: str | None = None
    sourceType: PolicySourceType = "internal"
    actionStatus: PolicyActionStatus | None = None
    photo: PolicyPhoto | None = None
    # island_visit only: derived from the approved eligible island catalog, never the full list.
    eligibleIslandCount: int | None = None
    eligibleIslandsOfficialUrl: str | None = None


class AppliedPolicyLinkedTrip(BaseModel):
    id: str
    title: str
    region: str
    startDate: str | None = None
    endDate: str | None = None


class AppliedPolicyLink(BaseModel):
    policy: Policy
    linkedTrips: list[AppliedPolicyLinkedTrip]


class SavePolicyResponse(BaseModel):
    policyId: str
    saved: bool
