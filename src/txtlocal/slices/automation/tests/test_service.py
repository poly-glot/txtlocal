import json
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from txtlocal.shared.bus import Queue
from txtlocal.shared.errors import BadRequest, Conflict, NotFound, PaymentRequired
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.slices.automation.model import (
    ActionOutcome,
    DeliveryEventsFilter,
    DeliveryReportRuleRequest,
    DemoInboundEmailRequest,
    EmailSender,
    EmailSenderRequest,
    InboundRule,
    InboundRuleRequest,
    MatchKind,
    Outcome,
    RuleAction,
    WebhookJob,
    Website,
    WebsiteRejectionRequest,
    WebsitesRequest,
    WebsiteStatus,
)
from txtlocal.slices.automation.service import (
    AutomationService,
    covers,
    first_word_of,
    normalised_domain,
    rule_matches,
    webhook_event_of,
)
from txtlocal.slices.automation.tests.fakes import (
    ACCOUNT,
    DESTINATION,
    NOW,
    PEER,
    FakeInbound,
    FakeSender,
    InMemoryAutomationRepo,
    RecordingCampaigns,
    RecordingContacts,
    RecordingEmail,
    StubMessages,
    StubSenders,
)
from txtlocal.slices.contacts.model import ContactInput, ContactList
from txtlocal.slices.identity.model import Role
from txtlocal.slices.messaging.model import (
    Direction,
    MessageRow,
    MessageStatus,
    MessageType,
    Product,
    Transition,
)
from txtlocal.slices.messaging.segments import Encoding

if TYPE_CHECKING:
    from txtlocal.shared.testing import RecordingBus

SECOND_NUMBER = "+447411972300"


def rule_request(action: RuleAction, **overrides: object) -> InboundRuleRequest:
    fields: dict[str, object] = {"action": action, "name": f"{action.value} rule"}
    fields.update(overrides)
    return InboundRuleRequest(**fields)


def rule_of(action: RuleAction, **overrides: object) -> InboundRule:
    fields: dict[str, object] = {
        "action": action,
        "created_at": NOW,
        "name": f"{action.value} rule",
        "rule_id": "rule-x",
    }
    fields.update(overrides)
    return InboundRule(**fields)


def website_of(domain: str, registered_at: object) -> Website:
    return Website(domain=domain, registered_at=registered_at, status=WebsiteStatus.UNDER_REVIEW)


def message_row(**overrides: object) -> MessageRow:
    fields: dict[str, object] = {
        "account_id": ACCOUNT,
        "body": "Your table is ready",
        "campaign_id": "campaign-1",
        "country": "GB",
        "direction": Direction.OUT,
        "encoding": Encoding.GSM7,
        "from_": "+447908661626",
        "kind": Product.SMS,
        "message_id": "msg-1",
        "parts": 1,
        "price_micro": Micro(42_700),
        "queued_at": NOW,
        "status": MessageStatus.DELIVERED,
        "to": E164("+447400123123"),
        "user_id": "user-1",
        "username": "demo",
    }
    fields.update(overrides)
    return MessageRow(**fields)


def transition_of(status: MessageStatus) -> Transition:
    return Transition(
        account_id=ACCOUNT,
        campaign_id="campaign-1",
        failure_reason=None,
        message_id="msg-1",
        status=status,
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [("stop please", "stop"), ("  hello world  ", "hello"), ("", ""), ("ONEWORD", "ONEWORD")],
    ids=["first-of-many", "leading-whitespace", "empty-body", "single-word"],
)
def test_first_word_of(body: str, expected: str) -> None:
    assert first_word_of(body) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("junaid.guru", "junaid.guru"),
        ("www.junaid.guru", "www.junaid.guru"),
        ("https://junaid.guru/about?x=1", "junaid.guru"),
        ("HTTP://WWW.JUNAID.GURU/", "www.junaid.guru"),
        ("junaid.guru.", "junaid.guru"),
    ],
    ids=["bare", "www-is-distinct", "scheme-path-query-stripped", "case-folded", "trailing-dot"],
)
def test_normalised_domain_accepts(raw: str, expected: str) -> None:
    assert normalised_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["not a domain", "", "https://", "-bad.com", "a..b.com"],
    ids=["spaces", "empty", "scheme-only", "leading-hyphen", "double-dot"],
)
def test_normalised_domain_refuses(raw: str) -> None:
    with pytest.raises(BadRequest):
        normalised_domain(raw)


