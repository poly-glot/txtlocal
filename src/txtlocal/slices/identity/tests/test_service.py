import base64
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from random import Random

import pytest
from fastapi import Request

from txtlocal.shared.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    Internal,
    NotFound,
    RateLimited,
    Unauthorized,
)
from txtlocal.shared.phone import E164, INVALID_NUMBER_MESSAGE
from txtlocal.slices.identity.auth import SIGN_IN_TO_CONTINUE, LocalVerifier
from txtlocal.slices.identity.dev_idp import DevIdp, sub_of
from txtlocal.slices.identity.model import (
    Account,
    AccountSettings,
    Claims,
    CreateUser,
    MessagingSettings,
    Principal,
    ProfileUpdate,
    Role,
    SubPointer,
    User,
    UserStatus,
    UserUpdate,
)
from txtlocal.slices.identity.service import (
    ACCOUNT_DISABLED,
    ACCOUNT_NAME_LENGTH,
    API_KEY_PREFIX_LENGTH,
    DUPLICATE_EMAIL,
    EMAIL_NOT_CONFIGURED,
    FIRST_NAME_LENGTH,
    INVALID_API_CREDENTIALS,
    INVALID_COUNTRY,
    INVALID_EMAIL,
    INVALID_TIMEZONE,
    INVITATION_SUBJECT,
    LAST_NAME_LENGTH,
    MAX_ACCOUNT_NAME,
    MAX_NAME,
    MAX_NOTES,
    MAX_PARTS_RANGE,
    NOTES_LENGTH,
    OWNER_ONLY,
    OWNER_STATUS,
    PRINCIPAL_CACHE_SIZE,
    PRINCIPAL_CACHE_TTL,
    RATE_LIMIT_MESSAGE,
    RATE_LIMIT_PER_MINUTE,
    STATUS_CHOICE,
    TEMP_PASSWORD_LENGTH,
    TEMP_SYMBOL_CHARS,
    USER_NOT_FOUND,
    CachedPrincipal,
    IdentityService,
    api_key_digest,
    api_user,
    authenticated,
    current_minute,
    invitation_body,
    is_over_rate_limit,
    new_api_key,
    new_temporary_password,
    outcome_of,
    remember,
)
from txtlocal.slices.identity.tests.fakes import (
    NOW,
    OWNER_EMAIL,
    SUB_EMAIL,
    TRIAL_BALANCE,
    FakeBalances,
    FakeClock,
    FakeDirectory,
    FakeRateLimits,
    FakeSenders,
    InMemoryRepo,
    RecordingEmail,
    RecordingHook,
)

type OwnerAction = Callable[[IdentityService, Principal], Awaitable[object]]

API_KEY_LENGTH = 40
ONE_SECOND = timedelta(seconds=1)
OWNER_CLAIMS = Claims(email=OWNER_EMAIL, email_verified=True, sub=sub_of(OWNER_EMAIL))
RATE_LIMIT_CLOCK = FakeClock(now=datetime(2026, 9, 20, 12, 30, 5, tzinfo=UTC))
SUB_CLAIMS = Claims(email=SUB_EMAIL, email_verified=True, sub=sub_of(SUB_EMAIL))
URLSAFE_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


@dataclass
class RacingRepo(InMemoryRepo):
    winner: tuple[Account, User, SubPointer] | None = None

    async def create_account(self, account: Account, owner: User, pointer: SubPointer) -> bool:
        if self.winner is None:
            return await super().create_account(account, owner, pointer)

        await super().create_account(*self.winner)
        return False


