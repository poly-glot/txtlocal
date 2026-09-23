import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import Field

from txtlocal.shared.model import Model, Rfc3339
from txtlocal.slices.messaging.model import Direction

SECRET_BYTES = 30


class RuleAction(StrEnum):
    AUTO_REPLY = "AUTO_REPLY"
    EMAIL_FIXED = "EMAIL_FIXED"
    EMAIL_USER = "EMAIL_USER"
    GROUP_SMS = "GROUP_SMS"
    MOVE_CONTACT = "MOVE_CONTACT"
    POLL = "POLL"
    SEND_TO_MESSENGER = "SEND_TO_MESSENGER"
    SMS = "SMS"
    URL = "URL"


class MatchKind(StrEnum):
    ANY = "ANY"
    KEYWORD = "KEYWORD"


class WebsiteStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"


class DeliveryEventsFilter(StrEnum):
    ALL = "ALL"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class Outcome(StrEnum):
    ADDED = "ADDED"
    EMAIL_UNAVAILABLE = "EMAIL_UNAVAILABLE"
    FAILED = "FAILED"
    INCREMENTED = "INCREMENTED"
    NOOP = "NOOP"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    QUEUED = "QUEUED"


class InboundRule(Model):
    action: RuleAction
    action_address: str | None = None
    backup_email: str | None = None
    created_at: Rfc3339
    enabled: bool = True
    keyword: str | None = None
    match_kind: MatchKind = MatchKind.ANY
    name: str
    number: str | None = None
    rule_id: str
    secret: str | None = None
    votes: dict[str, int] = Field(default_factory=dict)


class InboundRuleRequest(Model):
    action: RuleAction
    action_address: str | None = None
    backup_email: str | None = None
    enabled: bool = True
    keyword: str | None = None
    match_kind: MatchKind = MatchKind.ANY
    name: str
    number: str | None = None


class DeliveryReportRule(Model):
    created_at: Rfc3339
    enabled: bool = True
    events: DeliveryEventsFilter = DeliveryEventsFilter.ALL
    name: str
    rule_id: str
    secret: str
    url: str


class DeliveryReportRuleView(Model):
    created_at: Rfc3339
    enabled: bool
    events: DeliveryEventsFilter
    name: str
    rule_id: str
    url: str

    @classmethod
    def of(cls, rule: DeliveryReportRule) -> Self:
        return cls(
            created_at=rule.created_at,
            enabled=rule.enabled,
            events=rule.events,
            name=rule.name,
            rule_id=rule.rule_id,
            url=rule.url,
        )


class DeliveryReportRuleRequest(Model):
    enabled: bool = True
    events: DeliveryEventsFilter = DeliveryEventsFilter.ALL
    name: str
    url: str


class DeliveryReportRuleCreated(Model):
    rule: DeliveryReportRuleView
    secret: str


class Website(Model):
    domain: str
    registered_at: Rfc3339
    rejected_reason: str | None = None
    status: WebsiteStatus


class WebsitesRequest(Model):
    domains: list[str]


class WebsiteRejectionRequest(Model):
    reason: str


class EmailSender(Model):
    email: str
    sender_id: str | None = None
    user_id: str


class EmailSenderRequest(Model):
    email: str
    sender_id: str
    user_id: str


class DemoInboundEmailRequest(Model):
    body: str
    numbers: list[str]
    sender_email: str


class WebhookPayload(Model):
    account_id: str
    body: str
    custom_string: str | None = None
    direction: Direction
    event: str
    failure_reason: str | None = None
    from_: str = Field(alias="from")
    keyword: str | None = None
    message_id: str
    occurred_at: Rfc3339
    previous_message_id: str | None = None
    price: str | None = None
    rule_id: str | None = None
    to: str


class WebhookJob(Model):
    body: str
    event: str
    secret: str
    url: str


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    action: RuleAction
    outcome: Outcome
    rule_id: str


def new_secret() -> str:
    return secrets.token_urlsafe(SECRET_BYTES)


def secret_for(action: RuleAction, existing: str | None) -> str | None:
    if existing is not None:
        return existing
    return new_secret() if action is RuleAction.URL else None
