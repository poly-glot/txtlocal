import json
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, assert_never

from botocore.exceptions import BotoCoreError, ClientError

from txtlocal.shared.bus import Bus, Topic
from txtlocal.shared.errors import AppError, BadRequest, Internal, RateLimited, Upstream
from txtlocal.shared.phone import E164, country_of
from txtlocal.shared.table import error_code
from txtlocal.slices.messaging.model import EPOCH, MESSAGE_KEY, MILLISECOND, MessageType, Product
from txtlocal.slices.messaging.segments import encoding_of, segments_of

if TYPE_CHECKING:
    from types_aiobotocore_pinpoint_sms_voice_v2 import PinpointSMSVoiceV2Client
    from types_aiobotocore_pinpoint_sms_voice_v2.literals import MessageTypeType

    from txtlocal.shared.clock import Clock

PROVIDER_MAX_BODY_CHARS = 1_600
MMS_COUNTRIES = frozenset({"CA", "US"})
FAKE_PREFIX = "fake-"
FAKE_VERIFICATION_CODE = "000000"
REDACTED = "redacted"
TEXT: Final = "TEXT"
MEDIA: Final = "MEDIA"
DELIVERED = "DELIVERED"
VERIFIED = "VERIFIED"
QUOTA_CODE = "ServiceQuotaExceededException"
REFUSAL_CODES = frozenset(
    {
        "AccessDeniedException",
        "ConflictException",
        "ResourceNotFoundException",
        "ValidationException",
    }
)
FAKE_OUTCOME_BY_SUFFIX: Mapping[str, str] = {
    "00": "INVALID",
    "01": "CARRIER_UNREACHABLE",
    "02": "BLOCKED",
    "03": "SPAM",
}


@dataclass(frozen=True, slots=True)
class Capabilities:
    max_body_chars: int
    mms_countries: frozenset[str]
    two_way: bool


@dataclass(frozen=True, slots=True)
class Dispatch:
    body: str
    destination: E164
    max_price_usd: str
    message_key: str
    message_type: MessageType
    origination: str
    ttl_seconds: int


@dataclass(frozen=True, slots=True)
class MediaDispatch(Dispatch):
    media_urls: tuple[str, ...]
    subject: str


@dataclass(frozen=True, slots=True)
class Receipt:
    accepted_at: datetime
    provider_message_id: str


class SmsGateway(Protocol):
    @property
    def capabilities(self) -> Capabilities: ...

    async def send_text(self, dispatch: Dispatch) -> Receipt: ...

    async def send_media(self, dispatch: MediaDispatch) -> Receipt: ...

    async def start_verification(self, destination: E164) -> None: ...

    async def check_verification(self, destination: E164, code: str) -> bool: ...


PROVIDER_CAPABILITIES = Capabilities(
    max_body_chars=PROVIDER_MAX_BODY_CHARS, mms_countries=MMS_COUNTRIES, two_way=True
)

MEDIA_PATH_PREFIX = "/api/app/messaging/media/"
DEFAULT_MEDIA_SITE = "http://localhost:3000"
MEDIA_UPLOAD_TTL_SECONDS = 300
INVALID_MEDIA_KEY = "That media link is not valid"
MEDIA_SERVED_DIRECTLY = "media is served directly from storage in this mode"
MEDIA_KEY_PATTERN = re.compile(r"\A[0-9a-f-]{16,40}\.(?:gif|jpe?g|png)\Z")
MEDIA_EXTENSIONS: Mapping[str, str] = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
MEDIA_CONTENT_TYPES: Mapping[str, str] = {
    extension: content_type for content_type, extension in MEDIA_EXTENSIONS.items()
}


def product_for(requested: Product, country: str) -> Product:
    if requested is Product.SMS:
        return Product.SMS
    return Product.MMS if country in MMS_COUNTRIES else Product.MMS_AS_LINK


@dataclass(frozen=True, slots=True)
class MediaUpload:
    key: str
    upload_url: str


@dataclass(frozen=True, slots=True)
class MediaFile:
    body: bytes
    content_type: str


class MediaStorage(Protocol):
    async def upload_url(self, content_type: str) -> MediaUpload: ...

    def public_url(self, key: str) -> str: ...

    async def store(self, key: str, content_type: str, body: bytes) -> None: ...

    async def read(self, key: str) -> MediaFile | None: ...