def request_with(authorization: str | None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    return Request({"headers": headers, "method": "GET", "path": "/", "type": "http"})


def basic(username: str, api_key: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{api_key}".encode()).decode()


async def owner_of(service: IdentityService) -> Principal:
    return await service.open_session(OWNER_CLAIMS)


async def invited_sub(service: IdentityService, owner: Principal) -> tuple[str, str]:
    created = await service.create_user(owner, CreateUser(username=SUB_EMAIL))
    return created.user.user_id, created.api_key


def only_account(repo: InMemoryRepo) -> Account:
    (account,) = repo.accounts.values()
    return account


def email_of(service: IdentityService) -> RecordingEmail:
    assert isinstance(service.email, RecordingEmail)
    return service.email


async def test_first_sign_in_answers_the_owner_principal(service: IdentityService) -> None:
    principal = await owner_of(service)

    assert (principal.role, principal.username) == (Role.OWNER, OWNER_EMAIL)


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("balance_micro", 0),
        ("created_at", NOW),
        ("email", OWNER_EMAIL),
        ("has_topped_up", False),
        ("name", "demo"),
        ("pricing_country", "GB"),
        ("settings", MessagingSettings()),
        ("timezone", "Europe/London"),
    ],
    ids=[
        "no-balance-until-billing",
        "created-now",
        "billing-email",
        "not-topped-up",
        "name-is-the-local-part",
        "gb-pricing",
        "default-messaging-settings",
        "london-timezone",
    ],
)
async def test_first_sign_in_creates_the_account_row(
    service: IdentityService, repo: InMemoryRepo, attribute: str, expected: object
) -> None:
    await owner_of(service)

    assert getattr(only_account(repo), attribute) == expected


async def test_first_sign_in_creates_the_owner_and_the_pointer(
    service: IdentityService, repo: InMemoryRepo
) -> None:
    principal = await owner_of(service)

    owner = repo.users[(principal.account_id, principal.user_id)]
    pointer = repo.pointers[OWNER_CLAIMS.sub]
    assert (owner.role, owner.status, owner.cognito_sub, owner.email_verified) == (
        Role.OWNER,
        UserStatus.ACTIVE,
        OWNER_CLAIMS.sub,
        True,
    )
    assert (pointer.account_id, pointer.user_id) == (principal.account_id, principal.user_id)


async def test_first_sign_in_runs_every_hook_with_the_account_and_now(
    service: IdentityService, hook: RecordingHook
) -> None:
    principal = await owner_of(service)

    assert hook.calls == [(principal.account_id, NOW)]


async def test_a_second_sign_in_reuses_the_account(
    service: IdentityService, repo: InMemoryRepo, hook: RecordingHook
) -> None:
    first = await owner_of(service)
    second = await owner_of(service)

    assert first == second
    assert len(repo.accounts) == 1
    assert len(hook.calls) == 1


async def test_a_lost_create_rereads_the_winner(
    clock: FakeClock, directory: FakeDirectory, hook: RecordingHook, verifier: LocalVerifier
) -> None:
    winner_repo = InMemoryRepo()
    winner = await IdentityService(
        balances=FakeBalances(answer=TRIAL_BALANCE),
        clock=clock,
        directory=directory,
        hooks=(),
        repo=winner_repo,
        rng=Random(1),
        senders=FakeSenders(),
        verifier=verifier,
    ).open_session(OWNER_CLAIMS)
    rows = (
        only_account(winner_repo),
        winner_repo.users[(winner.account_id, winner.user_id)],
        winner_repo.pointers[OWNER_CLAIMS.sub],
    )
    loser = IdentityService(
        balances=FakeBalances(answer=TRIAL_BALANCE),
        clock=clock,
        directory=directory,
        hooks=(hook,),
        repo=RacingRepo(winner=rows),
        rng=Random(2),
        senders=FakeSenders(),
        verifier=verifier,
    )

    principal = await loser.open_session(OWNER_CLAIMS)

    assert principal == winner
    assert hook.calls == []


async def test_a_token_without_an_email_is_refused(service: IdentityService) -> None:
    with pytest.raises(Unauthorized) as caught:
        await service.open_session(Claims(sub=sub_of(OWNER_EMAIL)))
    assert str(caught.value) == SIGN_IN_TO_CONTINUE


async def test_an_invited_sub_account_is_linked_on_first_sign_in(
    service: IdentityService, repo: InMemoryRepo, directory: FakeDirectory, hook: RecordingHook
) -> None:
    owner = await owner_of(service)
    user_id, _ = await invited_sub(service, owner)

    principal = await service.open_session(SUB_CLAIMS)

    linked = repo.users[(owner.account_id, user_id)]
    assert principal == Principal(
        account_id=owner.account_id, role=Role.SUB, user_id=user_id, username=SUB_EMAIL
    )
    assert (linked.status, linked.cognito_sub) == (UserStatus.ACTIVE, SUB_CLAIMS.sub)
    assert directory.created == [SUB_EMAIL]
    assert len(hook.calls) == 1


