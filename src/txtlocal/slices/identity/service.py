import asyncio
import base64
import binascii
import hashlib
import hmac
import re
import secrets
import string
import time
import uuid
import zoneinfo
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import ceil
from random import Random
from typing import TYPE_CHECKING, Protocol, assert_never, cast

import phonenumbers
from fastapi import Request

from txtlocal.shared import telemetry
from txtlocal.shared.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    Internal,
    NotFound,
    RateLimited,
    Unauthorized,
)
from txtlocal.shared.phone import E164, normalise
from txtlocal.slices.identity.auth import SIGN_IN_TO_CONTINUE, TokenVerifier
from txtlocal.slices.identity.model import (
    Account,
    AccountSettings,
    Claims,
    CreatedUser,
    CreateUser,
    HomeView,
    IssuedKey,
    MessagingSettings,
    MeView,
    Principal,
    Profile,
    ProfileUpdate,
    Role,
    SubPointer,
    TokenUse,
    User,
    UserRow,
    UserStatus,
    UserUpdate,
)

if TYPE_CHECKING:
    from fastapi import Response

    from txtlocal.shared.clock import Clock
    from txtlocal.slices.identity.repo import IdentityRepo

type AccountHook = Callable[[str, datetime], Awaitable[None]]
type Authenticated = Callable[[Request], Awaitable[Principal]]
type CallNext = Callable[[Request], Awaitable[Response]]
type Middleware = Callable[[Request, CallNext], Awaitable[Response]]

ACCOUNT_DISABLED = "This user has been disabled. Contact your account owner"
ACCOUNT_NAME_LENGTH = "Enter an account name of 1 to 100 characters"
API_KEY_BYTES = 30
API_KEY_PREFIX_LENGTH = 8
BASIC = "basic"
BEARER = "bearer"
CLIENT_ERROR_STATUS = 400
DUPLICATE_EMAIL = "That email address already has an account"
EMAIL_NOT_CONFIGURED = "email sender not configured"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIRST_NAME_LENGTH = "Enter a first name of 1 to 50 characters"
INVALID_API_CREDENTIALS = "Invalid username or API key"
INVALID_COUNTRY = "Choose a country from the list"
INVALID_EMAIL = "Enter a valid email address"
INVALID_TIMEZONE = "Choose a timezone from the list"
INVITATION_SUBJECT = "You've been added to a txtlocal account"
LAST_NAME_LENGTH = "Enter a last name of 1 to 50 characters"
MAX_ACCOUNT_NAME = 100
MAX_NAME = 50
MAX_NOTES = 200
MAX_PARTS_RANGE = "Choose between 1 and 8 message parts"
NOTES_LENGTH = "Notes can be at most 200 characters"
OWNER_ONLY = "Only the account owner can do that"
OWNER_STATUS = "The account owner cannot be disabled"
PARTS_CEILING = 8
PRINCIPAL_CACHE_SIZE = 1024
PRINCIPAL_CACHE_TTL = timedelta(seconds=30)
RATE_LIMIT_MESSAGE = "Rate limit of 60 requests per minute reached"
RATE_LIMIT_PER_MINUTE = 60
SERVER_ERROR_STATUS = 500
STATUS_CHOICE = "Status must be ACTIVE or DISABLED"
OWNER_NOT_FOUND = "This account has no owner"
TEMP_PASSWORD_LENGTH = 20
TEMP_SYMBOL_CHARS = "!@#$%^&*"
UNKNOWN = "-"
USER_NOT_FOUND = "No user with that id"


class ApiKeyLookup(Protocol):
    async def user_for_api_key(self, digest: str) -> User | None: ...


class RateLimits(Protocol):
    async def count(self, user_id: str, minute: str) -> int: ...


class PrincipalLookup(Protocol):
    async def principal_for(self, sub: str) -> Principal | None: ...


class BalanceView(Protocol):
    @property
    def balance_micro(self) -> int: ...

    @property
    def can_send(self) -> bool: ...

    @property
    def has_topped_up(self) -> bool: ...

    @property
    def trial_days_left(self) -> int: ...

    @property
    def trial_ends_at(self) -> datetime | None: ...


class BalanceLookup(Protocol):
    async def balance(self, account_id: str, now: datetime) -> BalanceView: ...


