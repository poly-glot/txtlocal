from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.slices.automation.model import (
    DeliveryReportRule,
    EmailSender,
    InboundRule,
    Website,
    WebsiteStatus,
)
from txtlocal.slices.campaigns.model import QuickSendResult

if TYPE_CHECKING:
    from txtlocal.shared.errors import AppError
    from txtlocal.slices.contacts.model import ContactInput, ContactList
    from txtlocal.slices.identity.model import Principal
    from txtlocal.slices.messaging.model import MessageRow, QuickSendRequest

ACCOUNT = "account-1"
DESTINATION = "+447984390718"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
PEER = "+447411972333"


@dataclass(frozen=True, slots=True)
class FakeInbound:
    body: str
    destination: str = DESTINATION
    inbound_message_id: str = "inbound-1"
    peer: str = PEER
    previous_published_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class FakeSender:
    sender_id: str
    status: str = "READY"
    value: str = ""


@dataclass
class InMemoryAutomationRepo:
    delivery_rules: dict[tuple[str, str], DeliveryReportRule] = field(default_factory=dict)
    email_senders: dict[tuple[str, str], EmailSender] = field(default_factory=dict)
    rules: dict[tuple[str, str], InboundRule] = field(default_factory=dict)
    websites: dict[tuple[str, str], Website] = field(default_factory=dict)

    async def approve_website(self, account_id: str, domain: str) -> bool:
        current = self.websites.get((account_id, domain))
        if current is None:
            return False

        self.websites[(account_id, domain)] = current.model_copy(
            update={"status": WebsiteStatus.APPROVED}
        )
        return True

    async def delete_delivery_rule(self, account_id: str, rule_id: str) -> bool:
        return self.delivery_rules.pop((account_id, rule_id), None) is not None

    async def delete_email_sender(self, account_id: str, email: str) -> bool:
        return self.email_senders.pop((account_id, email), None) is not None

    async def delete_rule(self, account_id: str, rule_id: str) -> bool:
        return self.rules.pop((account_id, rule_id), None) is not None

    async def email_senders_by_address(self, email: str) -> list[tuple[str, EmailSender]]:
        return [
            (owner, sender)
            for (owner, _), sender in self.email_senders.items()
            if sender.email == email
        ]

    async def get_delivery_rule(self, account_id: str, rule_id: str) -> DeliveryReportRule | None:
        return self.delivery_rules.get((account_id, rule_id))

    async def get_email_sender(self, account_id: str, email: str) -> EmailSender | None:
        return self.email_senders.get((account_id, email))

    async def get_rule(self, account_id: str, rule_id: str) -> InboundRule | None:
        return self.rules.get((account_id, rule_id))

    async def get_website(self, account_id: str, domain: str) -> Website | None:
        return self.websites.get((account_id, domain))

    async def increment_vote(self, account_id: str, rule_id: str, keyword: str) -> bool:
        current = self.rules.get((account_id, rule_id))
        if current is None:
            return False

        votes = dict(current.votes)
        votes[keyword] = votes.get(keyword, 0) + 1
        self.rules[(account_id, rule_id)] = current.model_copy(update={"votes": votes})
        return True

    async def list_delivery_rules(self, account_id: str) -> list[DeliveryReportRule]:
        held = [rule for (owner, _), rule in self.delivery_rules.items() if owner == account_id]
        return sorted(held, key=lambda rule: rule.rule_id)

    async def list_email_senders(self, account_id: str) -> list[EmailSender]:
        held = [sender for (owner, _), sender in self.email_senders.items() if owner == account_id]
        return sorted(held, key=lambda sender: sender.email)

    async def list_rules(self, account_id: str) -> list[InboundRule]:
        held = [rule for (owner, _), rule in self.rules.items() if owner == account_id]
        return sorted(held, key=lambda rule: rule.rule_id)

    async def list_websites(self, account_id: str) -> list[Website]:
        held = [website for (owner, _), website in self.websites.items() if owner == account_id]
        return sorted(held, key=lambda website: website.domain)

    async def put_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> None:
        self.delivery_rules[(account_id, rule.rule_id)] = rule

    async def put_email_sender_if_absent(self, account_id: str, sender: EmailSender) -> bool:
        key = (account_id, sender.email)
        if key in self.email_senders:
            return False

        self.email_senders[key] = sender
        return True

    async def put_rule(self, account_id: str, rule: InboundRule) -> None:
        self.rules[(account_id, rule.rule_id)] = rule

    async def put_website_if_absent(self, account_id: str, website: Website) -> bool:
        key = (account_id, website.domain)
        if key in self.websites:
            return False

        self.websites[key] = website
        return True

    async def reject_website(self, account_id: str, domain: str, reason: str) -> bool:
        current = self.websites.get((account_id, domain))
        if current is None:
            return False

        self.websites[(account_id, domain)] = current.model_copy(
            update={"rejected_reason": reason, "status": WebsiteStatus.REJECTED}
        )
        return True

    async def replace_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> bool:
        key = (account_id, rule.rule_id)
        if key not in self.delivery_rules:
            return False

        self.delivery_rules[key] = rule
        return True

    async def replace_rule(self, account_id: str, rule: InboundRule) -> bool:
        key = (account_id, rule.rule_id)
        if key not in self.rules:
            return False

        self.rules[key] = rule
        return True

    async def websites_under_review(self) -> list[tuple[str, Website]]:
        return [
            (owner, website)
            for (owner, _), website in self.websites.items()
            if website.status is WebsiteStatus.UNDER_REVIEW
        ]


@dataclass
class RecordingContacts:
    added: list[tuple[str, str, ContactInput]] = field(default_factory=list)
    list_rows: dict[str, list[ContactList]] = field(default_factory=dict)

    async def add_contact(self, account_id: str, list_id: str, request: ContactInput) -> object:
        self.added.append((account_id, list_id, request))
        return object()

    async def lists(self, account_id: str, _q: str | None) -> list[ContactList]:
        return self.list_rows.get(account_id, [])


@dataclass
class RecordingCampaigns:
    calls: list[tuple[Principal, QuickSendRequest, datetime]] = field(default_factory=list)
    error: AppError | None = None
    recipients: int = 1

    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult:
        self.calls.append((principal, request, now))
        if self.error is not None:
            raise self.error
        return QuickSendResult(
            campaign_id="campaign-1", cost_micro=0, recipients=self.recipients, refused=[]
        )


@dataclass
class StubMessages:
    rows: dict[tuple[str, str], MessageRow] = field(default_factory=dict)

    async def detail(self, account_id: str, message_id: str) -> MessageRow:
        return self.rows[(account_id, message_id)]


@dataclass
class StubSenders:
    rows: dict[str, list[FakeSender]] = field(default_factory=dict)

    async def senders(self, account_id: str) -> list[FakeSender]:
        return self.rows.get(account_id, [])


@dataclass
class RecordingEmail:
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))