async def test_a_disabled_sub_account_cannot_open_a_session(service: IdentityService) -> None:
    owner = await owner_of(service)
    user_id, _ = await invited_sub(service, owner)
    await service.update_user(owner, user_id, UserUpdate(status=UserStatus.DISABLED))

    with pytest.raises(Forbidden) as caught:
        await service.open_session(SUB_CLAIMS)
    assert str(caught.value) == ACCOUNT_DISABLED


async def test_a_disabled_user_is_invisible_to_both_lookups(service: IdentityService) -> None:
    owner = await owner_of(service)
    user_id, api_key = await invited_sub(service, owner)
    await service.open_session(SUB_CLAIMS)
    await service.update_user(owner, user_id, UserUpdate(status=UserStatus.DISABLED))

    by_sub = await service.principal_for(SUB_CLAIMS.sub)
    by_key = await service.user_for_api_key(api_key_digest(api_key))

    assert (by_sub, by_key) == (None, None)


async def test_principal_for_an_unknown_sub_is_none(service: IdentityService) -> None:
    assert await service.principal_for("nobody") is None


def test_a_new_api_key_is_forty_urlsafe_characters_with_its_prefix_and_digest() -> None:
    issued = new_api_key(Random(7))

    assert len(issued.api_key) == API_KEY_LENGTH
    assert set(issued.api_key) <= URLSAFE_ALPHABET
    assert issued.prefix == issued.api_key[:API_KEY_PREFIX_LENGTH]
    assert issued.digest == hashlib.sha256(issued.api_key.encode()).hexdigest()


async def test_a_created_key_is_stored_as_its_hash(
    service: IdentityService, repo: InMemoryRepo
) -> None:
    owner = await owner_of(service)

    user_id, api_key = await invited_sub(service, owner)

    stored = repo.users[(owner.account_id, user_id)]
    assert stored.api_key_hash == api_key_digest(api_key)
    assert stored.api_key_prefix == api_key[:API_KEY_PREFIX_LENGTH]
    assert api_key not in {user.api_key_hash for user in repo.users.values()}


async def test_regenerating_retires_the_old_key(service: IdentityService) -> None:
    owner = await owner_of(service)
    user_id, old_key = await invited_sub(service, owner)

    issued = await service.regenerate_api_key(owner, user_id)

    retired = await service.user_for_api_key(api_key_digest(old_key))
    current = await service.user_for_api_key(api_key_digest(issued.api_key))
    assert retired is None
    assert current is not None
    assert (current.user_id, current.api_key_prefix) == (user_id, issued.api_key_prefix)


async def test_a_sub_account_regenerates_only_its_own_key(service: IdentityService) -> None:
    owner = await owner_of(service)
    await invited_sub(service, owner)
    sub = await service.open_session(SUB_CLAIMS)

    own = await service.regenerate_api_key(sub, sub.user_id)
    assert own.user_id == sub.user_id

    with pytest.raises(Forbidden) as caught:
        await service.regenerate_api_key(sub, owner.user_id)
    assert str(caught.value) == OWNER_ONLY


@pytest.mark.parametrize(
    "act",
    [
        lambda service, sub: service.create_user(sub, CreateUser(username="x@txtlocal.local")),
        lambda service, sub: service.update_user(sub, sub.user_id, UserUpdate(notes="n")),
        lambda service, sub: service.update_account_settings(
            sub, AccountSettings(default_country="GB", name="n", timezone="Europe/London")
        ),
        lambda service, sub: service.update_messaging_settings(sub, MessagingSettings()),
    ],
    ids=["create-user", "update-user", "account-settings", "messaging-settings"],
)
async def test_only_the_owner_manages_the_account(
    service: IdentityService, act: OwnerAction
) -> None:
    owner = await owner_of(service)
    await invited_sub(service, owner)
    sub = await service.open_session(SUB_CLAIMS)

    with pytest.raises(Forbidden) as caught:
        await act(service, sub)
    assert str(caught.value) == OWNER_ONLY


