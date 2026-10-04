"""주 1회 TourAPI 공공데이터 장소 동기화 - 기본 꺼짐, 때(오늘 시도 · 7일)는 DB 상태로 가리고, 실패는 오류 결과로 남긴다."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import replace

import pytest

from app.core.config import Settings
from app.services import public_places_scheduler
from app.services.public_places_scheduler import run_public_places_sync_once, start_public_places_sync_scheduler


def _fake_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places_scheduler, "build_tour_api_client", lambda *_: object())
    monkeypatch.setattr(public_places_scheduler, "get_session_factory", lambda: (lambda: nullcontext(object())))


def test_sync_scheduler_is_off_by_default() -> None:
    assert Settings().public_places_sync_enabled is False
    assert start_public_places_sync_scheduler(replace(Settings(), public_places_sync_enabled=False)) is None


def test_sync_once_is_skipped_when_tour_api_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places_scheduler, "build_tour_api_client", lambda *_: None)
    assert run_public_places_sync_once().outcome == "skipped"


def test_sync_once_does_nothing_when_it_is_not_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_session(monkeypatch)
    monkeypatch.setattr(public_places_scheduler, "tourapi_sync_due", lambda *_, **__: False)
    monkeypatch.setattr(public_places_scheduler, "sync_tourapi_places", lambda *_, **__: pytest.fail("must not sync"))
    assert run_public_places_sync_once().outcome == "skipped"


def test_sync_once_turns_a_failure_into_an_error_result(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("TourAPI request failed.")

    _fake_session(monkeypatch)
    monkeypatch.setattr(public_places_scheduler, "tourapi_sync_due", lambda *_, **__: True)
    monkeypatch.setattr(public_places_scheduler, "sync_tourapi_places", boom)
    caplog.set_level(logging.ERROR)
    assert run_public_places_sync_once().outcome == "error"
    assert "public_places_sync_failed" in caplog.text
