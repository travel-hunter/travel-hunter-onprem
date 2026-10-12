from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.places import GeoKind, PlaceMatchResponse, PublicPlaceCategory, PublicPlaceItem


InviteRole = Literal["editor"]
TripRole = Literal["owner", "editor", "viewer"]
TripStatus = Literal["draft", "confirmed"]
TripDateOverflowStrategy = Literal["moveToLastDay", "delete"]
RecommendationSourceType = Literal["freshCandidate", "savedSummary", "public_place"]
InviteEmailDeliveryStatus = Literal["sent", "notConfigured", "failed"]
PlaceOrigin = Literal["public", "custom", "needs_review"]
PublicSource = Literal["tourapi", "sangga"]
MAX_TRIP_PARTICIPANTS = 10
MIN_TRIP_DURATION_DAYS = 1
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
    # 사용자가 쓴 메모(trip_places.memo 그대로) - meta 는 메모가 있으면 메모, 없으면 주소다. 새로 담은 행은 비어 있고 수정(PATCH memo)으로 채운다
    memo: str | None = None
    # 3단계(카카오 운영정책): 저장하는 값은 공공데이터 장소 또는 사용자가 쓴 값이다. placeOrigin 이 비어 있으면 예전 행
    placeOrigin: PlaceOrigin | None = None
    publicSource: PublicSource | None = None
    publicSourceId: str | None = None
    publicCategory: PublicPlaceCategory | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None
    # 주소 채움으로 담은 나만의 장소의 출처 종류(건물 · 땅). 화면이 출처 표시(국토교통부 공공데이터)에 쓴다
    geoKind: GeoKind | None = None
    # 예전 카카오 행(placeOrigin 없음 + sourceProvider 가 kakao · kakao_local) - 편집하려면 이름을 다시 적어야 한다
    needsConfirmation: bool = False


ApplicationStatus = Literal[
    "not_started", "applied", "selected", "not_selected", "traveled", "documents_submitted", "paid"
]


class TripPolicyApplicationDocument(BaseModel):
    key: str
    label: str
    checked: bool


class TripPolicyApplicationChecks(BaseModel):
    inTravelWindow: bool | None = None
    meetsMinNights: bool
    eligibleIslandMatched: bool | None = None
    applyDeadline: str | None = None
    documentsDueDate: str | None = None


class TripPolicyApplication(BaseModel):
    status: ApplicationStatus
    roundKey: str | None = None
    checklist: list[TripPolicyApplicationDocument]
    checks: TripPolicyApplicationChecks
    updatedAt: str | None = None
    updatedBy: str | None = None


class UpdateTripPolicyApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    checklist: dict[str, bool] | None = Field(default=None, max_length=20)


class LinkedTripPolicy(BaseModel):
    slug: str
    title: str
    amount: str
    region: str
    status: Literal["active", "hidden"] = "active"
    deadline: str | None = None
    # 일정 화면의 "혜택 안내 보기"가 앱 안 정책 상세를 거치지 않고 공식 사이트로 바로 나간다
    officialUrl: str | None = None
    applyUrl: str | None = None
    application: TripPolicyApplication | None = None


class CreateTripRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    region: str | None = None
    travelAreaId: str | None = Field(default=None, max_length=120)
    participantCount: int = Field(default=1, ge=1, le=MAX_TRIP_PARTICIPANTS)
    style: str | None = None
    description: str | None = Field(default=None, max_length=500)
    policySlug: str | None = None
    durationDays: int | None = Field(default=None, ge=MIN_TRIP_DURATION_DAYS)
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
            if day_count < MIN_TRIP_DURATION_DAYS:
                raise ValueError("Trip endDate must be on or after startDate")
        return self


class Trip(BaseModel):
    id: str
    title: str
    status: TripStatus
    revision: int
    travelAreaId: str | None = None
    region: str
    dates: str
    startDate: date
    endDate: date
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
    # sourceType 이 public_place 인 추천(공공데이터 장소) - 담을 때 publicSource + publicSourceId 를 publicPlace 로 보낸다
    publicSource: PublicSource | None = None
    publicSourceId: str | None = None
    publicCategory: PublicPlaceCategory | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None


class TripAreaCenter(BaseModel):
    """일정 지역의 공공데이터 장소 위경도 중앙값 - 위치 찍기 지도가 여기서 연다. 지역을 가리지 못하거나 장소가 없으면 둘 다 null."""

    latitude: float | None = None
    longitude: float | None = None


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
    # 결정 23: 서버가 같은 요청 안에서 맞춰 본 결과(POST /api/places/match 와 같은 모양). 늘 내보내고, 좌표가 없거나 실패하면 null
    publicMatch: PlaceMatchResponse | None = None
    # 일정 지역 중심에서 20km 안이면 true, 밖이면 false, 일정에 지역 중심이 없으면 null - 화면이 '다른 지역' 구분 줄을 긋는다
    nearby: bool | None = None
    # 친 말로 카카오가 0곳이라 우리 공공데이터 완성어로 대신 찾은 줄이면 그 말(카카오 값 아님), 아니면 null
    viaWord: str | None = None


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


