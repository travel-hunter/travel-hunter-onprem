#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


PROVIDER_HOSTS = {
    "kakao": "kauth.kakao.com",
    "google": "accounts.google.com",
}


def env_name(provider: str, suffix: str) -> str:
    return f"{provider.upper()}_{suffix}"


def validate_env(provider: str) -> list[str]:
    required = [
        env_name(provider, "CLIENT_ID"),
        env_name(provider, "CLIENT_SECRET"),
        env_name(provider, "REDIRECT_URI"),
    ]
    missing = [name for name in required if not os.getenv(name)]
    redirect_uri = os.getenv(env_name(provider, "REDIRECT_URI"), "")
    parsed = urlparse(redirect_uri)
    if redirect_uri and parsed.hostname not in {"127.0.0.1", "localhost"}:
        missing.append(f"{env_name(provider, 'REDIRECT_URI')} must use localhost or 127.0.0.1")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check local OAuth start route without printing secrets.")
    parser.add_argument("provider", choices=sorted(PROVIDER_HOSTS))
    parser.add_argument("--backend", default=os.getenv("OAUTH_SMOKE_BACKEND", "http://127.0.0.1:8000"))
    parser.add_argument("--redirect", default="/home")
    args = parser.parse_args()

    missing = validate_env(args.provider)
    state_cookie_name = os.getenv("OAUTH_STATE_COOKIE_NAME", "travel_hunter_oauth_state")
    if missing:
        print("OAuth local smoke cannot run because required local configuration is missing:")
        for name in missing:
            print(f"- {name}")
        print("No secret values were printed.")
        return 2

    start_url = (
        f"{args.backend.rstrip('/')}/api/auth/oauth/{args.provider}/start?"
        f"{urlencode({'redirect': args.redirect})}"
    )
    opener = build_opener(NoRedirectHandler)
    request = Request(start_url, method="GET")

    try:
        opener.open(request, timeout=8)
    except HTTPError as error:
        if error.code != 302:
            print(f"Expected 302 from OAuth start route, got {error.code}.")
            return 1
        location = error.headers.get("Location", "")
        set_cookie = error.headers.get("Set-Cookie", "")
    except URLError as error:
        print(f"Could not reach backend OAuth start route: {error.reason}")
        return 1
    else:
        print("Expected OAuth start route to redirect, but it returned a non-redirect response.")
        return 1

    location_host = urlparse(location).hostname
    if location_host != PROVIDER_HOSTS[args.provider]:
        print(f"Expected provider host {PROVIDER_HOSTS[args.provider]}, got {location_host or '<missing>'}.")
        return 1

    cookie = SimpleCookie()
    cookie.load(set_cookie)
    if state_cookie_name not in cookie:
        print("OAuth state cookie was not set.")
        return 1

    print(f"{args.provider} OAuth start route is ready.")
    print(f"Open this local entry URL in a browser: {start_url}")
    print("After provider login returns, verify session and DB with:")
    print("  curl -i -X POST http://127.0.0.1:8000/api/auth/refresh --cookie 'travel_hunter_refresh=<browser-cookie>'")
    print("  psql \"$DATABASE_URL\" -c \"select provider, provider_id, user_id from social_accounts order by id desc limit 5;\"")
    print("No secret values were printed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
