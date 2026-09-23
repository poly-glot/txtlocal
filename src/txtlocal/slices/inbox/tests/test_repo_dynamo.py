from datetime import timedelta

import pytest

from txtlocal.shared.phone import E164
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.inbox.model import ConversationStatus
from txtlocal.slices.inbox.repo import InboxDynamoRepo, InboxRepo
from txtlocal.slices.inbox.tests.fakes import ACCOUNT, LATER, NOW, OTHER_PEER, PEER, SENDER_ID

CLOSED_AHEAD = 3
ONE_MINUTE = timedelta(minutes=1)


async def a_closed_run_newer_than(repo: InboxDynamoRepo, count: int) -> None:
    for index in range(count):
        peer = E164(f"+4479005551{index:02d}")
        await repo.upsert_inbound(ACCOUNT, peer, "closed", SENDER_ID, LATER + ONE_MINUTE * index)
        await repo.set_status(ACCOUNT, peer, ConversationStatus.CLOSED)


async def test_upsert_inbound_creates_a_conversation_with_unread_one() -> None:
    async with local_repo_table("inbox") as table:
        repo: InboxRepo = InboxDynamoRepo(table)

        await repo.upsert_inbound(ACCOUNT, PEER, "hello", SENDER_ID, NOW)

        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.unread == 1
        assert conversation.last_preview == "hello"
        assert conversation.last_sender_id == SENDER_ID
        assert conversation.status is ConversationStatus.OPEN


async def test_upsert_inbound_again_increments_unread() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "hello", SENDER_ID, NOW)

        await repo.upsert_inbound(ACCOUNT, PEER, "hello again", SENDER_ID, LATER)

        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.unread == 2
        assert conversation.last_preview == "hello again"


async def test_upsert_inbound_without_a_sender_id_leaves_it_absent() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)

        await repo.upsert_inbound(ACCOUNT, PEER, "hello", None, NOW)

        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.last_sender_id is None


async def test_upsert_outbound_does_not_change_unread() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "hello", SENDER_ID, NOW)

        await repo.upsert_outbound(ACCOUNT, PEER, "a reply", SENDER_ID, LATER)

        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.unread == 1
        assert conversation.last_preview == "a reply"


async def test_get_is_none_for_a_missing_conversation() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)

        assert await repo.get(ACCOUNT, PEER) is None


async def test_mark_read_zeroes_unread() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "hello", SENDER_ID, NOW)

        marked = await repo.mark_read(ACCOUNT, PEER)

        assert marked is True
        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.unread == 0


async def test_mark_read_is_false_for_a_missing_conversation() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)

        assert await repo.mark_read(ACCOUNT, PEER) is False


@pytest.mark.parametrize(
    "status", [ConversationStatus.CLOSED, ConversationStatus.OPEN], ids=["close", "reopen"]
)
async def test_set_status_round_trips(status: ConversationStatus) -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "hello", SENDER_ID, NOW)

        changed = await repo.set_status(ACCOUNT, PEER, status)

        assert changed is True
        conversation = await repo.get(ACCOUNT, PEER)
        assert conversation is not None
        assert conversation.status is status


async def test_set_status_is_false_for_a_missing_conversation() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)

        assert await repo.set_status(ACCOUNT, PEER, ConversationStatus.CLOSED) is False


async def test_list_conversations_orders_newest_first() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "first", SENDER_ID, NOW)
        await repo.upsert_inbound(ACCOUNT, OTHER_PEER, "second", SENDER_ID, LATER)

        page = await repo.list_conversations(ACCOUNT, None, None, 10)

        assert [c.peer for c in page.items] == [OTHER_PEER, PEER]
        assert page.next_cursor is None


async def test_list_conversations_pages_with_a_cursor() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "first", SENDER_ID, NOW)
        await repo.upsert_inbound(ACCOUNT, OTHER_PEER, "second", SENDER_ID, LATER)

        first_page = await repo.list_conversations(ACCOUNT, None, None, 1)
        assert [c.peer for c in first_page.items] == [OTHER_PEER]
        assert first_page.next_cursor is not None

        second_page = await repo.list_conversations(ACCOUNT, None, first_page.next_cursor, 1)
        assert [c.peer for c in second_page.items] == [PEER]


async def test_list_conversations_filters_by_status() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "first", SENDER_ID, NOW)
        await repo.upsert_inbound(ACCOUNT, OTHER_PEER, "second", SENDER_ID, LATER)
        await repo.set_status(ACCOUNT, PEER, ConversationStatus.CLOSED)

        open_page = await repo.list_conversations(ACCOUNT, ConversationStatus.OPEN, None, 10)
        closed_page = await repo.list_conversations(ACCOUNT, ConversationStatus.CLOSED, None, 10)

        assert [c.peer for c in open_page.items] == [OTHER_PEER]
        assert [c.peer for c in closed_page.items] == [PEER]


async def test_list_conversations_reaches_open_rows_behind_a_page_of_closed_ones() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "open", SENDER_ID, NOW)
        await a_closed_run_newer_than(repo, CLOSED_AHEAD)

        page = await repo.list_conversations(ACCOUNT, ConversationStatus.OPEN, None, 2)

        assert [c.peer for c in page.items] == [PEER]


async def test_list_conversations_resumes_a_filtered_page_from_its_cursor() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "open", SENDER_ID, NOW)
        await repo.upsert_inbound(ACCOUNT, OTHER_PEER, "open too", SENDER_ID, NOW + ONE_MINUTE)
        await a_closed_run_newer_than(repo, CLOSED_AHEAD)

        first_page = await repo.list_conversations(ACCOUNT, ConversationStatus.OPEN, None, 1)
        assert [c.peer for c in first_page.items] == [OTHER_PEER]
        assert first_page.next_cursor is not None

        second_page = await repo.list_conversations(
            ACCOUNT, ConversationStatus.OPEN, first_page.next_cursor, 1
        )
        assert [c.peer for c in second_page.items] == [PEER]


async def test_mark_all_read_zeroes_every_conversation() -> None:
    async with local_repo_table("inbox") as table:
        repo = InboxDynamoRepo(table)
        await repo.upsert_inbound(ACCOUNT, PEER, "first", SENDER_ID, NOW)
        await repo.upsert_inbound(ACCOUNT, OTHER_PEER, "second", SENDER_ID, LATER)

        await repo.mark_all_read(ACCOUNT)

        first = await repo.get(ACCOUNT, PEER)
        second = await repo.get(ACCOUNT, OTHER_PEER)
        assert first is not None
        assert second is not None
        assert (first.unread, second.unread) == (0, 0)
