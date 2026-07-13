from pydantic import BaseModel, EmailStr, Field


class SocialAccount(BaseModel):
    provider: str
    providerNickname: str | None = None
    connectedAt: str


class User(BaseModel):
    id: str
    nickname: str
    email: str
    role: str = "user"
    hasPassword: bool
    preferredRegions: list[str] | None = None
    persona: str
    savedAmount: int
    onboardingCompleted: bool
    nicknameSetupCompleted: bool
    socialAccounts: list[SocialAccount]
    createdAt: str
    updatedAt: str


class Profile(BaseModel):
    preferredRegions: list[str] | None = None
    style: str | None = None
    budget: str | None = None


class ProfileUpdate(BaseModel):
    preferredRegions: list[str] | None = None
    style: str | None = None
    budget: str | None = None

    model_config = {"extra": "forbid"}


class ProfileOptions(BaseModel):
    regions: list[str]
    travelStyles: list[str]
    budgets: list[str]


class ProfileSkipResponse(BaseModel):
    skipped: bool
    onboardingCompleted: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RequiredAgreement(BaseModel):
    termsAccepted: bool
    privacyAccepted: bool
    termsVersion: str = Field(min_length=1, max_length=32)
    privacyVersion: str = Field(min_length=1, max_length=32)


class SignupRequest(BaseModel):
    email: EmailStr
    agreements: RequiredAgreement


class SignupVerificationResponse(BaseModel):
    verificationRequired: bool
    email: str


class SignupVerifyRequest(BaseModel):
    token: str = Field(min_length=1)


class SignupVerifyResponse(BaseModel):
    verified: bool
    email: str


class SignupCompleteRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8)


class PendingSocialSignupResponse(BaseModel):
    provider: str
    email: str
    nickname: str | None = None
    expiresAt: str
    redirectPath: str


class CompleteSocialSignupRequest(BaseModel):
    token: str = Field(min_length=1)
    agreements: RequiredAgreement


class EmailAvailabilityRequest(BaseModel):
    email: EmailStr


class EmailAvailabilityResponse(BaseModel):
    available: bool


class NicknameSuggestion(BaseModel):
    nickname: str


class NicknameUpdate(BaseModel):
    nickname: str = Field(min_length=2, max_length=20, pattern=r"^[가-힣a-zA-Z0-9_ ]+$")


class AuthResponse(BaseModel):
    accessToken: str
    user: User


class LogoutResponse(BaseModel):
    loggedOut: bool


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordChangeRequest(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8)

    model_config = {"extra": "forbid"}


class PasswordChangeResponse(BaseModel):
    changed: bool


class WithdrawRequest(BaseModel):
    password: str | None = None
    confirmationPhrase: str | None = None

    model_config = {"extra": "forbid"}


class WithdrawResponse(BaseModel):
    withdrawn: bool


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1)
    newPassword: str = Field(min_length=8)


class PasswordResetResponse(BaseModel):
    requested: bool


class PasswordResetConfirmResponse(BaseModel):
    reset: bool
