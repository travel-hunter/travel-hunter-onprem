from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.data.itinerary_catalog import ITINERARY_PLACE_CATALOG
from app.data.travel_areas import TravelArea, list_travel_areas
from app.db.session import get_session_factory
from app.models import Recommendation, Trip, TripDay, TripPlace, User
from app.repositories import users as user_repository


DEFAULT_EMAIL = "recommendation-diagnostic@example.com"
DEFAULT_STYLE = "휴식"
DEFAULT_DURATION_DAYS = 3
LOCAL_API_HOSTS = {"127.0.0.1", "localhost", "backend"}


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: Any


@dataclass(frozen=True)
class CoverageRow:
    travel_area_id: str
    area_name: str
    sido: str
    trip_id: str | None
    recommendation_count: int
    status: str
    ai_results_url: str
    create_response: Any | None = None
    recommendation_response: Any | None = None
    failure_detail: dict[str, Any] | None = None


class ApiClient(Protocol):
    def post_json(self, path: str, payload: dict[str, Any]) -> ApiResponse:
        ...

    def get_json(self, path: str) -> ApiResponse:
        ...


class BearerApiClient:
    def __init__(self, *, base_url: str, bearer_token: str, timeout_seconds: float = 20) -> None:
        self._base_url = base_url.rstrip("/")
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds

    def post_json(self, path: str, payload: dict[str, Any]) -> ApiResponse:
        return self._request_json("POST", path, payload)

    def get_json(self, path: str) -> ApiResponse:
        return self._request_json("GET", path, None)

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None) -> ApiResponse:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return ApiResponse(response.status, _decode_json_response(response.read()))
        except urllib.error.HTTPError as error:
            return ApiResponse(error.code, _decode_json_response(error.read()))
        except urllib.error.URLError as error:
            return ApiResponse(0, {"error": str(error.reason)})


def _decode_json_response(raw_body: bytes) -> Any:
    if not raw_body:
        return None
    text = raw_body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def ensure_diagnostic_user(db: Session, *, email: str = DEFAULT_EMAIL) -> User:
    user = user_repository.get_user_by_email(db, email)
    if user is None:
        user = User(
            email=email,
            nickname="Recommendation Diagnostic",
            password_hash=None,
            onboarding_completed=True,
            travel_style=DEFAULT_STYLE,
            region="전국",
        )
        db.add(user)
        db.flush()
    else:
        user.onboarding_completed = True
    db.commit()
    db.refresh(user)
    return user


def _area_payload(area: TravelArea, *, title_prefix: str, style: str, duration_days: int) -> dict[str, Any]:
    return {
        "title": f"{title_prefix} {area.name} recommendation coverage",
        "travelAreaId": area.id,
        "style": style,
        "description": style,
        "durationDays": duration_days,
        "participantCount": 1,
    }


def _ai_results_url(frontend_base_url: str, trip_id: str | None) -> str:
    if not trip_id:
        return ""
    return f"{frontend_base_url.rstrip('/')}/ai-results?tripId={trip_id}"


def _recommendation_count(response: ApiResponse) -> int:
    if response.status_code != 200 or not isinstance(response.body, list):
        return 0
    return len(response.body)


def _created_trip_id(response: ApiResponse) -> str | None:
    if response.status_code != 200 or not isinstance(response.body, dict):
        return None
    trip_id = response.body.get("id")
    return str(trip_id) if trip_id else None


def run_coverage(
    *,
    areas: Iterable[TravelArea],
    api_client: ApiClient,
    frontend_base_url: str,
    title_prefix: str,
    style: str,
    duration_days: int,
    failure_diagnostics: Callable[[str | None, TravelArea], dict[str, Any]] | None = None,
) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for area in areas:
        create_response = api_client.post_json(
            "/api/trips",
            _area_payload(area, title_prefix=title_prefix, style=style, duration_days=duration_days),
        )
        trip_id = _created_trip_id(create_response)
        recommendation_response = (
            api_client.get_json(f"/api/trips/{trip_id}/recommendations")
            if trip_id
            else ApiResponse(0, {"error": "trip creation did not return an id"})
        )
        count = _recommendation_count(recommendation_response)
        status = "PASS" if count > 0 else "FAIL"
        failure_detail = None
        if status == "FAIL":
            diagnostics = failure_diagnostics(trip_id, area) if failure_diagnostics is not None else {}
            failure_detail = {
                "createResponse": create_response.body,
                "recommendationResponse": recommendation_response.body,
                "diagnostics": diagnostics,
            }
        rows.append(
            CoverageRow(
                travel_area_id=area.id,
                area_name=area.name,
                sido=area.sido,
                trip_id=trip_id,
                recommendation_count=count,
                status=status,
                ai_results_url=_ai_results_url(frontend_base_url, trip_id),
                create_response=create_response.body,
                recommendation_response=recommendation_response.body,
                failure_detail=failure_detail,
            )
        )
    return rows


def format_markdown_table(rows: list[CoverageRow]) -> str:
    lines = [
        "| travelAreaId | area | sido | tripId | recommendationCount | status | aiResultsUrl |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    "",
                    row.travel_area_id,
                    row.area_name,
                    row.sido,
                    row.trip_id or "",
                    str(row.recommendation_count),
                    row.status,
                    row.ai_results_url,
                    "",
                ]
            )
        )
    return "\n".join(lines)