@pytest.mark.parametrize(
    "username",
    [SUB_EMAIL, SUB_EMAIL.upper(), OWNER_EMAIL],
    ids=["same-email", "different-case", "the-owner"],
)
async def test_a_taken_email_is_a_conflict(service: IdentityService, username: str) -> None:
    owner = await owner_of(service)
    await invited_sub(service, owner)

    with pytest.raises(Conflict) as caught:
        await service.create_user(owner, CreateUser(username=username))
    assert str(caught.value) == DUPLICATE_EMAIL


@pytest.mark.parametrize(
    ("request_", "message"),
    [
        (CreateUser(username="not-an-email"), INVALID_EMAIL),
        (CreateUser(first_name="a" * (MAX_NAME + 1), username="a@b.co"), FIRST_NAME_LENGTH),
        (CreateUser(last_name="a" * (MAX_NAME + 1), username="a@b.co"), LAST_NAME_LENGTH),
        (CreateUser(notes="n" * (MAX_NOTES + 1), username="a@b.co"), NOTES_LENGTH),
        (CreateUser(phone="abc", username="a@b.co"), INVALID_NUMBER_MESSAGE),
    ],
    ids=["email", "first-name-51", "last-name-51", "notes-201", "phone"],
)
async def test_create_user_refuses_with_the_public_message(
    service: IdentityService, request_: CreateUser, message: str
) -> None:
    owner = await owner_of(service)

    with pytest.raises(BadRequest) as caught:
        await service.create_user(owner, request_)
    assert str(caught.value) == message


async def test_create_user_accepts_the_ceilings(service: IdentityService) -> None:
    owner = await owner_of(service)

    created = await service.create_user(
        owner,
        CreateUser(
            first_name="f" * MAX_NAME,
            last_name="l" * MAX_NAME,
            notes="n" * MAX_NOTES,
            phone="07411972333",
            username=" New@TxtLocal.local ",
        ),
    )

    assert (created.user.username, created.user.phone) == ("new@txtlocal.local", "+447411972333")
    assert (len(created.user.first_name), len(created.user.notes or "")) == (MAX_NAME, MAX_NOTES)


@pytest.mark.parametrize("seed", [0, 1, 2, 42], ids=["seed-0", "seed-1", "seed-2", "seed-42"])
def test_new_temporary_password_satisfies_every_character_class(seed: int) -> None:
    password = new_temporary_password(Random(seed))

    assert len(password) == TEMP_PASSWORD_LENGTH
    assert any(char.isupper() for char in password)
    assert any(char.islower() for char in password)
    assert any(char.isdigit() for char in password)
    assert any(char in TEMP_SYMBOL_CHARS for char in password)


async def test_create_user_sends_the_same_password_it_gave_the_directory(
    service: IdentityService, directory: FakeDirectory
) -> None:
    owner = await owner_of(service)

    await service.create_user(owner, CreateUser(username=SUB_EMAIL))

    [temporary_password] = directory.passwords
    assert email_of(service).sent == [
        (SUB_EMAIL, INVITATION_SUBJECT, invitation_body(SUB_EMAIL, temporary_password))
    ]


async def test_create_user_without_email_configured_is_internal(
    clock: FakeClock,
    directory: FakeDirectory,
    hook: RecordingHook,
    repo: InMemoryRepo,
    senders: FakeSenders,
    verifier: LocalVerifier,
) -> None:
    service = IdentityService(
        balances=FakeBalances(answer=TRIAL_BALANCE),
        clock=clock,
        directory=directory,
        hooks=(hook,),
        repo=repo,
        rng=Random(7),
        senders=senders,
        verifier=verifier,
    )
    owner = await owner_of(service)

    with pytest.raises(Internal) as caught:
        await service.create_user(owner, CreateUser(username=SUB_EMAIL))
    assert str(caught.value) == EMAIL_NOT_CONFIGURED


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (ProfileUpdate(first_name="", last_name="Ahmed"), FIRST_NAME_LENGTH),
        (ProfileUpdate(first_name="a" * (MAX_NAME + 1), last_name="Ahmed"), FIRST_NAME_LENGTH),
        (ProfileUpdate(first_name="Junaid", last_name="  "), LAST_NAME_LENGTH),
        (ProfileUpdate(first_name="Junaid", last_name="a" * (MAX_NAME + 1)), LAST_NAME_LENGTH),
        (
            ProfileUpdate(first_name="Junaid", last_name="Ahmed", phone="abc"),
            INVALID_NUMBER_MESSAGE,
        ),
    ],
    ids=["first-empty", "first-51", "last-blank", "last-51", "phone"],
)
async def test_profile_refuses_with_the_public_message(
    service: IdentityService, update: ProfileUpdate, message: str
) -> None:
    owner = await owner_of(service)

    with pytest.raises(BadRequest) as caught:
        await service.update_profile(owner, update)
    assert str(caught.value) == message


