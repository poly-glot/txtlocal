from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from txtlocal.shared.money import Micro, format_price
from txtlocal.shared.phone import E164, country_of
from txtlocal.slices.messaging.model import RefusalReason

READY = "READY"
SHARED = "SHARED"

COUNTRY_NOT_ENABLED_MESSAGE = "Sending to {country} is not enabled for this account"
OPTED_OUT_MESSAGE = "This contact has opted out"
TRIAL_ENDED_MESSAGE = "Your free trial has ended. Top up to keep sending"
INSUFFICIENT_BALANCE_MESSAGE = "Your balance is {balance}; this send costs {cost}"
DAILY_CAP_MESSAGE = "Daily sending limit reached"
SENDER_NOT_READY_MESSAGE = "{sender} is not ready to send to {country}"
NOT_VERIFIED_MESSAGE = "While your account is in trial you can send to your verified numbers only"


@dataclass(frozen=True, slots=True)
class AccountState:
    balance_micro: Micro
    has_topped_up: bool
    opted_out: frozenset[E164]
    sends_today: int
    trial_ends_at: datetime
    verified_numbers: frozenset[E164]


class SenderView(Protocol):
    @property
    def country(self) -> str: ...

    @property
    def display(self) -> str: ...

    @property
    def kind(self) -> str: ...

    @property
    def status(self) -> str: ...


@dataclass(frozen=True, slots=True)
class Allowed:
    max_price_usd: str


@dataclass(frozen=True, slots=True)
class Refused:
    message: str
    reason: RefusalReason


def is_within_trial(trial_ends_at: datetime, now: datetime) -> bool:
    return now < trial_ends_at


def can_send(account: AccountState, now: datetime) -> bool:
    return account.has_topped_up or is_within_trial(account.trial_ends_at, now)


def is_opted_out(destination: E164, opted_out: frozenset[E164]) -> bool:
    return destination in opted_out


def is_over_daily_cap(counted: int, daily_cap: int) -> bool:
    return counted > daily_cap


def is_at_daily_cap(sends_today: int, daily_cap: int) -> bool:
    return is_over_daily_cap(sends_today + 1, daily_cap)


def is_ready_for(sender: SenderView, country: str) -> bool:
    if sender.status != READY:
        return False
    return sender.kind == SHARED or sender.country == country


def is_verified_destination(destination: E164, account: AccountState) -> bool:
    return destination in account.verified_numbers


@dataclass(frozen=True, slots=True)
class SendPolicy:
    allowed_countries: frozenset[str]
    daily_cap: int
    max_price_usd: str
    sandbox: bool

    def allow(
        self,
        account: AccountState,
        sender: SenderView,
        destination: E164,
        quote: Micro,
        now: datetime,
    ) -> Allowed | Refused:
        country = country_of(destination)

        checks = (
            (
                country not in self.allowed_countries,
                RefusalReason.COUNTRY_NOT_ENABLED,
                COUNTRY_NOT_ENABLED_MESSAGE.format(country=country),
            ),
            (
                is_opted_out(destination, account.opted_out),
                RefusalReason.OPTED_OUT,
                OPTED_OUT_MESSAGE,
            ),
            (
                not can_send(account, now),
                RefusalReason.TRIAL_ENDED,
                TRIAL_ENDED_MESSAGE,
            ),
            (
                account.balance_micro < quote,
                RefusalReason.INSUFFICIENT_BALANCE,
                INSUFFICIENT_BALANCE_MESSAGE.format(
                    balance=format_price(account.balance_micro), cost=format_price(quote)
                ),
            ),
            (
                is_at_daily_cap(account.sends_today, self.daily_cap),
                RefusalReason.DAILY_CAP,
                DAILY_CAP_MESSAGE,
            ),
            (
                not is_ready_for(sender, country),
                RefusalReason.SENDER_NOT_READY,
                SENDER_NOT_READY_MESSAGE.format(country=country, sender=sender.display),
            ),
            (
                self.sandbox and not is_verified_destination(destination, account),
                RefusalReason.NOT_VERIFIED,
                NOT_VERIFIED_MESSAGE,
            ),
        )

        refused = next(
            (
                Refused(message=message, reason=reason)
                for failed, reason, message in checks
                if failed
            ),
            None,
        )
        return Allowed(max_price_usd=self.max_price_usd) if refused is None else refused
