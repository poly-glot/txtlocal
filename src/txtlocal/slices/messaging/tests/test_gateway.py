import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

import aioboto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from txtlocal.shared.bus import Topic
from txtlocal.shared.errors import AppError, BadRequest, Internal, RateLimited, Upstream
from txtlocal.shared.phone import E164
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.messaging.gateway import (
    FAKE_PREFIX,
    INVALID_MEDIA_KEY,
    AwsSmsGateway,
    FakeSmsGateway,
    LocalMediaStorage,
    MediaFile,
    Receipt,
    S3MediaStorage,
    epoch_millis,
    product_for,
)
from txtlocal.slices.messaging.model import Product, ProviderEvent
from txtlocal.slices.messaging.tests.support import (
    DESTINATION,
    FAKE_CODE,
    NOW,
    clock_at,
    dispatch,
    media_dispatch,
)

if TYPE_CHECKING:
    from types_aiobotocore_pinpoint_sms_voice_v2 import PinpointSMSVoiceV2Client

REGION = "eu-west-2"
CONFIGURATION_SET = "txtlocal"
PROTECT_CONFIGURATION = "protect-1"
VERIFIED_ID = "vdn-1"
PROVIDER_MESSAGE = "the provider message"
EVENT_KEYS = frozenset(
    {
        "context",
        "destinationPhoneNumber",
        "eventTimestamp",
        "eventType",
        "isoCountryCode",
        "messageId",
        "messageStatus",
        "totalMessageParts",
        "totalMessagePrice",
    }
)


def fake() -> tuple[FakeSmsGateway, RecordingBus]:
    bus = RecordingBus()
    return FakeSmsGateway(bus=bus, clock=clock_at(NOW)), bus


def published_event(bus: RecordingBus) -> dict[str, object]:
    topic, body = bus.published[0]
    assert topic is Topic.SMS_EVENTS
    event: dict[str, object] = json.loads(body)
    return event


@pytest.mark.parametrize(
    ("destination", "event_type"),
    [
        ("+447400123100", "TEXT_INVALID"),
        ("+447400123101", "TEXT_CARRIER_UNREACHABLE"),
        ("+447400123102", "TEXT_BLOCKED"),
        ("+447400123103", "TEXT_SPAM"),
        ("+447400123104", "TEXT_DELIVERED"),
        ("+447400123199", "TEXT_DELIVERED"),
    ],
    ids=[
        "00-invalid",
        "01-carrier-unreachable",
        "02-blocked",
        "03-spam",
        "04-delivered",
        "99-delivered",
    ],
)
async def test_fake_gateway_chooses_the_event_by_the_last_two_digits(
    destination: str, event_type: str
) -> None:
    gateway, bus = fake()

    await gateway.send_text(dispatch(E164(destination)))

    assert published_event(bus)["eventType"] == event_type


async def test_fake_gateway_receipt_is_synthetic() -> None:
    gateway, _ = fake()

    receipt = await gateway.send_text(dispatch())

    assert receipt.accepted_at == NOW
    assert receipt.provider_message_id.startswith(FAKE_PREFIX)


async def test_fake_gateway_event_is_provider_shaped_without_the_number() -> None:
    gateway, bus = fake()

    receipt = await gateway.send_text(dispatch())
    event = published_event(bus)

    assert set(event) == EVENT_KEYS
    assert event["destinationPhoneNumber"] == "redacted"
    assert event["context"] == {"messageKey": "pk|sk"}
    assert event["messageId"] == receipt.provider_message_id
    assert event["messageStatus"] == "DELIVERED"
    assert event["isoCountryCode"] == "GB"
    assert event["totalMessageParts"] == 1
    assert event["eventTimestamp"] == epoch_millis(NOW)


async def test_fake_gateway_event_parses_as_a_provider_event() -> None:
    gateway, bus = fake()

    await gateway.send_text(dispatch())
    event = ProviderEvent.model_validate_json(bus.published[0][1])

    assert event.event_timestamp == NOW
    assert event.context["messageKey"] == "pk|sk"


async def test_fake_gateway_media_events_use_the_media_channel() -> None:
    gateway, bus = fake()
    media = media_dispatch(E164("+12065550104"))

    await gateway.send_media(media)

    assert published_event(bus)["eventType"] == "MEDIA_DELIVERED"


