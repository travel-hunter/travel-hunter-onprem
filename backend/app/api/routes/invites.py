from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.trip import InviteState
from app.services import trips as trip_service

router = APIRouter(prefix="/invites", tags=["invites"])


def _require_db(db: Session | None) -> Session:
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is required")
    return db


def _require_user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.post("/{invite_token}/accept", response_model=InviteState)
def accept_invite(
    invite_token: str,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> InviteState:
    try:
        invite = trip_service.accept_invite(
            _require_db(db),
            _require_user(current_user),
            invite_token,
        )
    except trip_service.TripServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    return InviteState(**invite)