async def test_profile_normalises_the_phone_against_the_default_country(
    service: IdentityService,
) -> None:
    owner = await owner_of(service)

    profile = await service.update_profile(
        owner, ProfileUpdate(first_name="a" * MAX_NAME, last_name="Ahmed", phone="07411972333")
    )

    assert (profile.phone, profile.username, len(profile.first_name)) == (
        "+447411972333",
        OWNER_EMAIL,
        MAX_NAME,
    )


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            AccountSettings(
                default_country="GB", name="a" * (MAX_ACCOUNT_NAME + 1), timezone="Europe/London"
            ),
            ACCOUNT_NAME_LENGTH,
        ),
        (
            AccountSettings(default_country="GB", name=" ", timezone="Europe/London"),
            ACCOUNT_NAME_LENGTH,
        ),
        (AccountSettings(default_country="GB", name="n", timezone="Mars/Phobos"), INVALID_TIMEZONE),
        (AccountSettings(default_country="GB", name="n", timezone="../etc"), INVALID_TIMEZONE),
        (
            AccountSettings(default_country="ZZ", name="n", timezone="Europe/London"),
            INVALID_COUNTRY,
        ),
        (
            AccountSettings(default_country="gb", name="n", timezone="Europe/London"),
            INVALID_COUNTRY,
        ),
    ],
    ids=[
        "name-101",
        "name-blank",
        "timezone-unknown",
        "timezone-path",
        "country-zz",
        "country-case",
    ],
)
async def test_account_settings_refuse_with_the_public_message(
    service: IdentityService, settings: AccountSettings, message: str
) -> None:
    owner = await owner_of(service)

    with pytest.raises(BadRequest) as caught:
        await service.update_account_settings(owner, settings)
    assert str(caught.value) == message


async def test_account_settings_share_the_default_country_with_messaging(
    service: IdentityService,
) -> None:
    owner = await owner_of(service)
    settings = AccountSettings(
        default_country="US", name="a" * MAX_ACCOUNT_NAME, timezone="America/New_York"
    )

    saved = await service.update_account_settings(owner, settings)

    assert saved == settings
    assert await service.account_settings(owner) == settings
    assert (await service.messaging_settings(owner.account_id)).default_country == "US"


async def test_contact_details_reads_the_account(service: IdentityService) -> None:
    owner = await owner_of(service)

    contact = await service.contact_details(owner.account_id)

    assert (contact.email, contact.mobile, contact.name) == (OWNER_EMAIL, None, "demo")


async def test_update_contact_details_persists_name_email_and_mobile(
    service: IdentityService,
) -> None:
    owner = await owner_of(service)

    updated = await service.update_contact_details(
        owner.account_id, "Billing Contact", "billing@example.com", "+447411972333"
    )

    assert (updated.email, updated.mobile, updated.name) == (
        "billing@example.com",
        "+447411972333",
        "Billing Contact",
    )
    assert await service.contact_details(owner.account_id) == updated


async def test_update_contact_details_can_clear_the_mobile_number(
    service: IdentityService,
) -> None:
    owner = await owner_of(service)
    await service.update_contact_details(owner.account_id, "Name", OWNER_EMAIL, "+447411972333")

    cleared = await service.update_contact_details(owner.account_id, "Name", OWNER_EMAIL, None)

    assert cleared.mobile is None
    assert (await service.contact_details(owner.account_id)).mobile is None


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (MessagingSettings(max_parts=0), MAX_PARTS_RANGE),
        (MessagingSettings(max_parts=9), MAX_PARTS_RANGE),
        (MessagingSettings(default_country="ZZ"), INVALID_COUNTRY),
    ],
    ids=["zero-parts", "nine-parts", "country"],
)
async def test_messaging_settings_refuse_with_the_public_message(
    service: IdentityService, settings: MessagingSettings, message: str
) -> None:
    owner = await owner_of(service)

    with pytest.raises(BadRequest) as caught:
        await service.update_messaging_settings(owner, settings)
    assert str(caught.value) == message


