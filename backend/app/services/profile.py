from sqlalchemy.orm import Session

from app.models import User
from app.services import auth as auth_service
from app.repositories import users as user_repository
from app.schemas.user import ProfileUpdate
from app.services.profile_preferences import (
    ProfilePreferenceError,
    parse_preferred_regions,
    serialize_preferred_regions,
)


ProfileServiceError = ProfilePreferenceError


def profile_to_api(user: User) -> dict[str, object]:
    return {
        "preferredRegions": parse_preferred_regions(user.preferred_regions),
        "style": user.travel_style,
        "budget": user.travel_budget,
    }


def get_profile(user: User) -> dict[str, object]:
    return profile_to_api(user)


def update_profile(db: Session, user: User, request: ProfileUpdate) -> dict[str, object]:
    fields = request.model_fields_set
    updated = user_repository.update_user_profile(
        db,
        user,
        preferred_regions=serialize_preferred_regions(request.preferredRegions) if "preferredRegions" in fields else user_repository.UNSET,
        style=request.style if "style" in fields else user_repository.UNSET,
        budget=request.budget if "budget" in fields else user_repository.UNSET,
    )
    db.commit()
    return profile_to_api(updated)


def skip_profile_setup(db: Session, user: User) -> dict[str, object]:
    updated = user_repository.mark_profile_setup_skipped(db, user)
    db.commit()
    return auth_service.user_to_api(updated)