class PublicPlaceRef(BaseModel):
    """공공데이터 장소 참조 - 서버가 자기 표(public_places)에서 값을 채운다. 클라이언트가 보낸 이름 · 주소 · 좌표는 받지 않는다(422) -
    중첩 모델도 extra="forbid" 라 카카오 값이 이 안에 숨어 들어와도 조용히 버려지지 않는다."""

    model_config = ConfigDict(extra="forbid")

    source: PublicSource
    sourceId: str = Field(min_length=1, max_length=40)


class GeoRef(BaseModel):
    """주소 채움 참조 - 건물 · 땅의 종류와 이 판의 id, 핀까지 담을지(pin). 주소 · 좌표는 서버가 geo 표에서 다시 읽는다.
    pin 이 false 면(넓은 땅) 주소만 담는다. 어느 쪽이든 저장되는 좌표는 우리 표의 중심뿐이다."""

    model_config = ConfigDict(extra="forbid")

    kind: GeoKind
    id: int = Field(ge=1, le=2**63 - 1)   # geo 표 PK(BIGINT) 상한 - 넘으면 DB 오류(500)가 아니라 422
    pin: bool


class CustomPlaceInput(BaseModel):
    """나만의 장소 - 사용자가 쓴 이름과 (선택) 주소 채움 참조. 위도 · 경도 · 주소는 받지 않는다(422) -
    지도에서 찍은 좌표는 저장 · 활용 불가(데브톡 151842)라, 찍은 자리는 화면이 geoRef 로 바꿔 보낸다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    geoRef: GeoRef | None = None


class TripPlaceAddItem(BaseModel):
    """담을 장소 하나. 예전 카카오 필드(label · meta · address · 좌표 · 분류 · placeUrl · sourceProvider · externalPlaceId)는 받지 않는다(422).
    카카오 장소는 장소 ID(kakaoPlaceId)만 받고, place_url 은 서버가 만든다."""

    model_config = ConfigDict(extra="forbid")

    time: str | None = None
    publicPlace: PublicPlaceRef | None = None
    customPlace: CustomPlaceInput | None = None
    kakaoPlaceId: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")

    @model_validator(mode="after")
    def validate_exactly_one_place(self) -> "TripPlaceAddItem":
        if (self.publicPlace is None) == (self.customPlace is None):
            raise ValueError("Provide exactly one of publicPlace or customPlace")
        return self


class CreateTripPlaceRequest(TripPlaceAddItem):
    expectedRevision: int = Field(ge=1)


class CreateTripPlacesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectedRevision: int = Field(ge=1)
    places: list[TripPlaceAddItem] = Field(min_length=1, max_length=50)


class DeleteTripPlacesRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    # ids are ints, unlike batch-add's full place objects; a whole-trip clear must fit
    placeIds: list[int] = Field(min_length=1, max_length=200)


class UpdateTripPlaceRequest(BaseModel):
    """장소 수정 - 바뀐 필드만 보낸다. label(이름)과 memo(메모)는 사용자가 쓴 값이다. publicPlace · customPlace 는 그 장소로 바꾼다(함께 못 온다).
    예전 카카오 값(meta · address · 좌표 · 분류)은 받지 않는다(422)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=500)
    publicPlace: PublicPlaceRef | None = None
    customPlace: CustomPlaceInput | None = None

    @model_validator(mode="after")
    def validate_one_replacement(self) -> "UpdateTripPlaceRequest":
        if self.publicPlace is not None and self.customPlace is not None:
            raise ValueError("Provide only one of publicPlace or customPlace")
        return self


class LegacyPlaceCandidatesResponse(BaseModel):
    """예전 카카오 행과 겹치는 공공데이터 후보 - 가까운 순 최대 3곳(바로 맞는 곳 포함). 없으면 빈 목록."""

    places: list[PublicPlaceItem]


class MoveTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    dayNumber: int = Field(ge=1)
    position: int = Field(ge=1)


class UpdateTripStatusRequest(BaseModel):
    status: TripStatus


class UpdateTripSettingsRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    travelAreaId: str | None = Field(default=None, max_length=120)
    startDate: date | None = None
    endDate: date | None = None
    overflowPlaceStrategy: TripDateOverflowStrategy = "moveToLastDay"
    # 지역을 바꾸면 새 지역과 안 맞는 연결 정책이 생긴다. 기본은 거부하고 목록을 돌려준다 -
    # 사용자가 확인한 뒤 "remove" 로 다시 보내면 지역 변경과 함께 뺀다.
    mismatchedPolicyStrategy: Literal["reject", "remove"] = "reject"

    @model_validator(mode="after")
    def validate_date_range(self) -> "UpdateTripSettingsRequest":
        has_start = self.startDate is not None
        has_end = self.endDate is not None
        if has_start != has_end:
            raise ValueError("startDate and endDate must be provided together")
        if self.startDate is not None and self.endDate is not None:
            day_count = (self.endDate - self.startDate).days + 1
            if day_count < MIN_TRIP_DURATION_DAYS:
                raise ValueError("Trip endDate must be on or after startDate")
        return self
