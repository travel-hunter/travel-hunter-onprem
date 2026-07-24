from __future__ import annotations

import copy
import json

import pytest

from app.services import local_half_trip_corrections as corrections


def test_manifest_digest_excludes_only_its_own_field() -> None:
    manifest = corrections.load_local_half_trip_five_manifest()
    digest_payload = dict(manifest)
    stored_digest = digest_payload.pop("manifestDigest")

    assert corrections.canonical_sha256(digest_payload) == stored_digest
    assert len(manifest["records"]) == 5


def test_manifest_digest_tampering_fails_closed(tmp_path) -> None:
    manifest = corrections.load_local_half_trip_five_manifest()
    tampered = copy.deepcopy(manifest)
    tampered["records"][0]["slug"] = "travelmonth-tampered"
    path = tmp_path / "tampered-local-half-trip-five.json"
    path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(corrections.LocalHalfTripCorrectionManifestError, match="manifestDigest mismatch"):
        corrections.load_local_half_trip_five_manifest(path)


def test_correction_loader_fails_closed_when_manifest_digest_is_invalid(tmp_path, monkeypatch) -> None:
    manifest = corrections.load_local_half_trip_five_manifest()
    broken = dict(manifest)
    broken["manifestDigest"] = "0" * 64
    path = tmp_path / "broken-local-half-trip-five.json"
    path.write_text(json.dumps(broken, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(corrections, "MANIFEST_PATH", path)
    corrections.local_half_trip_five_corrections.cache_clear()

    with pytest.raises(corrections.LocalHalfTripCorrectionManifestError, match="manifestDigest mismatch"):
        corrections.local_half_trip_five_corrections()

    corrections.local_half_trip_five_corrections.cache_clear()