@pytest.mark.parametrize(
    ("started", "code", "verified"),
    [(True, FAKE_CODE, True), (True, "123456", False), (False, FAKE_CODE, False)],
    ids=["fixed-code-after-start", "wrong-code", "code-without-start"],
)
async def test_fake_gateway_verification(started: bool, code: str, verified: bool) -> None:
    gateway, _ = fake()
    if started:
        await gateway.start_verification(DESTINATION)

    assert await gateway.check_verification(DESTINATION, code) is verified


@pytest.fixture
async def client() -> AsyncIterator[PinpointSMSVoiceV2Client]:
    async with aioboto3.Session().client("pinpoint-sms-voice-v2", region_name=REGION) as client:
        yield client


def aws(client: PinpointSMSVoiceV2Client, *, dry_run: bool = False) -> AwsSmsGateway:
    return AwsSmsGateway(
        client=client,
        clock=clock_at(NOW),
        configuration_set=CONFIGURATION_SET,
        dry_run=dry_run,
        protect_configuration_id=PROTECT_CONFIGURATION,
    )


async def test_aws_send_text_is_one_call_carrying_every_field(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "send_text_message",
            {"MessageId": "aws-1"},
            {
                "ConfigurationSetName": CONFIGURATION_SET,
                "Context": {"messageKey": "pk|sk"},
                "DestinationPhoneNumber": DESTINATION,
                "DryRun": True,
                "MaxPrice": "0.10",
                "MessageBody": "Hello",
                "MessageType": "PROMOTIONAL",
                "OriginationIdentity": "pool-1",
                "ProtectConfigurationId": PROTECT_CONFIGURATION,
                "TimeToLive": 3_600,
            },
        )

        receipt = await aws(client, dry_run=True).send_text(dispatch())

        stubber.assert_no_pending_responses()
    assert receipt == Receipt(accepted_at=NOW, provider_message_id="aws-1")


async def test_aws_send_media_is_one_call_with_the_media_urls(
    client: PinpointSMSVoiceV2Client,
) -> None:
    media = media_dispatch(subject="Hi")
    with Stubber(client) as stubber:
        stubber.add_response(
            "send_media_message",
            {"MessageId": "aws-2"},
            {
                "ConfigurationSetName": CONFIGURATION_SET,
                "Context": {"messageKey": "pk|sk"},
                "DestinationPhoneNumber": DESTINATION,
                "DryRun": False,
                "MaxPrice": "0.10",
                "MediaUrls": ["https://x/y.png"],
                "MessageBody": "Hello",
                "OriginationIdentity": "pool-1",
                "ProtectConfigurationId": PROTECT_CONFIGURATION,
                "TimeToLive": 3_600,
            },
        )

        receipt = await aws(client).send_media(media)

        stubber.assert_no_pending_responses()
    assert receipt.provider_message_id == "aws-2"