@pytest.mark.parametrize(
    ("events", "status", "expected"),
    [
        (DeliveryEventsFilter.ALL, MessageStatus.SENT, True),
        (DeliveryEventsFilter.ALL, MessageStatus.DELIVERED, True),
        (DeliveryEventsFilter.ALL, MessageStatus.FAILED, True),
        (DeliveryEventsFilter.DELIVERED, MessageStatus.DELIVERED, True),
        (DeliveryEventsFilter.DELIVERED, MessageStatus.SENT, False),
        (DeliveryEventsFilter.FAILED, MessageStatus.FAILED, True),
        (DeliveryEventsFilter.FAILED, MessageStatus.DELIVERED, False),
    ],
    ids=[
        "all-sent",
        "all-delivered",
        "all-failed",
        "delivered-matches",
        "delivered-ignores-sent",
        "failed-matches",
        "failed-ignores-delivered",
    ],
)
def test_covers(events: DeliveryEventsFilter, status: MessageStatus, expected: bool) -> None:
    assert covers(events, status) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (MessageStatus.SENT, "message.sent"),
        (MessageStatus.DELIVERED, "message.delivered"),
        (MessageStatus.FAILED, "message.failed"),
        (MessageStatus.QUEUED, None),
        (MessageStatus.RECEIVED, None),
    ],
    ids=["sent", "delivered", "failed", "queued-is-not-a-webhook", "received-is-not-a-webhook"],
)
def test_webhook_event_of(status: MessageStatus, expected: str | None) -> None:
    assert webhook_event_of(status) == expected


@pytest.mark.parametrize(
    ("number", "destination", "keyword", "match_kind", "body", "expected"),
    [
        (None, DESTINATION, None, MatchKind.ANY, "hello", True),
        (DESTINATION, DESTINATION, None, MatchKind.ANY, "hello", True),
        (SECOND_NUMBER, DESTINATION, None, MatchKind.ANY, "hello", False),
        (None, DESTINATION, "vote1", MatchKind.KEYWORD, "VOTE1 yes", True),
        (None, DESTINATION, "vote1", MatchKind.KEYWORD, "vote1", True),
        (None, DESTINATION, "vote1", MatchKind.KEYWORD, "other", False),
    ],
    ids=[
        "any-number-any-message",
        "matching-number",
        "wrong-number",
        "keyword-case-insensitive",
        "keyword-exact",
        "keyword-mismatch",
    ],
)
def test_rule_matches(
    number: str | None,
    destination: str,
    keyword: str | None,
    match_kind: MatchKind,
    body: str,
    expected: bool,
) -> None:
    rule = rule_of(
        RuleAction.SEND_TO_MESSENGER, keyword=keyword, match_kind=match_kind, number=number
    )
    assert rule_matches(rule, destination, first_word_of(body)) is expected


async def test_provision_defaults_seeds_the_three_rules_from_the_screen(
    provisioned: AutomationService, opt_out_list: ContactList
) -> None:
    rules = await provisioned.inbound_rules(ACCOUNT)

    assert [
        (rule.name, rule.action, rule.match_kind, rule.keyword, rule.number) for rule in rules
    ] == [
        ("Send to messenger", RuleAction.SEND_TO_MESSENGER, MatchKind.KEYWORD, "stop", None),
        ("Opt-out contact", RuleAction.MOVE_CONTACT, MatchKind.KEYWORD, "stop", None),
        ("Default rule", RuleAction.EMAIL_USER, MatchKind.ANY, None, None),
    ]
    assert rules[1].action_address == opt_out_list.list_id


async def test_provision_defaults_skips_move_contact_when_the_opt_out_list_is_missing(
    service: AutomationService,
) -> None:
    await service.provision_defaults(ACCOUNT, NOW)

    actions = [rule.action for rule in await service.inbound_rules(ACCOUNT)]
    assert actions == [RuleAction.SEND_TO_MESSENGER, RuleAction.EMAIL_USER]


