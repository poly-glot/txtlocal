# The developer API: `/api/v3`, keys, webhooks, logs

The developer face is the same `api` Lambda and the same slices as the dashboard, reached under
`/api/v3/*` with HTTP Basic authentication instead of a Cognito token. Every route here calls the
same `service.py` function the dashboard route calls; the two faces differ in authentication, in the
`api_request` log line, and in the rate limit. `docs/architecture.md` decision 2 is why one Lambda
serves both; this file is the contract a customer integrates against and the contract the
`developer` slice implements.

## 1. Authentication

`Authorization: Basic base64(username:api_key)`. `username` is the user's email, the same value the
API Credentials screen shows; `api_key` is the 40-character base64url string shown once when the key
is created or regenerated.

Resolution is one read: the key's SHA-256 hex is looked up through GSI2 (`txtlocal#APIKEY#{sha256}`),
the returned user row's `username` is compared to the supplied one, and both comparisons are
`hmac.compare_digest`. A miss on either answers 401 with `WWW-Authenticate: Basic realm="txtlocal"`
and the envelope below. The user row carries `api_key_hash` and `api_key_prefix` (the first eight
characters, for display); the key itself is stored nowhere, which is why the screen shows it once. The
dashboard's `POST /api/app/users/{id}/api-key` regenerates: a new key, the old hash removed from GSI2
in the same update, the plaintext returned once.

A resolved credential is `Principal(account_id, user_id, role)`, the same value the JWT dependency
produces, so a router never knows which face called it.

## 2. Rate limit

Sixty requests per user per UTC minute, `RATE_LIMIT_PER_MINUTE` in the environment. Before the body is
parsed the router does `ADD n :one SET ttl = if_not_exists(ttl, :ttl)` on
`txtlocal#RL#{user_id}#{yyyy-mm-ddThh:mm}` with a two-day TTL and reads the updated value; a value
over the limit answers 429 with `Retry-After: <seconds to the next minute>`. The counter is the one
write a refused request makes. Local development and the fake mode use the same counter against
DynamoDB Local.

## 3. The `api_request` log line

Every `/api/v3` request writes one line through `telemetry.log("api_request", ...)` from a FastAPI
middleware on the `v3` router, after the response is built:

| Field | Value |
|---|---|
| `event` | `api_request` |
| `request_id` | the Lambda request id |
| `account_id`, `user_id` | from the principal; `-` when authentication failed |
| `method` | `POST` |
| `route` | the route template, `/api/v3/sms/{messageId}`, never the raw path |
| `status` | the HTTP status |
| `latency_ms` | integer milliseconds |
| `outcome` | `ok` for 2xx and 3xx, `refused` for 4xx, `failed` for 5xx |

No query string, no header, no body, no key. The API Logs screen reads these lines (§8) and
`specs/05-analytics.md` names the same contract.

## 4. Error envelope

Every non-2xx answer is `{"code": "...", "message": "..."}` with `Content-Type: application/json`,
mapped from `AppError` in the one handler `entrypoints/api.py` owns:

| `AppError` | Status | `code` | `message` |
|---|---|---|---|
| `BadRequest` | 400 | `BAD_REQUEST` | the guard's sentence, verbatim |
| `Unauthorized` | 401 | `UNAUTHORIZED` | `Invalid username or API key` |
| `PaymentRequired` | 402 | `INSUFFICIENT_BALANCE` | the policy's sentence |
| `Forbidden` | 403 | `FORBIDDEN` | the policy's sentence |
| `NotFound` | 404 | `NOT_FOUND` | `No <thing> with that id` |
| `Conflict` | 409 | `CONFLICT` | the guard's sentence |
| `RateLimited` | 429 | `RATE_LIMITED` | `Rate limit of 60 requests per minute reached` |
| `Internal` | 500 | `INTERNAL` | `Something went wrong on our side` |
| `Upstream` | 502 | `UPSTREAM` | `A provider is unavailable, try again` |

A pydantic validation failure is a `BadRequest` whose message names the first failing field:
`messages[0].to: must be an E.164 number`. FastAPI's default 422 body never reaches a client.