@pytest.mark.parametrize("max_parts", [1, 8], ids=["one-part", "eight-parts"])
async def test_messaging_settings_accept_the_parts_ceilings(
    service: IdentityService, max_parts: int
) -> None:
    owner = await owner_of(service)
    settings = MessagingSettings(max_parts=max_parts, show_own_number=False)

    await service.update_messaging_settings(owner, settings)

    assert await service.messaging_settings(owner.account_id) == settings


async def test_the_owner_cannot_be_disabled(service: IdentityService) -> None:
    owner = await owner_of(service)

    with pytest.raises(BadRequest) as caught:
        await service.update_user(owner, owner.user_id, UserUpdate(status=UserStatus.DISABLED))
    assert str(caught.value) == OWNER_STATUS


async def test_invited_is_not_a_status_an_owner_can_choose(service: IdentityService) -> None:
    owner = await owner_of(service)
    user_id, _ = await invited_sub(service, owner)

    with pytest.raises(BadRequest) as caught:
        await service.update_user(owner, user_id, UserUpdate(status=UserStatus.INVITED))
    assert str(caught.value) == STATUS_CHOICE


@pytest.mark.parametrize(
    ("signed_in", "expected"),
    [(False, UserStatus.INVITED), (True, UserStatus.ACTIVE)],
    ids=["re-enabled-before-sign-in-is-invited", "re-enabled-after-sign-in-is-active"],
)
async def test_re_enabling_restores_the_status_the_user_earned(
    service: IdentityService, signed_in: bool, expected: UserStatus
) -> None:
    owner = await owner_of(service)
    user_id, _ = await invited_sub(service, owner)
    if signed_in:
        await service.open_session(SUB_CLAIMS)
    await service.update_user(owner, user_id, UserUpdate(status=UserStatus.DISABLED))

    row = await service.update_user(owner, user_id, UserUpdate(status=UserStatus.ACTIVE))

    assert row.status is expected


async def test_update_user_changes_only_the_fields_sent(service: IdentityService) -> None:
    owner = await owner_of(service)
    user_id, _ = await invited_sub(service, owner)
    await service.update_user(owner, user_id, UserUpdate(notes="first", phone="07411972333"))

    row = await service.update_user(owner, user_id, UserUpdate(notes=None))

    assert (row.notes, row.phone) == (None, "+447411972333")


async def test_an_unknown_user_is_not_found(service: IdentityService) -> None:
    owner = await owner_of(service)

    with pytest.raises(NotFound) as caught:
        await service.update_user(owner, "missing", UserUpdate(notes="n"))
    assert str(caught.value) == USER_NOT_FOUND


async def test_users_lists_the_owner_first_and_filters_by_the_query(
    service: IdentityService,
) -> None:
    owner = await owner_of(service)
    await service.create_user(owner, CreateUser(notes="Warehouse", username="b@txtlocal.local"))
    await invited_sub(service, owner)

    everyone = await service.users(owner, None)
    searched = await service.users(owner, " WARE ")

    assert [row.username for row in everyone] == [OWNER_EMAIL, "b@txtlocal.local", SUB_EMAIL]
    assert [row.username for row in searched] == ["b@txtlocal.local"]


async def test_me_combines_user_account_and_balance(service: IdentityService) -> None:
    owner = await owner_of(service)

    me = await service.me(owner)

    assert (me.account_name, me.balance_micro, me.trial_days_left, me.role) == (
        "demo",
        TRIAL_BALANCE.balance_micro,
        TRIAL_BALANCE.trial_days_left,
        Role.OWNER,
    )
    assert (me.default_country, me.username, me.user_id) == ("GB", OWNER_EMAIL, owner.user_id)