async def test_provision_defaults_is_idempotent(provisioned: AutomationService) -> None:
    await provisioned.provision_defaults(ACCOUNT, NOW)

    assert len(await provisioned.inbound_rules(ACCOUNT)) == 3


async def test_run_inbound_runs_matched_rules_in_creation_order(service: AutomationService) -> None:
    first = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER))
    second = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.MOVE_CONTACT, action_address="list-1")
    )
    third = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.POLL, match_kind=MatchKind.ANY)
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert [outcome.rule_id for outcome in outcomes] == [
        first.rule_id,
        second.rule_id,
        third.rule_id,
    ]


async def test_run_inbound_skips_disabled_and_non_matching_rules(
    service: AutomationService,
) -> None:
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER, enabled=False)
    )
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER, number=SECOND_NUMBER)
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == []


async def test_run_inbound_isolates_a_failing_rule(
    service: AutomationService, campaigns: RecordingCampaigns
) -> None:
    campaigns.error = BadRequest("This contact has opted out")
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.AUTO_REPLY, action_address="Thanks")
    )
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.POLL, match_kind=MatchKind.ANY)
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert [outcome.outcome for outcome in outcomes] == [Outcome.FAILED, Outcome.INCREMENTED]


async def test_send_to_messenger_is_a_pure_marker(
    service: AutomationService,
    bus: RecordingBus,
    campaigns: RecordingCampaigns,
    contacts: RecordingContacts,
) -> None:
    created = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER))

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == [
        ActionOutcome(
            action=RuleAction.SEND_TO_MESSENGER, outcome=Outcome.NOOP, rule_id=created.rule_id
        )
    ]
    assert campaigns.calls == []
    assert contacts.added == []
    assert bus.sent == []


async def test_auto_reply_sends_a_transactional_quick_send_from_the_destination_number(
    service: AutomationService, campaigns: RecordingCampaigns, senders: StubSenders
) -> None:
    senders.rows[ACCOUNT] = [FakeSender(sender_id="sender-1", value=DESTINATION)]
    created = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.AUTO_REPLY, action_address="Thanks for your message")
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == [
        ActionOutcome(action=RuleAction.AUTO_REPLY, outcome=Outcome.QUEUED, rule_id=created.rule_id)
    ]
    [(principal, request, now)] = campaigns.calls
    assert principal.account_id == ACCOUNT
    assert principal.role is Role.OWNER
    assert (request.body, request.to, request.message_type, request.sender_id) == (
        "Thanks for your message",
        [PEER],
        MessageType.TRANSACTIONAL,
        "sender-1",
    )
    assert now == NOW


async def test_sms_forwards_the_inbound_body_to_the_configured_number(
    service: AutomationService, campaigns: RecordingCampaigns
) -> None:
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.SMS, action_address=SECOND_NUMBER)
    )

    await service.run_inbound(ACCOUNT, FakeInbound(body="forward me"), NOW)

    [(_, request, _)] = campaigns.calls
    assert (request.body, request.to, request.message_type) == (
        "forward me",
        [SECOND_NUMBER],
        MessageType.TRANSACTIONAL,
    )


async def test_sms_without_a_forward_number_is_not_configured(
    service: AutomationService, campaigns: RecordingCampaigns
) -> None:
    created = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.SMS))

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == [
        ActionOutcome(
            action=RuleAction.SMS, outcome=Outcome.NOT_CONFIGURED, rule_id=created.rule_id
        )
    ]
    assert campaigns.calls == []


async def test_group_sms_forwards_to_the_list_as_a_default_promotional_send(
    service: AutomationService, campaigns: RecordingCampaigns
) -> None:
    await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.GROUP_SMS, action_address="list-1")
    )

    await service.run_inbound(ACCOUNT, FakeInbound(body="fan out"), NOW)

    [(_, request, _)] = campaigns.calls
    assert (request.body, request.list_ids, request.message_type) == (
        "fan out",
        ["list-1"],
        MessageType.PROMOTIONAL,
    )


