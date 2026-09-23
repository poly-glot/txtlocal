import argparse
import base64
import hashlib
import os
import secrets
import sys
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:9000"
DEFAULT_CLIENT_ID = "local"
DEFAULT_REDIRECT_URI = "http://localhost:3000/auth/callback"
DEFAULT_USER = "demo@txtlocal.local"

_failures: list[int] = []


def ok(label: str) -> None:
    sys.stdout.write(f"ok    {label}\n")


def note(label: str) -> None:
    sys.stdout.write(f"      {label}\n")


def fail(label: str) -> None:
    _failures.append(1)
    sys.stderr.write(f"FAIL  {label}\n")


def assert_eq(actual: object, expected: object, label: str) -> None:
    ok(label) if actual == expected else fail(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(condition: bool, label: str) -> None:
    ok(label) if condition else fail(label)


def finish(script_name: str) -> int:
    if _failures:
        sys.stderr.write(f"\n{script_name}: {len(_failures)} assertion(s) failed\n")
        return 1
    sys.stdout.write(f"\n{script_name}: every assertion passed\n")
    return 0


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--base-url", default=os.environ.get("QA_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--client-id", default=os.environ.get("QA_CLIENT_ID", DEFAULT_CLIENT_ID))
    parser.add_argument("--user", default=os.environ.get("QA_USER", DEFAULT_USER))
    parser.add_argument(
        "--operator-secret", default=os.environ.get("QA_OPERATOR_SECRET", "local-operator-secret")
    )
    return parser


def challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign_in(client: httpx.Client, base_url: str, client_id: str, user: str) -> dict[str, Any]:
    verifier = secrets.token_urlsafe(48)
    params = {
        "client_id": client_id,
        "code_challenge": challenge_of(verifier),
        "code_challenge_method": "S256",
        "login": user,
        "redirect_uri": DEFAULT_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email",
        "state": "qa",
    }
    authorized = client.get(f"{base_url}/api/dev-idp/oauth2/authorize", params=params)
    code = httpx.URL(authorized.headers["location"]).params["code"]

    tokens = client.post(
        f"{base_url}/api/dev-idp/oauth2/token",
        data={
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": DEFAULT_REDIRECT_URI,
        },
    )
    tokens.raise_for_status()
    return dict(tokens.json())


def sign_in_session(
    client: httpx.Client, base_url: str, client_id: str, user: str
) -> tuple[dict[str, str], dict[str, Any]]:
    tokens = sign_in(client, base_url, client_id, user)
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    session = client.post(
        f"{base_url}/api/app/session", json={"idToken": tokens["id_token"]}, headers=auth
    )
    session.raise_for_status()
    return auth, session.json()
