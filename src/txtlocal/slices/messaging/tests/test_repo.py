from datetime import timedelta

from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.messaging.model import (
    DeliveryStatus,
    DeliveryUpdate,
    MessageStatus,
    Product,
    SearchField,
    Template,
)
from txtlocal.slices.messaging.repo import HistoryWindow, MessagingDynamoRepo
from txtlocal.slices.messaging.tests.support import (
    ACCOUNT,
    CAMPAIGN,
    DESTINATION,
    NOW,
    inbound_row_at,
    row_at,
)

SEPTEMBER = "2026-09"
AUGUST = "2026-08"
WIDE_OPEN = HistoryWindow(
    field=SearchField.TO,
    kind=None,
    months=(SEPTEMBER, AUGUST),
    number=None,
    since="2026-08-01T00:00:00.000Z",
    until="2026-09-20T00:00:00.000Z",
)


def delivery(status: DeliveryStatus, event_type: str) -> DeliveryUpdate:
    return DeliveryUpdate(
        at=NOW + timedelta(seconds=5),
        event_type=event_type,
        provider_message_id="aws-1",
        status=status,
    )


async def test_claim_writes_the_row_and_its_marker_in_one_transaction() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)

        claimed = await repo.claim(row)

        assert claimed is True
        assert await repo.get(row.key) == row
        assert await repo.find_claim(ACCOUNT, CAMPAIGN, DESTINATION) == row.key


async def test_a_second_claim_for_the_same_recipient_loses_on_the_marker() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        first = row_at(NOW, 1)
        retry = row_at(NOW + timedelta(seconds=30), 2)
        await repo.claim(first)

        claimed = await repo.claim(retry)

        assert claimed is False
        assert await repo.get(retry.key) is None
        assert await repo.find_claim(ACCOUNT, CAMPAIGN, DESTINATION) == first.key


async def test_mark_sent_wins_once_from_queued() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        first = await repo.mark_sent(row.key, "aws-1", NOW)
        second = await repo.mark_sent(row.key, "aws-2", NOW)

        stored = await repo.get(row.key)
        assert (first, second) == (True, False)
        assert stored is not None
        assert (stored.status, stored.provider_message_id, stored.sent_at) == (
            MessageStatus.SENT,
            "aws-1",
            NOW,
        )


async def test_refuse_settles_only_a_queued_row() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        queued, sent = row_at(NOW, 1), row_at(NOW, 2, campaign_id="camp-2")
        await repo.claim(queued)
        await repo.claim(sent)
        await repo.mark_sent(sent.key, "aws-1", NOW)

        refused = await repo.refuse(queued.key, "OPTED_OUT")
        lost = await repo.refuse(sent.key, "OPTED_OUT")

        stored = await repo.get(queued.key)
        assert (refused, lost) == (True, False)
        assert stored is not None
        assert (stored.status, stored.failure_reason) == (MessageStatus.FAILED, "OPTED_OUT")


async def test_apply_delivery_moves_sent_to_delivered_and_returns_the_row() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)
        await repo.mark_sent(row.key, "aws-1", NOW)

        delivered = await repo.apply_delivery(
            row.key, delivery(MessageStatus.DELIVERED, "TEXT_DELIVERED")
        )

        assert delivered is not None
        assert (delivered.status, delivered.delivered_at, delivered.sent_at) == (
            MessageStatus.DELIVERED,
            NOW + timedelta(seconds=5),
            NOW,
        )


async def test_apply_delivery_from_queued_fills_in_the_receipt() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        failed = await repo.apply_delivery(
            row.key, delivery(MessageStatus.FAILED, "TEXT_CARRIER_UNREACHABLE")
        )

        assert failed is not None
        assert (
            failed.status,
            failed.failure_reason,
            failed.provider_message_id,
            failed.sent_at,
        ) == (
            MessageStatus.FAILED,
            "TEXT_CARRIER_UNREACHABLE",
            "aws-1",
            NOW + timedelta(seconds=5),
        )


async def test_apply_delivery_loses_against_a_final_status() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)
        await repo.apply_delivery(row.key, delivery(MessageStatus.DELIVERED, "TEXT_DELIVERED"))

        late = await repo.apply_delivery(row.key, delivery(MessageStatus.SENT, "TEXT_SENT"))

        stored = await repo.get(row.key)
        assert late is None
        assert stored is not None
        assert stored.status is MessageStatus.DELIVERED


async def test_count_send_increments_the_day_counter() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        day = NOW.date()

        counts = [await repo.count_send(ACCOUNT, day) for _ in range(3)]

        assert counts == [1, 2, 3]
        assert await repo.sends_on(ACCOUNT, day) == 3
        assert await repo.sends_on(ACCOUNT, day + timedelta(days=1)) == 0


async def test_history_page_reads_newest_first_and_continues_from_the_cursor() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        rows = [row_at(NOW - timedelta(minutes=i), i, campaign_id=f"camp-{i}") for i in range(3)]
        for row in rows:
            await repo.claim(row)

        first, cursor = await repo.history_page(ACCOUNT, SEPTEMBER, WIDE_OPEN, None, 2)
        assert cursor is not None
        rest, end = await repo.history_page(ACCOUNT, SEPTEMBER, WIDE_OPEN, cursor, 2)

        assert [row.message_id for row in first + rest] == [row.message_id for row in rows]
        assert end is None


