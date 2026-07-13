from typing import Any, Literal

from pydantic import BaseModel, Field


PolicyCategory = Literal["교통", "숙박", "여행상품", "지역할인", "이벤트", "기타"]
PolicySourceType = Literal["internal", "external"]
PolicyActionStatus = Literal["infoOnly"]


class PolicyStructuredDetail(BaseModel):
    benefits: list[dict[str, Any]] = Field(default_factory=list)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    periods: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    notices: list[dict[str, Any]] = Field(default_factory=list)


class Policy(BaseModel):
    id: str
    slug: str
    label: str
    tag: str
    title: str
    org: str
    region: str
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
