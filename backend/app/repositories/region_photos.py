from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RegionPhoto


def list_active_region_photos(db: Session) -> list[RegionPhoto]:
    stmt = (
        select(RegionPhoto)
        .where(RegionPhoto.status == "active")
        .where(RegionPhoto.hero_image_url.is_not(None))
    )
    return list(db.scalars(stmt))


def get_region_photo(
    db: Session, *, provider: str, sido: str, city: str
) -> RegionPhoto | None:
    stmt = (
        select(RegionPhoto)
        .where(RegionPhoto.provider == provider)
        .where(RegionPhoto.sido == sido)
        .where(RegionPhoto.city == city)
    )
    return db.scalars(stmt).first()


def upsert_region_photo(
    db: Session, *, provider: str, sido: str, city: str, **fields: object
) -> RegionPhoto:
    photo = get_region_photo(db, provider=provider, sido=sido, city=city)
    if photo is None:
        photo = RegionPhoto(provider=provider, sido=sido, city=city)
        db.add(photo)
    for name, value in fields.items():
        setattr(photo, name, value)
    db.flush()
    return photo
