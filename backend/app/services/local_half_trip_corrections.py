from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any
import unicodedata
from urllib.parse import urlparse

from app.models import ExternalSourceRecord


MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "policy_corrections"
    / "local_half_trip_five_20260716.json"
)
PUBLIC_MANUAL_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "policy_corrections"
    / "local_half_trip_public_manual_20260726.json"
)
SOURCE_CATEGORY = "local_half_trip"


class LocalHalfTripCorrectionManifestError(RuntimeError):
    """Raised when the scoped local-half-trip correction manifest is not trusted."""


@dataclass(frozen=True)
class LocalHalfTripCorrection:
    slug: str
    external_source_record_id: int
    status: str
    verification_status: str
    structured_detail: dict[str, list[dict[str, Any]]]
    target_condition: str | None


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {_normalize(key): _normalize(item) for key, item in value.items()}
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_local_half_trip_five_manifest(
    path: Path | None = None,
) -> dict[str, Any]:
    manifest_path = path or MANIFEST_PATH
    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)
    if not isinstance(manifest, dict):
        raise LocalHalfTripCorrectionManifestError("manifest root must be an object")
    digest_payload = dict(manifest)
    stored_digest = digest_payload.pop("manifestDigest", None)
    if not isinstance(stored_digest, str) or not re_fullmatch_sha256(stored_digest):
        raise LocalHalfTripCorrectionManifestError("manifestDigest must be a SHA-256 hex string")
    actual_digest = canonical_sha256(digest_payload)
    if actual_digest != stored_digest:
        raise LocalHalfTripCorrectionManifestError(
            f"manifestDigest mismatch: expected {stored_digest}, calculated {actual_digest}"
        )
    return manifest


def re_fullmatch_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _item(title: str, description: str) -> dict[str, str]:
    return {"title": title, "description": " ".join(description.split())}


def _period_item(value: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": str(value.get("title") or "기간"),
        "description": " ".join(str(value.get("description") or "").split()),
    }
    for key in ("type", "startDate", "endDate"):
        if value.get(key) is not None:
            item[key] = value[key]
    return item


def _structured_detail(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "supportContent": [
            _item("지원내용", value)
            for value in summary.get("supportContent", [])
            if isinstance(value, str) and value.strip()
        ],
        "periods": [
            _period_item(value)
            for value in summary.get("periods", [])
            if isinstance(value, dict)
        ],
        "applicationTarget": [
            _item("신청대상", value)
            for value in summary.get("applicationTarget", [])
            if isinstance(value, str) and value.strip()
        ],
        "requiredDocuments": [
            _item("필요서류", value)
            for value in summary.get("requiredDocuments", [])
            if isinstance(value, str) and value.strip()
        ],
        "notes": [
            _item("비고", value)
            for value in summary.get("notes", [])
            if isinstance(value, str) and value.strip()
        ],
    }


@lru_cache(maxsize=1)
def local_half_trip_five_corrections() -> dict[int, LocalHalfTripCorrection]:
    manifest = load_local_half_trip_five_manifest()
    corrections: dict[int, LocalHalfTripCorrection] = {}
    for record in manifest.get("records", []):
        if not isinstance(record, dict):
            continue
        source_id = int(record["externalSourceRecordId"])
        status = record.get("desiredStatus", {})
        summary = record.get("expectedFiveSectionSummary", {})
        structured_detail = _structured_detail(summary if isinstance(summary, dict) else {})
        target_values = [
            str(item["description"])
            for item in structured_detail["applicationTarget"]
            if item.get("description")
        ]
        corrections[source_id] = LocalHalfTripCorrection(
            slug=str(record["slug"]),
            external_source_record_id=source_id,
            status=str(status.get("status") or "hidden"),
            verification_status=str(status.get("verificationStatus") or "needs_review"),
            structured_detail=structured_detail,
            target_condition="\n".join(target_values) if target_values else None,
        )
    return corrections


def correction_for_record(record: ExternalSourceRecord) -> LocalHalfTripCorrection | None:
    if record.source_category != SOURCE_CATEGORY or record.id is None:
        return None
    scoped = local_half_trip_five_corrections().get(int(record.id))
    if scoped is not None:
        return scoped
    return local_half_trip_public_manual_correction_for_record(record)


@lru_cache(maxsize=1)
def local_half_trip_public_manual_corrections() -> dict[str, dict[str, Any]]:
    if not PUBLIC_MANUAL_PATH.exists():
        return {}
    with PUBLIC_MANUAL_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)
    if not isinstance(manifest, dict):
        return {}
    records = manifest.get("records")
    if not isinstance(records, list):
        return {}
    corrections: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        city = str(record.get("city") or "").strip()
        summary = record.get("expectedFiveSectionSummary")
        if city and isinstance(summary, dict):
            corrections[city] = record
    return corrections


def local_half_trip_public_manual_correction_for_record(
    record: ExternalSourceRecord,
) -> LocalHalfTripCorrection | None:
    city = str(record.city or "").strip()
    if not city:
        return None
    correction = local_half_trip_public_manual_corrections().get(city)
    if correction is None:
        return None
    evidence_hosts = {
        urlparse(str(url)).netloc.removeprefix("www.")
        for url in correction.get("evidenceUrls", [])
        if isinstance(url, str)
    }
    detail_host = urlparse(str(record.detail_url or "")).netloc.removeprefix("www.")
    if evidence_hosts and detail_host not in evidence_hosts:
        return None
    summary = correction.get("expectedFiveSectionSummary")
    if not isinstance(summary, dict):
        return None
    structured_detail = _structured_detail(summary)
    target_values = [
        str(item["description"])
        for item in structured_detail["applicationTarget"]
        if item.get("description")
    ]
    return LocalHalfTripCorrection(
        slug=str(correction.get("slug") or f"travelmonth-{record.id}"),
        external_source_record_id=int(record.id or 0),
        status=str(correction.get("status") or record.status or "active"),
        verification_status=str(correction.get("verificationStatus") or "needs_review"),
        structured_detail=structured_detail,
        target_condition="\n".join(target_values) if target_values else None,
    )