## 5. Idempotency

Any `POST` may carry `Idempotency-Key`, one to 64 characters. The router puts
`txtlocal#IDEM#{user_id}#{key}` with `attribute_not_exists(PK)` and a 24-hour TTL before doing the
work, and stores the response body and status on the row after. A second request with the same key
answers the stored response with `Idempotent-Replayed: true`; a second request that arrives while the
first is still running answers 409 `CONFLICT` `A request with this Idempotency-Key is in progress`.
The send endpoints are where this matters; a retried `POST /sms/send` without the header sends twice,
and the documentation says so on the endpoint.

## 6. Endpoints

All requests and responses are JSON, camelCase, times in RFC 3339 UTC, money in pounds as a decimal
string with four places (`"0.0427"`), converted from `*_micro` at the router and nowhere else. Paged
responses carry `nextCursor`, an opaque string, or `null`; `limit` is 1 to 100, default 20.

### `POST /api/v3/sms/send`

```json
{
  "messages": [
    {
      "body": "Your table is ready",
      "customString": "order-8812",
      "from": "snd_01J8...",
      "schedule": "2026-10-01T09:00:00Z",
      "to": "+447400123123"
    }
  ]
}
```

| Field | Rule |
|---|---|
| `messages` | 1 to 1,000 entries |
| `to` | E.164, `phone.normalise` with the account's default country for national formats; refused as `messages[i].to: must be an E.164 number` |
| `body` | 1 to 1,224 characters after `messaging.segments` counts it; the count and encoding come back in the response |
| `from` | a sender id the account owns and that is `READY` for the destination country, or omitted for the smart sender; refused as `messages[i].from: not a sender you can use for GB` |
| `schedule` | RFC 3339 in the future, at most 90 days out, or omitted for now |
| `customString` | up to 100 characters, echoed on the message, on webhooks and in history |

Each message runs through `SendPolicy` and the cost quote; the whole batch is refused if any message
is refused, with the first refusal's message, so a batch is all or nothing before money moves. Billing
reserves the batch total in one conditional debit; each message becomes a `QUEUED` row and one
`send-jobs` entry, or a `SCHEDULED` row on the `DUE` index when `schedule` is set.

```json
{
  "messages": [
    {
      "body": "Your table is ready",
      "country": "GB",
      "customString": "order-8812",
      "encoding": "GSM7",
      "from": "snd_01J8...",
      "messageId": "msg_01J8...",
      "parts": 1,
      "price": "0.0427",
      "schedule": null,
      "status": "QUEUED",
      "to": "+447400123123"
    }
  ],
  "totalPrice": "0.0427"
}
```