async def test_move_contact_adds_the_sender_by_mobile_only(
    service: AutomationService, contacts: RecordingContacts
) -> None:
    created = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.MOVE_CONTACT, action_address="list-1")
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="stop"), NOW)

    assert outcomes == [
        ActionOutcome(
            action=RuleAction.MOVE_CONTACT, outcome=Outcome.ADDED, rule_id=created.rule_id
        )
    ]
    assert contacts.added == [(ACCOUNT, "list-1", ContactInput(mobile=PEER))]


@pytest.mark.parametrize(
    ("action", "backup_email", "fixed_email", "expected_to"),
    [
        (RuleAction.EMAIL_USER, "backup@example.com", None, "backup@example.com"),
        (RuleAction.EMAIL_FIXED, None, "fixed@example.com", "fixed@example.com"),
    ],
    ids=["email-user-falls-back-to-backup", "email-fixed-uses-the-configured-address"],
)
async def test_email_actions_log_unavailable_and_do_not_send(
    service: AutomationService,
    email: RecordingEmail,
    action: RuleAction,
    backup_email: str | None,
    fixed_email: str | None,
    expected_to: str,
) -> None:
    created = await service.create_inbound_rule(
        ACCOUNT, rule_request(action, action_address=fixed_email, backup_email=backup_email)
    )

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == [
        ActionOutcome(action=action, outcome=Outcome.EMAIL_UNAVAILABLE, rule_id=created.rule_id)
    ]
    [(to, _, _)] = email.sent
    assert to == expected_to


async def test_poll_increments_votes_per_keyword_case_insensitively(
    service: AutomationService, repo: InMemoryAutomationRepo
) -> None:
    created = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.POLL, match_kind=MatchKind.ANY)
    )

    await service.run_inbound(ACCOUNT, FakeInbound(body="vote1 yes"), NOW)
    await service.run_inbound(ACCOUNT, FakeInbound(body="VOTE1 yes"), NOW)
    await service.run_inbound(ACCOUNT, FakeInbound(body="vote2"), NOW)

    stored = await repo.get_rule(ACCOUNT, created.rule_id)
    assert stored is not None
    assert stored.votes == {"VOTE1": 2, "VOTE2": 1}


async def test_url_action_enqueues_a_job_carrying_the_rules_own_secret(
    service: AutomationService, bus: RecordingBus
) -> None:
    created = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.URL, action_address="https://example.com/hook")
    )
    assert created.secret is not None

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello there"), NOW)

    assert outcomes == [
        ActionOutcome(action=RuleAction.URL, outcome=Outcome.QUEUED, rule_id=created.rule_id)
    ]
    [(queue, [message])] = bus.sent
    assert queue is Queue.WEBHOOKS
    job = WebhookJob.model_validate_json(message.body)
    assert (job.url, job.event, job.secret) == (
        "https://example.com/hook",
        "message.received",
        created.secret,
    )

    payload = json.loads(job.body)
    assert payload["direction"] == "IN"
    assert payload["keyword"] == "HELLO"
    assert payload["ruleId"] == created.rule_id
    assert payload["to"] == DESTINATION
    assert payload["from"] == PEER


async def test_url_action_without_a_url_is_not_configured(service: AutomationService) -> None:
    created = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.URL))

    outcomes = await service.run_inbound(ACCOUNT, FakeInbound(body="hello"), NOW)

    assert outcomes == [
        ActionOutcome(
            action=RuleAction.URL, outcome=Outcome.NOT_CONFIGURED, rule_id=created.rule_id
        )
    ]


async def test_on_delivery_does_not_read_the_message_when_no_rule_covers_it(
    service: AutomationService, bus: RecordingBus
) -> None:
    await service.create_delivery_rule(
        ACCOUNT,
        DeliveryReportRuleRequest(
            events=DeliveryEventsFilter.FAILED, name="Failures", url="https://example.com/report"
        ),
    )

    await service.on_delivery(transition_of(MessageStatus.DELIVERED), NOW)

    assert bus.sent == []