@pytest.mark.parametrize("verified", [False, True], ids=["no-verified-number", "verified-number"])
async def test_home_reports_the_checklist(
    service: IdentityService, senders: FakeSenders, verified: bool
) -> None:
    owner = await owner_of(service)
    if verified:
        senders.verified[owner.account_id] = frozenset({E164("+447411972333")})

    home = await service.home(owner)

    assert (home.number_verified, home.email_verified, home.trial_days_left) == (
        verified,
        True,
        TRIAL_BALANCE.trial_days_left,
    )


async def test_authenticated_maps_a_bearer_token_to_the_principal(
    service: IdentityService, idp: DevIdp, verifier: LocalVerifier, clock: FakeClock
) -> None:
    owner = await owner_of(service)
    dependency = authenticated(verifier, service, clock)

    principal = await dependency(request_with(bearer_for(idp)))

    assert principal == owner


async def test_authenticated_keeps_the_mapping_after_the_first_lookup(
    service: IdentityService,
    idp: DevIdp,
    verifier: LocalVerifier,
    repo: InMemoryRepo,
    clock: FakeClock,
) -> None:
    owner = await owner_of(service)
    dependency = authenticated(verifier, service, clock)
    await dependency(request_with(bearer_for(idp)))

    repo.pointers.clear()
    principal = await dependency(request_with(bearer_for(idp)))

    assert principal == owner


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer", "Bearer  ", "Basic abc", "Bearer not-a-jwt"],
    ids=["missing", "bare-scheme", "blank-token", "basic-scheme", "garbage"],
)
async def test_authenticated_refuses_with_the_public_message(
    service: IdentityService,
    verifier: LocalVerifier,
    authorization: str | None,
    clock: FakeClock,
) -> None:
    dependency = authenticated(verifier, service, clock)

    with pytest.raises(Unauthorized) as caught:
        await dependency(request_with(authorization))
    assert str(caught.value) == SIGN_IN_TO_CONTINUE


async def test_authenticated_refuses_a_verified_token_without_a_session(
    service: IdentityService, idp: DevIdp, verifier: LocalVerifier, clock: FakeClock
) -> None:
    dependency = authenticated(verifier, service, clock)

    with pytest.raises(Unauthorized) as caught:
        await dependency(request_with(bearer_for(idp)))
    assert str(caught.value) == SIGN_IN_TO_CONTINUE


def test_the_principal_cache_is_bounded() -> None:
    cache: dict[str, CachedPrincipal] = {}
    principal = Principal(account_id="a", role=Role.OWNER, user_id="u", username="x@y.z")

    for index in range(PRINCIPAL_CACHE_SIZE + 1):
        remember(cache, str(index), principal, NOW)

    assert len(cache) == PRINCIPAL_CACHE_SIZE
    assert "0" not in cache
    assert str(PRINCIPAL_CACHE_SIZE) in cache


async def test_api_user_maps_basic_credentials_to_the_principal(
    service: IdentityService, rate_limits: FakeRateLimits, clock: FakeClock
) -> None:
    owner = await owner_of(service)
    user_id, api_key = await invited_sub(service, owner)
    dependency = api_user(service, rate_limits, clock)
    request = request_with(basic(SUB_EMAIL.upper(), api_key))

    principal = await dependency(request)

    assert principal == Principal(
        account_id=owner.account_id, role=Role.SUB, user_id=user_id, username=SUB_EMAIL
    )
    assert request.state.principal == principal


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer abc",
        "Basic %%%",
        basic("", ""),
        "Basic " + base64.b64encode(b"no-colon").decode(),
        basic(SUB_EMAIL, "wrong-key"),
        basic(OWNER_EMAIL, "SUB_KEY"),
    ],
    ids=[
        "missing",
        "bearer-scheme",
        "not-base64",
        "empty-pair",
        "no-colon",
        "wrong-key",
        "wrong-username",
    ],
)
async def test_api_user_refuses_with_the_public_message(
    service: IdentityService,
    rate_limits: FakeRateLimits,
    clock: FakeClock,
    authorization: str | None,
) -> None:
    owner = await owner_of(service)
    _, api_key = await invited_sub(service, owner)
    dependency = api_user(service, rate_limits, clock)

    with pytest.raises(Unauthorized) as caught:
        await dependency(
            request_with(authorization.replace("SUB_KEY", api_key) if authorization else None)
        )
    assert str(caught.value) == INVALID_API_CREDENTIALS


