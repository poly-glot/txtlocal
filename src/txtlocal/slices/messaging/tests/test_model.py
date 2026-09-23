import uuid
from datetime import timedelta
from random import Random

import pytest

from txtlocal.slices.messaging.model import (
    InboundMessage,
    MessageKey,
    message_key_for,
    minted_at,
    uuid7_at,
)
from txtlocal.slices.messaging.tests.support import ACCOUNT, NOW


def test_uuid7_at_is_a_version_seven_uuid_carrying_the_instant() -> None:
    minted = uuid7_at(NOW, Random(3))

    assert (minted.version, minted.variant) == (7, uuid.RFC_4122)
    assert minted_at(str(minted)) == NOW


def test_uuid7_at_sorts_by_time() -> None:
    earlier = str(uuid7_at(NOW, Random(9)))
    later = str(uuid7_at(NOW + timedelta(milliseconds=1), Random(1)))

    assert earlier < later


def test_message_key_for_places_the_row_in_its_month_partition() -> None:
    message_id = str(uuid7_at(NOW, Random(3)))

    key = message_key_for(ACCOUNT, message_id)

    assert key == MessageKey(
        pk="txtlocal#ACCOUNT#acct-1#MSG#2026-09", sk=f"2026-09-19T12:00:00.000Z#{message_id}"
    )


def test_message_key_round_trips_through_its_text_form() -> None:
    key = MessageKey(pk="txtlocal#ACCOUNT#a#MSG#2026-09", sk="2026-09-19T12:00:00.000Z#id")

    assert MessageKey.parse(str(key)) == key


@pytest.mark.parametrize(
    "text", ["", "no-separator", "|sk-only", "pk-only|"], ids=["empty", "plain", "no-pk", "no-sk"]
)
def test_message_key_parse_rejects_malformed_text(text: str) -> None:
    assert MessageKey.parse(text) is None


def test_inbound_message_round_trips_camel_case_and_defaults_the_previous_id() -> None:
    wire = {
        "body": "STOP",
        "destination": "+447400900100",
        "inboundMessageId": "aws-inbound-1",
        "keyword": "STOP",
        "peer": "+447400123105",
        "receivedAt": "2026-09-19T12:00:00.000Z",
    }

    parsed = InboundMessage.model_validate(wire)

    assert parsed.previous_published_message_id is None
    assert parsed.model_dump(by_alias=True)["inboundMessageId"] == "aws-inbound-1"
