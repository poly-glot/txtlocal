import functools
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit

import aioboto3
import httpx

from txtlocal.entrypoints.billing_charge import BillingCharge
from txtlocal.entrypoints.delivery_events import DeliveryEvents
from txtlocal.entrypoints.inbound import Inbound
from txtlocal.entrypoints.send_worker import SendWorker
from txtlocal.entrypoints.stripe_webhook import StripeWebhook
from txtlocal.entrypoints.stripe_webhook import build_local_router as build_local_stripe_router
from txtlocal.entrypoints.webhook_dispatch import WebhookDispatch
from txtlocal.shared import runtime
from txtlocal.shared.bus import Bus, Handler, LocalBus, Queue, SqsBus, Topic
from txtlocal.shared.clock import utc_now
from txtlocal.shared.email import SesEmail
from txtlocal.shared.errors import Internal
from txtlocal.shared.table import Table
from txtlocal.slices.analytics.repo import (
    AnalyticsDynamoRepo,
    AthenaClickQueries,
    ClickQueries,
    InsightsUsageQueries,
    LocalClickQueries,
    LocalUsageQueries,
    UsageQueries,
)
from txtlocal.slices.analytics.router import build_public_router as build_redirect_router
from txtlocal.slices.analytics.router import build_router as build_analytics_router
from txtlocal.slices.analytics.service import AnalyticsService
from txtlocal.slices.automation.repo import AutomationDynamoRepo
from txtlocal.slices.automation.router import build_email_demo_router, build_operator_router
from txtlocal.slices.automation.router import build_router as build_automation_router
from txtlocal.slices.automation.service import AutomationService, Email, LoggingEmail
from txtlocal.slices.billing.gateway import (
    CONNECT_TIMEOUT_SECONDS,
    TOTAL_TIMEOUT_SECONDS,
    PaymentGateway,
    StripeGateway,
)
from txtlocal.slices.billing.repo import BillingDynamoRepo
from txtlocal.slices.billing.router import build_router as build_billing_router
from txtlocal.slices.billing.service import BillingService
from txtlocal.slices.campaigns.repo import CampaignsDynamoRepo
from txtlocal.slices.campaigns.router import build_public_router as build_unsubscribe_router
from txtlocal.slices.campaigns.router import build_router as build_campaigns_router
from txtlocal.slices.campaigns.service import CampaignsService
from txtlocal.slices.contacts.repo import ContactsDynamoRepo
from txtlocal.slices.contacts.router import build_router as build_contacts_router
from txtlocal.slices.contacts.service import ContactsService
from txtlocal.slices.developer.repo import (
    DeveloperDynamoRepo,
    InsightsLogQueries,
    LocalLogQueries,
    LogQueries,
)
from txtlocal.slices.developer.router import build_public_router as build_developer_public_router
from txtlocal.slices.developer.router import build_router as build_developer_router
from txtlocal.slices.developer.service import DeveloperService
from txtlocal.slices.identity.auth import CognitoVerifier, LocalVerifier, TokenVerifier
from txtlocal.slices.identity.dev_idp import DevIdp, build_dev_idp_router
from txtlocal.slices.identity.repo import IdentityDynamoRepo, RateLimitsDynamoRepo
from txtlocal.slices.identity.router import build_router as build_identity_router
from txtlocal.slices.identity.service import (
    RATE_LIMIT_PER_MINUTE,
    Authenticated,
    CognitoUserDirectory,
    IdentityService,
    UserDirectory,
    api_user,
    authenticated,
)
from txtlocal.slices.inbox.repo import InboxDynamoRepo
from txtlocal.slices.inbox.router import build_demo_router
from txtlocal.slices.inbox.router import build_router as build_inbox_router
from txtlocal.slices.inbox.service import InboxService
from txtlocal.slices.messaging.gateway import (
    AwsSmsGateway,
    FakeSmsGateway,
    LocalMediaStorage,
    MediaStorage,
    S3MediaStorage,
    SmsGateway,
)
from txtlocal.slices.messaging.policy import SendPolicy
from txtlocal.slices.messaging.repo import MessagingDynamoRepo
from txtlocal.slices.messaging.router import build_router as build_messaging_router
from txtlocal.slices.messaging.service import MessagingService
from txtlocal.slices.senders.catalogue import (
    AwsNumberCatalogue,
    FakeNumberCatalogue,
    NumberCatalogue,
)
from txtlocal.slices.senders.repo import SendersDynamoRepo
from txtlocal.slices.senders.router import build_numbers_router
from txtlocal.slices.senders.router import build_router as build_senders_router
from txtlocal.slices.senders.service import SendersService