class UserDirectory(Protocol):
    async def create_user(self, email: str, temporary_password: str) -> None: ...


class VerifiedNumbers(Protocol):
    async def verified_numbers(self, account_id: str) -> frozenset[E164]: ...


class Email(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class CognitoUserDirectory:
    admin_create_user: Callable[..., Awaitable[object]]
    user_pool_id: str

    async def create_user(self, email: str, temporary_password: str) -> None:
        await self.admin_create_user(
            MessageAction="SUPPRESS",
            TemporaryPassword=temporary_password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            UserPoolId=self.user_pool_id,
            Username=email,
        )


@dataclass(frozen=True, slots=True)
class AccountOwner:
    email: str
    first_name: str
    last_name: str
    mobile: str | None


@dataclass(frozen=True, slots=True)
class NewKey:
    api_key: str
    digest: str
    prefix: str


def api_key_digest(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def new_api_key(rng: Random) -> NewKey:
    api_key = base64.urlsafe_b64encode(rng.randbytes(API_KEY_BYTES)).decode()
    return NewKey(
        api_key=api_key, digest=api_key_digest(api_key), prefix=api_key[:API_KEY_PREFIX_LENGTH]
    )


def new_temporary_password(rng: Random) -> str:
    required = [
        rng.choice(string.ascii_uppercase),
        rng.choice(string.ascii_lowercase),
        rng.choice(string.digits),
        rng.choice(TEMP_SYMBOL_CHARS),
    ]
    filler = [
        rng.choice(string.ascii_letters + string.digits)
        for _ in range(TEMP_PASSWORD_LENGTH - len(required))
    ]
    password = [*required, *filler]
    rng.shuffle(password)
    return "".join(password)


def invitation_body(username: str, temporary_password: str) -> str:
    return (
        "An account has been created for you on txtlocal.\n\n"
        f"Username: {username}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Sign in and you will be asked to choose a new password."
    )


def can_sign_in(user: User) -> bool:
    return user.status is not UserStatus.DISABLED


def is_supported_country(code: str) -> bool:
    return code in phonenumbers.SUPPORTED_REGIONS


def is_timezone(name: str) -> bool:
    try:
        zoneinfo.ZoneInfo(name)
    except ValueError, zoneinfo.ZoneInfoNotFoundError:
        return False
    return True


def is_within_length(value: str, ceiling: int) -> bool:
    return 1 <= len(value) <= ceiling


def normalise_email(raw: str) -> str:
    email = raw.strip().lower()
    if EMAIL_PATTERN.match(email) is None:
        raise BadRequest(INVALID_EMAIL)
    return email


def checked_name(value: str, message: str) -> str:
    name = value.strip()
    if not is_within_length(name, MAX_NAME):
        raise BadRequest(message)
    return name


def checked_optional_name(value: str, message: str) -> str:
    return checked_name(value, message) if value.strip() else ""


def checked_notes(value: str | None) -> str | None:
    notes = (value or "").strip()
    if len(notes) > MAX_NOTES:
        raise BadRequest(NOTES_LENGTH)
    return notes or None


def checked_phone(value: str | None, default_country: str) -> E164 | None:
    raw = (value or "").strip()
    return normalise(raw, default_country) if raw else None


def checked_account_settings(settings: AccountSettings) -> AccountSettings:
    name = settings.name.strip()
    if not is_within_length(name, MAX_ACCOUNT_NAME):
        raise BadRequest(ACCOUNT_NAME_LENGTH)
    if not is_timezone(settings.timezone):
        raise BadRequest(INVALID_TIMEZONE)
    if not is_supported_country(settings.default_country):
        raise BadRequest(INVALID_COUNTRY)
    return AccountSettings(
        default_country=settings.default_country, name=name, timezone=settings.timezone
    )


def checked_messaging_settings(settings: MessagingSettings) -> MessagingSettings:
    if not 1 <= settings.max_parts <= PARTS_CEILING:
        raise BadRequest(MAX_PARTS_RANGE)
    if not is_supported_country(settings.default_country):
        raise BadRequest(INVALID_COUNTRY)
    return settings


def enabled_status(user: User) -> UserStatus:
    return UserStatus.ACTIVE if user.cognito_sub else UserStatus.INVITED


def checked_status(user: User, status: UserStatus) -> UserStatus:
    if user.role is Role.OWNER:
        raise BadRequest(OWNER_STATUS)

    match status:
        case UserStatus.ACTIVE:
            return enabled_status(user)
        case UserStatus.DISABLED:
            return status
        case UserStatus.INVITED:
            raise BadRequest(STATUS_CHOICE)
        case _:
            assert_never(status)


def require_owner(principal: Principal) -> None:
    if principal.role is not Role.OWNER:
        raise Forbidden(OWNER_ONLY)


def principal_of(user: User) -> Principal:
    return Principal(
        account_id=user.account_id, role=user.role, user_id=user.user_id, username=user.username
    )


def row_of(user: User) -> UserRow:
    return UserRow(
        api_key_prefix=user.api_key_prefix,
        created_at=user.created_at,
        first_name=user.first_name,
        last_name=user.last_name,
        notes=user.notes,
        phone=user.phone,
        role=user.role,
        status=user.status,
        user_id=user.user_id,
        username=user.username,
    )


def listing_order(user: User) -> tuple[bool, datetime]:
    return (user.role is not Role.OWNER, user.created_at)


def matches(user: User, needle: str) -> bool:
    haystack = " ".join(
        filter(None, (user.username, user.first_name, user.last_name, user.phone, user.notes))
    )
    return needle in haystack.casefold()


@dataclass(frozen=True, slots=True)
class IdentityService:
    balances: BalanceLookup
    clock: Clock
    directory: UserDirectory
    hooks: Sequence[AccountHook]
    repo: IdentityRepo
    senders: VerifiedNumbers
    verifier: TokenVerifier
    email: Email | None = None
    rng: Random = field(default_factory=secrets.SystemRandom)

    async def principal_for(self, sub: str) -> Principal | None:
        pointer = await self.repo.get_pointer(sub)
        if pointer is None:
            return None

        user = await self.repo.get_user(pointer.account_id, pointer.user_id)
        if user is None or not can_sign_in(user):
            return None

        return principal_of(user)

    async def user_for_api_key(self, digest: str) -> User | None:
        indexed = await self.repo.find_user_by_api_key(digest)
        if indexed is None:
            return None

        user = await self.repo.get_user(indexed.account_id, indexed.user_id)
        if user is None or not can_sign_in(user) or user.api_key_hash != digest:
            return None

        return user

    async def open_session(self, claims: Claims) -> Principal:
        if claims.email is None:
            raise Unauthorized(SIGN_IN_TO_CONTINUE)

        pointer = await self.repo.get_pointer(claims.sub)
        if pointer is not None:
            return await self.signed_in(pointer)

        username = claims.email.strip().lower()
        invited = await self.repo.find_user_by_username(username)
        if invited is not None:
            return await self.link_invited(invited, claims)

        return await self.create_owner(claims, username)

    async def signed_in(self, pointer: SubPointer) -> Principal:
        user = await self.repo.get_user(pointer.account_id, pointer.user_id)
        if user is None:
            raise Unauthorized(SIGN_IN_TO_CONTINUE)
        if not can_sign_in(user):
            raise Forbidden(ACCOUNT_DISABLED)

        return principal_of(user)

    async def link_invited(self, invited: User, claims: Claims) -> Principal:
        if not can_sign_in(invited):
            raise Forbidden(ACCOUNT_DISABLED)

        linked = invited.model_copy(
            update={
                "cognito_sub": claims.sub,
                "email_verified": claims.email_verified,
                "status": UserStatus.ACTIVE,
            }
        )
        pointer = SubPointer(
            account_id=invited.account_id,
            created_at=self.clock(),
            sub=claims.sub,
            user_id=invited.user_id,
        )

        if not await self.repo.link_user(linked, pointer):
            return await self.reread(claims.sub)

        return principal_of(linked)

    async def create_owner(self, claims: Claims, username: str) -> Principal:
        now = self.clock()
        account_id = str(uuid.uuid7())
        issued = new_api_key(self.rng)

        account = Account(
            account_id=account_id, created_at=now, email=username, name=username.partition("@")[0]
        )
        owner = User(
            account_id=account_id,
            api_key_hash=issued.digest,
            api_key_issued_at=now,
            api_key_prefix=issued.prefix,
            cognito_sub=claims.sub,
            created_at=now,
            email_verified=claims.email_verified,
            role=Role.OWNER,
            status=UserStatus.ACTIVE,
            user_id=str(uuid.uuid7()),
            username=username,
        )
        pointer = SubPointer(
            account_id=account_id, created_at=now, sub=claims.sub, user_id=owner.user_id
        )

        if not await self.repo.create_account(account, owner, pointer):
            return await self.reread(claims.sub)

        for hook in self.hooks:
            await hook(account_id, now)

        return principal_of(owner)

    async def reread(self, sub: str) -> Principal:
        pointer = await self.repo.get_pointer(sub)
        if pointer is None:
            raise Conflict(DUPLICATE_EMAIL)

        return await self.signed_in(pointer)

    async def me(self, principal: Principal) -> MeView:
        user, account, balance = await asyncio.gather(
            self.user_of(principal),
            self.account_of(principal.account_id),
            self.balances.balance(principal.account_id, self.clock()),
        )

        return MeView(
            account_id=account.account_id,
            account_name=account.name,
            balance_micro=balance.balance_micro,
            can_send=balance.can_send,
            default_country=account.settings.default_country,
            first_name=user.first_name,
            has_topped_up=balance.has_topped_up,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role,
            trial_days_left=balance.trial_days_left,
            trial_ends_at=balance.trial_ends_at,
            user_id=user.user_id,
            username=user.username,
        )

    async def home(self, principal: Principal) -> HomeView:
        user, balance, verified = await asyncio.gather(
            self.user_of(principal),
            self.balances.balance(principal.account_id, self.clock()),
            self.senders.verified_numbers(principal.account_id),
        )

        return HomeView(
            balance_micro=balance.balance_micro,
            can_send=balance.can_send,
            email_verified=user.email_verified,
            first_name=user.first_name,
            last_name=user.last_name,
            number_verified=bool(verified),
            trial_days_left=balance.trial_days_left,
        )

    async def update_profile(self, principal: Principal, update: ProfileUpdate) -> Profile:
        first_name = checked_name(update.first_name, FIRST_NAME_LENGTH)
        last_name = checked_name(update.last_name, LAST_NAME_LENGTH)

        user, account = await asyncio.gather(
            self.user_of(principal), self.account_of(principal.account_id)
        )
        phone = checked_phone(update.phone, account.settings.default_country)

        await self.save(
            user.model_copy(
                update={"first_name": first_name, "last_name": last_name, "phone": phone}
            )
        )

        return Profile(
            first_name=first_name, last_name=last_name, phone=phone, username=user.username
        )

    async def account_settings(self, principal: Principal) -> AccountSettings:
        account = await self.account_of(principal.account_id)
        return AccountSettings(
            default_country=account.settings.default_country,
            name=account.name,
            timezone=account.timezone,
        )

    async def update_account_settings(
        self, principal: Principal, settings: AccountSettings
    ) -> AccountSettings:
        require_owner(principal)
        checked = checked_account_settings(settings)

        if not await self.repo.set_account_settings(principal.account_id, checked):
            raise Internal("account missing")

        return checked

    async def contact_details(self, account_id: str) -> Account:
        return await self.account_of(account_id)

    async def update_contact_details(
        self, account_id: str, name: str, email: str, mobile: str | None
    ) -> Account:
        account = await self.account_of(account_id)
        updated = account.model_copy(update={"email": email, "mobile": mobile, "name": name})

        if not await self.repo.save_account(updated):
            raise Internal("account missing")

        return updated

    async def messaging_settings(self, account_id: str) -> MessagingSettings:
        account = await self.account_of(account_id)
        return account.settings

    async def owner_of(self, account_id: str) -> AccountOwner:
        users = await self.repo.list_users(account_id)
        owner = next((user for user in users if user.role is Role.OWNER), None)
        if owner is None:
            raise NotFound(OWNER_NOT_FOUND)

        return AccountOwner(
            email=owner.username,
            first_name=owner.first_name,
            last_name=owner.last_name,
            mobile=owner.phone,
        )

    async def update_messaging_settings(
        self, principal: Principal, settings: MessagingSettings
    ) -> MessagingSettings:
        require_owner(principal)
        checked = checked_messaging_settings(settings)

        if not await self.repo.set_messaging_settings(principal.account_id, checked):
            raise Internal("account missing")

        return checked

    async def users(self, principal: Principal, q: str | None) -> list[UserRow]:
        users = sorted(await self.repo.list_users(principal.account_id), key=listing_order)
        needle = (q or "").strip().casefold()
        return [row_of(user) for user in users if not needle or matches(user, needle)]

    async def create_user(self, principal: Principal, request: CreateUser) -> CreatedUser:
        require_owner(principal)
        username = normalise_email(request.username)
        first_name = checked_optional_name(request.first_name, FIRST_NAME_LENGTH)
        last_name = checked_optional_name(request.last_name, LAST_NAME_LENGTH)
        notes = checked_notes(request.notes)

        account = await self.account_of(principal.account_id)
        phone = checked_phone(request.phone, account.settings.default_country)

        if await self.repo.find_user_by_username(username) is not None:
            raise Conflict(DUPLICATE_EMAIL)

        temporary_password = new_temporary_password(self.rng)
        await self.directory.create_user(username, temporary_password)

        now = self.clock()
        issued = new_api_key(self.rng)
        user = User(
            account_id=principal.account_id,
            api_key_hash=issued.digest,
            api_key_issued_at=now,
            api_key_prefix=issued.prefix,
            created_at=now,
            first_name=first_name,
            last_name=last_name,
            notes=notes,
            phone=phone,
            role=Role.SUB,
            status=UserStatus.INVITED,
            user_id=str(uuid.uuid7()),
            username=username,
        )
        if not await self.repo.put_user(user):
            raise Conflict(DUPLICATE_EMAIL)

        await self._email().send(
            to=username,
            subject=INVITATION_SUBJECT,
            body=invitation_body(username, temporary_password),
        )

        return CreatedUser(api_key=issued.api_key, user=row_of(user))

    async def update_user(self, principal: Principal, user_id: str, update: UserUpdate) -> UserRow:
        require_owner(principal)

        user, account = await asyncio.gather(
            self.member(principal.account_id, user_id), self.account_of(principal.account_id)
        )

        changes: dict[str, object] = {}
        if "notes" in update.model_fields_set:
            changes["notes"] = checked_notes(update.notes)
        if "phone" in update.model_fields_set:
            changes["phone"] = checked_phone(update.phone, account.settings.default_country)
        if update.status is not None:
            changes["status"] = checked_status(user, update.status)

        saved = user.model_copy(update=changes)
        await self.save(saved)

        return row_of(saved)

    async def regenerate_api_key(self, principal: Principal, user_id: str) -> IssuedKey:
        if principal.role is not Role.OWNER and principal.user_id != user_id:
            raise Forbidden(OWNER_ONLY)

        user = await self.member(principal.account_id, user_id)
        issued = new_api_key(self.rng)

        await self.save(
            user.model_copy(
                update={
                    "api_key_hash": issued.digest,
                    "api_key_issued_at": self.clock(),
                    "api_key_prefix": issued.prefix,
                }
            )
        )

        return IssuedKey(api_key=issued.api_key, api_key_prefix=issued.prefix, user_id=user_id)

    async def user_of(self, principal: Principal) -> User:
        user = await self.repo.get_user(principal.account_id, principal.user_id)
        if user is None:
            raise Internal("user missing")
        return user

    async def member(self, account_id: str, user_id: str) -> User:
        user = await self.repo.get_user(account_id, user_id)
        if user is None:
            raise NotFound(USER_NOT_FOUND)
        return user

    async def account_of(self, account_id: str) -> Account:
        account = await self.repo.get_account(account_id)
        if account is None:
            raise Internal("account missing")
        return account

    async def save(self, user: User) -> None:
        if not await self.repo.save_user(user):
            raise NotFound(USER_NOT_FOUND)

    def _email(self) -> Email:
        if self.email is None:
            raise Internal(EMAIL_NOT_CONFIGURED)
        return self.email


def bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != BEARER or not token.strip():
        raise Unauthorized(SIGN_IN_TO_CONTINUE)
    return token.strip()


def basic_credentials(request: Request) -> tuple[str, str]:
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != BASIC:
        raise Unauthorized(INVALID_API_CREDENTIALS)

    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode()
    except (binascii.Error, UnicodeDecodeError) as error:
        raise Unauthorized(INVALID_API_CREDENTIALS) from error

    username, separator, api_key = decoded.partition(":")
    if not separator:
        raise Unauthorized(INVALID_API_CREDENTIALS)

    return username, api_key


def credentials_match(user: User, username: str, api_key: str) -> bool:
    same_user = hmac.compare_digest(user.username.encode(), username.strip().lower().encode())
    same_key = hmac.compare_digest(user.api_key_hash.encode(), api_key_digest(api_key).encode())
    return same_user and same_key


@dataclass(frozen=True, slots=True)
class CachedPrincipal:
    principal: Principal
    seen_at: datetime


def remember(
    cache: dict[str, CachedPrincipal], sub: str, principal: Principal, now: datetime
) -> None:
    if len(cache) >= PRINCIPAL_CACHE_SIZE:
        cache.pop(next(iter(cache)))
    cache[sub] = CachedPrincipal(principal=principal, seen_at=now)


def is_fresh(cached: CachedPrincipal, now: datetime) -> bool:
    return now - cached.seen_at < PRINCIPAL_CACHE_TTL


def current_minute(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


def seconds_to_next_minute(now: datetime) -> int:
    utc = now.astimezone(UTC)
    top_of_next_minute = utc.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return ceil((top_of_next_minute - utc).total_seconds())


def is_over_rate_limit(counted: int) -> bool:
    return counted > RATE_LIMIT_PER_MINUTE


def outcome_of(status: int) -> str:
    if status < CLIENT_ERROR_STATUS:
        return "ok"
    if status < SERVER_ERROR_STATUS:
        return "refused"
    return "failed"


def stashed_principal(request: Request) -> Principal | None:
    return cast("Principal | None", getattr(request.state, "principal", None))


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    return cast("str", route.path) if route is not None else UNKNOWN


def request_id_of(request: Request) -> str:
    context = request.scope.get("aws.context")
    return cast("str", context.aws_request_id) if context is not None else UNKNOWN


def authenticated(
    verifier: TokenVerifier, principals: PrincipalLookup, clock: Clock
) -> Authenticated:
    cache: dict[str, CachedPrincipal] = {}

    async def dependency(request: Request) -> Principal:
        claims = await verifier.verify(bearer_token(request), TokenUse.ACCESS)
        now = clock()

        cached = cache.get(claims.sub)
        if cached is not None and is_fresh(cached, now):
            request.state.principal = cached.principal
            return cached.principal

        principal = await principals.principal_for(claims.sub)
        if principal is None:
            cache.pop(claims.sub, None)
            raise Unauthorized(SIGN_IN_TO_CONTINUE)

        remember(cache, claims.sub, principal, now)
        request.state.principal = principal
        return principal

    return dependency


def api_user(users: ApiKeyLookup, rate_limits: RateLimits, clock: Clock) -> Authenticated:
    async def dependency(request: Request) -> Principal:
        username, api_key = basic_credentials(request)

        user = await users.user_for_api_key(api_key_digest(api_key))
        if user is None or not credentials_match(user, username, api_key):
            raise Unauthorized(INVALID_API_CREDENTIALS)

        principal = principal_of(user)
        request.state.principal = principal

        now = clock()
        counted = await rate_limits.count(principal.user_id, current_minute(now))
        if is_over_rate_limit(counted):
            raise RateLimited(RATE_LIMIT_MESSAGE, retry_after=seconds_to_next_minute(now))

        return principal

    return dependency


def api_request_logger() -> Middleware:
    async def dispatch(request: Request, call_next: CallNext) -> Response:
        started = time.monotonic()
        status = SERVER_ERROR_STATUS
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            principal = stashed_principal(request)

            telemetry.log(
                "api_request",
                account_id=principal.account_id if principal else UNKNOWN,
                latency_ms=round((time.monotonic() - started) * 1000),
                method=request.method,
                outcome=outcome_of(status),
                request_id=request_id_of(request),
                route=route_template(request),
                status=status,
                user_id=principal.user_id if principal else UNKNOWN,
            )

    return dispatch
