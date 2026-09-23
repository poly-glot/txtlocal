from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from txtlocal.shared.phone import E164
    from txtlocal.slices.identity.model import (
        Account,
        AccountSettings,
        MessagingSettings,
        SubPointer,
        User,
    )

CLIENT_ID = "local"
ISSUER = "http://localhost:3000/api/dev-idp"
NOW = datetime.now(UTC).replace(microsecond=0)
OWNER_EMAIL = "demo@txtlocal.local"
SUB_EMAIL = "sub@txtlocal.local"


@dataclass
class FakeClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now


@dataclass(frozen=True, slots=True)
class Balance:
    balance_micro: int
    can_send: bool
    has_topped_up: bool
    trial_days_left: int
    trial_ends_at: datetime


TRIAL_BALANCE = Balance(
    balance_micro=2_000_000,
    can_send=True,
    has_topped_up=False,
    trial_days_left=14,
    trial_ends_at=NOW + timedelta(days=14),
)


@dataclass
class FakeBalances:
    answer: Balance
    asked: list[tuple[str, datetime]] = field(default_factory=list)

    async def balance(self, account_id: str, now: datetime) -> Balance:
        self.asked.append((account_id, now))
        return self.answer


@dataclass
class FakeDirectory:
    created: list[str] = field(default_factory=list)
    passwords: list[str] = field(default_factory=list)

    async def create_user(self, email: str, temporary_password: str) -> None:
        self.created.append(email)
        self.passwords.append(temporary_password)


@dataclass
class FakeSenders:
    verified: dict[str, frozenset[E164]] = field(default_factory=dict)

    async def verified_numbers(self, account_id: str) -> frozenset[E164]:
        return self.verified.get(account_id, frozenset())


@dataclass
class FakeRateLimits:
    counts: dict[tuple[str, str], int] = field(default_factory=dict)

    async def count(self, user_id: str, minute: str) -> int:
        counted = self.counts.get((user_id, minute), 0) + 1
        self.counts[(user_id, minute)] = counted
        return counted


@dataclass
class RecordingEmail:
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@dataclass
class RecordingHook:
    calls: list[tuple[str, datetime]] = field(default_factory=list)

    async def __call__(self, account_id: str, now: datetime) -> None:
        self.calls.append((account_id, now))


@dataclass
class InMemoryRepo:
    accounts: dict[str, Account] = field(default_factory=dict)
    pointers: dict[str, SubPointer] = field(default_factory=dict)
    users: dict[tuple[str, str], User] = field(default_factory=dict)

    async def create_account(self, account: Account, owner: User, pointer: SubPointer) -> bool:
        owner_key = (owner.account_id, owner.user_id)
        if account.account_id in self.accounts or owner_key in self.users:
            return False
        if pointer.sub in self.pointers:
            return False

        self.accounts[account.account_id] = account
        self.users[owner_key] = owner
        self.pointers[pointer.sub] = pointer
        return True

    async def find_user_by_api_key(self, digest: str) -> User | None:
        return next((user for user in self.users.values() if user.api_key_hash == digest), None)

    async def find_user_by_username(self, username: str) -> User | None:
        return next((user for user in self.users.values() if user.username == username), None)

    async def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    async def get_pointer(self, sub: str) -> SubPointer | None:
        return self.pointers.get(sub)

    async def get_user(self, account_id: str, user_id: str) -> User | None:
        return self.users.get((account_id, user_id))

    async def link_user(self, user: User, pointer: SubPointer) -> bool:
        user_key = (user.account_id, user.user_id)
        current = self.users.get(user_key)
        if current is None or current.cognito_sub is not None or pointer.sub in self.pointers:
            return False

        self.pointers[pointer.sub] = pointer
        self.users[user_key] = current.model_copy(
            update={
                "cognito_sub": pointer.sub,
                "email_verified": user.email_verified,
                "status": user.status,
            }
        )
        return True

    async def list_users(self, account_id: str) -> list[User]:
        return [user for user in self.users.values() if user.account_id == account_id]

    async def put_user(self, user: User) -> bool:
        user_key = (user.account_id, user.user_id)
        if user_key in self.users:
            return False
        self.users[user_key] = user
        return True

    async def save_account(self, account: Account) -> bool:
        if account.account_id not in self.accounts:
            return False
        self.accounts[account.account_id] = account
        return True

    async def save_user(self, user: User) -> bool:
        user_key = (user.account_id, user.user_id)
        if user_key not in self.users:
            return False
        self.users[user_key] = user
        return True

    async def set_account_settings(self, account_id: str, settings: AccountSettings) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False

        self.accounts[account_id] = account.model_copy(
            update={
                "name": settings.name,
                "settings": account.settings.model_copy(
                    update={"default_country": settings.default_country}
                ),
                "timezone": settings.timezone,
            }
        )
        return True

    async def set_messaging_settings(self, account_id: str, settings: MessagingSettings) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False

        self.accounts[account_id] = account.model_copy(update={"settings": settings})
        return True
