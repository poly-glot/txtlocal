from dataclasses import replace
from datetime import timedelta

from txtlocal.shared.money import Micro
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignCounter,
    CampaignCounts,
    CampaignQuery,
    CampaignRef,
    CampaignStatus,
    FanoutStep,
    SchedulePlan,
)
from txtlocal.slices.campaigns.repo import PAGE_SIZE, CampaignsDynamoRepo
from txtlocal.slices.campaigns.tests.fakes import (
    ACCOUNT_ID,
    GB_RATE,
    NOW,
    draft_campaign,
    list_campaign,
)
from txtlocal.slices.messaging.model import Product

COUNTED = CampaignCounts(recipients=2, refused=1, sent=1)
LATER = NOW + timedelta(hours=1)
PLAN = SchedulePlan(
    quote_micro=Micro(GB_RATE),
    recipients=2,
    reserved_micro=Micro(GB_RATE * 2),
    scheduled_at=LATER,
)
STALE = NOW - timedelta(seconds=60)


async def completed_campaign(repo: CampaignsDynamoRepo) -> Campaign:
    campaign = list_campaign()
    await repo.put_draft(ACCOUNT_ID, campaign)
    await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
    await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
    await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.REFUSED, NOW)
    await repo.complete(ACCOUNT_ID, campaign.campaign_id, COUNTED, NOW)
    return campaign


async def test_put_draft_is_put_if_absent() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()

        first = await repo.put_draft(ACCOUNT_ID, campaign)
        second = await repo.put_draft(ACCOUNT_ID, campaign)
        assert (first, second) == (True, False)


async def test_get_round_trips_the_row() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        assert await repo.get(ACCOUNT_ID, campaign.campaign_id) == campaign


async def test_get_answers_none_for_an_unknown_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        assert await CampaignsDynamoRepo(table).get(ACCOUNT_ID, "missing") is None


async def test_claim_draft_flips_once() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        first = await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
        second = await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
        claimed = await repo.get(ACCOUNT_ID, campaign.campaign_id)
        assert (first, second, claimed and claimed.status) == (True, False, CampaignStatus.SENDING)


async def test_add_count_adds_one_and_returns_the_new_row() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
        updated = await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
        assert updated.counts == CampaignCounts(recipients=2, sent=2)


async def test_complete_flips_sending_to_sent_once() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.REFUSED, NOW)

        first = await repo.complete(ACCOUNT_ID, campaign.campaign_id, COUNTED, NOW)
        second = await repo.complete(ACCOUNT_ID, campaign.campaign_id, COUNTED, NOW)
        assert (first, second) == (True, False)


async def test_complete_leaves_the_campaign_unsettled() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.REFUSED, NOW)
        await repo.complete(ACCOUNT_ID, campaign.campaign_id, COUNTED, NOW)

        completed = await repo.get(ACCOUNT_ID, campaign.campaign_id)
        assert completed is not None
        assert (completed.status, completed.settled_micro, completed.completed_at) == (
            CampaignStatus.SENT,
            None,
            NOW,
        )


async def test_mark_settled_records_the_settlement_once() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = await completed_campaign(repo)

        first = await repo.mark_settled(ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE))
        second = await repo.mark_settled(ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE))

        settled = await repo.get(ACCOUNT_ID, campaign.campaign_id)
        assert settled is not None
        assert (first, second, settled.settled_micro) == (True, False, GB_RATE)


async def test_mark_settled_refuses_a_campaign_that_is_still_sending() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)

        assert await repo.mark_settled(ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE)) is False


async def test_complete_needs_the_observed_counts() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)

        assert await repo.complete(ACCOUNT_ID, campaign.campaign_id, COUNTED, NOW) is False


async def test_list_pages_newest_first() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        ids = []
        for _ in range(PAGE_SIZE + 1):
            campaign = draft_campaign()
            await repo.put_draft(ACCOUNT_ID, campaign)
            ids.append(campaign.campaign_id)

        first = await repo.page(ACCOUNT_ID, CampaignQuery())
        second = await repo.page(ACCOUNT_ID, CampaignQuery(cursor=first.cursor))
        assert (
            [c.campaign_id for c in first.items],
            [c.campaign_id for c in second.items],
            second.cursor,
        ) == (ids[:0:-1], [ids[0]], None)