201 on success. Errors: 400 for any rule above, 402 `INSUFFICIENT_BALANCE`, 403 for a policy refusal
(`COUNTRY_NOT_ENABLED`, `OPTED_OUT`, `TRIAL_ENDED`, `DAILY_CAP`, `SENDER_NOT_READY`, `NOT_VERIFIED`, the
reason in `code` and the policy's sentence in `message`).

### `GET /api/v3/sms/history`

Query `from`, `to` (RFC 3339, default the last 7 days, at most 120 days apart because that is the
retention), `status` (one of `QUEUED SCHEDULED SENT DELIVERED FAILED RECEIVED CANCELLED`),
`direction` (`OUT`, `IN`), `limit`, `cursor`. One query per month partition in the window, newest first;
the cursor encodes the month and the last key.

```json
{
  "messages": [
    {
      "body": "Your table is ready",
      "customString": "order-8812",
      "deliveredAt": "2026-09-19T12:10:07Z",
      "direction": "OUT",
      "failureReason": null,
      "from": "+447908661626",
      "messageId": "msg_01J8...",
      "parts": 1,
      "price": "0.0427",
      "sentAt": "2026-09-19T12:10:04Z",
      "status": "DELIVERED",
      "to": "+447400123123",
      "userId": "usr_01J8..."
    }
  ],
  "nextCursor": null
}
```

### `GET /api/v3/sms/{messageId}`

The same object, 404 `No message with that id` for another account's message as for a missing one.

### `POST /api/v3/mms/send`

As `sms/send` with `subject` (up to 40 characters), `mediaUrl` (https, fetched by the worker, up to
1 MB, `image/jpeg image/png image/gif`) and `body` up to 1,500 characters. Outside the gateway's
`mms_countries` the message is sent as an SMS carrying a hosted link and the response `product` is
`MMS_AS_LINK`; the documentation states this on the endpoint.

### `GET /api/v3/account`

```json
{
  "accountId": "acc_01J8...",
  "balance": "1.9573",
  "country": "GB",
  "currency": "GBP",
  "email": "owner@example.com",
  "name": "junaid",
  "trialEndsAt": "2026-09-30T00:00:00Z"
}
```

### `GET /api/v3/account/balance`

`{"balance": "1.9573", "currency": "GBP"}`, read with consistent read so a client polling after a send
sees the debit.

### `GET /api/v3/lists`, `POST /api/v3/lists`

`POST {"name": "Autumn launch"}`, 1 to 100 characters, unique per account, 409 `A list named "Autumn
launch" already exists`. Response and list entries: `{"contactCount": 0, "isOptOut": false,
"listId": "lst_01J8...", "name": "Autumn launch", "updatedAt": "..."}`. The opt-out list appears
with `isOptOut: true` and cannot be deleted through any face.

### `GET /api/v3/lists/{listId}/contacts`, `POST`, `DELETE /api/v3/lists/{listId}/contacts/{contactId}`

`POST` takes one contact or `{"contacts": [...]}` up to 1,000:

```json
{
  "customFields": {"cf1": "Gold", "cf2": "", "cf3": "", "cf4": ""},
  "email": "sam@example.com",
  "firstName": "Sam",
  "lastName": "Jones",
  "mobile": "+447400123123"
}
```

`mobile` is required and normalised; a contact already in the list by mobile is updated, not
duplicated, and the response marks it `"created": false`. `firstName`, `lastName` up to 50,
`email` optional and validated by shape only, custom fields up to 100 characters each. Adding a
number to the opt-out list is how the API opts someone out. `DELETE` answers 204; 404 for an unknown
contact.

### `GET /api/v3/sender-ids`

```json
{
  "senders": [
    {"kind": "SHARED", "senderId": "snd_shared", "status": "READY", "value": "Shared number", "countries": ["GB"]},
    {"kind": "OWN", "senderId": "snd_01J8...", "status": "READY", "value": "+447411972333", "countries": ["GB"]},
    {"kind": "ALPHA", "senderId": "snd_01J9...", "status": "UNDER_REVIEW", "value": "JUNAIDGURU", "countries": ["GB"]}
  ]
}
```

### `GET /api/v3/templates`

`{"templates": [{"body": "...", "name": "test", "templateId": "tpl_01J8..."}]}`.

## 7. Webhooks

Two things produce a webhook: a delivery report rule (every status change of an outbound message the
account sent) and an inbound rule whose action is `URL`. Both are `POST` with `Content-Type:
application/json` and two headers:

```
X-Txtlocal-Event: message.delivered
X-Txtlocal-Signature: t=1758283204,v1=5f1c...e2a
```

`v1` is `hmac_sha256(secret, f"{t}.{body}")` in lowercase hex, the secret being the rule's, shown once
when the rule is created. Receivers reject a timestamp older than five minutes. Verification:

```python
import hmac
import time
from hashlib import sha256


def verified(secret: str, header: str, body: bytes, now: float = time.time()) -> bool:
    fields = dict(part.split("=", 1) for part in header.split(","))
    fresh = abs(now - int(fields["t"])) <= 300
    expected = hmac.new(secret.encode(), f"{fields['t']}.".encode() + body, sha256).hexdigest()
    return fresh and hmac.compare_digest(expected, fields["v1"])
```

Events and payloads:

| `X-Txtlocal-Event` | When |
|---|---|
| `message.sent` | the provider accepted the message |
| `message.delivered` | the handset confirmed |
| `message.failed` | a terminal failure, `failureReason` set |
| `message.received` | an inbound message matched a rule with action `URL` |

```json
{
  "accountId": "acc_01J8...",
  "body": "Your table is ready",
  "customString": "order-8812",
  "direction": "OUT",
  "event": "message.delivered",
  "failureReason": null,
  "from": "+447908661626",
  "messageId": "msg_01J8...",
  "occurredAt": "2026-09-19T12:10:07Z",
  "price": "0.0427",
  "to": "+447400123123"
}
```

An inbound payload has `direction: "IN"`, `keyword` (the first word, upper-cased), `ruleId`, and
`previousMessageId` when the reply could be tied to an outbound message.

Delivery is `webhook-dispatch` reading the `webhooks` queue one message at a time: `httpx` with 5 s
connect and 10 s total, any 2xx is success, anything else or a timeout raises so SQS retries. The queue
redrive policy allows three receives with the visibility timeout stepped by the handler to 60 s, 300 s
and 1,800 s before the message lands on the dead-letter queue and one line
`event=webhook_dead outcome=exhausted rule_id=… status=…` is logged. No delivery-attempt rows are
written; a customer debugging a receiver looks at their own logs and at the dead-letter alarm's
absence. `POST /api/app/webhooks/{ruleId}/test` enqueues a `message.delivered` sample with
`messageId: "msg_test"` and answers 202.

## 8. OpenAPI and the documentation page

The `v3` routers are mounted on their own `FastAPI` sub-application so `openapi()` describes exactly
the public face: tags per slice, the security scheme `basicAuth`, the envelope as the shared error
response, examples above as the examples. `scripts/export-openapi.py` imports the app without
touching AWS and writes `specs/openapi.v3.json`, sorted keys, two-space indent; `scripts/check.sh` runs
it and fails when `git diff --exit-code specs/openapi.v3.json` is dirty, so the committed file is the
deployed contract. The "API Documentation" menu entry is a screen in
`frontend/src/screens/developer/docs/` that renders the committed JSON with a small client-side
renderer and no third-party viewer.

## 9. The API Logs screen

The screen is a Logs Insights query over the `txtlocal-api` log group, whose retention is seven
days, which is the retention the screenshot promises. `GET /api/app/developer/logs` runs:

```
fields @timestamp, request_id, user_id, route, method, status, latency_ms, outcome
| filter event = "api_request" and account_id = "<account>"
| sort @timestamp desc
| limit 400
```

with `StartQuery` over the window, polls `GetQueryResults` with the shared backoff to a 20 s deadline,
and answers the page. Filters map onto the query: `Status` to `outcome`, `Endpoint` to `route`,
`Subaccount` to `user_id`, `Date Range` to the query window (default 24 hours, at most 7 days). The
three tiles are one `stats count() by outcome` over the same window; `Successful` is `ok`, `Failed` is
`refused` plus `failed`. Twenty rows a page, paged client-side from the 400 returned; `Refresh table`
runs the query again. A query that misses the deadline answers 504 `The log search took too long,
try a narrower range`.

Ceilings: a query takes two to ten seconds, results cap at 400 rows a page and Insights allows 30
concurrent queries per account, shared with the rollup. Past that, a subscription filter on the group
into Firehose, S3 and Athena, and the screen reads rows the way Usage does.

## 10. Ceilings

- **One key per user.** Regenerating invalidates the old key at once; there is no overlap window.
  Past that, a `KEY#` row per key with `expires_at` and GSI2 entries for each.
- **No scopes.** A key does everything its user's role allows. Past that, a `scopes` set on the key
  row checked by a dependency per router.
- **No IP allow-list, no per-key labels, no last-used stamp.** The screen shows none of them.
- **Rate limit is a per-minute counter.** A burst of sixty in one second passes. Past that, a token
  bucket in the same row or a rate-based rule at the edge.
- **Batch sends are all or nothing at validation, first come first served at the provider.** A batch
  of a thousand is a thousand queue entries and about three minutes of sending; the response reports
  `QUEUED`, and the status arrives by webhook or history.
- **Webhook attempts are not stored.** Three tries, a dead-letter queue, one log line.
