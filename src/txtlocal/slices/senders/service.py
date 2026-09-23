import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from re import compile as re_compile
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.errors import BadRequest, Conflict, Internal, NotFound
from txtlocal.shared.phone import E164, country_of, normalise
from txtlocal.slices.senders.model import (
    SHARED_VALUE,
    AlphaTagRequest,
    Channel,
    NumberCataloguePage,
    NumberSearchQuery,
    OwnNumberRequest,
    Sender,
    SenderKind,
    SenderStatus,
    SmartSender,
    SmartSenderRequest,
    VerificationRequest,
    display_of,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.money import Micro
    from txtlocal.slices.senders.catalogue import NumberCatalogue
    from txtlocal.slices.senders.repo import SendersRepo

ALPHA_REVIEW_OUTCOME = SenderStatus.READY
ALPHA_TAG_INVALID = "Enter an alpha tag of 3 to 11 characters: letters, numbers and + only"
ALPHA_TAG_PATTERN = re_compile(r"[A-Za-z0-9+]{3,11}")
BILLING_NOT_CONFIGURED = "billing gate not configured"
CATALOGUE_NOT_CONFIGURED = "number catalogue not configured"
CODE_INCORRECT = "The code you entered is not correct"
CODE_LENGTH = 6
DEFAULT_COUNTRY = "GB"
ENTER_CODE = "Enter your 6-digit code"
NUMBER_ALREADY_ADDED = "This number is already one of your own numbers"
NUMBER_NOT_FOUND = "Number not found"
ONLY_OWN_OR_DEDICATED_REMOVABLE = "Only own or dedicated numbers can be removed"
RENEWAL_PERIOD = timedelta(days=30)
RENTED_SENDER_MISSING_PRICE = "rented sender has no monthly price"
RENTED_SENDER_MISSING_RENEWAL_DATE = "rented sender has no renewal date"
SENDER_NOT_FOUND = "Sender not found"
SHARED_POOL_IDENTITY = "shared-pool"
TOP_UP_TO_RENT = "Top up to rent a number"


class VerificationGateway(Protocol):
    async def start_verification(self, destination: E164) -> None: ...

    async def check_verification(self, destination: E164, code: str) -> bool: ...


class BillingGate(Protocol):
    async def can_purchase(self, account_id: str, now: datetime) -> bool: ...

    async def charge_and_rent(
        self, account_id: str, sender_id: str, amount_micro: Micro, now: datetime
    ) -> None: ...


def country_not_enabled(country: str) -> str:
    return f"Sending to {country} is not enabled for this account"


def not_ready(sender: Sender, country: str) -> str:
    return f"{display_of(sender)} is not ready to send to {country}"


def is_ready_for(sender: Sender, country: str) -> bool:
    return sender.status is SenderStatus.READY and sender.country == country


def is_six_digits(code: str) -> bool:
    return len(code) == CODE_LENGTH and code.isascii() and code.isdigit()


def is_valid_alpha_tag(tag: str) -> bool:
    return ALPHA_TAG_PATTERN.fullmatch(tag) is not None


def new_id() -> str:
    return str(uuid.uuid7())


def sender_named(senders: Iterable[Sender], sender_id: str) -> Sender | None:
    return next((sender for sender in senders if sender.sender_id == sender_id), None)


def own_number_in(senders: Iterable[Sender], number: E164) -> Sender | None:
    own = (sender for sender in senders if sender.kind is SenderKind.OWN)
    return next((sender for sender in own if sender.value == number), None)


def shared_sender_for(senders: Iterable[Sender], country: str) -> Sender | None:
    shared = (sender for sender in senders if sender.kind is SenderKind.SHARED)
    return next((sender for sender in shared if sender.country == country), None)


def smart_for(smarts: Iterable[SmartSender], country: str) -> SmartSender | None:
    return next((smart for smart in smarts if smart.country == country), None)


def verified_numbers_of(senders: Iterable[Sender]) -> frozenset[E164]:
    own = (sender for sender in senders if sender.kind is SenderKind.OWN)
    return frozenset(E164(sender.value) for sender in own if sender.status is SenderStatus.READY)


def is_active_rental(sender: Sender) -> bool:
    return sender.kind is SenderKind.DEDICATED and sender.status is not SenderStatus.RELEASED


@dataclass(frozen=True, slots=True)
class DueSender:
    account_id: str
    sender: Sender

    @property
    def monthly_price_micro(self) -> Micro:
        if self.sender.monthly_price_micro is None:
            raise Internal(RENTED_SENDER_MISSING_PRICE)
        return self.sender.monthly_price_micro

    @property
    def renewal_attempt(self) -> int:
        return self.sender.renewal_attempt

    @property
    def renews_at(self) -> datetime:
        if self.sender.renews_at is None:
            raise Internal(RENTED_SENDER_MISSING_RENEWAL_DATE)
        return self.sender.renews_at

    @property
    def sender_id(self) -> str:
        return self.sender.sender_id

    @property
    def value(self) -> str:
        return self.sender.value


@dataclass(frozen=True, slots=True)
class SendersService:
    clock: Clock
    gateway: VerificationGateway
    repo: SendersRepo
    billing: BillingGate | None = None
    catalogue: NumberCatalogue | None = None

    async def provision_defaults(self, account_id: str, now: datetime) -> None:
        shared = Sender(
            capabilities=(Channel.MMS, Channel.SMS),
            country=DEFAULT_COUNTRY,
            created_at=now,
            kind=SenderKind.SHARED,
            provider_identity=SHARED_POOL_IDENTITY,
            sender_id=new_id(),
            status=SenderStatus.READY,
            value=SHARED_VALUE,
        )
        smart = SmartSender(country=DEFAULT_COUNTRY, sender_id=shared.sender_id)

        await self.repo.put_defaults_if_absent(account_id, shared, smart)

    async def resolve(self, account_id: str, sender_id: str | None, country: str) -> Sender:
        chosen = (
            sender_id if sender_id is not None else await self._smart_sender_id(account_id, country)
        )

        sender = await self.repo.get_sender(account_id, chosen)
        if sender is None:
            raise NotFound(SENDER_NOT_FOUND)
        if not is_ready_for(sender, country):
            raise BadRequest(not_ready(sender, country))

        return sender

    async def verified_numbers(self, account_id: str) -> frozenset[E164]:
        return verified_numbers_of(await self.repo.list_senders(account_id))

    async def senders(self, account_id: str) -> list[Sender]:
        return await self.repo.list_senders(account_id)

    async def smart_senders(self, account_id: str) -> list[SmartSender]:
        return await self.repo.list_smart(account_id)

    async def set_smart(
        self, account_id: str, country: str, request: SmartSenderRequest
    ) -> SmartSender:
        senders = await self.repo.list_senders(account_id)
        if shared_sender_for(senders, country) is None:
            raise BadRequest(country_not_enabled(country))

        sender = sender_named(senders, request.sender_id)
        if sender is None:
            raise NotFound(SENDER_NOT_FOUND)
        if not is_ready_for(sender, country):
            raise BadRequest(not_ready(sender, country))

        smart = SmartSender(country=country, sender_id=sender.sender_id)
        await self.repo.set_smart(account_id, smart)
        return smart

    async def add_own(self, account_id: str, request: OwnNumberRequest) -> Sender:
        number = normalise(request.number)

        senders = await self.repo.list_senders(account_id)
        existing = own_number_in(senders, number)
        if existing is not None and existing.status is SenderStatus.READY:
            raise Conflict(NUMBER_ALREADY_ADDED)

        sender = existing or self._pending_own(number, request.nickname)
        if existing is None:
            await self.repo.put_sender(account_id, sender)

        await self.gateway.start_verification(number)
        return sender

    async def verify_own(
        self, account_id: str, sender_id: str, request: VerificationRequest
    ) -> Sender:
        if not is_six_digits(request.code):
            raise BadRequest(ENTER_CODE)

        sender = await self.repo.get_sender(account_id, sender_id)
        if sender is None or sender.kind is not SenderKind.OWN:
            raise NotFound(SENDER_NOT_FOUND)
        if not await self.gateway.check_verification(E164(sender.value), request.code):
            raise BadRequest(CODE_INCORRECT)

        now = self.clock()
        if not await self.repo.mark_verified(account_id, sender_id, now):
            raise NotFound(SENDER_NOT_FOUND)

        return sender.model_copy(update={"status": SenderStatus.READY, "verified_at": now})

    async def register_alpha(self, account_id: str, request: AlphaTagRequest) -> Sender:
        if not is_valid_alpha_tag(request.tag):
            raise BadRequest(ALPHA_TAG_INVALID)

        senders = await self.repo.list_senders(account_id)
        if shared_sender_for(senders, request.country) is None:
            raise BadRequest(country_not_enabled(request.country))

        sender = Sender(
            capabilities=(Channel.SMS,),
            country=request.country,
            created_at=self.clock(),
            kind=SenderKind.ALPHA,
            sender_id=new_id(),
            status=SenderStatus.UNDER_REVIEW,
            use_case=request.use_case,
            value=request.tag,
        )
        await self.repo.put_sender(account_id, sender)
        return sender

    async def search_numbers(self, query: NumberSearchQuery) -> NumberCataloguePage:
        return await self._catalogue().search(
            query.country, query.use_for, query.contains, query.page
        )

    async def buy_number(self, account_id: str, number: str) -> Sender:
        now = self.clock()
        if not await self._billing().can_purchase(account_id, now):
            raise BadRequest(TOP_UP_TO_RENT)

        catalogue_entry = await self._catalogue().get(number)
        if catalogue_entry is None:
            raise NotFound(NUMBER_NOT_FOUND)

        sender_id = new_id()
        price = catalogue_entry.monthly_price_micro
        await self._billing().charge_and_rent(account_id, sender_id, price, now)

        sender = Sender(
            capabilities=catalogue_entry.capabilities,
            country=catalogue_entry.country,
            created_at=now,
            kind=SenderKind.DEDICATED,
            monthly_price_micro=price,
            renews_at=now + RENEWAL_PERIOD,
            sender_id=sender_id,
            status=SenderStatus.READY,
            value=catalogue_entry.value,
        )
        await self.repo.put_sender(account_id, sender)
        return sender

    async def remove(self, account_id: str, sender_id: str) -> None:
        senders = await self.repo.list_senders(account_id)
        sender = sender_named(senders, sender_id)
        if sender is None:
            raise NotFound(SENDER_NOT_FOUND)

        match sender.kind:
            case SenderKind.OWN:
                await self._remove_own(account_id, sender, senders)
            case SenderKind.DEDICATED:
                await self._cancel_dedicated(account_id, sender)
            case SenderKind.ALPHA | SenderKind.SHARED:
                raise BadRequest(ONLY_OWN_OR_DEDICATED_REMOVABLE)
            case _ as unreachable:
                assert_never(unreachable)

    async def due_for_renewal(self, now: datetime) -> Sequence[DueSender]:
        rented = await self.repo.rented_numbers()
        return [
            DueSender(account_id, sender)
            for account_id, sender in rented
            if sender.renews_at is not None and sender.renews_at <= now and not sender.cancelled
        ]

    async def rented_by(self, account_id: str) -> Sequence[DueSender]:
        senders = await self.repo.list_senders(account_id)
        return [DueSender(account_id, sender) for sender in senders if is_active_rental(sender)]

    async def record_renewal(self, account_id: str, sender_id: str, now: datetime) -> None:
        if not await self.repo.record_renewal(account_id, sender_id, now + RENEWAL_PERIOD):
            raise NotFound(SENDER_NOT_FOUND)

    async def record_renewal_attempt(self, account_id: str, sender_id: str, _now: datetime) -> None:
        if not await self.repo.record_renewal_attempt(account_id, sender_id):
            raise NotFound(SENDER_NOT_FOUND)

    async def release(self, account_id: str, sender_id: str) -> None:
        if not await self.repo.release(account_id, sender_id):
            raise NotFound(SENDER_NOT_FOUND)

    async def run_due_sweep(self, now: datetime) -> int:
        completed = await self._complete_due_alpha_tags()
        released = await self._release_due_cancellations(now)
        return completed + released

    async def _remove_own(self, account_id: str, sender: Sender, senders: Iterable[Sender]) -> None:
        if not await self.repo.delete_sender(account_id, sender.sender_id):
            raise NotFound(SENDER_NOT_FOUND)

        shared = shared_sender_for(senders, sender.country)
        if shared is not None:
            fallback = SmartSender(country=sender.country, sender_id=shared.sender_id)
            await self.repo.replace_smart_if_pointing_at(account_id, fallback, sender.sender_id)

    async def _cancel_dedicated(self, account_id: str, sender: Sender) -> None:
        if not await self.repo.cancel_rental(account_id, sender.sender_id):
            raise NotFound(SENDER_NOT_FOUND)

    async def _complete_due_alpha_tags(self) -> int:
        completed = 0
        for account_id, sender in await self.repo.alpha_tags_under_review():
            settled = await self.repo.complete_alpha_tag(
                account_id, sender.sender_id, ALPHA_REVIEW_OUTCOME
            )
            if settled:
                completed += 1
        return completed

    async def _release_due_cancellations(self, now: datetime) -> int:
        released = 0
        for account_id, sender in await self.repo.rented_numbers():
            due = sender.cancelled and sender.renews_at is not None and sender.renews_at <= now
            if due and await self.repo.release(account_id, sender.sender_id):
                released += 1
        return released

    async def _smart_sender_id(self, account_id: str, country: str) -> str:
        smart = smart_for(await self.repo.list_smart(account_id), country)
        if smart is None:
            raise BadRequest(country_not_enabled(country))
        return smart.sender_id

    def _pending_own(self, number: E164, nickname: str | None) -> Sender:
        return Sender(
            capabilities=(Channel.SMS,),
            country=country_of(number),
            created_at=self.clock(),
            kind=SenderKind.OWN,
            nickname=nickname,
            sender_id=new_id(),
            status=SenderStatus.PENDING_VERIFICATION,
            value=number,
        )

    def _billing(self) -> BillingGate:
        if self.billing is None:
            raise Internal(BILLING_NOT_CONFIGURED)
        return self.billing

    def _catalogue(self) -> NumberCatalogue:
        if self.catalogue is None:
            raise Internal(CATALOGUE_NOT_CONFIGURED)
        return self.catalogue