async def test_list_filters_by_product_and_name() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        await repo.put_draft(ACCOUNT_ID, list_campaign())

        matching = await repo.page(ACCOUNT_ID, CampaignQuery(kind=Product.SMS, q="Hello"))
        other = await repo.page(ACCOUNT_ID, CampaignQuery(kind=Product.MMS))
        assert (len(matching.items), len(other.items)) == (1, 0)


async def test_save_draft_replaces_a_draft_only() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        renamed = campaign.model_copy(update={"name": "Renamed"})
        saved = await repo.save_draft(ACCOUNT_ID, renamed)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)
        after_claim = await repo.save_draft(ACCOUNT_ID, renamed)
        assert (saved, after_claim) == (True, False)


async def test_save_draft_refuses_an_absent_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        assert await CampaignsDynamoRepo(table).save_draft(ACCOUNT_ID, list_campaign()) is False


async def test_delete_draft_removes_a_draft_only() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)

        refused = await repo.delete_draft(ACCOUNT_ID, campaign.campaign_id)
        assert (refused, await repo.get(ACCOUNT_ID, campaign.campaign_id) is not None) == (
            False,
            True,
        )


async def test_schedule_writes_the_due_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        due = await repo.due(LATER, 25)
        assert due == [CampaignRef(account_id=ACCOUNT_ID, campaign_id=campaign.campaign_id)]


async def test_schedule_records_the_confirmation() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)

        scheduled = await repo.get(ACCOUNT_ID, campaign.campaign_id)
        assert scheduled is not None
        assert (scheduled.status, scheduled.scheduled_at, scheduled.reserved_micro) == (
            CampaignStatus.SCHEDULED,
            LATER,
            GB_RATE * 2,
        )


async def test_a_campaign_is_not_due_before_its_time() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)

        assert await repo.due(LATER - timedelta(milliseconds=1), 25) == []


async def test_a_campaign_scheduled_for_now_is_due_now() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, replace(PLAN, scheduled_at=NOW))

        assert len(await repo.due(NOW, 25)) == 1


async def test_schedule_flips_a_draft_only() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        first = await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        second = await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        assert (first, second) == (True, False)


async def test_claim_due_flips_a_scheduled_campaign_once() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)

        first = await repo.claim_due(ACCOUNT_ID, campaign.campaign_id, LATER, STALE)
        second = await repo.claim_due(ACCOUNT_ID, campaign.campaign_id, LATER, STALE)
        assert (first, second) == (True, False)


async def test_claim_due_resumes_a_stale_sending_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.claim_due(ACCOUNT_ID, campaign.campaign_id, NOW, STALE)

        resumed = await repo.claim_due(
            ACCOUNT_ID, campaign.campaign_id, LATER, NOW + timedelta(seconds=1)
        )
        assert resumed is True


async def test_advance_fanout_counts_the_batch_and_keeps_the_cursor() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)

        step = FanoutStep(at=NOW, cursor="10", queued=9, recipients=25, refused=1)
        row = await repo.advance_fanout(ACCOUNT_ID, campaign.campaign_id, step)
        assert (row.counts, row.fanout_cursor) == (
            CampaignCounts(queued=9, recipients=25, refused=1),
            "10",
        )


async def test_the_last_batch_clears_the_cursor_and_the_due_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.advance_fanout(
            ACCOUNT_ID,
            campaign.campaign_id,
            FanoutStep(at=NOW, cursor="10", queued=10, recipients=15, refused=0),
        )

        row = await repo.advance_fanout(
            ACCOUNT_ID,
            campaign.campaign_id,
            FanoutStep(at=NOW, cursor=None, queued=5, recipients=15, refused=0),
        )
        assert (row.fanout_cursor, await repo.due(LATER, 25)) == (None, [])