@dataclass(frozen=True, slots=True)
class LocalMediaStorage:
    directory: Path
    site: str

    async def upload_url(self, content_type: str) -> MediaUpload:
        key = f"{uuid.uuid7()}{MEDIA_EXTENSIONS[content_type]}"
        return MediaUpload(key=key, upload_url=self.public_url(key))

    def public_url(self, key: str) -> str:
        return f"{self.site}{MEDIA_PATH_PREFIX}{key}"

    async def store(self, key: str, content_type: str, body: bytes) -> None:
        path = self._path_for(key)
        if MEDIA_EXTENSIONS.get(content_type) != path.suffix:
            raise BadRequest(INVALID_MEDIA_KEY)

        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    async def read(self, key: str) -> MediaFile | None:
        path = self._path_for(key)
        if not path.is_file():
            return None
        return MediaFile(body=path.read_bytes(), content_type=MEDIA_CONTENT_TYPES[path.suffix])

    def _path_for(self, key: str) -> Path:
        if not MEDIA_KEY_PATTERN.fullmatch(key):
            raise BadRequest(INVALID_MEDIA_KEY)
        return self.directory / key


@dataclass(frozen=True, slots=True)
class S3MediaStorage:
    bucket: str
    presign: Callable[..., Awaitable[str]]
    prefix: str
    site: str

    async def upload_url(self, content_type: str) -> MediaUpload:
        key = f"{uuid.uuid7()}{MEDIA_EXTENSIONS[content_type]}"
        url = await self.presign(
            ClientMethod="put_object",
            ExpiresIn=MEDIA_UPLOAD_TTL_SECONDS,
            Params={
                "Bucket": self.bucket,
                "ContentType": content_type,
                "Key": f"{self.prefix}{key}",
            },
        )
        return MediaUpload(key=key, upload_url=url)

    def public_url(self, key: str) -> str:
        return f"{self.site}/{self.prefix}{key}"

    async def store(self, key: str, content_type: str, body: bytes) -> None:
        raise Internal(f"{MEDIA_SERVED_DIRECTLY}: {key} ({len(body)} bytes, {content_type})")

    async def read(self, key: str) -> MediaFile | None:
        raise Internal(f"{MEDIA_SERVED_DIRECTLY}: {key}")


def reason_of(error: ClientError) -> str:
    response: Mapping[str, object] = error.response
    reason = response.get("Reason")
    if isinstance(reason, str):
        return reason

    details = response.get("Error")
    message = details.get("Message") if isinstance(details, dict) else None
    return str(message) if message else error_code(error)


def provider_error(error: ClientError) -> AppError:
    code = error_code(error)
    if code in REFUSAL_CODES:
        return BadRequest(reason_of(error))
    if code == QUOTA_CODE:
        return RateLimited(reason_of(error))
    return Upstream(code)


@contextmanager
def provider_errors() -> Iterator[None]:
    try:
        yield
    except ClientError as error:
        raise provider_error(error) from error
    except BotoCoreError as error:
        raise Upstream(type(error).__name__) from error


def provider_message_type(message_type: MessageType) -> MessageTypeType:
    match message_type:
        case MessageType.PROMOTIONAL:
            return "PROMOTIONAL"
        case MessageType.TRANSACTIONAL:
            return "TRANSACTIONAL"
        case _:
            assert_never(message_type)


