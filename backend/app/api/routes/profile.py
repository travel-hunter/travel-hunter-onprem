from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.data import seed
from app.models import User as UserModel
from app.schemas.user import (
    NicknameSuggestion,
    NicknameUpdate,
    Profile,
    ProfileOptions,
    ProfileSkipResponse,
    ProfileUpdate,
    User,
)
from app.services import auth as auth_service
from app.services import nicknames as nickname_service
from app.services import profile as profile_service

router = APIRouter(tags=["profile"])


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is required")
    return db


def _require_user(user: UserModel | None) -> UserModel:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.get("/me", response_model=User)
def get_me(current_user: UserModel | None = Depends(get_current_user)) -> User:
    return User(**auth_service.user_to_api(_require_user(current_user)))


@router.get("/me/profile", response_model=Profile)
def get_profile(current_user: UserModel | None = Depends(get_current_user)) -> Profile:
    return Profile(**profile_service.get_profile(_require_user(current_user)))


@router.patch("/me/profile", response_model=Profile)
def update_profile(
    profile: ProfileUpdate,
    db: Session | None = Depends(get_optional_db),
    current_user: UserModel | None = Depends(get_current_user),
) -> Profile:
    try:
        return Profile(
            **profile_service.update_profile(
                _require_db(db),
                _require_user(current_user),
                profile,
            )
        )
    except profile_service.ProfileServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/me/profile/skip", response_model=ProfileSkipResponse)
def skip_profile_setup(
    db: Session | None = Depends(get_optional_db),
    current_user: UserModel | None = Depends(get_current_user),
) -> ProfileSkipResponse:
    user = profile_service.skip_profile_setup(
        _require_db(db),
        _require_user(current_user),
    )
    return ProfileSkipResponse(skipped=True, onboardingCompleted=bool(user["onboardingCompleted"]))


@router.get("/me/nickname-suggestion", response_model=NicknameSuggestion)
def get_nickname_suggestion(current_user: UserModel | None = Depends(get_current_user)) -> NicknameSuggestion:
    _require_user(current_user)
    return NicknameSuggestion(nickname=nickname_service.generate_random_nickname())


@router.patch("/me/nickname", response_model=User)
def update_nickname(
    nickname: NicknameUpdate,
    db: Session | None = Depends(get_optional_db),
    current_user: UserModel | None = Depends(get_current_user),
) -> User:
    try:
        user = nickname_service.update_nickname(
            _require_db(db),
            _require_user(current_user),
            nickname.nickname,
        )
    except nickname_service.NicknameServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return User(**auth_service.user_to_api(user))


@router.get("/profile-options", response_model=ProfileOptions)
def get_profile_options() -> ProfileOptions:
    return ProfileOptions(
        regions=list(seed.REGIONS),
        travelStyles=list(seed.TRAVEL_STYLES),
        budgets=list(seed.BUDGETS),
    )