async def test_cancel_scheduled_settles_and_leaves_the_due_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)

        cancelled = await repo.cancel_scheduled(ACCOUNT_ID, campaign.campaign_id, NOW)
        row = await repo.get(ACCOUNT_ID, campaign.campaign_id)
        assert row is not None
        assert (cancelled, row.status, row.settled_micro, await repo.due(LATER, 25)) == (
            True,
            CampaignStatus.CANCELLED,
            0,
            [],
        )


async def test_cancel_scheduled_loses_to_a_claim() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.claim_due(ACCOUNT_ID, campaign.campaign_id, LATER, STALE)

        assert await repo.cancel_scheduled(ACCOUNT_ID, campaign.campaign_id, NOW) is False


async def test_the_last_batch_moves_the_campaign_to_the_sending_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.advance_fanout(
            ACCOUNT_ID,
            campaign.campaign_id,
            FanoutStep(at=NOW, cursor=None, queued=2, recipients=2, refused=0),
        )

        assert await repo.stuck(NOW + timedelta(milliseconds=1), 25) == [
            CampaignRef(account_id=ACCOUNT_ID, campaign_id=campaign.campaign_id)
        ]


async def test_a_counter_bumps_the_progress_key() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.advance_fanout(
            ACCOUNT_ID,
            campaign.campaign_id,
            FanoutStep(at=NOW, cursor=None, queued=2, recipients=2, refused=0),
        )
        await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, LATER)

        assert (
            await repo.stuck(LATER, 25),
            len(await repo.stuck(LATER + timedelta(milliseconds=1), 25)),
        ) == ([], 1)


async def test_complete_keeps_the_campaign_on_the_sending_index_until_it_is_settled() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = await completed_campaign(repo)

        assert await repo.stuck(LATER, 25) == [
            CampaignRef(account_id=ACCOUNT_ID, campaign_id=campaign.campaign_id)
        ]


async def test_mark_settled_takes_the_campaign_off_the_sending_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = await completed_campaign(repo)

        await repo.mark_settled(ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE))

        assert await repo.stuck(LATER, 25) == []


async def test_a_campaign_claimed_from_the_due_index_settles_onto_the_sending_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.schedule(ACCOUNT_ID, campaign.campaign_id, PLAN)
        await repo.claim_due(ACCOUNT_ID, campaign.campaign_id, NOW, STALE)

        await repo.complete(ACCOUNT_ID, campaign.campaign_id, CampaignCounts(recipients=0), NOW)

        assert (await repo.due(LATER, 25), await repo.stuck(LATER, 25)) == (
            [],
            [CampaignRef(account_id=ACCOUNT_ID, campaign_id=campaign.campaign_id)],
        )


async def test_claim_draft_puts_an_inline_send_on_the_sending_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = draft_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)

        assert len(await repo.stuck(LATER, 25)) == 1


async def test_clear_index_takes_a_finished_campaign_off_the_index() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)
        await repo.claim_draft(ACCOUNT_ID, campaign.campaign_id, NOW)

        cleared = await repo.clear_index(ACCOUNT_ID, campaign.campaign_id)
        assert (cleared, await repo.stuck(LATER, 25)) == (True, [])


async def test_clear_index_writes_nothing_for_an_absent_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)

        cleared = await repo.clear_index(ACCOUNT_ID, "missing")
        assert (cleared, await repo.get(ACCOUNT_ID, "missing")) == (False, None)


async def test_a_counter_bumps_a_freshly_created_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        counted = await repo.add_count(ACCOUNT_ID, campaign.campaign_id, CampaignCounter.SENT, NOW)
        assert counted.counts == CampaignCounts(recipients=0, sent=1)


async def test_a_batch_counts_a_freshly_created_campaign() -> None:
    async with local_repo_table("campaigns") as table:
        repo = CampaignsDynamoRepo(table)
        campaign = list_campaign()
        await repo.put_draft(ACCOUNT_ID, campaign)

        counted = await repo.advance_fanout(
            ACCOUNT_ID,
            campaign.campaign_id,
            FanoutStep(at=NOW, cursor="10", queued=9, recipients=25, refused=1),
        )
        assert counted.counts == CampaignCounts(queued=9, recipients=25, refused=1)
