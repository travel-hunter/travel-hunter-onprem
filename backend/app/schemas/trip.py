from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


InviteRole = Literal["viewer", "editor"]
TripRole = Literal["owner", "editor", "viewer"]
TripStatus = Literal["draft", "confirmed"]
RecommendationSourceType = Literal["freshCandidate", "savedSummary"]
InviteEmailDeliveryStatus = Literal["sent", "notConfigured", "failed"]
MAX_TRIP_PARTICIPANTS = 10
MAX_TRIP_DURATION_DAYS = 7


class ItineraryPlace(BaseModel):
    id: str | None = None
    time: str
    label: str
    meta: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    categoryCode: str | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = None
    externalPlaceId: str | None = None


class LinkedTripPolicy(BaseModel):
    slug: str
    title: str
    amount: str
    region: str
    status: Literal["active", "hidden"] = "active"


class CreateTripRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    region: str | None = None
    travelAreaId: str | None = Field(default=None, max_length=120)
    participantCount: int = Field(default=1, ge=1, le=MAX_TRIP_PARTICIPANTS)
    style: str | None = None
    description: str | None = Field(default=None, max_length=500)
    policySlug: str | None = None
    durationDays: int | None = Field(default=None, ge=2, le=MAX_TRIP_DURATION_DAYS)
    startDate: date | None = None
    endDate: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "CreateTripRequest":
        has_start = self.startDate is not None
        has_end = self.endDate is not None
        if has_start != has_end:
            raise ValueError("startDate and endDate must be provided together")
        if self.startDate is not None and self.endDate is not None:
            day_count = (self.endDate - self.startDate).days + 1
            if day_count < 2 or day_count > MAX_TRIP_DURATION_DAYS:
                raise ValueError("Trip date range must be between 2 and 7 days")
        return self


class Trip(BaseModel):
    id: str
    title: str
    status: TripStatus
    revision: int
    travelAreaId: str | None = None
    dates: str
    people: list[str]
    participantCount: int
    expectedSaving: str
    linkedPolicies: list[LinkedTripPolicy]
    recommendedPolicies: list[LinkedTripPolicy] = Field(default_factory=list)
    days: dict[int, list[ItineraryPlace]]
    currentUserRole: TripRole


class Recommendation(BaseModel):
    id: str | None = None
    label: str
    title: str
    meta: str
    reason: str
    categoryGroup: str | None = None
    categoryCode: str | None = None
    categoryName: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    placeUrl: str | None = None
    suggestedDay: int | None = None
    aiReview: str | None = None
    sourceProvider: str | None = None
    externalPlaceId: str | None = None
    sourceType: RecommendationSourceType | None = None


class PlaceSearchCandidate(BaseModel):
    id: str | None = None
    label: str = "📍"
    title: str
    meta: str
    categoryCode: str | None = None
    categoryName: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = "kakao"
    externalPlaceId: str | None = None


class InviteState(BaseModel):
    id: str
    tripId: str
    inviteToken: str
    inviteUrl: str
    expiresAt: str
    createdAt: str
    acceptedAt: str | None = None
    invited: bool
    copied: bool
    role: InviteRole = "editor"
    alreadyMember: bool = False


class InviteLinksState(BaseModel):
    tripId: str
    viewer: InviteState | None = None
    editor: InviteState | None = None


class ConfirmInviteRequest(BaseModel):
    role: InviteRole = "editor"


class SendInviteEmailRequest(BaseModel):
    email: EmailStr
    role: InviteRole = "editor"


class InviteEmailResult(BaseModel):
    invite: InviteState
    deliveryStatus: InviteEmailDeliveryStatus
    message: str


class TripPolicyResponse(BaseModel):
    tripId: str
    policyId: str
    added: bool


class DeleteTripResponse(BaseModel):
    tripId: str
    deleted: bool


class CreateTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str = Field(min_length=1, max_length=200)
    meta: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    categoryCode: str | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = None
    externalPlaceId: str | None = None


class UpdateTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)
    meta: str | None = None


class MoveTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    dayNumber: int = Field(ge=1)
    position: int = Field(ge=1)


class UpdateTripStatusRequest(BaseModel):
    status: TripStatus
