"""Public projection of the reviewed island_visit procedure (policies.structured_detail["applicationGuide"]).

Round status, document due dates and the open application form are computed on read, because they change with
the calendar while the approved procedure does not.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.services.island_visit_parser import representative_round, round_status

_GOOGLE_FORM = re.compile(r"^https://(?:forms\.gle/[A-Za-z0-9_-]+|docs\.google\.com/forms/\S+)$")


def _form_url(value: object) -> str | None:
    return value if isinstance(value, str) and _GOOGLE_FORM.match(value) else None


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _texts(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def application_guide_for_api(structured_detail: object, *, today: date) -> dict[str, Any] | None:
    guide = structured_detail.get("applicationGuide") if isinstance(structured_detail, dict) else None
    if not isinstance(guide, dict):
        return None
    raw_rounds = [item for item in guide.get("rounds") or [] if isinstance(item, dict) and item.get("key")]
    if not raw_rounds:
        return None
    days = _int(guide.get("documentDeadlineDaysAfterTrip")) or 0

    rounds: list[dict[str, Any]] = []
    for item in raw_rounds:
        travel_end = _text(item.get("travelEnd"))
        rounds.append(
            {
                "key": str(item["key"]),
                "label": f"{item['key']}차",
                "status": round_status(item, today=today, document_deadline_days=days),
                "applyStart": _text(item.get("applyStart")),
                "applyUntil": _text(item.get("applyUntil")),
                "travelStart": _text(item.get("travelStart")),
                "travelEnd": travel_end,
                "documentsDueBy": (date.fromisoformat(travel_end) + timedelta(days=days)).isoformat() if travel_end else None,
                "applicationFormUrl": _form_url(item.get("applicationFormUrl")),
                "documentFormUrl": _form_url(item.get("documentFormUrl")),
            }
        )

    representative = representative_round(rounds, today=today, document_deadline_days=days)
    current = representative if representative is not None and representative["status"] != "past" else None
    apply_form_url = None
    # ponytail: date-level comparison — on the deadline day the form stays offered after the stated hour.
    if (
        current is not None
        and current["status"] == "current"
        and current["applicationFormUrl"]
        and current["applyUntil"]
        and today <= date.fromisoformat(current["applyUntil"][:10])
    ):
        apply_form_url = current["applicationFormUrl"]

    contacts = guide.get("contacts") if isinstance(guide.get("contacts"), dict) else {}
    return {
        "rounds": rounds,
        "currentRoundKey": current["key"] if current is not None else None,
        "applyFormUrl": apply_form_url,
        "documentDeadlineDaysAfterTrip": _int(guide.get("documentDeadlineDaysAfterTrip")),
        "minNights": _int(guide.get("minNights")),
        "minPaymentKrw": _int(guide.get("minPaymentKrw")),
        "requiredDocuments": _texts(guide.get("requiredDocuments")),
        "photoRequirement": _text(guide.get("photoRequirement")),
        "exclusions": _texts(guide.get("exclusions")),
        "contacts": {"email": _text(contacts.get("email")), "phones": _texts(contacts.get("phones"))},
    }
