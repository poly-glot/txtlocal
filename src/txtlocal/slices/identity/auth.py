from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import jwt
from pydantic import ValidationError

from txtlocal.shared.errors import Unauthorized, Upstream
from txtlocal.slices.identity.model import Claims, TokenUse

ALGORITHMS = ("RS256",)
CLIENT_ID_CLAIM = "client_id"
JWKS_PATH = "/.well-known/jwks.json"
KID_HEADER = "kid"
REQUIRED_CLAIMS = ["exp", "sub", "token_use"]
SIGN_IN_TO_CONTINUE = "Sign in to continue"
USE_CLAIM = "token_use"


class TokenVerifier(Protocol):
    async def verify(self, token: str, use: TokenUse) -> Claims: ...


def keys_by_kid(jwks: Mapping[str, object]) -> dict[str, jwt.PyJWK]:
    keyset = jwt.PyJWKSet.from_dict(dict(jwks))
    return {key.key_id: key for key in keyset.keys if key.key_id is not None}


def kid_of(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise Unauthorized(SIGN_IN_TO_CONTINUE) from error
    return str(header.get(KID_HEADER, ""))


def decode_claims(token: str, key: jwt.PyJWK, issuer: str, client_id: str, use: TokenUse) -> Claims:
    is_id_token = use is TokenUse.ID
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=client_id if is_id_token else None,
            issuer=issuer,
            options={"require": REQUIRED_CLAIMS, "verify_aud": is_id_token},
        )
        claims = Claims.model_validate(payload)
    except (jwt.PyJWTError, ValidationError) as error:
        raise Unauthorized(SIGN_IN_TO_CONTINUE) from error

    if payload.get(USE_CLAIM) != use:
        raise Unauthorized(SIGN_IN_TO_CONTINUE)
    if not is_id_token and payload.get(CLIENT_ID_CLAIM) != client_id:
        raise Unauthorized(SIGN_IN_TO_CONTINUE)

    return claims


@dataclass(frozen=True, slots=True)
class LocalVerifier:
    client_id: str
    issuer: str
    keys: Mapping[str, jwt.PyJWK]

    async def verify(self, token: str, use: TokenUse) -> Claims:
        key = self.keys.get(kid_of(token))
        if key is None:
            raise Unauthorized(SIGN_IN_TO_CONTINUE)

        return decode_claims(token, key, self.issuer, self.client_id, use)


@dataclass(slots=True)
class CognitoVerifier:
    client_id: str
    http: httpx.AsyncClient
    issuer: str
    keys: dict[str, jwt.PyJWK] = field(default_factory=dict)

    async def verify(self, token: str, use: TokenUse) -> Claims:
        kid = kid_of(token)
        if kid not in self.keys:
            self.keys = await self.fetch_keys()

        key = self.keys.get(kid)
        if key is None:
            raise Unauthorized(SIGN_IN_TO_CONTINUE)

        return decode_claims(token, key, self.issuer, self.client_id, use)

    async def fetch_keys(self) -> dict[str, jwt.PyJWK]:
        try:
            response = await self.http.get(f"{self.issuer}{JWKS_PATH}")
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise Upstream("jwks") from error

        return keys_by_kid(response.json())
