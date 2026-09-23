from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.shared.errors import PaymentRequired
from txtlocal.slices.senders.model import Channel, Sender, SenderKind, SenderStatus, SmartSender

if TYPE_CHECKING:
    from txtlocal.shared.money import Micro
    from txtlocal.shared.phone import E164

ACCOUNT = "account-1"
ALPHA_TAG = "TXTLOCAL"
CODE = "123456"
DEDICATED_NUMBER = "+447984390718"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
OWN_NUMBER = "+447411972333"
OWN_NUMBER_AS_TYPED = "07411 972333"
SECOND_NUMBER = "+447411972300"
US_NUMBER = "+12025550123"


def sender_of(
    kind: SenderKind,
    value: str,
    nickname: str | None = None,
    provider_identity: str | None = None,
    sender_id: str = "sender-1",
    status: SenderStatus = SenderStatus.READY,
) -> Sender:
    shared = kind is SenderKind.SHARED
    return Sender(
        capabilities=(Channel.MMS, Channel.SMS) if shared else (Channel.SMS,),
        country="GB",
        created_at=NOW,
        kind=kind,
        nickname=nickname,
        provider_identity=provider_identity,
        sender_id=sender_id,
        status=status,
        value=value,
    )


@dataclass
class ScriptedBilling:
    can_send: bool = True
    charge_refused: bool = False
    charged: list[tuple[str, str, Micro]] = field(default_factory=list)

    async def can_purchase(self, _account_id: str, _now: datetime) -> bool:
        return self.can_send

    async def charge_and_rent(
        self, account_id: str, sender_id: str, amount_micro: Micro, _now: datetime
    ) -> None:
        if self.charge_refused:
            raise PaymentRequired("Your balance is £0.00; this send costs £2.65")
        self.charged.append((account_id, sender_id, amount_micro))


@dataclass
class InMemorySendersRepo:
    senders: dict[tuple[str, str], Sender] = field(default_factory=dict)
    smart: dict[tuple[str, str], SmartSender] = field(default_factory=dict)

    async def alpha_tags_under_review(self) -> list[tuple[str, Sender]]:
        return [
            (account_id, sender)
            for (account_id, _), sender in self.senders.items()
            if sender.kind is SenderKind.ALPHA and sender.status is SenderStatus.UNDER_REVIEW
        ]

    async def cancel_rental(self, account_id: str, sender_id: str) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        self.senders[(account_id, sender_id)] = sender.model_copy(update={"cancelled": True})
        return True

    async def complete_alpha_tag(
        self, account_id: str, sender_id: str, status: SenderStatus
    ) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        self.senders[(account_id, sender_id)] = sender.model_copy(update={"status": status})
        return True

    async def delete_sender(self, account_id: str, sender_id: str) -> bool:
        return self.senders.pop((account_id, sender_id), None) is not None

    async def get_sender(self, account_id: str, sender_id: str) -> Sender | None:
        return self.senders.get((account_id, sender_id))

    async def list_senders(self, account_id: str) -> list[Sender]:
        return [sender for (owner, _), sender in self.senders.items() if owner == account_id]

    async def list_smart(self, account_id: str) -> list[SmartSender]:
        return [smart for (owner, _), smart in self.smart.items() if owner == account_id]

    async def mark_verified(self, account_id: str, sender_id: str, now: datetime) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        verified = {"status": SenderStatus.READY, "verified_at": now}
        self.senders[(account_id, sender_id)] = sender.model_copy(update=verified)
        return True

    async def put_defaults_if_absent(
        self, account_id: str, sender: Sender, smart: SmartSender
    ) -> bool:
        sender_key = (account_id, sender.sender_id)
        smart_key = (account_id, smart.country)
        if sender_key in self.senders or smart_key in self.smart:
            return False

        self.senders[sender_key] = sender
        self.smart[smart_key] = smart
        return True

    async def put_sender(self, account_id: str, sender: Sender) -> None:
        self.senders[(account_id, sender.sender_id)] = sender

    async def record_renewal(self, account_id: str, sender_id: str, renews_at: datetime) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        renewed = {"renewal_attempt": 0, "renews_at": renews_at}
        self.senders[(account_id, sender_id)] = sender.model_copy(update=renewed)
        return True

    async def record_renewal_attempt(self, account_id: str, sender_id: str) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        attempted = {"renewal_attempt": sender.renewal_attempt + 1}
        self.senders[(account_id, sender_id)] = sender.model_copy(update=attempted)
        return True

    async def release(self, account_id: str, sender_id: str) -> bool:
        sender = self.senders.get((account_id, sender_id))
        if sender is None:
            return False

        self.senders[(account_id, sender_id)] = sender.model_copy(
            update={"status": SenderStatus.RELEASED}
        )
        return True

    async def rented_numbers(self) -> list[tuple[str, Sender]]:
        return [
            (account_id, sender)
            for (account_id, _), sender in self.senders.items()
            if sender.kind is SenderKind.DEDICATED and sender.status is not SenderStatus.RELEASED
        ]

    async def replace_smart_if_pointing_at(
        self, account_id: str, smart: SmartSender, current: str
    ) -> bool:
        existing = self.smart.get((account_id, smart.country))
        if existing is None or existing.sender_id != current:
            return False

        self.smart[(account_id, smart.country)] = smart
        return True

    async def set_smart(self, account_id: str, smart: SmartSender) -> None:
        self.smart[(account_id, smart.country)] = smart


@dataclass
class ScriptedVerification:
    code: str = CODE
    started: list[E164] = field(default_factory=list)

    async def start_verification(self, destination: E164) -> None:
        self.started.append(destination)

    async def check_verification(self, destination: E164, code: str) -> bool:
        return destination in self.started and code == self.code