@pytest.mark.parametrize(
    ("code", "modeled", "error_type", "message"),
    [
        ("ThrottlingException", {}, Upstream, "ThrottlingException"),
        ("InternalServerException", {}, Upstream, "InternalServerException"),
        ("ValidationException", {"Reason": "INVALID_PARAMETER"}, BadRequest, "INVALID_PARAMETER"),
        (
            "ResourceNotFoundException",
            {"ResourceId": "pool-1", "ResourceType": "pool"},
            BadRequest,
            PROVIDER_MESSAGE,
        ),
        ("AccessDeniedException", {"Reason": "ACCOUNT_DISABLED"}, BadRequest, "ACCOUNT_DISABLED"),
        (
            "ConflictException",
            {"Reason": "DESTINATION_COUNTRY_BLOCKED_BY_PROTECT_CONFIGURATION"},
            BadRequest,
            "DESTINATION_COUNTRY_BLOCKED_BY_PROTECT_CONFIGURATION",
        ),
        (
            "ServiceQuotaExceededException",
            {"Reason": "MONTHLY_SPEND_LIMIT_REACHED_FOR_TEXT"},
            RateLimited,
            "MONTHLY_SPEND_LIMIT_REACHED_FOR_TEXT",
        ),
        ("ValidationException", {}, BadRequest, PROVIDER_MESSAGE),
        ("BrandNewException", {}, Upstream, "BrandNewException"),
    ],
    ids=[
        "throttling-is-upstream",
        "internal-server-is-upstream",
        "validation-is-bad-request-with-the-reason",
        "resource-not-found-is-bad-request-with-the-message",
        "access-denied-is-bad-request",
        "conflict-is-bad-request",
        "quota-is-rate-limited",
        "missing-reason-falls-back-to-the-message",
        "unknown-code-is-upstream",
    ],
)
async def test_aws_provider_errors_map_per_the_spec(
    client: PinpointSMSVoiceV2Client,
    code: str,
    modeled: dict[str, str],
    error_type: type[AppError],
    message: str,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_client_error(
            "send_text_message",
            modeled_fields=modeled,
            service_error_code=code,
            service_message=PROVIDER_MESSAGE,
        )

        with pytest.raises(error_type) as caught:
            await aws(client).send_text(dispatch())

    assert str(caught.value) == message


class DisconnectedClient:
    async def send_text_message(self, **request: object) -> NoReturn:
        raise EndpointConnectionError(endpoint_url=str(len(request)))


async def test_aws_connection_errors_are_upstream() -> None:
    gateway = aws(cast("PinpointSMSVoiceV2Client", DisconnectedClient()))

    with pytest.raises(Upstream) as caught:
        await gateway.send_text(dispatch())

    assert str(caught.value) == "EndpointConnectionError"


def verified_number(verified_id: str, status: str = "PENDING") -> dict[str, object]:
    return {
        "CreatedTimestamp": NOW,
        "DestinationPhoneNumber": DESTINATION,
        "Status": status,
        "VerifiedDestinationNumberArn": f"arn:aws:sms-voice::1:vdn/{verified_id}",
        "VerifiedDestinationNumberId": verified_id,
    }


def verified_numbers(*ids: str) -> dict[str, list[dict[str, object]]]:
    return {"VerifiedDestinationNumbers": [verified_number(verified_id) for verified_id in ids]}


async def test_aws_start_verification_registers_a_new_destination_then_sends_the_code(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_verified_destination_numbers",
            verified_numbers(),
            {"DestinationPhoneNumbers": [DESTINATION]},
        )
        stubber.add_response(
            "create_verified_destination_number",
            verified_number(VERIFIED_ID),
            {"DestinationPhoneNumber": DESTINATION},
        )
        stubber.add_response(
            "send_destination_number_verification_code",
            {"MessageId": "code-1"},
            {"VerificationChannel": "TEXT", "VerifiedDestinationNumberId": VERIFIED_ID},
        )

        await aws(client).start_verification(DESTINATION)

        stubber.assert_no_pending_responses()


async def test_aws_start_verification_reuses_a_known_destination(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_verified_destination_numbers",
            verified_numbers(VERIFIED_ID),
            {"DestinationPhoneNumbers": [DESTINATION]},
        )
        stubber.add_response(
            "send_destination_number_verification_code",
            {"MessageId": "code-2"},
            {"VerificationChannel": "TEXT", "VerifiedDestinationNumberId": VERIFIED_ID},
        )

        await aws(client).start_verification(DESTINATION)

        stubber.assert_no_pending_responses()


async def test_aws_check_verification_accepts_a_verified_status(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_verified_destination_numbers",
            verified_numbers(VERIFIED_ID),
            {"DestinationPhoneNumbers": [DESTINATION]},
        )
        stubber.add_response(
            "verify_destination_number",
            verified_number(VERIFIED_ID, status="VERIFIED"),
            {"VerificationCode": "123456", "VerifiedDestinationNumberId": VERIFIED_ID},
        )

        assert await aws(client).check_verification(DESTINATION, "123456") is True


async def test_aws_check_verification_refuses_a_wrong_code(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_verified_destination_numbers",
            verified_numbers(VERIFIED_ID),
            {"DestinationPhoneNumbers": [DESTINATION]},
        )
        stubber.add_client_error(
            "verify_destination_number",
            modeled_fields={"Reason": "VERIFICATION_CODE_MISMATCH"},
            service_error_code="ValidationException",
        )

        assert await aws(client).check_verification(DESTINATION, "000000") is False


async def test_aws_check_verification_refuses_an_unknown_destination(
    client: PinpointSMSVoiceV2Client,
) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_verified_destination_numbers",
            verified_numbers(),
            {"DestinationPhoneNumbers": [DESTINATION]},
        )

        assert await aws(client).check_verification(DESTINATION, "000000") is False


