import base64
import hashlib
import hmac
import html
import secrets
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, assert_never
from urllib.parse import parse_qsl, urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jwt.algorithms import RSAAlgorithm

from txtlocal.slices.identity.auth import keys_by_kid
from txtlocal.slices.identity.model import TokenUse

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

ACCESS_LIFETIME = timedelta(hours=1)
ALGORITHM = "RS256"
AUTHORIZE_PARAMS = (
    "client_id",
    "code_challenge",
    "code_challenge_method",
    "redirect_uri",
    "response_type",
    "scope",
    "state",
)
CHALLENGE_METHOD = "S256"
CODE_LIFETIME = timedelta(minutes=5)
INVALID_CLIENT = "invalid_client"
INVALID_GRANT = "invalid_grant"
INVALID_REQUEST = "invalid_request"
KEY_SIZE = 2048
LOGIN_PARAM = "login"
PREFIX = "/api/dev-idp"
PUBLIC_EXPONENT = 65537
RESPONSE_TYPE = "code"
SCOPE = "openid email"
UNSUPPORTED_GRANT = "unsupported_grant_type"


class Grant(StrEnum):
    CODE = "authorization_code"
    REFRESH = "refresh_token"


@dataclass(frozen=True, slots=True)
class PendingCode:
    challenge: str
    email: str
    expires_at: datetime
    redirect_uri: str


def new_signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=PUBLIC_EXPONENT, key_size=KEY_SIZE)


def new_kid() -> str:
    return secrets.token_hex(8)


def sub_of(email: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, email))


def challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def is_authorize_request(params: Mapping[str, str], client_id: str) -> bool:
    expected = {
        "client_id": client_id,
        "code_challenge_method": CHALLENGE_METHOD,
        "response_type": RESPONSE_TYPE,
    }
    required = ("code_challenge", "redirect_uri")
    return all(params.get(name) == value for name, value in expected.items()) and all(
        params.get(name) for name in required
    )


def sign_in_page(action: str, params: Mapping[str, str], users: Sequence[str]) -> str:
    hidden = "".join(
        f'<input name="{html.escape(name)}" type="hidden" value="{html.escape(params[name])}">'
        for name in AUTHORIZE_PARAMS
        if name in params
    )
    options = "".join(
        f'<option value="{html.escape(user)}">{html.escape(user)}</option>' for user in users
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>txtlocal local sign-in</title></head><body>"
        f'<form action="{html.escape(action)}" method="get"><h1>Sign in to txtlocal</h1>'
        f'<label>User <select name="{LOGIN_PARAM}">{options}</select></label>{hidden}'
        '<button type="submit">Sign in</button></form></body></html>'
    )


def oauth_error(code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=400)


@dataclass(slots=True)
class DevIdp:
    client_id: str
    clock: Clock
    issuer: str
    users: set[str]
    codes: dict[str, PendingCode] = field(default_factory=dict)
    key: rsa.RSAPrivateKey = field(default_factory=new_signing_key)
    kid: str = field(default_factory=new_kid)
    refreshes: dict[str, str] = field(default_factory=dict)

    async def create_user(self, email: str, _temporary_password: str) -> None:
        self.users.add(email)

    def jwks(self) -> dict[str, list[dict[str, object]]]:
        jwk = RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {"keys": [{**jwk, "alg": ALGORITHM, "kid": self.kid, "use": "sig"}]}

    def keys(self) -> dict[str, jwt.PyJWK]:
        return keys_by_kid(self.jwks())

    def authorize(self, email: str, challenge: str, redirect_uri: str) -> str:
        code = secrets.token_urlsafe(32)
        self.codes[code] = PendingCode(
            challenge=challenge,
            email=email,
            expires_at=self.clock() + CODE_LIFETIME,
            redirect_uri=redirect_uri,
        )
        return code

    def exchange(self, code: str, verifier: str, redirect_uri: str) -> dict[str, object] | None:
        pending = self.codes.pop(code, None)
        if pending is None or self.clock() >= pending.expires_at:
            return None
        if pending.redirect_uri != redirect_uri:
            return None
        if not hmac.compare_digest(pending.challenge, challenge_of(verifier)):
            return None

        refresh = secrets.token_urlsafe(32)
        self.refreshes[refresh] = pending.email
        return {**self.tokens(pending.email), "refresh_token": refresh}

    def refresh(self, refresh: str) -> dict[str, object] | None:
        email = self.refreshes.get(refresh)
        return None if email is None else self.tokens(email)

    def tokens(self, email: str) -> dict[str, object]:
        now = self.clock()
        shared = {
            "exp": now + ACCESS_LIFETIME,
            "iat": now,
            "iss": self.issuer,
            "sub": sub_of(email),
        }

        access = self.sign(
            {
                **shared,
                "client_id": self.client_id,
                "scope": SCOPE,
                "token_use": TokenUse.ACCESS,
                "username": email,
            }
        )
        identity = self.sign(
            {
                **shared,
                "aud": self.client_id,
                "cognito:username": email,
                "email": email,
                "email_verified": True,
                "token_use": TokenUse.ID,
            }
        )

        return {
            "access_token": access,
            "expires_in": int(ACCESS_LIFETIME.total_seconds()),
            "id_token": identity,
            "token_type": "Bearer",
        }

    def sign(self, payload: dict[str, object]) -> str:
        return jwt.encode(payload, self.key, algorithm=ALGORITHM, headers={"kid": self.kid})


def authorize_response(idp: DevIdp, request: Request) -> Response:
    params = request.query_params
    if not is_authorize_request(params, idp.client_id):
        return HTMLResponse(INVALID_REQUEST, status_code=400)

    login = params.get(LOGIN_PARAM)
    if login is None:
        return HTMLResponse(sign_in_page(request.url.path, params, sorted(idp.users)))
    if login not in idp.users:
        return HTMLResponse(INVALID_REQUEST, status_code=400)

    code = idp.authorize(login, params["code_challenge"], params["redirect_uri"])
    query = urlencode({"code": code, "state": params.get("state", "")})
    return RedirectResponse(f"{params['redirect_uri']}?{query}", status_code=302)


def token_response(idp: DevIdp, form: Mapping[str, str]) -> JSONResponse:
    if form.get("client_id") != idp.client_id:
        return oauth_error(INVALID_CLIENT)

    try:
        grant = Grant(form.get("grant_type", ""))
    except ValueError:
        return oauth_error(UNSUPPORTED_GRANT)

    match grant:
        case Grant.CODE:
            issued = idp.exchange(
                form.get("code", ""), form.get("code_verifier", ""), form.get("redirect_uri", "")
            )
        case Grant.REFRESH:
            issued = idp.refresh(form.get("refresh_token", ""))
        case _:
            assert_never(grant)

    if issued is None:
        return oauth_error(INVALID_GRANT)
    return JSONResponse(issued, headers={"Cache-Control": "no-store"})


def build_dev_idp_router(idp: DevIdp) -> APIRouter:
    router = APIRouter(prefix=PREFIX)

    @router.get("/oauth2/authorize")
    async def authorize(request: Request) -> Response:
        return authorize_response(idp, request)

    @router.post("/oauth2/token")
    async def token(request: Request) -> JSONResponse:
        return token_response(idp, dict(parse_qsl((await request.body()).decode())))

    @router.get("/.well-known/jwks.json")
    async def jwks() -> dict[str, list[dict[str, object]]]:
        return idp.jwks()

    @router.get("/logout")
    async def logout(logout_uri: str) -> RedirectResponse:
        return RedirectResponse(logout_uri, status_code=302)

    return router