def catalog_match_counts(
    area: TravelArea,
    catalog: Iterable[dict[str, Any]] = ITINERARY_PLACE_CATALOG,
) -> dict[str, int]:
    exact_term = str(area.name).strip()
    terms = {area.name, area.sido, *area.included_cities, *area.aliases}
    normalized_terms = {str(term).strip() for term in terms if str(term).strip()}
    exact_count = 0
    related_count = 0
    for item in catalog:
        region = str(item.get("region", "")).strip()
        if region == exact_term:
            exact_count += 1
        if region in normalized_terms:
            related_count += 1
    return {
        "exactCatalogRegionMatchCount": exact_count,
        "relatedCatalogRegionMatchCount": related_count,
    }


def validate_persistent_diagnostic_target(
    *,
    base_url: str,
    protected_env: bool,
    allow_persistent_diagnostics: bool,
) -> None:
    if allow_persistent_diagnostics:
        return

    host = (urlparse(base_url).hostname or "").lower()
    problems: list[str] = []
    if protected_env:
        problems.append("APP_ENV is protected")
    if host not in LOCAL_API_HOSTS:
        problems.append(f"base URL host is not local/dev ({host or 'unknown'})")
    if problems:
        print(
            "Refusing to create persistent diagnostic trips: "
            + "; ".join(problems)
            + ". Re-run with --allow-persistent-diagnostics only when this write-heavy diagnostic is intentional.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def build_failure_diagnostics(db: Session, *, trip_id: str | None, area: TravelArea) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "kakaoLocalEnabled": settings.kakao_local_enabled,
        "hasKakaoLocalRestApiKey": bool(settings.kakao_local_rest_api_key),
        **catalog_match_counts(area),
    }
    if not trip_id or not trip_id.isdigit():
        return diagnostics

    numeric_trip_id = int(trip_id)
    persisted_lengths = [
        len(recommendation.result)
        for recommendation in db.scalars(
            select(Recommendation).where(Recommendation.trip_id == numeric_trip_id)
        ).all()
        if isinstance(recommendation.result, list)
    ]
    diagnostics.update(
        {
            "tripRows": db.scalar(select(func.count()).select_from(Trip).where(Trip.id == numeric_trip_id)),
            "tripDayRows": db.scalar(select(func.count()).select_from(TripDay).where(TripDay.trip_id == numeric_trip_id)),
            "tripPlaceRows": db.scalar(
                select(func.count())
                .select_from(TripPlace)
                .join(TripDay, TripPlace.trip_day_id == TripDay.id)
                .where(TripDay.trip_id == numeric_trip_id)
            ),
            "persistedRecommendationResultLengths": persisted_lengths,
        }
    )
    return diagnostics


def _print_report(rows: list[CoverageRow], *, include_json: bool) -> None:
    print(format_markdown_table(rows))
    failures = [row for row in rows if row.status == "FAIL"]
    print()
    print(f"Summary: {len(rows) - len(failures)} PASS / {len(failures)} FAIL / {len(rows)} total")
    if failures:
        print("\nFailure details:")
        for row in failures:
            print(f"\n## {row.travel_area_id} ({row.area_name}) tripId={row.trip_id or '-'}")
            print(json.dumps(row.failure_detail, ensure_ascii=False, indent=2, default=str))
    if include_json:
        print("\nJSON:")
        print(json.dumps([row.__dict__ for row in rows], ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create one new trip per travel area and report whether AI recommendations are non-empty."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend API base URL.")
    parser.add_argument("--frontend-base-url", default=settings.frontend_base_url(), help="Frontend base URL for ai-results links.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Local diagnostic user email.")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="Trip style used for every diagnostic trip.")
    parser.add_argument("--duration-days", type=int, default=DEFAULT_DURATION_DAYS, help="Trip duration for generated trips.")
    parser.add_argument(
        "--allow-persistent-diagnostics",
        action="store_true",
        help="Allow persistent diagnostic trip creation outside local/dev targets.",
    )
    parser.add_argument("--json", action="store_true", help="Also print a JSON copy of all rows.")
    args = parser.parse_args(argv)

    validate_persistent_diagnostic_target(
        base_url=args.base_url,
        protected_env=settings.is_protected_env,
        allow_persistent_diagnostics=args.allow_persistent_diagnostics,
    )

    title_prefix = f"[diagnostic {datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}]"
    session_factory = get_session_factory()
    with session_factory() as db:
        user = ensure_diagnostic_user(db, email=args.email)
        token = security.create_access_token(user.id)
        api_client = BearerApiClient(base_url=args.base_url, bearer_token=token)
        rows = run_coverage(
            areas=list_travel_areas(),
            api_client=api_client,
            frontend_base_url=args.frontend_base_url,
            title_prefix=title_prefix,
            style=args.style,
            duration_days=args.duration_days,
            failure_diagnostics=lambda trip_id, area: build_failure_diagnostics(db, trip_id=trip_id, area=area),
        )

    _print_report(rows, include_json=args.json)
    return 1 if any(row.status == "FAIL" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