async def test_on_delivery_sends_one_signed_job_per_covering_rule(
    service: AutomationService, messages: StubMessages, bus: RecordingBus
) -> None:
    messages.rows[(ACCOUNT, "msg-1")] = message_row(status=MessageStatus.DELIVERED)
    await service.create_delivery_rule(
        ACCOUNT,
        DeliveryReportRuleRequest(
            events=DeliveryEventsFilter.ALL, name="All", url="https://example.com/all"
        ),
    )
    await service.create_delivery_rule(
        ACCOUNT,
        DeliveryReportRuleRequest(
            events=DeliveryEventsFilter.FAILED, name="Failures", url="https://example.com/failures"
        ),
    )

    await service.on_delivery(transition_of(MessageStatus.DELIVERED), NOW)

    [(queue, sent_messages)] = bus.sent
    assert queue is Queue.WEBHOOKS
    assert len(sent_messages) == 1
    job = WebhookJob.model_validate_json(sent_messages[0].body)
    payload = json.loads(job.body)
    assert (payload["event"], payload["price"], payload["direction"]) == (
        "message.delivered",
        "0.0427",
        "OUT",
    )


async def test_test_webhook_enqueues_the_delivered_sample(
    service: AutomationService, bus: RecordingBus
) -> None:
    created = await service.create_delivery_rule(
        ACCOUNT, DeliveryReportRuleRequest(name="Report", url="https://example.com/report")
    )

    await service.test_webhook(ACCOUNT, created.rule.rule_id)

    [(_, [message])] = bus.sent
    job = WebhookJob.model_validate_json(message.body)
    payload = json.loads(job.body)
    assert (payload["event"], payload["messageId"]) == ("message.delivered", "msg_test")
    assert job.secret == created.secret


async def test_test_webhook_refuses_an_unknown_rule(service: AutomationService) -> None:
    with pytest.raises(NotFound):
        await service.test_webhook(ACCOUNT, "no-such-rule")


async def test_delivery_rule_secret_is_returned_once_and_hidden_thereafter(
    service: AutomationService,
) -> None:
    created = await service.create_delivery_rule(
        ACCOUNT, DeliveryReportRuleRequest(name="Report", url="https://example.com/report")
    )

    assert created.secret
    listed = await service.delivery_rules(ACCOUNT)
    assert not hasattr(listed[0], "secret")


async def test_create_delivery_rule_refuses_a_non_https_url(service: AutomationService) -> None:
    with pytest.raises(BadRequest):
        await service.create_delivery_rule(
            ACCOUNT, DeliveryReportRuleRequest(name="Report", url="http://example.com")
        )


async def test_register_websites_accepts_three_and_refuses_a_fourth(
    service: AutomationService,
) -> None:
    created = await service.register_websites(
        ACCOUNT, WebsitesRequest(domains=["one.example", "two.example", "three.example"])
    )
    assert [website.domain for website in created] == [
        "one.example",
        "two.example",
        "three.example",
    ]
    assert all(website.status is WebsiteStatus.UNDER_REVIEW for website in created)

    with pytest.raises(BadRequest) as caught:
        await service.register_websites(
            ACCOUNT,
            WebsitesRequest(domains=["a.example", "b.example", "c.example", "d.example"]),
        )
    assert str(caught.value) == "You can register up to 3 websites at once"


async def test_register_websites_refuses_a_duplicate(service: AutomationService) -> None:
    await service.register_websites(ACCOUNT, WebsitesRequest(domains=["junaid.guru"]))

    with pytest.raises(Conflict) as caught:
        await service.register_websites(ACCOUNT, WebsitesRequest(domains=["junaid.guru"]))
    assert str(caught.value) == "junaid.guru is already registered"


async def test_register_websites_treats_www_as_a_distinct_domain(
    service: AutomationService,
) -> None:
    created = await service.register_websites(
        ACCOUNT, WebsitesRequest(domains=["junaid.guru", "www.junaid.guru"])
    )
    assert [website.domain for website in created] == ["junaid.guru", "www.junaid.guru"]