if TYPE_CHECKING:
    from fastapi import APIRouter

    from txtlocal.shared.money import Micro
    from txtlocal.slices.billing.service import DedicatedNumbers
    from txtlocal.slices.identity.model import Account

_clients = AsyncExitStack()
_handlers: dict[Queue, Handler] = {}
_subscribers: dict[Topic, Handler] = {}


class SmsMode(StrEnum):
    DRYRUN = "dryrun"
    FAKE = "fake"
    LIVE = "live"
    SANDBOX = "sandbox"


class BusMode(StrEnum):
    LOCAL = "local"
    SQS = "sqs"


@dataclass(frozen=True, slots=True)
class Settings:
    api_base_url: str
    api_log_file: str | None
    api_log_group: str
    athena_output: str
    athena_workgroup: str
    aws_region: str
    bus: BusMode
    cognito_client_id: str
    cognito_issuer: str
    dev_idp_users: tuple[str, ...]
    dynamodb_endpoint: str | None
    media_bucket: str
    media_dir: str | None
    operator_secret: str
    public_base_url: str
    send_log_group: str
    ses_sender_address: str
    sms_allowed_countries: frozenset[str]
    sms_daily_cap_per_account: int
    sms_max_price_usd: str
    sms_mode: SmsMode
    stripe_secret_key: str
    stripe_webhook_secret: str
    table_name: str
    unsubscribe_secret: str

    @classmethod
    def from_env(cls) -> Self:
        env = os.environ
        public_base_url = env.get("PUBLIC_BASE_URL", "http://localhost:3000")
        dev_idp_users = tuple(u for u in env.get("DEV_IDP_USERS", "").split(",") if u)
        default_issuer = f"{public_base_url}/api/dev-idp" if dev_idp_users else ""
        return cls(
            api_base_url=env.get("API_BASE_URL", "http://localhost:9000"),
            api_log_file=env.get("API_LOG_FILE"),
            api_log_group=env.get("API_LOG_GROUP", "txtlocal-api"),
            athena_output=env.get("ATHENA_OUTPUT", ""),
            athena_workgroup=env.get("ATHENA_WORKGROUP", ""),
            aws_region=env.get("AWS_REGION", "eu-west-2"),
            bus=BusMode(env.get("BUS", BusMode.LOCAL)),
            cognito_client_id=env.get("COGNITO_CLIENT_ID", "local"),
            cognito_issuer=env.get("COGNITO_ISSUER", default_issuer),
            dev_idp_users=dev_idp_users,
            dynamodb_endpoint=env.get("AWS_ENDPOINT_URL_DYNAMODB"),
            media_bucket=env.get("MEDIA_BUCKET", ""),
            media_dir=env.get("MEDIA_DIR"),
            operator_secret=env.get("OPERATOR_SECRET", "local-operator-secret"),
            public_base_url=public_base_url,
            send_log_group=env.get("SEND_LOG_GROUP", ""),
            ses_sender_address=env.get("SES_SENDER_ADDRESS", ""),
            sms_allowed_countries=frozenset(env.get("SMS_ALLOWED_COUNTRIES", "GB").split(",")),
            sms_daily_cap_per_account=int(env.get("SMS_DAILY_CAP_PER_ACCOUNT", "500")),
            sms_max_price_usd=env.get("SMS_MAX_PRICE_USD", "0.10"),
            sms_mode=SmsMode(env.get("SMS_MODE", SmsMode.FAKE)),
            stripe_secret_key=env.get("STRIPE_SECRET_KEY", ""),
            stripe_webhook_secret=env.get("STRIPE_WEBHOOK_SECRET", ""),
            table_name=env.get("TABLE_NAME", "txtlocal-local"),
            unsubscribe_secret=env.get("UNSUBSCRIBE_SECRET", "local-unsubscribe-secret"),
        )


@functools.cache
def settings() -> Settings:
    return Settings.from_env()


@functools.cache
def table() -> Table:
    config = settings()
    session = aioboto3.Session()
    creator = session.client(
        "dynamodb", endpoint_url=config.dynamodb_endpoint, region_name=config.aws_region
    )
    client = runtime.run(_clients.enter_async_context(creator))
    return Table(client=client, name=config.table_name)


