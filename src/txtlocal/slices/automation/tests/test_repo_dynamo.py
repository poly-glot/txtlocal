from datetime import UTC, datetime

from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.automation.model import (
    DeliveryEventsFilter,
    DeliveryReportRule,
    EmailSender,
    InboundRule,
    MatchKind,
    RuleAction,
    Website,
    WebsiteStatus,
)
from txtlocal.slices.automation.repo import AutomationDynamoRepo, AutomationRepo

ACCOUNT = "account-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

RULE = InboundRule(
    action=RuleAction.POLL,
    created_at=NOW,
    keyword="vote1",
    match_kind=MatchKind.KEYWORD,
    name="Vote for option 1",
    rule_id="rule-1",
)


async def test_rule_round_trips_with_an_empty_votes_map() -> None:
    async with local_repo_table("automation") as table:
        repo: AutomationRepo = AutomationDynamoRepo(table)
        await repo.put_rule(ACCOUNT, RULE)

        assert await repo.get_rule(ACCOUNT, RULE.rule_id) == RULE


async def test_increment_vote_creates_and_accumulates_the_keyword_counter() -> None:
    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_rule(ACCOUNT, RULE)

        first = await repo.increment_vote(ACCOUNT, RULE.rule_id, "VOTE1")
        second = await repo.increment_vote(ACCOUNT, RULE.rule_id, "VOTE1")
        third = await repo.increment_vote(ACCOUNT, RULE.rule_id, "VOTE2")

        assert (first, second, third) == (True, True, True)
        stored = await repo.get_rule(ACCOUNT, RULE.rule_id)
        assert stored is not None
        assert stored.votes == {"VOTE1": 2, "VOTE2": 1}


async def test_increment_vote_is_false_for_a_missing_rule() -> None:
    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)

        assert await repo.increment_vote(ACCOUNT, "missing", "VOTE1") is False


async def test_replace_rule_requires_an_existing_row() -> None:
    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_rule(ACCOUNT, RULE)

        replaced = await repo.replace_rule(ACCOUNT, RULE.model_copy(update={"enabled": False}))
        missing = await repo.replace_rule(
            ACCOUNT, RULE.model_copy(update={"rule_id": "no-such-rule"})
        )

        assert (replaced, missing) == (True, False)
        stored = await repo.get_rule(ACCOUNT, RULE.rule_id)
        assert stored is not None
        assert stored.enabled is False


async def test_delete_rule_wins_once() -> None:
    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_rule(ACCOUNT, RULE)

        outcomes = (
            await repo.delete_rule(ACCOUNT, RULE.rule_id),
            await repo.delete_rule(ACCOUNT, RULE.rule_id),
        )

        assert outcomes == (True, False)


async def test_delivery_rule_round_trip_and_replace() -> None:
    rule = DeliveryReportRule(
        created_at=NOW,
        events=DeliveryEventsFilter.FAILED,
        name="Report failures",
        rule_id="dlr-1",
        secret="shh-secret",
        url="https://example.com/report",
    )

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_delivery_rule(ACCOUNT, rule)

        assert await repo.get_delivery_rule(ACCOUNT, rule.rule_id) == rule
        assert await repo.list_delivery_rules(ACCOUNT) == [rule]

        disabled = rule.model_copy(update={"enabled": False})
        assert await repo.replace_delivery_rule(ACCOUNT, disabled) is True
        assert await repo.delete_delivery_rule(ACCOUNT, rule.rule_id) is True
        assert await repo.delete_delivery_rule(ACCOUNT, rule.rule_id) is False


async def test_website_registration_is_under_review_with_the_gsi2_queue() -> None:
    website = Website(domain="junaid.guru", registered_at=NOW, status=WebsiteStatus.UNDER_REVIEW)

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        won = await repo.put_website_if_absent(ACCOUNT, website)
        lost = await repo.put_website_if_absent(ACCOUNT, website)

        assert (won, lost) == (True, False)
        assert await repo.list_websites(ACCOUNT) == [website]
        assert await repo.websites_under_review() == [(ACCOUNT, website)]


async def test_approving_a_website_removes_it_from_the_review_queue() -> None:
    website = Website(domain="junaid.guru", registered_at=NOW, status=WebsiteStatus.UNDER_REVIEW)

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_website_if_absent(ACCOUNT, website)

        approved = await repo.approve_website(ACCOUNT, website.domain)

        assert approved is True
        assert await repo.websites_under_review() == []
        stored = await repo.get_website(ACCOUNT, website.domain)
        assert stored is not None
        assert stored.status is WebsiteStatus.APPROVED


async def test_rejecting_a_website_removes_it_from_the_review_queue() -> None:
    website = Website(domain="junaid.guru", registered_at=NOW, status=WebsiteStatus.UNDER_REVIEW)

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_website_if_absent(ACCOUNT, website)

        rejected = await repo.reject_website(ACCOUNT, website.domain, "Looks unsafe")

        assert rejected is True
        assert await repo.websites_under_review() == []
        stored = await repo.get_website(ACCOUNT, website.domain)
        assert stored is not None
        assert (stored.status, stored.rejected_reason) == (WebsiteStatus.REJECTED, "Looks unsafe")


async def test_reject_website_is_false_for_a_missing_website() -> None:
    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)

        assert await repo.reject_website(ACCOUNT, "missing.example", "Looks unsafe") is False


async def test_email_sender_round_trip_and_uniqueness() -> None:
    sender = EmailSender(email="a@example.com", sender_id="sender-1", user_id="user-1")

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        won = await repo.put_email_sender_if_absent(ACCOUNT, sender)
        lost = await repo.put_email_sender_if_absent(ACCOUNT, sender)

        assert (won, lost) == (True, False)
        assert await repo.list_email_senders(ACCOUNT) == [sender]
        assert await repo.delete_email_sender(ACCOUNT, sender.email) is True
        assert await repo.get_email_sender(ACCOUNT, sender.email) is None


async def test_email_senders_by_address_finds_the_owning_account() -> None:
    sender = EmailSender(email="jan@example.com", sender_id="sender-1", user_id="user-1")

    async with local_repo_table("automation") as table:
        repo = AutomationDynamoRepo(table)
        await repo.put_email_sender_if_absent(ACCOUNT, sender)

        assert await repo.email_senders_by_address("jan@example.com") == [(ACCOUNT, sender)]
        assert await repo.email_senders_by_address("nobody@example.com") == []