@pytest.mark.parametrize(
    ("age", "expected_approved"),
    [
        (timedelta(hours=24), 1),
        (timedelta(hours=23, minutes=59), 0),
        (timedelta(hours=24, seconds=1), 1),
    ],
    ids=["exactly-24h-is-due", "just-under-24h-is-not-due", "just-over-24h-is-due"],
)
async def test_approve_due_websites_boundary(
    service: AutomationService,
    repo: InMemoryAutomationRepo,
    age: timedelta,
    expected_approved: int,
) -> None:
    await repo.put_website_if_absent(ACCOUNT, website_of("old.example", NOW - age))

    approved = await service.approve_due_websites(NOW)

    assert approved == expected_approved
    website = await repo.get_website(ACCOUNT, "old.example")
    assert website is not None
    expected_status = WebsiteStatus.APPROVED if expected_approved else WebsiteStatus.UNDER_REVIEW
    assert website.status is expected_status


async def test_approve_website_now_skips_the_review_wait(
    service: AutomationService, repo: InMemoryAutomationRepo
) -> None:
    await service.register_websites(ACCOUNT, WebsitesRequest(domains=["junaid.guru"]))

    approved = await service.approve_website_now(ACCOUNT, "junaid.guru")

    assert approved.status is WebsiteStatus.APPROVED
    assert await repo.websites_under_review() == []


async def test_approve_website_now_refuses_an_unknown_website(service: AutomationService) -> None:
    with pytest.raises(NotFound):
        await service.approve_website_now(ACCOUNT, "unknown.example")


async def test_reject_website_records_the_reason(
    service: AutomationService, repo: InMemoryAutomationRepo
) -> None:
    await service.register_websites(ACCOUNT, WebsitesRequest(domains=["junaid.guru"]))

    rejected = await service.reject_website(
        ACCOUNT, "junaid.guru", WebsiteRejectionRequest(reason="Looks like a phishing page")
    )

    assert (rejected.status, rejected.rejected_reason) == (
        WebsiteStatus.REJECTED,
        "Looks like a phishing page",
    )
    assert await repo.websites_under_review() == []


async def test_reject_website_refuses_an_unknown_website(service: AutomationService) -> None:
    with pytest.raises(NotFound):
        await service.reject_website(
            ACCOUNT, "unknown.example", WebsiteRejectionRequest(reason="No")
        )


async def test_reject_website_requires_a_reason(service: AutomationService) -> None:
    await service.register_websites(ACCOUNT, WebsitesRequest(domains=["junaid.guru"]))

    with pytest.raises(BadRequest) as caught:
        await service.reject_website(ACCOUNT, "junaid.guru", WebsiteRejectionRequest(reason="   "))
    assert str(caught.value) == "Enter a reason of 1 to 500 characters"


async def test_add_email_sender_requires_a_ready_sender(
    service: AutomationService, senders: StubSenders
) -> None:
    senders.rows[ACCOUNT] = [FakeSender(sender_id="sender-1", status="PENDING_VERIFICATION")]

    with pytest.raises(BadRequest):
        await service.add_email_sender(
            ACCOUNT,
            EmailSenderRequest(email="a@example.com", sender_id="sender-1", user_id="user-1"),
        )


async def test_add_email_sender_refuses_a_duplicate_address(
    service: AutomationService, senders: StubSenders
) -> None:
    senders.rows[ACCOUNT] = [FakeSender(sender_id="sender-1")]
    request = EmailSenderRequest(email="a@example.com", sender_id="sender-1", user_id="user-1")
    await service.add_email_sender(ACCOUNT, request)

    with pytest.raises(Conflict):
        await service.add_email_sender(ACCOUNT, request)


async def test_remove_email_sender_refuses_an_unknown_address(service: AutomationService) -> None:
    with pytest.raises(NotFound):
        await service.remove_email_sender(ACCOUNT, "nobody@example.com")


