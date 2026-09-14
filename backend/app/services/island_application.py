"""Team (trip) level progress through the island travel support procedure.

The approved procedure comes from applicationGuide; checks are computed from the trip, never stored.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.models import Policy, Trip, TripPolicy
from app.models import policy_status as policy_status_module
from app.repositories.eligible_islands import normalize_island_name
from app.services.island_application_guide import application_guide_for_api

ISLAND_SOURCE_CATEGORY = "island_visit"

# One step forward along the official procedure; stepping back one step is also allowed (a mistaken tap).
_FORWARD: dict[str, frozenset[str]] = {
    "not_started": frozenset({"applied"}),
    "applied": frozenset({"selected", "not_selected"}),
    "selected": frozenset({"traveled"}),
    "not_selected": frozenset(),
    "traveled": frozenset({"documents_submitted"}),
    "documents_submitted": frozenset({"paid"}),
    "paid": frozenset(),
}


def today() -> date:
    return policy_status_module.policy_visibility_date()


def active_guide(policy: Policy | None, *, on: date) -> dict[str, Any] | None:
    """The projected guide while some round can still be acted on (through its document due date)."""
    if policy is None or policy.source_category != ISLAND_SOURCE_CATEGORY:
        return None
    guide = application_guide_for_api(policy.structured_detail, today=on)
    return guide if guide is not None and guide["currentRoundKey"] is not None else None


def can_transition(current: str, target: str) -> bool:
    if target == current:
        return True
    return target in _FORWARD.get(current, frozenset()) or current in _FORWARD.get(target, frozenset())


def application_view(
    trip: Trip,
    link: TripPolicy,
    guide: dict[str, Any],
    *,
    approved_island_names: frozenset[str] | None,
    people_by_id: dict[int, str],
) -> dict[str, Any]:
    round_ = next((item for item in guide["rounds"] if item["key"] == guide["currentRoundKey"]), None)
    in_window = None
    if round_ is not None and round_["travelStart"] and round_["travelEnd"]:
        in_window = (
            date.fromisoformat(round_["travelStart"]) <= trip.start_date
            and trip.end_date <= date.fromisoformat(round_["travelEnd"])
        )
    matched = None
    if approved_island_names is not None:
        matched = any(
            normalize_island_name(place.place_name or "") in approved_island_names
            for day in trip.days
            for place in day.places
        )
    days = guide["documentDeadlineDaysAfterTrip"]
    checked = link.application_checklist if isinstance(link.application_checklist, dict) else {}
    updated_by = link.application_updated_by_user_id
    return {
        "status": link.application_status or "not_started",
        "roundKey": round_["key"] if round_ is not None else None,
        "checklist": [
            {"key": document, "label": document, "checked": bool(checked.get(document))}
            for document in guide["requiredDocuments"]
        ],
        "checks": {
            "inTravelWindow": in_window,
            "meetsMinNights": (trip.end_date - trip.start_date).days >= (guide["minNights"] or 1),
            "eligibleIslandMatched": matched,
            "applyDeadline": round_["applyUntil"] if round_ is not None else None,
            "documentsDueDate": (trip.end_date + timedelta(days=days)).isoformat() if days else None,
        },
        "updatedAt": f"{link.application_updated_at.isoformat()}Z" if link.application_updated_at else None,
        "updatedBy": people_by_id.get(int(updated_by)) if updated_by is not None else None,
    }
