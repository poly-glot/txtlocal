# The SMS gateway: one port, four modes, one policy

Every message the platform sends passes through one port, `SmsGateway`, after one pure policy,
`SendPolicy`, has allowed it. The port has two implementations and the policy has one; what changes
between a laptop, the public demo, a trial account and production is configuration read once in
`entrypoints/wiring.py`. This spec is the contract those pieces meet. `docs/architecture.md` decision 5
is why AWS End User Messaging SMS v2 is the provider; this file is how it is held at arm's length.

## 1. Why a port

Three things would otherwise leak into every slice: the AWS API surface, the cost of a real send, and
the difference between environments. Behind the port, `campaigns`, `inbox`, `automation` and `senders`
send a `Dispatch` and receive a `Receipt`, and none of them can tell a fake from a live send. The
public demo runs `fake` for ever and costs nothing; CI runs `fake`; a developer testing against real
AWS runs `dryrun` and is not charged; a trial account on the deployed stack runs under AWS's own
sandbox; production runs `live` with the same fences and a deliberately low spend quota.

## 2. The port

```python
class SmsGateway(Protocol):
    capabilities: Capabilities

    async def send_text(self, dispatch: Dispatch) -> Receipt: ...
    async def send_media(self, dispatch: MediaDispatch) -> Receipt: ...
    async def start_verification(self, destination: E164) -> None: ...
    async def check_verification(self, destination: E164, code: str) -> bool: ...
```

`Dispatch` is a frozen dataclass: `message_key` (the row's `PK`/`SK`, passed through as `Context` so a
delivery event addresses its row without a lookup), `destination` (E.164), `origination` (the sender's
provider identity: a phone number id, pool id or sender id), `body`, `message_type`
(`PROMOTIONAL` for campaigns and quick sends, `TRANSACTIONAL` for verification codes and rule
auto-replies), `max_price_usd` (from the policy, never omitted), `ttl_seconds` (86,400 for campaigns,
3,600 for quick sends and replies). `MediaDispatch` adds `subject` and `media_urls`.

`Receipt` is `provider_message_id` and `accepted_at`. A gateway raises `AppError.Upstream` for a
provider failure that a retry may cure (throttling, 5xx) and `AppError.BadRequest` with the provider's
reason for one it will not (invalid destination, unregistered origination, country blocked). The send
worker retries the first through SQS and settles the second as `FAILED` with the reason.

`Capabilities` is `mms_countries` (a frozenset of ISO codes), `two_way` (bool) and `max_body_chars`
(1,600, the provider's limit; the product's own ceiling of 1,224 is enforced earlier by
`messaging.segments`). MMS outside `mms_countries` is delivered by `messaging.service` as an SMS whose
body ends with a hosted link to the media, because AWS sends MMS to the United States and Canada only;
the History row records `kind = MMS_AS_LINK`.

## 3. The two implementations

**`AwsSmsGateway`** wraps an `aioboto3` `pinpoint-sms-voice-v2` client created once per process.
`send_text` is one `SendTextMessage` with `ConfigurationSetName`, `Context={"messageKey": …}`,
`DestinationPhoneNumber`, `DryRun` (true in `dryrun` mode only), `MaxPrice`, `MessageBody`,
`MessageType`, `OriginationIdentity`, `ProtectConfigurationId` and `TimeToLive`. `send_media` is one
`SendMediaMessage`. `start_verification` and `check_verification` use the account-level verified
destination number API in `sandbox` mode and a code the platform sends itself as a `TRANSACTIONAL`
text in `live` mode; either way the number is also written as the account's own number once verified.
`ThrottlingException`, `InternalServerException` and connection errors map to `Upstream`;
`ValidationException`, `ResourceNotFoundException`, `AccessDeniedException` and `ConflictException` map
to `BadRequest` with the `Reason` field as the message; `ServiceQuotaExceededException` maps to
`RateLimited`, which the worker settles as `FAILED` with reason `SPEND_LIMIT`, because a quota is a
fence and not a transient.