@functools.cache
def bus() -> Bus:
    if settings().bus is BusMode.LOCAL:
        return LocalBus(handlers=_handlers, subscribers=_subscribers)

    env = os.environ
    session = aioboto3.Session()
    region = settings().aws_region
    sqs = runtime.run(_clients.enter_async_context(session.client("sqs", region_name=region)))
    sns = runtime.run(_clients.enter_async_context(session.client("sns", region_name=region)))
    return SqsBus(
        queue_urls={
            Queue.RECHARGE: env["RECHARGE_QUEUE_URL"],
            Queue.SEND_JOBS: env["SEND_QUEUE_URL"],
            Queue.WEBHOOKS: env["WEBHOOK_QUEUE_URL"],
        },
        sns=sns,
        sqs=sqs,
        topic_arns={
            Topic.SMS_EVENTS: env["SMS_EVENTS_TOPIC_ARN"],
            Topic.SMS_INBOUND: env["SMS_INBOUND_TOPIC_ARN"],
        },
    )


@functools.cache
def gateway() -> SmsGateway:
    mode = settings().sms_mode
    if mode is SmsMode.FAKE:
        return FakeSmsGateway(bus=bus(), clock=utc_now)

    env = os.environ
    session = aioboto3.Session()
    creator = session.client("pinpoint-sms-voice-v2", region_name=settings().aws_region)
    return AwsSmsGateway(
        client=runtime.run(_clients.enter_async_context(creator)),
        clock=utc_now,
        configuration_set=env["SMS_CONFIGURATION_SET"],
        dry_run=mode is SmsMode.DRYRUN,
        protect_configuration_id=env["SMS_PROTECT_CONFIGURATION_ID"],
    )


@functools.cache
def payment_gateway() -> PaymentGateway:
    config = settings()
    creator = httpx.AsyncClient(
        timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
    )
    return StripeGateway(
        http=creator,
        secret_key=config.stripe_secret_key,
        webhook_secret=config.stripe_webhook_secret,
    )


