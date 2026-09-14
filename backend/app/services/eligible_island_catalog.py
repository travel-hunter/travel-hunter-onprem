"""Eligible island catalog lifecycle: stage a diffed pending snapshot, approve atomically, reject.

Only `eligible_islands` changes on approval. policies / trip_policies / PolicyReviewCandidate are never touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import security
from app.models import EligibleIsland, EligibleIslandCatalogSnapshot, EligibleIslandSnapshotEntry, User
from app.repositories import admin as admin_repository
from app.repositories import eligible_islands as repository
from app.repositories.eligible_islands import EligibleIslandCatalogError
from app.services.eligible_island_notice import PARSER_VERSION, ParsedIsland, SourceDocument, source_fingerprint

# Shrinking by more than this percent of the approved catalog needs a human to look at the source first.
SUSPICIOUS_SHRINK_PERCENT = 30

DiffKey = tuple[str, str]  # (normalized_name, jurisdiction_name)


@dataclass(frozen=True)
class StageResult:
    outcome: str  # created | identical | empty | suspicious_shrink
    snapshot: EligibleIslandCatalogSnapshot | None = None
    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0


@dataclass(frozen=True)
class SnapshotDiff:
    snapshot: EligibleIslandCatalogSnapshot
    added: list[EligibleIslandSnapshotEntry]
    removed: list[EligibleIsland]
    unchanged: list[EligibleIslandSnapshotEntry]


def _key(item: ParsedIsland | EligibleIsland | EligibleIslandSnapshotEntry) -> DiffKey:
    return (item.normalized_name, item.jurisdiction_name)


def stage_snapshot(
    db: Session,
    *,
    catalog_key: str,
    entries: list[ParsedIsland],
    notice_url: str,
    notice_title: str | None,
    documents: list[SourceDocument],
    fetched_at: datetime,
) -> StageResult:
    catalog = repository.lock_catalog_row(db, catalog_key=catalog_key)
    if not entries:
        return StageResult(outcome="empty")

    approved = {_key(row): row for row in repository.list_approved_entries(db, catalog_key=catalog_key)}
    incoming = {_key(item): item for item in entries}
    added = incoming.keys() - approved.keys()
    removed = approved.keys() - incoming.keys()
    changed = {key for key in incoming.keys() & approved.keys() if incoming[key].display_name != approved[key].display_name}
    if not added and not removed and not changed:
        return StageResult(outcome="identical")
    # Spec: total count shrinking by more than 30% versus the approved catalog (not per-row churn).
    if approved and (len(approved) - len(incoming)) * 100 > SUSPICIOUS_SHRINK_PERCENT * len(approved):
        return StageResult(outcome="suspicious_shrink", added_count=len(added), removed_count=len(removed), changed_count=len(changed))

    snapshot = repository.create_snapshot(
        db,
        catalog_key=catalog_key,
        notice_url=notice_url,
        notice_title=notice_title,
        attachment_url=documents[0].url if documents else None,
        attachment_filename=documents[0].filename if documents else None,
        attachment_fingerprint=source_fingerprint(documents) if documents else None,
        attachment_documents=[document.to_json() for document in documents],
        parser_version=PARSER_VERSION,
        fetched_at=fetched_at,
        added_count=len(added),
        removed_count=len(removed),
        changed_count=len(changed),
    )
    for item in entries:
        repository.add_snapshot_entry(
            db, snapshot=snapshot, name=item.display_name, jurisdiction=item.jurisdiction_name, raw_region_text=item.raw_region_text
        )
    db.flush()
    repository.supersede_pending_snapshots(db, catalog_id=catalog.id, keep_snapshot_id=snapshot.id)
    return StageResult(outcome="created", snapshot=snapshot, added_count=len(added), removed_count=len(removed), changed_count=len(changed))


def _pending_snapshot_for_update(db: Session, *, catalog_id: int, snapshot_id: int) -> EligibleIslandCatalogSnapshot:
    snapshot = db.scalar(
        select(EligibleIslandCatalogSnapshot)
        .where(EligibleIslandCatalogSnapshot.id == snapshot_id, EligibleIslandCatalogSnapshot.catalog_id == catalog_id)
        .with_for_update()
    )
    if snapshot is None:
        raise EligibleIslandCatalogError("snapshot_not_found")
    if snapshot.review_status != "pending":
        raise EligibleIslandCatalogError("snapshot_not_pending")
    return snapshot


def approve_snapshot(db: Session, *, catalog_key: str, snapshot_id: int, admin: User) -> EligibleIslandCatalogSnapshot:
    catalog = repository.lock_catalog_row(db, catalog_key=catalog_key)
    snapshot = _pending_snapshot_for_update(db, catalog_id=catalog.id, snapshot_id=snapshot_id)
    previous_snapshot_id = catalog.approved_snapshot_id

    db.execute(delete(EligibleIsland).where(EligibleIsland.catalog_id == catalog.id))
    entries = db.scalars(
        select(EligibleIslandSnapshotEntry).where(EligibleIslandSnapshotEntry.snapshot_id == snapshot.id)
    ).all()
    db.add_all(
        EligibleIsland(
            catalog_id=catalog.id,
            snapshot_id=snapshot.id,
            display_name=entry.display_name,
            normalized_name=entry.normalized_name,
            jurisdiction_name=entry.jurisdiction_name,
        )
        for entry in entries
    )
    catalog.approved_snapshot_id = snapshot.id
    snapshot.review_status = "approved"
    snapshot.reviewed_by_user_id = admin.id
    snapshot.reviewed_at = security.utc_now_naive()
    db.flush()
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(admin.id),
        action="eligible_island_catalog.approve",
        target_type="eligible_island_catalog_snapshot",
        target_id=str(snapshot.id),
        summary=f"Approved eligible island catalog {catalog.key} snapshot {snapshot.id}",
        before_json={"approvedSnapshotId": previous_snapshot_id},
        after_json={
            "approvedSnapshotId": snapshot.id,
            "entryCount": len(entries),
            "addedCount": snapshot.added_count,
            "removedCount": snapshot.removed_count,
            "changedCount": snapshot.changed_count,
        },
    )
    db.commit()
    return snapshot


def reject_snapshot(db: Session, *, catalog_key: str, snapshot_id: int, admin: User, note: str) -> EligibleIslandCatalogSnapshot:
    cleaned_note = note.strip()
    if not cleaned_note:
        raise EligibleIslandCatalogError("note_required")
    catalog = repository.lock_catalog_row(db, catalog_key=catalog_key)
    snapshot = _pending_snapshot_for_update(db, catalog_id=catalog.id, snapshot_id=snapshot_id)
    snapshot.review_status = "rejected"
    snapshot.review_note = cleaned_note
    snapshot.reviewed_by_user_id = admin.id
    snapshot.reviewed_at = security.utc_now_naive()
    db.flush()
    admin_repository.add_audit_log(
        db,
        admin_user_id=int(admin.id),
        action="eligible_island_catalog.reject",
        target_type="eligible_island_catalog_snapshot",
        target_id=str(snapshot.id),
        summary=f"Rejected eligible island catalog {catalog.key} snapshot {snapshot.id}",
        before_json={"reviewStatus": "pending"},
        after_json={"reviewStatus": "rejected", "note": cleaned_note},
    )
    db.commit()
    return snapshot


def get_snapshot_diff(db: Session, *, catalog_key: str, snapshot_id: int) -> SnapshotDiff:
    catalog = repository.lock_catalog_row(db, catalog_key=catalog_key)
    snapshot = db.scalar(
        select(EligibleIslandCatalogSnapshot).where(
            EligibleIslandCatalogSnapshot.id == snapshot_id, EligibleIslandCatalogSnapshot.catalog_id == catalog.id
        )
    )
    if snapshot is None:
        raise EligibleIslandCatalogError("snapshot_not_found")
    approved = {_key(row): row for row in repository.list_approved_entries(db, catalog_key=catalog_key)}
    entries = db.scalars(
        select(EligibleIslandSnapshotEntry)
        .where(EligibleIslandSnapshotEntry.snapshot_id == snapshot.id)
        .order_by(EligibleIslandSnapshotEntry.normalized_name, EligibleIslandSnapshotEntry.jurisdiction_name)
    ).all()
    incoming = {_key(entry) for entry in entries}
    return SnapshotDiff(
        snapshot=snapshot,
        added=[entry for entry in entries if _key(entry) not in approved],
        removed=[row for key, row in approved.items() if key not in incoming],
        unchanged=[entry for entry in entries if _key(entry) in approved],
    )
