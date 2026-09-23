from collections.abc import Iterable
from enum import StrEnum
from typing import Self, assert_never

from txtlocal.shared.model import Model, Rfc3339
from txtlocal.shared.money import Micro

SHARED_DISPLAY = "Shared Number"
SHARED_VALUE = "SHARED"


class Channel(StrEnum):
    MMS = "MMS"
    SMS = "SMS"


class SenderKind(StrEnum):
    ALPHA = "ALPHA"
    DEDICATED = "DEDICATED"
    OWN = "OWN"
    SHARED = "SHARED"


class SenderStatus(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PROVISIONING = "PROVISIONING"
    READY = "READY"
    REJECTED = "REJECTED"
    RELEASED = "RELEASED"
    UNDER_REVIEW = "UNDER_REVIEW"


class UseCase(StrEnum):
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    MARKETING = "MARKETING"
    NOTIFICATIONS = "NOTIFICATIONS"
    OTHER = "OTHER"
    TWO_FACTOR_AUTHENTICATION = "TWO_FACTOR_AUTHENTICATION"


class UseFor(StrEnum):
    MMS = "MMS"
    SMS = "SMS"
    SMS_MMS = "SMS_MMS"


class Sender(Model):
    cancelled: bool = False
    capabilities: tuple[Channel, ...]
    country: str
    created_at: Rfc3339
    kind: SenderKind
    monthly_price_micro: Micro | None = None
    nickname: str | None = None
    provider_identity: str | None = None
    renewal_attempt: int = 0
    renews_at: Rfc3339 | None = None
    sender_id: str
    status: SenderStatus
    use_case: UseCase | None = None
    value: str
    verified_at: Rfc3339 | None = None


def display_of(sender: Sender) -> str:
    match sender.kind:
        case SenderKind.ALPHA | SenderKind.DEDICATED:
            return sender.value
        case SenderKind.OWN:
            return f"{sender.value} (Own Number)"
        case SenderKind.SHARED:
            return SHARED_DISPLAY
        case _ as unreachable:
            assert_never(unreachable)


def status_label_of(status: SenderStatus) -> str:
    match status:
        case SenderStatus.PENDING_VERIFICATION:
            return "Pending verification"
        case SenderStatus.PROVISIONING:
            return "Provisioning"
        case SenderStatus.READY:
            return "Ready to use"
        case SenderStatus.REJECTED:
            return "Rejected"
        case SenderStatus.RELEASED:
            return "Released"
        case SenderStatus.UNDER_REVIEW:
            return "Under review"
        case _ as unreachable:
            assert_never(unreachable)


class SenderView(Sender):
    display: str
    status_label: str

    @classmethod
    def of(cls, sender: Sender) -> Self:
        return cls(
            **sender.model_dump(by_alias=False),
            display=display_of(sender),
            status_label=status_label_of(sender.status),
        )


class SmartSender(Model):
    channel: Channel = Channel.SMS
    country: str
    sender_id: str


class AlphaTagRequest(Model):
    country: str
    tag: str
    use_case: UseCase


class OwnNumberRequest(Model):
    nickname: str | None = None
    number: str


class SmartSenderRequest(Model):
    sender_id: str


class VerificationRequest(Model):
    code: str


class CatalogueNumber(Model):
    capabilities: tuple[Channel, ...]
    country: str
    monthly_price_micro: Micro
    value: str


class NumberCataloguePage(Model):
    numbers: list[CatalogueNumber]
    page: int
    total_pages: int


class NumberSearchQuery(Model):
    contains: str = ""
    country: str
    page: int = 1
    use_for: UseFor | None = None


class SendersView(Model):
    senders: dict[SenderKind, list[SenderView]]
    smart: dict[str, str]

    @classmethod
    def of(cls, senders: Iterable[Sender], smarts: Iterable[SmartSender]) -> Self:
        groups: dict[SenderKind, list[SenderView]] = {kind: [] for kind in SenderKind}
        for sender in senders:
            groups[sender.kind].append(SenderView.of(sender))

        return cls(senders=groups, smart={smart.country: smart.sender_id for smart in smarts})