async def test_history_page_filters_by_number_and_kind() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        sms = row_at(NOW, 1, campaign_id="camp-sms")
        link = row_at(
            NOW - timedelta(minutes=1), 2, campaign_id="camp-link", product=Product.MMS_AS_LINK
        )
        other = row_at(NOW - timedelta(minutes=2), 3, campaign_id="camp-other", to="+447400123106")
        for row in (sms, link, other):
            await repo.claim(row)
        window = HistoryWindow(
            field=SearchField.TO,
            kind=Product.MMS,
            months=(SEPTEMBER,),
            number=DESTINATION,
            since=WIDE_OPEN.since,
            until=WIDE_OPEN.until,
        )

        page, cursor = await repo.history_page(ACCOUNT, SEPTEMBER, window, None, 20)

        assert [row.message_id for row in page] == [link.message_id]
        assert cursor is None


async def test_mark_sent_also_indexes_the_row_by_provider_message_id() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        await repo.mark_sent(row.key, "aws-99", NOW)

        found = await repo.find_by_provider_id("aws-99")
        assert found is not None
        assert found.message_id == row.message_id


async def test_apply_delivery_indexes_the_row_when_it_beats_mark_sent() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        await repo.apply_delivery(row.key, delivery(MessageStatus.SENT, "TEXT_SENT"))
        lost = await repo.mark_sent(row.key, "aws-1", NOW)

        found = await repo.find_by_provider_id("aws-1")
        assert lost is False
        assert found is not None
        assert found.message_id == row.message_id


async def test_find_by_provider_id_of_an_unknown_id_is_none() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)

        assert await repo.find_by_provider_id("nonsense") is None


async def test_record_inbound_writes_the_row_and_its_marker_in_one_transaction() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = inbound_row_at(NOW)

        recorded = await repo.record_inbound(row, "inbound-1", NOW)

        assert recorded is True
        assert await repo.get(row.key) == row


async def test_a_redelivered_inbound_notification_loses_on_the_marker() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        first = inbound_row_at(NOW, 1)
        retry = inbound_row_at(NOW + timedelta(minutes=5), 2)
        await repo.record_inbound(first, "inbound-1", NOW)

        recorded = await repo.record_inbound(retry, "inbound-1", NOW + timedelta(minutes=5))

        assert recorded is False
        assert await repo.get(retry.key) is None
        assert await repo.get(first.key) == first


async def test_conversation_page_reads_the_thread_newest_first() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        reply = row_at(NOW - timedelta(minutes=5), 1)
        received = inbound_row_at(NOW, 2)
        unrelated = row_at(NOW - timedelta(minutes=1), 3, to="+447400123106")
        await repo.claim(reply)
        await repo.record_inbound(received, "inbound-1", NOW)
        await repo.claim(unrelated)

        page, cursor = await repo.conversation_page(ACCOUNT, DESTINATION, None, 20)

        assert [row.message_id for row in page] == [received.message_id, reply.message_id]
        assert cursor is None


async def test_conversation_page_continues_from_the_cursor() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        thread = [inbound_row_at(NOW - timedelta(minutes=i), i) for i in range(3)]
        for row in thread:
            await repo.record_inbound(row, f"inbound-{row.message_id}", NOW)

        first, cursor = await repo.conversation_page(ACCOUNT, DESTINATION, None, 2)
        assert cursor is not None
        rest, end = await repo.conversation_page(ACCOUNT, DESTINATION, cursor, 2)

        assert [row.message_id for row in first + rest] == [row.message_id for row in thread]
        assert end is None


async def test_templates_are_stored_edited_and_deleted_under_their_conditions() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        template = Template(body="Hi", created_at=NOW, name="Greeting", template_id="t-1")

        created = await repo.put_template(ACCOUNT, template)
        duplicate = await repo.put_template(ACCOUNT, template)
        edited = await repo.edit_template(ACCOUNT, "t-1", "Greeting v2", "Hello")
        missing = await repo.edit_template(ACCOUNT, "t-2", "x", "y")
        listed = await repo.list_templates(ACCOUNT)
        deleted = await repo.delete_template(ACCOUNT, "t-1")
        gone = await repo.delete_template(ACCOUNT, "t-1")

        assert (created, duplicate, missing, deleted, gone) == (True, False, None, True, False)
        assert edited == Template(
            body="Hello", created_at=NOW, name="Greeting v2", template_id="t-1"
        )
        assert listed == [edited]


async def test_claim_attempt_marks_a_queued_row_once() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        first = await repo.claim_attempt(row.key, NOW)
        second = await repo.claim_attempt(row.key, NOW + timedelta(seconds=90))

        assert (first, second) == (True, False)


async def test_claim_attempt_records_when_the_provider_was_called() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)

        await repo.claim_attempt(row.key, NOW)

        stored = await repo.get(row.key)
        assert stored is not None
        assert stored.attempted_at == NOW


async def test_claim_attempt_refuses_a_row_that_has_left_queued() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)
        await repo.mark_sent(row.key, "aws-1", NOW)

        assert await repo.claim_attempt(row.key, NOW) is False


async def test_apply_delivery_of_a_repeated_sent_event_loses_against_a_sent_row() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)
        update = delivery(MessageStatus.SENT, "TEXT_SENT")

        first = await repo.apply_delivery(row.key, update)
        second = await repo.apply_delivery(row.key, update)

        assert (first is None, second) == (False, None)


async def test_apply_delivery_of_a_sent_event_after_mark_sent_changes_nothing() -> None:
    async with local_repo_table("messaging") as table:
        repo = MessagingDynamoRepo(table)
        row = row_at(NOW)
        await repo.claim(row)
        await repo.mark_sent(row.key, "aws-1", NOW)

        applied = await repo.apply_delivery(row.key, delivery(MessageStatus.SENT, "TEXT_SENT"))

        assert applied is None