**`FakeSmsGateway`** performs no I/O. It returns `provider_message_id = f"fake-{uuid7()}"` and hands
the bus a synthetic delivery event chosen by the destination's last two digits: `00` becomes
`TEXT_INVALID`, `01` becomes `TEXT_CARRIER_UNREACHABLE`, `02` becomes `TEXT_BLOCKED`, `03` becomes
`TEXT_SPAM`, anything else becomes `TEXT_DELIVERED`. Locally the bus is `LocalBus`, so the event is
handled before the send call returns; on the deployed demo the bus is SQS and the event arrives a
second later. Verification always accepts the code `000000`. `capabilities.mms_countries` is
`{"US", "CA"}` so the fake behaves like the real thing about MMS, and `two_way` is true so the inbox
can be demonstrated through `POST /api/app/demo/inbound`.

There is no third implementation. `sandbox` and `live` are `AwsSmsGateway` with different account
state and a different spend quota, and `dryrun` is `AwsSmsGateway` with `DryRun=true`; a dry run emits
no delivery event, so the worker settles the row as `SENT` and the fake event path marks it
`DELIVERED`, which is what the History screen should show for a rehearsal.

## 4. The modes

| `SMS_MODE` | Gateway | Where | What a send costs | Who can receive |
|---|---|---|---|---|
| `fake` | `FakeSmsGateway` | laptop, CI, the public demo | nothing | anyone, nothing is sent |
| `dryrun` | `AwsSmsGateway`, `DryRun=true` | a developer against real AWS | nothing | nobody, AWS validates and stops |
| `sandbox` | `AwsSmsGateway` | the deployed stack while the AWS account is in the SMS sandbox | real, under AWS's $1.00 a month cap | the ten verified destination numbers |
| `live` | `AwsSmsGateway` | production after the support case grants production access | real, under the account spend quota | anyone the policy allows |

The mode is read once, in `wiring.py`. Nothing else branches on it: `messaging.service` asks
`capabilities`, the policy asks the account, and the demo endpoint is registered by `wiring.py` only
when the gateway is the fake.

## 5. The policy

`SendPolicy.allow(account, sender, destination, quote, now) -> Allowed | Refused` is a pure function
of its arguments and runs before every send in every mode, including `fake`, so the demo refuses the
same things production refuses. A refusal is a `Refused(reason, message)` whose message is the
user-facing sentence and whose reason is the `StrEnum` the History row records.

| Check | Refusal | Message |
|---|---|---|
| destination country not in `SMS_ALLOWED_COUNTRIES` (default `GB`) | `COUNTRY_NOT_ENABLED` | `Sending to <country> is not enabled for this account` |
| destination in the account's opt-out list | `OPTED_OUT` | `This contact has opted out` |
| account outside its trial and never topped up | `TRIAL_ENDED` | `Your free trial has ended. Top up to keep sending` |
| balance below the quote | `INSUFFICIENT_BALANCE` | `Your balance is £<x>; this send costs £<y>` |
| account's sends today at `SMS_DAILY_CAP_PER_ACCOUNT` (default 500) | `DAILY_CAP` | `Daily sending limit reached` |
| sender not `READY` for the destination country | `SENDER_NOT_READY` | `<sender> is not ready to send to <country>` |
| `sandbox` mode and destination not one of the account's verified own numbers | `NOT_VERIFIED` | `While your account is in trial you can send to your verified numbers only` |

The policy also sets `Dispatch.max_price_usd` from `SMS_MAX_PRICE_USD` (default `0.10`) so a routing
surprise fails the message rather than the budget. Two fences the policy does not implement, because
AWS does: the account spend quota, kept at the minimum that covers a month of the trial cohort and
raised by a deliberate quota request, and the protect configuration that blocks every country outside
the allow-list at the provider even if the policy were bypassed.

The daily cap is the one counter the send path writes: `ADD n :1` on `CAP#{account}#{day}` with a
two-day TTL, returned value compared against the cap. It is the abuse fence for the money path and is
not lazy-able.

## 6. Provider events

The configuration set's event destination publishes every `TEXT_*` and `MEDIA_*` event to the
`sms-events` SNS topic; `delivery-events` maps them onto the message row named by `Context.messageKey`:

| Provider event | Row status | Notes |
|---|---|---|
| `TEXT_QUEUED`, `TEXT_PENDING`, `TEXT_SENT` | `SENT` | only if the row is still `QUEUED` or `SENT` |
| `TEXT_SUCCESSFUL`, `TEXT_DELIVERED` | `DELIVERED` | records `delivered_at` and the provider's `price` when present |
| `TEXT_INVALID`, `TEXT_INVALID_MESSAGE`, `TEXT_UNREACHABLE`, `TEXT_CARRIER_UNREACHABLE`, `TEXT_BLOCKED`, `TEXT_CARRIER_BLOCKED`, `TEXT_SPAM`, `TEXT_TTL_EXPIRED`, `TEXT_UNKNOWN` | `FAILED` | records the event name as `failure_reason` and adds one to the campaign's `undelivered` count; nothing is refunded, because the provider bills on acceptance |
| `MEDIA_*` | the same mapping by suffix | |

Every transition is a conditional update `status IN (:from…)` so a late `TEXT_SENT` never overwrites
`DELIVERED`, and a repeated event is a lost condition, not an error. A `FAILED` transition that wins
its condition enqueues one delivery-report webhook if the account has a rule; a `DELIVERED`
transition does the same. Neither refunds: the provider bills on acceptance, and both rows were
accepted. The only refund is for a recipient never accepted, a gateway `BadRequest` the send worker
settles as `FAILED` with its reason and leaves unsent, so the campaign's settlement returns its quote. The exact event names are the provider's
`EventType` enumeration; `delivery_events.EVENT_STATUS` is the one table that maps them and a new name
that is not in it is logged as `outcome=unmapped` and ignored.

Inbound messages arrive on `sms-inbound` from a two-way number as `originationNumber`,
`destinationNumber`, `messageKeyword`, `messageBody`, `previousPublishedMessageId` and
`inboundMessageId`. `inbound` finds the account by the destination number (a dedicated number the
account rents) or, for a shared number, by the message `previousPublishedMessageId` names; a message it
cannot attribute is logged with `outcome=unattributed` and dropped. `STOP` and its variants move the
sender into the account's opt-out list before any rule runs, in every mode; AWS's own opt-out list
runs as well and is the reason the platform never resends to a number AWS has marked opted out.

## 7. Senders and the provider

| Product sender | Provider identity | Status flow |
|---|---|---|
| Shared number | the platform's phone pool, `PoolId` | always `READY`; replies route by `previousPublishedMessageId` |
| Own number | not an origination identity; a verified destination the account may also display as "from" where the country allows | `PENDING_VERIFICATION` → `READY` on a correct code |
| Dedicated number | a `PhoneNumberId` requested through `RequestPhoneNumber` where the country offers self-service, two-way enabled to `sms-inbound` | `PROVISIONING` → `READY`; released by `ReleasePhoneNumber` when rental lapses |
| Alpha tag | a `SenderId` registered per country; the United Kingdom requires registration | `UNDER_REVIEW` → `READY` or `REJECTED` |

In `fake` mode the sender slice's catalogue of numbers to buy is a seeded list and every registration
completes on the next scheduler tick, so the flows can be demonstrated end to end.

## 8. Testing the port

`RecordingGateway` in `shared/testing.py` records every dispatch and returns receipts in order; it is
the double every service test uses. `AwsSmsGateway` has one test per error mapping through
`botocore.stub.Stubber`, and one integration test that runs only when `SMS_MODE=dryrun` and real
credentials are present, sending a dry run to a fixed number. `FakeSmsGateway` has a table test over
the suffix mapping. `SendPolicy` has a table test with one row per refusal and one row for the send
that passes, and its messages are asserted verbatim because the page shows them.

## 9. Ceilings

- **One `SendTextMessage` per message.** The provider has no batch call; a campaign of ten thousand is
  ten thousand calls paced by the worker's concurrency of two, about five a second, roughly half an
  hour. Past that, raise the event source mapping's concurrency in `aws-cloud` once the table is no
  longer shared.
- **Two-way needs a dedicated number.** Shared-number replies route only when the recipient replies to
  the last message; an unsolicited inbound to the pool cannot be attributed and is dropped. Past that,
  a dedicated two-way number per account, which is the product's paid feature anyway.
- **MMS is a link outside the United States and Canada.** The provider does not send MMS elsewhere.
  Past that, a second provider behind the same port for MMS routes.
- **Verification in `live` mode is a code the platform sends.** Each costs one SMS and is counted
  against the account's daily cap so it cannot be used to spam a number.
