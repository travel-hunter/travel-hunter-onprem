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