async def test_api_user_allows_the_sixtieth_request_in_a_minute(
    service: IdentityService, rate_limits: FakeRateLimits
) -> None:
    owner = await owner_of(service)
    user_id, api_key = await invited_sub(service, owner)
    minute = current_minute(RATE_LIMIT_CLOCK.now)
    rate_limits.counts[(user_id, minute)] = RATE_LIMIT_PER_MINUTE - 1
    dependency = api_user(service, rate_limits, RATE_LIMIT_CLOCK)

    principal = await dependency(request_with(basic(SUB_EMAIL, api_key)))

    assert principal.user_id == user_id


async def test_api_user_refuses_the_sixty_first_request_in_a_minute(
    service: IdentityService, rate_limits: FakeRateLimits
) -> None:
    owner = await owner_of(service)
    user_id, api_key = await invited_sub(service, owner)
    minute = current_minute(RATE_LIMIT_CLOCK.now)
    rate_limits.counts[(user_id, minute)] = RATE_LIMIT_PER_MINUTE
    dependency = api_user(service, rate_limits, RATE_LIMIT_CLOCK)

    with pytest.raises(RateLimited) as caught:
        await dependency(request_with(basic(SUB_EMAIL, api_key)))

    assert (str(caught.value), caught.value.retry_after) == (RATE_LIMIT_MESSAGE, 55)


@pytest.mark.parametrize(
    ("counted", "expected"),
    [(RATE_LIMIT_PER_MINUTE, False), (RATE_LIMIT_PER_MINUTE + 1, True)],
    ids=["sixtieth-request-passes", "sixty-first-request-is-over"],
)
def test_is_over_rate_limit_at_the_ceiling(counted: int, expected: bool) -> None:
    assert is_over_rate_limit(counted) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [(399, "ok"), (400, "refused"), (499, "refused"), (500, "failed")],
    ids=["last-2xx-3xx", "first-4xx", "last-4xx", "first-5xx"],
)
def test_outcome_of_the_status_bucket(status: int, expected: str) -> None:
    assert outcome_of(status) == expected


def bearer_for(idp: DevIdp) -> str:
    return f"Bearer {idp.tokens(OWNER_EMAIL)['access_token']}"


async def test_a_disabled_user_is_refused_once_the_cached_principal_expires(
    service: IdentityService,
    idp: DevIdp,
    verifier: LocalVerifier,
    repo: InMemoryRepo,
    clock: FakeClock,
) -> None:
    owner = await owner_of(service)
    dependency = authenticated(verifier, service, clock)
    token = bearer_for(idp)
    await dependency(request_with(token))

    stored = repo.users[owner.account_id, owner.user_id]
    repo.users[owner.account_id, owner.user_id] = stored.model_copy(
        update={"status": UserStatus.DISABLED}
    )
    clock.now += PRINCIPAL_CACHE_TTL + ONE_SECOND

    with pytest.raises(Unauthorized) as caught:
        await dependency(request_with(token))

    assert str(caught.value) == SIGN_IN_TO_CONTINUE


async def test_a_cached_principal_is_reused_inside_the_ttl(
    service: IdentityService,
    idp: DevIdp,
    verifier: LocalVerifier,
    repo: InMemoryRepo,
    clock: FakeClock,
) -> None:
    owner = await owner_of(service)
    dependency = authenticated(verifier, service, clock)
    token = bearer_for(idp)
    await dependency(request_with(token))

    repo.pointers.clear()
    clock.now += PRINCIPAL_CACHE_TTL - ONE_SECOND

    assert await dependency(request_with(token)) == owner


async def test_a_regenerated_api_key_stops_working_even_while_the_index_is_stale(
    service: IdentityService, repo: InMemoryRepo
) -> None:
    owner = await owner_of(service)
    issued = await service.regenerate_api_key(owner, owner.user_id)
    stale = api_key_digest(issued.api_key)
    stored = repo.users[owner.account_id, owner.user_id]
    repo.users[owner.account_id, owner.user_id] = stored.model_copy(
        update={"api_key_hash": api_key_digest("a-newer-key")}
    )

    assert await service.user_for_api_key(stale) is None