@functools.cache
def email() -> Email:
    config = settings()
    if not config.ses_sender_address:
        return LoggingEmail()

    session = aioboto3.Session()
    creator = session.client("ses", region_name=config.aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return SesEmail(send_email=client.send_email, sender=config.ses_sender_address)


@dataclass(frozen=True, slots=True)
class LazyAccountContacts:
    async def contact_details(self, account_id: str) -> Account:
        return await identity().contact_details(account_id)

    async def update_contact_details(
        self, account_id: str, name: str, email: str, mobile: str | None
    ) -> Account:
        return await identity().update_contact_details(account_id, name, email, mobile)


@dataclass(frozen=True, slots=True)
class LazyBillingGate:
    async def can_purchase(self, account_id: str, now: datetime) -> bool:
        return await billing().can_purchase(account_id, now)

    async def charge_and_rent(
        self, account_id: str, sender_id: str, amount_micro: Micro, now: datetime
    ) -> None:
        await billing().charge_and_rent(account_id, sender_id, amount_micro, now)


@functools.cache
def billing() -> BillingService:
    return BillingService(
        bus=bus(),
        clock=utc_now,
        contacts=LazyAccountContacts(),
        email=email(),
        gateway=payment_gateway(),
        numbers=dedicated_numbers(),
        public_base_url=settings().public_base_url,
        repo=BillingDynamoRepo(table()),
    )


@functools.cache
def number_catalogue() -> NumberCatalogue:
    if settings().sms_mode is SmsMode.FAKE:
        return FakeNumberCatalogue()

    session = aioboto3.Session()
    creator = session.client("pinpoint-sms-voice-v2", region_name=settings().aws_region)
    return AwsNumberCatalogue(client=runtime.run(_clients.enter_async_context(creator)))


@functools.cache
def senders() -> SendersService:
    return SendersService(
        billing=LazyBillingGate(),
        catalogue=number_catalogue(),
        clock=utc_now,
        gateway=gateway(),
        repo=SendersDynamoRepo(table()),
    )


@functools.cache
def dedicated_numbers() -> DedicatedNumbers:
    return senders()


@functools.cache
def stripe_webhook() -> StripeWebhook:
    return StripeWebhook(billing=billing(), clock=utc_now, gateway=payment_gateway())


@functools.cache
def billing_charge() -> BillingCharge:
    return BillingCharge(billing=billing(), clock=utc_now, gateway=payment_gateway())


@functools.cache
def policy() -> SendPolicy:
    config = settings()
    return SendPolicy(
        allowed_countries=config.sms_allowed_countries,
        daily_cap=config.sms_daily_cap_per_account,
        max_price_usd=config.sms_max_price_usd,
        sandbox=config.sms_mode is SmsMode.SANDBOX,
    )


@functools.cache
def media_storage() -> MediaStorage:
    config = settings()
    if config.media_dir is not None:
        return LocalMediaStorage(directory=Path(config.media_dir), site=config.public_base_url)

    session = aioboto3.Session()
    creator = session.client("s3", region_name=config.aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return S3MediaStorage(
        bucket=config.media_bucket,
        presign=client.generate_presigned_url,
        prefix="media/",
        site=config.public_base_url,
    )


@functools.cache
def messaging() -> MessagingService:
    return MessagingService(
        clock=utc_now,
        gateway=gateway(),
        media=media_storage(),
        mode=settings().sms_mode,
        opt_outs=contacts(),
        policy=policy(),
        repo=MessagingDynamoRepo(table()),
    )


@functools.cache
def campaigns() -> CampaignsService:
    config = settings()
    return CampaignsService(
        billing=billing(),
        bus=bus(),
        clock=utc_now,
        contacts=contacts(),
        links=analytics(),
        media=media_storage(),
        policy=policy(),
        quoting=messaging(),
        repo=CampaignsDynamoRepo(table()),
        senders=senders(),
        settings=identity(),
        site=config.public_base_url,
        unsubscribe_secret=config.unsubscribe_secret,
    )


@functools.cache
def automation() -> AutomationService:
    return AutomationService(
        bus=bus(),
        campaigns=campaigns(),
        clock=utc_now,
        contacts=contacts(),
        email=email(),
        messages=messaging(),
        repo=AutomationDynamoRepo(table()),
        senders=senders(),
    )


async def provision_automation(account_id: str, now: datetime) -> None:
    await automation().provision_defaults(account_id, now)


@functools.cache
def inbox() -> InboxService:
    return InboxService(
        clock=utc_now,
        contacts=contacts(),
        messaging=messaging(),
        quick_send=campaigns(),
        repo=InboxDynamoRepo(table()),
    )


@functools.cache
def inbound() -> Inbound:
    return Inbound(
        automation=automation(),
        clock=utc_now,
        contacts=contacts(),
        inbox=inbox(),
        messaging=messaging(),
    )


@functools.cache
def webhook_dispatch() -> WebhookDispatch:
    return WebhookDispatch(
        clock=utc_now, http=httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
    )


@functools.cache
def send_worker() -> SendWorker:
    return SendWorker(campaigns=campaigns(), clock=utc_now, inbox=inbox(), messaging=messaging())


@functools.cache
def delivery_events() -> DeliveryEvents:
    return DeliveryEvents(
        automation=automation(), campaigns=campaigns(), clock=utc_now, messaging=messaging()
    )


def register_handlers() -> None:
    _handlers[Queue.RECHARGE] = billing_charge().handle_body
    _handlers[Queue.SEND_JOBS] = send_worker().handle_body
    _handlers[Queue.WEBHOOKS] = webhook_dispatch().handle_body
    _subscribers[Topic.SMS_EVENTS] = delivery_events().handle_body
    _subscribers[Topic.SMS_INBOUND] = inbound().handle_body


DEV_IDP_OUTSIDE_LOCAL = (
    "DEV_IDP_USERS is set without AWS_ENDPOINT_URL_DYNAMODB: the local sign-in provider "
    "accepts any listed address without a password and must never run outside a laptop"
)


@functools.cache
def dev_idp() -> DevIdp | None:
    config = settings()
    if not config.dev_idp_users:
        return None
    if config.dynamodb_endpoint is None:
        raise Internal(DEV_IDP_OUTSIDE_LOCAL)
    return DevIdp(
        client_id=config.cognito_client_id,
        clock=utc_now,
        issuer=config.cognito_issuer,
        users=set(config.dev_idp_users),
    )


@functools.cache
def verifier() -> TokenVerifier:
    config = settings()
    idp = dev_idp()
    if idp is not None:
        return LocalVerifier(
            client_id=config.cognito_client_id, issuer=config.cognito_issuer, keys=idp.keys()
        )
    return CognitoVerifier(
        client_id=config.cognito_client_id,
        http=httpx.AsyncClient(timeout=5.0),
        issuer=config.cognito_issuer,
    )


@functools.cache
def directory() -> UserDirectory:
    idp = dev_idp()
    if idp is not None:
        return idp

    session = aioboto3.Session()
    creator = session.client("cognito-idp", region_name=settings().aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return CognitoUserDirectory(
        admin_create_user=client.admin_create_user,
        user_pool_id=os.environ.get("COGNITO_USER_POOL_ID", ""),
    )


@functools.cache
def contacts() -> ContactsService:
    return ContactsService(
        clock=utc_now,
        owners=identity(),
        repo=ContactsDynamoRepo(table()),
        settings=identity(),
    )


async def provision_contacts(account_id: str, now: datetime) -> None:
    await contacts().provision_defaults(account_id, now)


@functools.cache
def identity() -> IdentityService:
    return IdentityService(
        balances=billing(),
        clock=utc_now,
        directory=directory(),
        email=email(),
        hooks=(
            billing().open_account,
            provision_contacts,
            provision_automation,
            senders().provision_defaults,
        ),
        repo=IdentityDynamoRepo(table()),
        senders=senders(),
        verifier=verifier(),
    )


@functools.cache
def signed_in() -> Authenticated:
    return authenticated(verifier(), identity(), utc_now)


@functools.cache
def rate_limits() -> RateLimitsDynamoRepo:
    return RateLimitsDynamoRepo(table())


@functools.cache
def api_key_user() -> Authenticated:
    return api_user(identity(), rate_limits(), utc_now)


@functools.cache
def log_queries() -> LogQueries:
    log_file = settings().api_log_file
    if log_file is not None:
        return LocalLogQueries(path=Path(log_file))

    session = aioboto3.Session()
    creator = session.client("logs", region_name=settings().aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return InsightsLogQueries(log_group=settings().api_log_group, logs_client=client)


@functools.cache
def usage_queries() -> UsageQueries:
    log_file = settings().api_log_file
    if log_file is not None:
        return LocalUsageQueries(path=Path(log_file))

    session = aioboto3.Session()
    creator = session.client("logs", region_name=settings().aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return InsightsUsageQueries(log_group=settings().send_log_group, logs_client=client)


@functools.cache
def click_queries() -> ClickQueries:
    log_file = settings().api_log_file
    if log_file is not None:
        return LocalClickQueries(path=Path(log_file))

    session = aioboto3.Session()
    creator = session.client("athena", region_name=settings().aws_region)
    client = runtime.run(_clients.enter_async_context(creator))
    return AthenaClickQueries(
        athena_client=client,
        host=urlsplit(settings().public_base_url).hostname or "",
        output=settings().athena_output,
        workgroup=settings().athena_workgroup,
    )


@functools.cache
def analytics() -> AnalyticsService:
    return AnalyticsService(
        click_queries=click_queries(),
        clock=utc_now,
        public_base_url=settings().public_base_url,
        repo=AnalyticsDynamoRepo(table()),
        usage_queries=usage_queries(),
    )


@functools.cache
def developer() -> DeveloperService:
    return DeveloperService(
        accounts=identity(),
        base_url=settings().api_base_url,
        billing=billing(),
        campaigns=campaigns(),
        clock=utc_now,
        contacts=contacts(),
        docs_url=f"{settings().public_base_url}/developer/docs",
        gateway=gateway(),
        log_queries=log_queries(),
        messaging=messaging(),
        policy=policy(),
        rate_limit_per_minute=RATE_LIMIT_PER_MINUTE,
        repo=DeveloperDynamoRepo(table()),
        senders=senders(),
        settings=identity(),
    )


@functools.cache
def v3_router() -> APIRouter:
    return build_developer_public_router(developer(), api_key_user())


def routers() -> list[APIRouter]:
    register_handlers()

    built = [
        build_identity_router(identity(), signed_in()),
        build_billing_router(billing(), signed_in()),
        build_contacts_router(contacts(), signed_in()),
        build_senders_router(senders(), signed_in()),
        build_numbers_router(senders(), signed_in()),
        build_messaging_router(messaging(), signed_in(), campaigns()),
        build_campaigns_router(campaigns(), signed_in()),
        build_unsubscribe_router(campaigns()),
        build_automation_router(automation(), signed_in()),
        build_operator_router(automation(), settings().operator_secret),
        build_inbox_router(inbox(), signed_in()),
        build_developer_router(developer(), signed_in()),
        build_analytics_router(analytics(), signed_in()),
        build_redirect_router(analytics()),
    ]

    idp = dev_idp()
    if idp is not None:
        built.append(build_dev_idp_router(idp))

    if settings().dynamodb_endpoint is not None:
        built.append(build_local_stripe_router(stripe_webhook()))

    if settings().sms_mode is SmsMode.FAKE:
        built.append(build_demo_router(bus()))
        built.append(build_email_demo_router(automation()))

    return built