async def test_handle_inbound_email_sends_once_per_matching_account(
    service: AutomationService, repo: InMemoryAutomationRepo, campaigns: RecordingCampaigns
) -> None:
    sender = EmailSender(email="jan@example.com", sender_id="sender-1", user_id="user-9")
    await repo.put_email_sender_if_absent(ACCOUNT, sender)

    await service.handle_inbound_email(
        DemoInboundEmailRequest(
            body="Please call me back",
            numbers=["+447984390718", "+447411972333"],
            sender_email="jan@example.com",
        ),
        NOW,
    )

    [(principal, request, now)] = campaigns.calls
    assert (principal.account_id, principal.user_id) == (ACCOUNT, "user-9")
    assert (request.body, request.sender_id, request.to) == (
        "Please call me back",
        "sender-1",
        ["+447984390718", "+447411972333"],
    )
    assert now == NOW


async def test_handle_inbound_email_sends_for_every_account_that_allow_lists_the_address(
    service: AutomationService, repo: InMemoryAutomationRepo, campaigns: RecordingCampaigns
) -> None:
    await repo.put_email_sender_if_absent(
        ACCOUNT, EmailSender(email="jan@example.com", sender_id="sender-1", user_id="user-9")
    )
    await repo.put_email_sender_if_absent(
        "account-2", EmailSender(email="jan@example.com", sender_id="sender-2", user_id="user-2")
    )

    await service.handle_inbound_email(
        DemoInboundEmailRequest(
            body="hi", numbers=["+447984390718"], sender_email="jan@example.com"
        ),
        NOW,
    )

    assert {call[0].account_id for call in campaigns.calls} == {ACCOUNT, "account-2"}


async def test_handle_inbound_email_rejects_silently_when_sender_is_not_allowed(
    service: AutomationService, campaigns: RecordingCampaigns
) -> None:
    await service.handle_inbound_email(
        DemoInboundEmailRequest(
            body="hi", numbers=["+447984390718"], sender_email="nobody@example.com"
        ),
        NOW,
    )

    assert campaigns.calls == []


async def test_handle_inbound_email_does_nothing_without_a_destination_number(
    service: AutomationService, repo: InMemoryAutomationRepo, campaigns: RecordingCampaigns
) -> None:
    sender = EmailSender(email="jan@example.com", sender_id="sender-1", user_id="user-9")
    await repo.put_email_sender_if_absent(ACCOUNT, sender)

    await service.handle_inbound_email(
        DemoInboundEmailRequest(body="hi", numbers=[], sender_email="jan@example.com"), NOW
    )

    assert campaigns.calls == []


async def test_handle_inbound_email_survives_a_refused_send(
    service: AutomationService, repo: InMemoryAutomationRepo, campaigns: RecordingCampaigns
) -> None:
    sender = EmailSender(email="jan@example.com", sender_id="sender-1", user_id="user-9")
    await repo.put_email_sender_if_absent(ACCOUNT, sender)
    campaigns.error = PaymentRequired("Top up your balance")

    await service.handle_inbound_email(
        DemoInboundEmailRequest(
            body="hi", numbers=["+447984390718"], sender_email="jan@example.com"
        ),
        NOW,
    )

    assert len(campaigns.calls) == 1


async def test_update_and_delete_inbound_rule(service: AutomationService) -> None:
    created = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER))

    updated = await service.update_inbound_rule(
        ACCOUNT, created.rule_id, rule_request(RuleAction.SEND_TO_MESSENGER, enabled=False)
    )
    assert updated.enabled is False

    await service.delete_inbound_rule(ACCOUNT, created.rule_id)
    with pytest.raises(NotFound):
        await service.update_inbound_rule(
            ACCOUNT, created.rule_id, rule_request(RuleAction.SEND_TO_MESSENGER)
        )


async def test_url_rule_is_given_a_secret_only_when_created_or_edited_to_url(
    service: AutomationService,
) -> None:
    plain = await service.create_inbound_rule(ACCOUNT, rule_request(RuleAction.SEND_TO_MESSENGER))
    assert plain.secret is None

    with_url = await service.create_inbound_rule(
        ACCOUNT, rule_request(RuleAction.URL, action_address="https://example.com/hook")
    )
    assert with_url.secret is not None

    edited = await service.update_inbound_rule(
        ACCOUNT,
        plain.rule_id,
        rule_request(RuleAction.URL, action_address="https://example.com/hook"),
    )
    assert edited.secret is not None
