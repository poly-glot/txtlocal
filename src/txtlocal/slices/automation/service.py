import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from re import compile as re_compile
from typing import TYPE_CHECKING, Protocol, assert_never
from urllib.parse import urlsplit

from txtlocal.shared import telemetry
from txtlocal.shared.bus import Bus, Message, Queue
from txtlocal.shared.errors import AppError, BadRequest, Conflict, Internal, NotFound
from txtlocal.shared.money import format_decimal
from txtlocal.slices.automation.model import (
    ActionOutcome,
    DeliveryEventsFilter,
    DeliveryReportRule,
    DeliveryReportRuleCreated,
    DeliveryReportRuleRequest,
    DeliveryReportRuleView,
    EmailSender,
    EmailSenderRequest,
    InboundRule,
    InboundRuleRequest,
    MatchKind,
    Outcome,
    RuleAction,
    WebhookJob,
    WebhookPayload,
    Website,
    WebsiteRejectionRequest,
    WebsitesRequest,
    WebsiteStatus,
    new_secret,
    secret_for,
)
from txtlocal.slices.contacts.model import ContactInput
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.messaging.model import (
    Direction,
    MessageStatus,
    MessageType,
    QuickSendRequest,
    Transition,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.automation.repo import AutomationRepo
    from txtlocal.slices.campaigns.model import QuickSendResult
    from txtlocal.slices.messaging.model import MessageRow

DELIVERED_EVENT = "message.delivered"
EMAIL_ALREADY_ADDED = "This email address is already an allowed address"
EMAIL_SENDER_NOT_FOUND = "Allowed address not found"
EMAIL_SMS_USERNAME = "email-sms"
FAILED_EVENT = "message.failed"
INBOUND_EVENT = "message.received"
INVALID_DOMAIN = "Enter a valid website domain"
INVALID_EMAIL = "Enter a valid email address"
MAX_REJECTION_REASON = 500
MAX_RULE_NAME = 100
MAX_WEBSITES_PER_SUBMISSION = 3
OPT_OUT_KIND = "OPT_OUT"
DEFAULT_RULE_NAME = "Default rule"
OPT_OUT_RULE_NAME = "Opt-out contact"
READY_STATUS = "READY"
REASON_LENGTH = "Enter a reason of 1 to 500 characters"
REVIEW_PERIOD = timedelta(hours=24)
RULE_NAME_LENGTH = "Enter a rule name of 1 to 100 characters"
RULE_NOT_FOUND = "Rule not found"
DELIVERY_RULE_NOT_FOUND = "Delivery report rule not found"
SENDER_NOT_READY = "Choose a sender that is ready to use"
SENT_EVENT = "message.sent"
SEND_TO_MESSENGER_NAME = "Send to messenger"
STOP_KEYWORD = "stop"
TEST_BODY = "This is a test message"
TEST_FROM = "+447900000000"
TEST_MESSAGE_ID = "msg_test"
TEST_PRICE = "0.0427"
TEST_TO = "+447900000001"
URL_MUST_BE_HTTPS = "Enter a URL that starts with https://"
WEBSITE_NOT_FOUND = "Website not found"

HOSTNAME_RE = re_compile(r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$")


def already_registered(domain: str) -> str:
    return f"{domain} is already registered"


class InboundMessage(Protocol):
    @property
    def body(self) -> str: ...

    @property
    def destination(self) -> str: ...

    @property
    def inbound_message_id(self) -> str: ...

    @property
    def peer(self) -> str: ...

    @property
    def previous_published_message_id(self) -> str | None: ...


class InboundEmail(Protocol):
    @property
    def body(self) -> str: ...

    @property
    def numbers(self) -> Sequence[str]: ...

    @property
    def sender_email(self) -> str: ...


class ListRef(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def list_id(self) -> str: ...


class Contacts(Protocol):
    async def add_contact(self, account_id: str, list_id: str, request: ContactInput) -> object: ...

    async def lists(self, account_id: str, q: str | None) -> Iterable[ListRef]: ...


class QuickSend(Protocol):
    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult: ...


class MessageLookup(Protocol):
    async def detail(self, account_id: str, message_id: str) -> MessageRow: ...


class SenderRef(Protocol):
    @property
    def sender_id(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def value(self) -> str: ...


class SenderLookup(Protocol):
    async def senders(self, account_id: str) -> Iterable[SenderRef]: ...


class Email(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class LoggingEmail:
    async def send(self, to: str, subject: str, body: str) -> None:
        telemetry.log(
            "email_unavailable",
            body_length=len(body),
            subject_length=len(subject),
            to_present=bool(to),
        )


def new_id() -> str:
    return str(uuid.uuid7())


def system_principal(account_id: str) -> Principal:
    return Principal(
        account_id=account_id, role=Role.OWNER, user_id="system", username="automation"
    )


def email_sender_principal(account_id: str, user_id: str) -> Principal:
    return Principal(
        account_id=account_id, role=Role.SUB, user_id=user_id, username=EMAIL_SMS_USERNAME
    )


def checked_rule_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= MAX_RULE_NAME:
        raise BadRequest(RULE_NAME_LENGTH)
    return name


def checked_https_url(value: str) -> str:
    url = value.strip()
    if not url.lower().startswith("https://"):
        raise BadRequest(URL_MUST_BE_HTTPS)
    return url


def checked_email(value: str) -> str:
    email = value.strip()
    if not email or "@" not in email:
        raise BadRequest(INVALID_EMAIL)
    return email


def checked_reason(value: str) -> str:
    reason = value.strip()
    if not 1 <= len(reason) <= MAX_REJECTION_REASON:
        raise BadRequest(REASON_LENGTH)
    return reason


def normalised_domain(raw: str) -> str:
    text = raw.strip()
    if "//" not in text:
        text = f"//{text}"

    host = (urlsplit(text).hostname or "").rstrip(".").lower()
    if not host or not HOSTNAME_RE.fullmatch(host):
        raise BadRequest(INVALID_DOMAIN)
    return host


def sender_ready(senders: Iterable[SenderRef], sender_id: str) -> bool:
    return any(
        sender.sender_id == sender_id and sender.status == READY_STATUS for sender in senders
    )


def opt_out_list_id_of(lists: Iterable[ListRef]) -> str | None:
    return next((one.list_id for one in lists if one.kind == OPT_OUT_KIND), None)


def default_rules(now: datetime, opt_out_list_id: str | None) -> list[InboundRule]:
    rules = [
        InboundRule(
            action=RuleAction.SEND_TO_MESSENGER,
            created_at=now,
            keyword=STOP_KEYWORD,
            match_kind=MatchKind.KEYWORD,
            name=SEND_TO_MESSENGER_NAME,
            rule_id=new_id(),
        )
    ]
    if opt_out_list_id is not None:
        rules.append(
            InboundRule(
                action=RuleAction.MOVE_CONTACT,
                action_address=opt_out_list_id,
                created_at=now,
                keyword=STOP_KEYWORD,
                match_kind=MatchKind.KEYWORD,
                name=OPT_OUT_RULE_NAME,
                rule_id=new_id(),
            )
        )
    rules.append(
        InboundRule(
            action=RuleAction.EMAIL_USER, created_at=now, name=DEFAULT_RULE_NAME, rule_id=new_id()
        )
    )
    return rules


def first_word_of(body: str) -> str:
    words = body.split()
    return words[0] if words else ""


def number_matches(rule: InboundRule, destination: str) -> bool:
    return rule.number is None or rule.number == destination


def keyword_matches(rule: InboundRule, first_word: str) -> bool:
    if rule.match_kind is MatchKind.ANY:
        return True
    return rule.keyword is not None and rule.keyword.casefold() == first_word.casefold()


def rule_matches(rule: InboundRule, destination: str, first_word: str) -> bool:
    return number_matches(rule, destination) and keyword_matches(rule, first_word)


def email_subject_for(peer: str) -> str:
    return f"SMS received from {peer}"


def quick_send_request_for(
    rule: InboundRule, inbound: InboundMessage, sender_id: str | None
) -> QuickSendRequest | None:
    if rule.action is RuleAction.AUTO_REPLY:
        return QuickSendRequest(
            body=rule.action_address or "",
            message_type=MessageType.TRANSACTIONAL,
            sender_id=sender_id,
            to=[inbound.peer],
        )

    if rule.action is RuleAction.SMS:
        if rule.action_address is None:
            return None
        return QuickSendRequest(
            body=inbound.body,
            message_type=MessageType.TRANSACTIONAL,
            sender_id=sender_id,
            to=[rule.action_address],
        )

    if rule.action is RuleAction.GROUP_SMS:
        if rule.action_address is None:
            return None
        return QuickSendRequest(body=inbound.body, list_ids=[rule.action_address], to=[])

    return None


def webhook_event_of(status: MessageStatus) -> str | None:
    match status:
        case MessageStatus.DELIVERED:
            return DELIVERED_EVENT
        case MessageStatus.FAILED:
            return FAILED_EVENT
        case MessageStatus.SENT:
            return SENT_EVENT
        case MessageStatus.QUEUED | MessageStatus.RECEIVED:
            return None
        case _:
            assert_never(status)


def covers(events: DeliveryEventsFilter, status: MessageStatus) -> bool:
    match events:
        case DeliveryEventsFilter.ALL:
            return True
        case DeliveryEventsFilter.DELIVERED:
            return status is MessageStatus.DELIVERED
        case DeliveryEventsFilter.FAILED:
            return status is MessageStatus.FAILED
        case _:
            assert_never(events)


def delivery_payload(row: MessageRow, event: str, now: datetime) -> WebhookPayload:
    return WebhookPayload(
        account_id=row.account_id,
        body=row.body,
        direction=Direction.OUT,
        event=event,
        failure_reason=row.failure_reason,
        from_=row.from_,
        message_id=row.message_id,
        occurred_at=now,
        price=format_decimal(row.price_micro),
        to=row.to,
    )


def inbound_payload(
    account_id: str, inbound: InboundMessage, rule_id: str, first_word: str, now: datetime
) -> WebhookPayload:
    return WebhookPayload(
        account_id=account_id,
        body=inbound.body,
        direction=Direction.IN,
        event=INBOUND_EVENT,
        from_=inbound.peer,
        keyword=first_word.upper(),
        message_id=inbound.inbound_message_id,
        occurred_at=now,
        previous_message_id=inbound.previous_published_message_id,
        rule_id=rule_id,
        to=inbound.destination,
    )


def sample_payload(account_id: str, now: datetime) -> WebhookPayload:
    return WebhookPayload(
        account_id=account_id,
        body=TEST_BODY,
        direction=Direction.OUT,
        event=DELIVERED_EVENT,
        from_=TEST_FROM,
        message_id=TEST_MESSAGE_ID,
        occurred_at=now,
        price=TEST_PRICE,
        to=TEST_TO,
    )


@dataclass(frozen=True, slots=True)
class AutomationService:
    bus: Bus
    campaigns: QuickSend
    clock: Clock
    contacts: Contacts
    email: Email
    messages: MessageLookup
    repo: AutomationRepo
    senders: SenderLookup

    async def provision_defaults(self, account_id: str, now: datetime) -> None:
        if await self.repo.list_rules(account_id):
            return

        opt_out_list_id = opt_out_list_id_of(await self.contacts.lists(account_id, None))
        if opt_out_list_id is None:
            telemetry.log(
                "automation_provision_incomplete",
                account_id=account_id,
                level=telemetry.WARNING,
                reason="opt_out_list_missing",
            )

        for rule in default_rules(now, opt_out_list_id):
            await self.repo.put_rule(account_id, rule)

    async def run_inbound(
        self, account_id: str, inbound: InboundMessage, now: datetime
    ) -> list[ActionOutcome]:
        first_word = first_word_of(inbound.body)
        matched = [
            rule
            for rule in await self.repo.list_rules(account_id)
            if rule.enabled and rule_matches(rule, inbound.destination, first_word)
        ]

        return [
            await self._safe_run(account_id, rule, inbound, first_word, now) for rule in matched
        ]

    async def on_delivery(self, transition: Transition, now: datetime) -> None:
        event = webhook_event_of(transition.status)
        if event is None:
            return

        rules = await self.repo.list_delivery_rules(transition.account_id)
        covering = [
            rule for rule in rules if rule.enabled and covers(rule.events, transition.status)
        ]
        if not covering:
            return

        row = await self.messages.detail(transition.account_id, transition.message_id)
        body = delivery_payload(row, event, now).model_dump_json()
        jobs = [
            Message(
                body=WebhookJob(
                    body=body, event=event, secret=rule.secret, url=rule.url
                ).model_dump_json()
            )
            for rule in covering
        ]
        await self.bus.send(Queue.WEBHOOKS, jobs)

    async def inbound_rules(self, account_id: str) -> list[InboundRule]:
        return await self.repo.list_rules(account_id)

    async def create_inbound_rule(
        self, account_id: str, request: InboundRuleRequest
    ) -> InboundRule:
        rule = InboundRule(
            action=request.action,
            action_address=request.action_address,
            backup_email=request.backup_email,
            created_at=self.clock(),
            enabled=request.enabled,
            keyword=request.keyword,
            match_kind=request.match_kind,
            name=checked_rule_name(request.name),
            number=request.number,
            rule_id=new_id(),
            secret=secret_for(request.action, None),
        )
        await self.repo.put_rule(account_id, rule)
        return rule

    async def update_inbound_rule(
        self, account_id: str, rule_id: str, request: InboundRuleRequest
    ) -> InboundRule:
        existing = await self.repo.get_rule(account_id, rule_id)
        if existing is None:
            raise NotFound(RULE_NOT_FOUND)

        updated = existing.model_copy(
            update={
                "action": request.action,
                "action_address": request.action_address,
                "backup_email": request.backup_email,
                "enabled": request.enabled,
                "keyword": request.keyword,
                "match_kind": request.match_kind,
                "name": checked_rule_name(request.name),
                "number": request.number,
                "secret": secret_for(request.action, existing.secret),
            }
        )
        if not await self.repo.replace_rule(account_id, updated):
            raise NotFound(RULE_NOT_FOUND)
        return updated

    async def delete_inbound_rule(self, account_id: str, rule_id: str) -> None:
        if not await self.repo.delete_rule(account_id, rule_id):
            raise NotFound(RULE_NOT_FOUND)

    async def delivery_rules(self, account_id: str) -> list[DeliveryReportRuleView]:
        rules = await self.repo.list_delivery_rules(account_id)
        return [DeliveryReportRuleView.of(rule) for rule in rules]

    async def create_delivery_rule(
        self, account_id: str, request: DeliveryReportRuleRequest
    ) -> DeliveryReportRuleCreated:
        rule = DeliveryReportRule(
            created_at=self.clock(),
            enabled=request.enabled,
            events=request.events,
            name=checked_rule_name(request.name),
            rule_id=new_id(),
            secret=new_secret(),
            url=checked_https_url(request.url),
        )
        await self.repo.put_delivery_rule(account_id, rule)
        return DeliveryReportRuleCreated(rule=DeliveryReportRuleView.of(rule), secret=rule.secret)

    async def update_delivery_rule(
        self, account_id: str, rule_id: str, request: DeliveryReportRuleRequest
    ) -> DeliveryReportRuleView:
        existing = await self.repo.get_delivery_rule(account_id, rule_id)
        if existing is None:
            raise NotFound(DELIVERY_RULE_NOT_FOUND)

        updated = existing.model_copy(
            update={
                "enabled": request.enabled,
                "events": request.events,
                "name": checked_rule_name(request.name),
                "url": checked_https_url(request.url),
            }
        )
        if not await self.repo.replace_delivery_rule(account_id, updated):
            raise NotFound(DELIVERY_RULE_NOT_FOUND)
        return DeliveryReportRuleView.of(updated)

    async def delete_delivery_rule(self, account_id: str, rule_id: str) -> None:
        if not await self.repo.delete_delivery_rule(account_id, rule_id):
            raise NotFound(DELIVERY_RULE_NOT_FOUND)

    async def test_webhook(self, account_id: str, rule_id: str) -> None:
        rule = await self.repo.get_delivery_rule(account_id, rule_id)
        if rule is None:
            raise NotFound(DELIVERY_RULE_NOT_FOUND)

        body = sample_payload(account_id, self.clock()).model_dump_json()
        job = WebhookJob(body=body, event=DELIVERED_EVENT, secret=rule.secret, url=rule.url)
        await self.bus.send(Queue.WEBHOOKS, [Message(body=job.model_dump_json())])

    async def websites(self, account_id: str) -> list[Website]:
        return await self.repo.list_websites(account_id)

    async def register_websites(self, account_id: str, request: WebsitesRequest) -> list[Website]:
        if len(request.domains) > MAX_WEBSITES_PER_SUBMISSION:
            raise BadRequest(
                f"You can register up to {MAX_WEBSITES_PER_SUBMISSION} websites at once"
            )

        now = self.clock()
        existing = {website.domain for website in await self.repo.list_websites(account_id)}
        created: list[Website] = []
        for raw in request.domains:
            domain = normalised_domain(raw)
            if domain in existing:
                raise Conflict(already_registered(domain))
            existing.add(domain)
            created.append(
                Website(domain=domain, registered_at=now, status=WebsiteStatus.UNDER_REVIEW)
            )

        for website in created:
            if not await self.repo.put_website_if_absent(account_id, website):
                raise Internal(f"website {website.domain} already exists")

        return created

    async def approve_due_websites(self, now: datetime) -> int:
        cutoff = now - REVIEW_PERIOD
        due = [
            (account_id, website)
            for account_id, website in await self.repo.websites_under_review()
            if website.registered_at <= cutoff
        ]

        approved = 0
        for account_id, website in due:
            if await self.repo.approve_website(account_id, website.domain):
                approved += 1
        return approved

    async def approve_website_now(self, account_id: str, domain: str) -> Website:
        existing = await self.repo.get_website(account_id, domain)
        if existing is None:
            raise NotFound(WEBSITE_NOT_FOUND)

        updated = existing.model_copy(update={"status": WebsiteStatus.APPROVED})
        if not await self.repo.approve_website(account_id, domain):
            raise NotFound(WEBSITE_NOT_FOUND)
        return updated

    async def reject_website(
        self, account_id: str, domain: str, request: WebsiteRejectionRequest
    ) -> Website:
        existing = await self.repo.get_website(account_id, domain)
        if existing is None:
            raise NotFound(WEBSITE_NOT_FOUND)

        reason = checked_reason(request.reason)
        updated = existing.model_copy(
            update={"rejected_reason": reason, "status": WebsiteStatus.REJECTED}
        )
        if not await self.repo.reject_website(account_id, domain, reason):
            raise NotFound(WEBSITE_NOT_FOUND)
        return updated

    async def email_senders(self, account_id: str) -> list[EmailSender]:
        return await self.repo.list_email_senders(account_id)

    async def add_email_sender(self, account_id: str, request: EmailSenderRequest) -> EmailSender:
        email = checked_email(request.email)
        if await self.repo.get_email_sender(account_id, email) is not None:
            raise Conflict(EMAIL_ALREADY_ADDED)
        if not sender_ready(await self.senders.senders(account_id), request.sender_id):
            raise BadRequest(SENDER_NOT_READY)

        sender = EmailSender(email=email, sender_id=request.sender_id, user_id=request.user_id)
        if not await self.repo.put_email_sender_if_absent(account_id, sender):
            raise Internal(f"email sender {email} already exists")
        return sender

    async def remove_email_sender(self, account_id: str, email: str) -> None:
        if not await self.repo.delete_email_sender(account_id, email):
            raise NotFound(EMAIL_SENDER_NOT_FOUND)

    async def handle_inbound_email(self, email: InboundEmail, now: datetime) -> None:
        if not email.numbers:
            telemetry.log("email_inbound", outcome="no_destination")
            return

        matches = await self.repo.email_senders_by_address(email.sender_email)
        if not matches:
            telemetry.log("email_inbound", outcome="sender_not_allowed")
            return

        for account_id, sender in matches:
            await self._send_inbound_email(account_id, sender, email, now)

    async def _safe_run(
        self,
        account_id: str,
        rule: InboundRule,
        inbound: InboundMessage,
        first_word: str,
        now: datetime,
    ) -> ActionOutcome:
        try:
            return await self._run_action(account_id, rule, inbound, first_word, now)
        except AppError as error:
            telemetry.log(
                "automation_action_failed",
                account_id=account_id,
                action=rule.action,
                code=error.code,
                level=telemetry.WARNING,
                rule_id=rule.rule_id,
            )
            return ActionOutcome(action=rule.action, outcome=Outcome.FAILED, rule_id=rule.rule_id)

    async def _run_action(
        self,
        account_id: str,
        rule: InboundRule,
        inbound: InboundMessage,
        first_word: str,
        now: datetime,
    ) -> ActionOutcome:
        match rule.action:
            case RuleAction.AUTO_REPLY | RuleAction.SMS | RuleAction.GROUP_SMS:
                return await self._send(account_id, rule, inbound, now)
            case RuleAction.EMAIL_FIXED | RuleAction.EMAIL_USER:
                return await self._email(rule, inbound)
            case RuleAction.MOVE_CONTACT:
                return await self._move_contact(account_id, rule, inbound)
            case RuleAction.POLL:
                return await self._poll(account_id, rule, first_word)
            case RuleAction.SEND_TO_MESSENGER:
                return ActionOutcome(action=rule.action, outcome=Outcome.NOOP, rule_id=rule.rule_id)
            case RuleAction.URL:
                return await self._url(account_id, rule, inbound, first_word, now)
            case _ as unreachable:
                assert_never(unreachable)

    async def _send(
        self, account_id: str, rule: InboundRule, inbound: InboundMessage, now: datetime
    ) -> ActionOutcome:
        sender_id = await self._sender_for(account_id, inbound.destination)
        request = quick_send_request_for(rule, inbound, sender_id)
        if request is None:
            return ActionOutcome(
                action=rule.action, outcome=Outcome.NOT_CONFIGURED, rule_id=rule.rule_id
            )

        result = await self.campaigns.send_quick(system_principal(account_id), request, now)
        outcome = Outcome.QUEUED if result.recipients > 0 else Outcome.FAILED
        return ActionOutcome(action=rule.action, outcome=outcome, rule_id=rule.rule_id)

    async def _email(self, rule: InboundRule, inbound: InboundMessage) -> ActionOutcome:
        to = rule.action_address if rule.action is RuleAction.EMAIL_FIXED else rule.backup_email
        await self.email.send(
            to=to or "", subject=email_subject_for(inbound.peer), body=inbound.body
        )
        return ActionOutcome(
            action=rule.action, outcome=Outcome.EMAIL_UNAVAILABLE, rule_id=rule.rule_id
        )

    async def _move_contact(
        self, account_id: str, rule: InboundRule, inbound: InboundMessage
    ) -> ActionOutcome:
        if rule.action_address is None:
            return ActionOutcome(
                action=rule.action, outcome=Outcome.NOT_CONFIGURED, rule_id=rule.rule_id
            )

        await self.contacts.add_contact(
            account_id, rule.action_address, ContactInput(mobile=inbound.peer)
        )
        return ActionOutcome(action=rule.action, outcome=Outcome.ADDED, rule_id=rule.rule_id)

    async def _poll(self, account_id: str, rule: InboundRule, first_word: str) -> ActionOutcome:
        won = await self.repo.increment_vote(account_id, rule.rule_id, first_word.upper())
        outcome = Outcome.INCREMENTED if won else Outcome.FAILED
        return ActionOutcome(action=rule.action, outcome=outcome, rule_id=rule.rule_id)

    async def _url(
        self,
        account_id: str,
        rule: InboundRule,
        inbound: InboundMessage,
        first_word: str,
        now: datetime,
    ) -> ActionOutcome:
        if rule.action_address is None or rule.secret is None:
            return ActionOutcome(
                action=rule.action, outcome=Outcome.NOT_CONFIGURED, rule_id=rule.rule_id
            )

        body = inbound_payload(account_id, inbound, rule.rule_id, first_word, now).model_dump_json()
        job = WebhookJob(
            body=body, event=INBOUND_EVENT, secret=rule.secret, url=rule.action_address
        )
        await self.bus.send(Queue.WEBHOOKS, [Message(body=job.model_dump_json())])
        return ActionOutcome(action=rule.action, outcome=Outcome.QUEUED, rule_id=rule.rule_id)

    async def _sender_for(self, account_id: str, destination: str) -> str | None:
        senders = await self.senders.senders(account_id)
        return next((sender.sender_id for sender in senders if sender.value == destination), None)

    async def _send_inbound_email(
        self, account_id: str, sender: EmailSender, email: InboundEmail, now: datetime
    ) -> None:
        principal = email_sender_principal(account_id, sender.user_id)
        request = QuickSendRequest(
            body=email.body,
            message_type=MessageType.TRANSACTIONAL,
            sender_id=sender.sender_id,
            to=list(email.numbers),
        )
        try:
            result = await self.campaigns.send_quick(principal, request, now)
        except AppError as error:
            telemetry.log(
                "email_inbound",
                account_id=account_id,
                code=error.code,
                level=telemetry.WARNING,
                outcome="failed",
            )
            return

        telemetry.log(
            "email_inbound",
            account_id=account_id,
            outcome="queued" if result.recipients > 0 else "failed",
            recipients=result.recipients,
        )