@dataclass(frozen=True, slots=True)
class AwsSmsGateway:
    client: PinpointSMSVoiceV2Client
    clock: Clock
    configuration_set: str
    dry_run: bool
    protect_configuration_id: str
    capabilities: ClassVar[Capabilities] = PROVIDER_CAPABILITIES

    async def send_text(self, dispatch: Dispatch) -> Receipt:
        with provider_errors():
            result = await self.client.send_text_message(
                ConfigurationSetName=self.configuration_set,
                Context={MESSAGE_KEY: dispatch.message_key},
                DestinationPhoneNumber=dispatch.destination,
                DryRun=self.dry_run,
                MaxPrice=dispatch.max_price_usd,
                MessageBody=dispatch.body,
                MessageType=provider_message_type(dispatch.message_type),
                OriginationIdentity=dispatch.origination,
                ProtectConfigurationId=self.protect_configuration_id,
                TimeToLive=dispatch.ttl_seconds,
            )
        return Receipt(accepted_at=self.clock(), provider_message_id=result["MessageId"])

    async def send_media(self, dispatch: MediaDispatch) -> Receipt:
        with provider_errors():
            result = await self.client.send_media_message(
                ConfigurationSetName=self.configuration_set,
                Context={MESSAGE_KEY: dispatch.message_key},
                DestinationPhoneNumber=dispatch.destination,
                DryRun=self.dry_run,
                MaxPrice=dispatch.max_price_usd,
                MediaUrls=list(dispatch.media_urls),
                MessageBody=dispatch.body,
                OriginationIdentity=dispatch.origination,
                ProtectConfigurationId=self.protect_configuration_id,
                TimeToLive=dispatch.ttl_seconds,
            )
        return Receipt(accepted_at=self.clock(), provider_message_id=result["MessageId"])

    async def start_verification(self, destination: E164) -> None:
        with provider_errors():
            verified_id = await self._verified_destination_id(destination)
            if verified_id is None:
                created = await self.client.create_verified_destination_number(
                    DestinationPhoneNumber=destination
                )
                verified_id = created["VerifiedDestinationNumberId"]

            await self.client.send_destination_number_verification_code(
                VerificationChannel=TEXT, VerifiedDestinationNumberId=verified_id
            )

    async def check_verification(self, destination: E164, code: str) -> bool:
        with provider_errors():
            verified_id = await self._verified_destination_id(destination)
        if verified_id is None:
            return False

        try:
            with provider_errors():
                result = await self.client.verify_destination_number(
                    VerificationCode=code, VerifiedDestinationNumberId=verified_id
                )
        except BadRequest:
            return False
        return result["Status"] == VERIFIED

    async def _verified_destination_id(self, destination: E164) -> str | None:
        described = await self.client.describe_verified_destination_numbers(
            DestinationPhoneNumbers=[destination]
        )
        numbers = described.get("VerifiedDestinationNumbers", [])
        return numbers[0]["VerifiedDestinationNumberId"] if numbers else None


def epoch_millis(moment: datetime) -> int:
    return (moment - EPOCH) // MILLISECOND


def fake_outcome(destination: E164) -> str:
    return FAKE_OUTCOME_BY_SUFFIX.get(destination[-2:], DELIVERED)


def fake_event(dispatch: Dispatch, receipt: Receipt, channel: str) -> str:
    outcome = fake_outcome(dispatch.destination)
    return json.dumps(
        {
            "context": {MESSAGE_KEY: dispatch.message_key},
            "destinationPhoneNumber": REDACTED,
            "eventTimestamp": epoch_millis(receipt.accepted_at),
            "eventType": f"{channel}_{outcome}",
            "isoCountryCode": country_of(dispatch.destination),
            "messageId": receipt.provider_message_id,
            "messageStatus": outcome,
            "totalMessageParts": segments_of(dispatch.body, encoding_of(dispatch.body)),
            "totalMessagePrice": 0,
        }
    )


@dataclass(frozen=True, slots=True)
class FakeSmsGateway:
    bus: Bus
    clock: Clock
    started: set[E164] = field(default_factory=set)
    capabilities: ClassVar[Capabilities] = PROVIDER_CAPABILITIES

    async def send_text(self, dispatch: Dispatch) -> Receipt:
        return await self._accept(dispatch, TEXT)

    async def send_media(self, dispatch: MediaDispatch) -> Receipt:
        return await self._accept(dispatch, MEDIA)

    async def start_verification(self, destination: E164) -> None:
        self.started.add(destination)

    async def check_verification(self, destination: E164, code: str) -> bool:
        return destination in self.started and code == FAKE_VERIFICATION_CODE

    async def _accept(self, dispatch: Dispatch, channel: str) -> Receipt:
        receipt = Receipt(
            accepted_at=self.clock(), provider_message_id=f"{FAKE_PREFIX}{uuid.uuid7()}"
        )
        await self.bus.publish(Topic.SMS_EVENTS, fake_event(dispatch, receipt, channel))
        return receipt