@pytest.mark.parametrize(
    ("requested", "country", "expected"),
    [
        (Product.SMS, "GB", Product.SMS),
        (Product.SMS, "US", Product.SMS),
        (Product.MMS, "US", Product.MMS),
        (Product.MMS, "CA", Product.MMS),
        (Product.MMS, "GB", Product.MMS_AS_LINK),
    ],
    ids=[
        "sms-stays-sms-in-gb",
        "sms-stays-sms-in-us",
        "mms-stays-mms-in-us",
        "mms-stays-mms-in-ca",
        "mms-becomes-a-link-outside-us-ca",
    ],
)
def test_product_for(requested: Product, country: str, expected: Product) -> None:
    assert product_for(requested, country) is expected


async def test_local_media_storage_round_trips_an_upload(tmp_path: Path) -> None:
    storage = LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test")

    upload = await storage.upload_url("image/png")
    assert upload.key.endswith(".png")
    assert (
        upload.upload_url
        == storage.public_url(upload.key)
        == f"https://txtlocal.test/api/app/messaging/media/{upload.key}"
    )

    await storage.store(upload.key, "image/png", b"pixels")
    assert await storage.read(upload.key) == MediaFile(body=b"pixels", content_type="image/png")


async def test_local_media_storage_read_of_an_unknown_key_is_none(tmp_path: Path) -> None:
    storage = LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test")
    assert await storage.read(f"{uuid.uuid7()}.png") is None


async def test_local_media_storage_refuses_a_content_type_that_does_not_match_the_key(
    tmp_path: Path,
) -> None:
    storage = LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test")
    upload = await storage.upload_url("image/png")

    with pytest.raises(BadRequest) as caught:
        await storage.store(upload.key, "image/gif", b"pixels")
    assert str(caught.value) == INVALID_MEDIA_KEY


@pytest.mark.parametrize(
    "key",
    ["../../etc/passwd", "no-extension", "media.exe", ""],
    ids=["path-traversal", "missing-extension", "disallowed-extension", "empty"],
)
async def test_local_media_storage_refuses_an_unsafe_key(tmp_path: Path, key: str) -> None:
    storage = LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test")
    with pytest.raises(BadRequest) as caught:
        await storage.read(key)
    assert str(caught.value) == INVALID_MEDIA_KEY


async def presign_stub(**_kwargs: object) -> str:
    return "https://sites-bucket.s3.amazonaws.com/signed"


async def test_s3_media_storage_presigns_a_put_under_its_prefix() -> None:
    calls: list[dict[str, object]] = []

    async def presign(**kwargs: object) -> str:
        calls.append(kwargs)
        return "https://sites-bucket.s3.amazonaws.com/signed"

    storage = S3MediaStorage(
        bucket="sites", prefix="txtlocal/media/", presign=presign, site="https://txtlocal.example"
    )

    upload = await storage.upload_url("image/jpeg")
    assert upload.upload_url == "https://sites-bucket.s3.amazonaws.com/signed"
    assert upload.key.endswith(".jpg")
    params = cast("dict[str, object]", calls[0]["Params"])
    assert params["Key"] == f"txtlocal/media/{upload.key}"


def test_s3_media_storage_public_url_serves_from_the_site_under_its_prefix() -> None:
    storage = S3MediaStorage(
        bucket="sites",
        prefix="txtlocal/media/",
        presign=presign_stub,
        site="https://txtlocal.example",
    )
    assert storage.public_url("a.png") == "https://txtlocal.example/txtlocal/media/a.png"


async def test_s3_media_storage_never_serves_bytes_directly() -> None:
    storage = S3MediaStorage(
        bucket="sites",
        prefix="txtlocal/media/",
        presign=presign_stub,
        site="https://txtlocal.example",
    )
    with pytest.raises(Internal):
        await storage.store("a.png", "image/png", b"x")
    with pytest.raises(Internal):
        await storage.read("a.png")
