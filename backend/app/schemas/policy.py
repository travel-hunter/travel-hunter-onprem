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


class ApplicationGuideRound(BaseModel):
    key: str
    label: str
    status: Literal["past", "current", "upcoming"]
    applyStart: str | None = None
    applyUntil: str | None = None
    travelStart: str | None = None
    travelEnd: str | None = None
    documentsDueBy: str | None = None
    applicationFormUrl: str | None = None
    documentFormUrl: str | None = None


class ApplicationGuideContacts(BaseModel):
    email: str | None = None
    phones: list[str] = Field(default_factory=list)


class ApplicationGuide(BaseModel):
    rounds: list[ApplicationGuideRound]
    currentRoundKey: str | None = None
    applyFormUrl: str | None = None
    documentDeadlineDaysAfterTrip: int | None = None
    minNights: int | None = None
    minPaymentKrw: int | None = None
    requiredDocuments: list[str] = Field(default_factory=list)
    photoRequirement: str | None = None
    exclusions: list[str] = Field(default_factory=list)
    contacts: ApplicationGuideContacts = Field(default_factory=ApplicationGuideContacts)


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
    # island_visit only: reviewed procedure with round status and open form computed at read time.
    applicationGuide: ApplicationGuide | None = None


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
