# Data model: an SMS platform on DynamoDB

## Overview

An account holds a GBP balance and spends it on messages. Contacts live in lists; one list per account
is the opt-out list. A message goes out from a sender the account owns, rents or shares, through the
gateway in `specs/02-sms-gateway.md`, and comes back as delivery events that settle the row. Replies
land in an inbox and run the account's rules. Developers hold one key per user, call `/api/v3`, and
receive webhooks. Billing is Stripe; usage, clicks and API logs are counted from logs, never in a
request. `docs/architecture.md` holds the fifteen decisions this model implements; this file holds the
rows, the queries, the flows and every deliberate ceiling.

### What the screens require

| Requirement (screen) | Where it lands |
|---|---|
| Balance in GBP with sub-penny prices, £0.0427 an SMS (Top Up Account, confirm dialogs) | `Account.balance_micro`, integer micro-pounds; `PLATFORM` rates and packs |
| 14-day trial with £2.00 credit, then "Top up for full access" (banner, Home) | `Account.trial_ends_at`, `has_topped_up`; ledger `TRIAL` row; `can_send` predicate |
| Sub-accounts each with a username, API key, email, phone, notes (API Credentials, Subaccounts) | `User` rows under the account, GSI1 by username, GSI2 by key hash |
| Lists with contact counts, one system Opt-Out List, contacts with CF1–CF4 (Contacts) | `ContactList` under the account; `Contact` under the list keyed by E.164 |
| Own numbers verified by a 6-digit code, shared numbers, dedicated numbers at £2.65 a month, alpha tags 3–11 chars registered per country, a Smart Sender per country (Sender IDs) | `Sender` rows with `kind`, `status`, `renews_at`; `SmartSender` per country; `PLATFORM` number catalogue |
| Quick SMS to contacts, lists or typed numbers, now or later, with cost and recipient count on confirm (Quick SMS) | `Campaign` with `kind = QUICK` and embedded recipients; balance reserved on confirm |
| Campaigns to one list with opt-out footer, saved as draft, scheduled or sent now, listed with status, date, from, recipients (SMS Campaign) | `Campaign` with `kind = LIST`; `DUE` index while scheduled; `ADD` counters |
| Message length up to 8 parts, 1,224 characters, unicode autodetect or GSM only (Messaging Settings) | `Account.settings`; `messaging.segments` rule |
| History for 4 months, both directions, status, from, to, body, searchable by number, exportable (History) | `Message` rows in monthly partitions with `ttl` 120 days |
| Inbox of conversations by contact or number with last message and time (Messenger) | `Conversation` rows, GSI1 by `last_at`; thread through GSI1 on messages |
| Templates with name and body (Templates) | `Template` rows |
| Websites registered for link sending, reviewed (Website Registration) | `Website` rows; GSI2 review queue |
| Email-to-SMS allowed addresses per sub-account (Email SMS) | `EmailSender` rows, GSI1 by address |
| Inbound rules: number, match, action enum, address, enabled; delivery report rules (Webhooks) | `InboundRule`, `DeliveryReportRule` rows |
| API logs for 7 days with total, successful, failed tiles and filters (API Logs) | no rows: Logs Insights over the `api` log group |
| Usage by month, product and username; reporting by day, product, sub-account, sender, country (Usage, Usage Reporting) | `Usage` rows written nightly from `send-worker` logs |
| Transactions as invoices with number, date, status, amount; cards; upcoming number charges (Billing) | `Ledger` rows with Stripe invoice fields; cards live in Stripe; `Sender.renews_at` |
| Auto top-up and a low-balance alert threshold (Billing › General) | `Account.auto_recharge`, `recharge_amount_micro`, `low_balance_threshold_micro`, `alert_threshold_micro` |
| "Shorten my URL" and clicks per campaign (Quick SMS, campaigns) | `TrackedLink` and `LinkDay` rows, the shorten pattern |

### Design principles

1. **One table, one prefix, no exceptions.** Every partition key value on the table and both indexes
   begins `txtlocal#`, written by `shared.table.partition` and nowhere else. The prefix is what the
   platform's `dynamodb:LeadingKeys` condition matches; the same table serves `donation` and `shorten`
   behind their own prefixes. Sort keys carry no prefix and the two overloaded indexes are shared as
   they are.
2. **The account is the partition.** Almost every row an account owns lives under
   `txtlocal#ACCOUNT#{account_id}` with a typed sort key prefix, so the dashboard's lists are one
   `Query` with `begins_with`. The three things that grow without bound, messages, the ledger and
   usage, get partitions of their own, sliced by month, so no partition ever holds a year of traffic.
3. **Money is an integer in micro-pounds.** £0.0427 is `42700`; £2.00 is `2000000`. Stripe speaks
   pence and is converted at its boundary. No float touches a balance, a quote or a rate.
4. **The balance changes in one place and always with its ledger row.** Reserve, settle, refund,
   top-up and rental are `TransactWriteItems` of the account row and one ledger row, guarded by a
   condition. The ledger is append-only and carries `balance_after_micro`, so a balance can be
   re-derived by reading one partition.
5. **Rows are written once by the path that owns them and settled by conditional update.** The
   send worker creates a message row put-if-absent, the delivery event moves it forward under a
   `status IN` condition, a repeated event loses its condition and is not an error. At-least-once
   delivery from SQS and SNS is absorbed by the write, never by memory.
6. **Nothing is counted in a request path.** Clicks come from CloudFront logs through Athena, usage
   from the send worker's own log lines through Logs Insights, API logs from the `api` log group read
   on demand. The only counters the request path writes are the two fences, the daily cap and the
   rate limit, and the campaign's own progress counters, because money and abuse are not lazy-able.
7. **Provider events address their row directly.** Every send carries the row's key as `Context`,
   so a delivery event is one `UpdateItem` with no index and no lookup.
8. **Indexes are for the five questions the account partition cannot answer.** Who is this username
   or this API key, who owns this number, what is due now, what is under review, what happened in this
   conversation. Everything else is a `begins_with` on the account.
9. **Every ceiling is named, tested on both sides and given an upgrade path.** The register at the
   end is the contract; a new shortcut goes there, never into a comment.

## The table

The table is the shared `aws-cloud` table, reached through `TABLE_NAME`, `txtlocal-local` on a laptop
and in CI. Provisioned at the free 25 read and 25 write units, 15 on the table and 5 on each index, no
autoscaling, shared with two other applications. TTL is enabled on the attribute `ttl`; a row without
one never expires.

| Attribute | Role |
|---|---|
| `PK` | partition key, always `txtlocal#…` |
| `SK` | sort key, `#METADATA` for a singleton, otherwise `TYPE#…` |
| `GSI1PK`, `GSI1SK` | index 1, partition and sort, both optional |
| `GSI2PK` | index 2, partition only |
| `ttl` | epoch seconds, optional |

| Index | Keys | Projection | Used for |
|---|---|---|---|
| table | `PK`, `SK` | | everything an account owns, sliced by sort key prefix |
| `GSI1` | `GSI1PK`, `GSI1SK` | ALL | username, mobile within an account, number owner, conversation list, thread, due campaigns, a campaign's links, email sender |
| `GSI2` | `GSI2PK` | ALL | API key hash, numbers due for renewal, websites under review |

Items are pydantic models serialised camelCase; absent optionals are absent, never `null`; statuses
are `SCREAMING_SNAKE_CASE`; ids are `uuid7` strings; timestamps are RFC 3339 with milliseconds and a
`Z`, which sort correctly as strings. The runtime role grants the single-item actions,
`BatchGetItem`, `BatchWriteItem`, `Query` and `TransactWriteItems`, fenced to `txtlocal#*`, and does
not grant `Scan`.

## Entity map

| Entity | PK | SK | GSI1PK | GSI1SK | GSI2PK |
|---|---|---|---|---|---|
| Account | `txtlocal#ACCOUNT#{a}` | `#METADATA` | | | |
| User | `txtlocal#ACCOUNT#{a}` | `USER#{user_id}` | `txtlocal#USERNAME#{username}` | `#METADATA` | `txtlocal#APIKEY#{sha256}` |
| SubPointer | `txtlocal#SUB#{cognito_sub}` | `#METADATA` | | | |
| ContactList | `txtlocal#ACCOUNT#{a}` | `LIST#{list_id}` | | | |
| Contact | `txtlocal#LIST#{list_id}` | `CONTACT#{e164}` | `txtlocal#ACCOUNT#{a}#MOBILE#{e164}` | `LIST#{list_id}` | |
| Sender | `txtlocal#ACCOUNT#{a}` | `SENDER#{sender_id}` | `txtlocal#NUMBER#{e164}` when dedicated | `#METADATA` | `txtlocal#RENEWALS` when dedicated |
| SmartSender | `txtlocal#ACCOUNT#{a}` | `SMART#{country}` | | | |
| Template | `txtlocal#ACCOUNT#{a}` | `TEMPLATE#{template_id}` | | | |
| Website | `txtlocal#ACCOUNT#{a}` | `WEBSITE#{domain}` | | | `txtlocal#WEBSITES#UNDER_REVIEW` while under review |
| EmailSender | `txtlocal#ACCOUNT#{a}` | `EMAILSENDER#{email}` | `txtlocal#EMAILSENDER#{email}` | `#METADATA` | |
| Message | `txtlocal#ACCOUNT#{a}#MSG#{yyyy-mm}` | `{iso_ts}#{message_id}` | `txtlocal#CONV#{a}#{peer}` | `{iso_ts}` | |
| Conversation | `txtlocal#ACCOUNT#{a}` | `CONV#{peer}` | `txtlocal#ACCOUNT#{a}#CONV` | `{last_at}` | |
| Campaign | `txtlocal#ACCOUNT#{a}` | `CAMPAIGN#{campaign_id}` | `txtlocal#DUE` while scheduled | `{scheduled_at}#{a}#{campaign_id}` | |
| SentMarker | `txtlocal#ACCOUNT#{a}` | `SENT#{campaign_id}#{e164}` | | | |
| InboundRule | `txtlocal#ACCOUNT#{a}` | `RULE#{rule_id}` | | | |
| DeliveryReportRule | `txtlocal#ACCOUNT#{a}` | `DLRRULE#{rule_id}` | | | |
| Ledger | `txtlocal#ACCOUNT#{a}#LEDGER` | `{iso_ts}#{entry_id}` | | | |
| StripeEvent | `txtlocal#EVENT#{event_id}` | `#METADATA` | | | |
| DailyCap | `txtlocal#CAP#{a}#{yyyy-mm-dd}` | `#METADATA` | | | |
| RateLimit | `txtlocal#RL#{user_id}#{yyyy-mm-ddTHH:MM}` | `#METADATA` | | | |
| Idempotency | `txtlocal#IDEM#{user_id}#{idempotency_key}` | `#METADATA` | | | |
| TrackedLink | `txtlocal#LINK#{code}` | `#METADATA` | `txtlocal#CAMPAIGN#{campaign_id}#LINKS` | `{created_at}#{code}` | |
| LinkDay | `txtlocal#LINK#{code}` | `DAY#{yyyy-mm-dd}` | | | |
| Usage | `txtlocal#USAGE#{a}#{yyyy-mm}` | `{yyyy-mm-dd}#{product}#{username}#{sender_id}#{country}` | | | |
| RollupMarker | `txtlocal#ROLLUP#{yyyy-mm-dd}` | `#METADATA` | | | |
| Platform | `txtlocal#PLATFORM` | `RATE#{country}#{product}`, `PACK#{code}`, `SHAREDPOOL#{country}`, `NUMBERS#{country}` | | | |

`{a}` is the account id. `{peer}` and `{e164}` are E.164 with the leading `+`. `{country}` is ISO
3166-1 alpha-2. A `GSI1PK` that is conditional is removed with `REMOVE GSI1PK, GSI1SK` in the same
update that changes the state, so the index never lists a stale row.

## Entities

### Account

| Attribute | Example | Notes |
|---|---|---|
| `accountId` | `0192f1a2-…` | `uuid7`, minted on first sign-in |
| `name` | `junaid` | billing contact name |
| `email` | `junaidart@gmail.com` | billing contact email |
| `mobile` | `+447411972333` | billing contact mobile |
| `pricingCountry` | `GB` | drives rates and estimates on Top Up |
| `balanceMicro` | `1960000` | £1.96; changed only by `billing.service` |
| `trialEndsAt` | `2026-10-03T12:00:00.000Z` | 14 days after creation |
| `hasToppedUp` | `false` | flips on the first `TOPUP` ledger row, never back |
| `autoRecharge` | `false` | Billing › General toggle |
| `rechargeAmountMicro` | `10000000` | the boost charged when auto-recharging, £10 default |
| `lowBalanceThresholdMicro` | `5000000` | £5.00; auto-recharge fires below it |
| `alertThresholdMicro` | `5000000` | £5.00; the low-balance email fires below it |
| `lowBalanceAlertedAt` | `2026-09-19T11:02:00.000Z` | absent unless the alert fired and no credit has lifted the balance back |
| `rechargeInFlight` | `2026-09-19T11:02:00.000Z` | absent unless a recharge job is queued; condition for the next one |
| `stripeCustomerId` | `cus_…` | absent until the first Checkout Session |
| `settings.maxParts` | `8` | 1–8; 8 is 1,224 GSM characters |
| `settings.unicodeMode` | `AUTODETECT` | or `GSM_ONLY` |
| `settings.defaultCountry` | `GB` | national numbers are parsed against it |
| `settings.showOwnNumber` | `true` | From options toggle |
| `settings.showBusinessName` | `true` | From options toggle |
| `createdAt` | | |

`can_send(account, now)` is `account.has_topped_up or now < account.trial_ends_at`. The trial credit
is never clawed back; an expired, never-topped-up account keeps its £2.00 on the row and cannot spend
it until it tops up.

### User

| Attribute | Example | Notes |
|---|---|---|
| `userId` | `uuid7` | |
| `accountId` | | |
| `username` | `junaidart@gmail.com` | the Cognito username; unique because the pool is |
| `role` | `OWNER` | or `SUB`; one owner per account |
| `cognitoSub` | | absent for a `SUB` that has not signed in yet |
| `phone` | `+447411972333` | |
| `notes` | | free text from the Subaccounts form |
| `apiKeyHash` | hex SHA-256 | of the 40-character base64url key made from 30 CSPRNG bytes; the key is shown once and never stored |
| `apiKeyPrefix` | `k7Qx2m9P` | the key's first eight characters, shown in the table |
| `apiKeyIssuedAt` | | rewritten on Regenerate |
| `createdAt` | | |

`GSI1PK = txtlocal#USERNAME#{username}` answers sign-in; `GSI2PK = txtlocal#APIKEY#{sha256}` answers
Basic auth. Regenerating a key rewrites `GSI2PK`, so the old key stops resolving in the same write.

### ContactList

| Attribute | Example | Notes |
|---|---|---|
| `listId` | `uuid7` | |
| `name` | `Example List` | |
| `contactCount` | `1` | `ADD` on contact create and delete; a lost condition on the contact write does not touch it |
| `isOptOut` | `true` | exactly one list per account carries it, created with the account |
| `createdAt` | | |

### Contact

| Attribute | Example | Notes |
|---|---|---|
| `listId` | | |
| `accountId` | | |
| `mobile` | `+447411972333` | E.164; the sort key, so a number appears once per list |
| `firstName`, `lastName` | | |
| `email` | | |
| `cf1` … `cf4` | | the four custom fields; placeholders resolve from these and the names |
| `updatedAt` | | the DATE UPDATED column |

`GSI1PK = txtlocal#ACCOUNT#{a}#MOBILE#{e164}`, `GSI1SK = LIST#{list_id}` finds every list a number is
in, which is how History and the inbox show a name for a number, how `MOVE_CONTACT` and `STOP` find
the rows to move, and how Clean Up finds duplicates across lists without a scan.

### Sender

| Attribute | Example | Notes |
|---|---|---|
| `senderId` | `uuid7` | |
| `kind` | `DEDICATED` | `ALPHA`, `DEDICATED`, `OWN`, `SHARED` |
| `value` | `+447984390718` | E.164 for numbers, the tag for `ALPHA` |
| `country` | `GB` | destination country the sender serves |
| `status` | `READY` | `PENDING_VERIFICATION`, `PROVISIONING`, `READY`, `REJECTED`, `UNDER_REVIEW` |
| `useCase` | `MARKETING` | alpha tags only |
| `nickname` | `Sam's Phone` | own numbers only |
| `providerIdentity` | `pool-…` or `phone-…` or `sender-…` | what `Dispatch.origination` carries |
| `capabilities` | `["SMS"]` | `MMS`, `SMS`; the Use for column |
| `monthlyPriceMicro` | `2650000` | dedicated only, £2.65 |
| `renewsAt` | `2026-10-19` | dedicated only; `GSI2PK = txtlocal#RENEWALS` while rented |
| `verifiedAt` | | own numbers, the Last verified column |
| `verificationHash` | | own numbers while `PENDING_VERIFICATION`; SHA-256 of the 6-digit code |
| `createdAt` | | |

A dedicated number carries `GSI1PK = txtlocal#NUMBER#{e164}` so an inbound message finds its account
in one index read. Shared numbers are one row per account per country pointing at the platform pool,
created with the account.

### SmartSender

`SK = SMART#{country}`, attributes `senderId` and `channel` (`SMS`). One per country the account can
send to; defaults to the shared number row. The Smart Senders tab is a `begins_with` on `SMART#`.

### Template

`SK = TEMPLATE#{template_id}`, attributes `name`, `body`, `createdAt`. The list is sortable by either
in the page.

### Website

| Attribute | Example | Notes |
|---|---|---|
| `domain` | `junaid.guru` | scheme stripped, lowercased, the sort key |
| `status` | `UNDER_REVIEW` | `APPROVED`, `REJECTED`, `UNDER_REVIEW` |
| `registeredAt` | | |

`GSI2PK = txtlocal#WEBSITES#UNDER_REVIEW` while under review is the operator's queue; approval
removes it.

### EmailSender

`SK = EMAILSENDER#{email}`, attributes `userId`, `senderId` (optional). `GSI1PK =
txtlocal#EMAILSENDER#{email}` is how an inbound email finds its account in phase 7.

### Message

| Attribute | Example | Notes |
|---|---|---|
| `messageId` | `uuid7` | minted at fan-out, carried by the job, so a redelivered job names the same row |
| `accountId`, `userId`, `username` | | the USERNAME column |
| `direction` | `OUT` | or `IN` |
| `kind` | `SMS` | `MMS`, `MMS_AS_LINK`, `SMS` |
| `from`, `to` | `+447908661626`, `+447411972333` | E.164; names are resolved at read time through the mobile index |
| `country` | `GB` | destination country |
| `body` | | the sent text including any footer |
| `parts` | `1` | |
| `encoding` | `GSM7` | or `UCS2` |
| `status` | `DELIVERED` | `DELIVERED`, `FAILED`, `QUEUED`, `RECEIVED`, `SENT` |
| `failureReason` | `TEXT_CARRIER_UNREACHABLE` | the provider event name or a policy refusal |
| `priceMicro` | `42700` | the quote at send time |
| `campaignId` | | present for every outbound row; quick sends are campaigns too |
| `providerMessageId` | | |
| `queuedAt`, `sentAt`, `deliveredAt` | | |
| `ttl` | | 120 days after `queuedAt` |

The partition is the account and the month of `queuedAt` (`receivedAt` for inbound); the sort key is
`{iso_ts}#{message_id}`, so History is a `Query` newest first with a `between` on the sort key. Both
directions carry `GSI1PK = txtlocal#CONV#{a}#{peer}`, `GSI1SK = {iso_ts}`, where `peer` is `to` for
outbound and `from` for inbound, which is the thread.

### Conversation

| Attribute | Example | Notes |
|---|---|---|
| `peer` | `+447411972333` | the sort key |
| `lastPreview` | first 80 characters of the last message | |
| `lastAt` | | `GSI1SK`, rewritten on every message |
| `lastDirection` | `IN` | |
| `unread` | `1` | `ADD` on inbound, set to 0 on open |
| `status` | `OPEN` | or `CLOSED`; the Status filter |

`GSI1PK = txtlocal#ACCOUNT#{a}#CONV` lists conversations newest first.

### Campaign

| Attribute | Example | Notes |
|---|---|---|
| `campaignId` | `uuid7` | |
| `kind` | `LIST` | `API` (`POST /api/v3/sms/send`, at most 1,000 messages, fanned out inline by `api`), `LIST` (the SMS Campaign screen) or `QUICK` (Quick SMS, at most 1,000 recipients embedded); `API` and `QUICK` with Send Time `Now` are fanned out inline by `api`, and any scheduled kind goes through the `DUE` index |
| `channel` | `SMS` | or `MMS` |
| `name` | `Helloworld` | quick sends are named `Quick SMS {date}` |
| `listId` | | `LIST` kind |
| `recipients` | `[{"mobile": "+44…", "listId": "…"}]` | `QUICK` kind, at most 1,000 entries |
| `senderId` | | |
| `body` | | without footer; absent for `API`, whose messages carry their own bodies in the jobs |
| `optOutMode` | `REPLY_STOP` | or `UNSUBSCRIBE_LINK`, `LIST` kind |
| `footer` | `Reply STOP to opt-out` | appended to every message |
| `subject`, `mediaKey` | | `MMS` channel; the object key in the sites bucket |
| `shortenUrls` | `true` | rewrites every URL in the body through a `TrackedLink` |
| `status` | `SCHEDULED` | `CANCELLED`, `DRAFT`, `FAILED`, `SCHEDULED`, `SENDING`, `SENT` |
| `scheduledAt` | `2027-07-31T22:59:00.000Z` | absent for send-now until claimed |
| `claimedAt`, `completedAt` | | |
| `counts.recipients` | `1` | fixed at confirmation |
| `counts.queued`, `counts.sent`, `counts.refused`, `counts.delivered`, `counts.undelivered` | | `ADD` counters; `queued` is fan-out progress, `sent` is provider-accepted and billed, `refused` is a policy or gateway refusal before acceptance, `undelivered` is a delivery failure after acceptance |
| `fanoutCursor` | a `LastEvaluatedKey` or an index into `recipients` | present while fan-out is incomplete |
| `quoteMicro` | `42700` | per message at confirmation |
| `reservedMicro` | `42700` | `quoteMicro × counts.recipients`, debited at confirmation |
| `settledMicro` | | what was actually spent, written on completion |
| `createdAt` | | |

From confirmation until fan-out completes, `GSI1PK = txtlocal#DUE`, `GSI1SK =
{scheduled_at}#{a}#{campaign_id}`; the update that records `counts.queued == counts.recipients` removes
both, so a `SENDING` campaign whose fan-out died midway is still listed as due and resumes from
`fanoutCursor`. Send-now sets `scheduledAt = now` and takes the same path, so there is one fan-out.
GSI2 on the shared table has no sort key, which is why the due index lives on GSI1.

### SentMarker

`SK = SENT#{campaign_id}#{e164}` with `messageId` and a 2-day `ttl`, written in the same transaction
as the message row. It is what makes a recipient appear once per campaign however many times the
fan-out or the queue repeats the job; the message id in the job is only a name for the row.

### InboundRule

| Attribute | Example | Notes |
|---|---|---|
| `ruleId` | `uuid7` | creation order is ascending `ruleId`; there is no separate priority field |
| `name` | `Opt-out contact` | |
| `senderId` | `ANY` | or a dedicated sender id, the DEDICATED NUMBER column |
| `match` | `stop` | `ANY` or a keyword, matched case-insensitively against the first word |
| `action` | `MOVE_CONTACT` | `AUTO_REPLY`, `EMAIL_FIXED`, `EMAIL_USER`, `GROUP_SMS`, `MOVE_CONTACT`, `POLL`, `SEND_TO_MESSENGER`, `SMS`, `URL` |
| `actionAddress` | a list id, a URL, an email, a number, a reply text | meaning depends on `action` |
| `backupEmail` | | `EMAIL_USER` only |
| `secret` | | `URL` only; signs the webhook body, plaintext for the same reason `DeliveryReportRule.secret` is |
| `enabled` | `true` | |
| `votes` | `{}` | `POLL` only; incremented per keyword, never with a nested `ADD` |

Every account is created with three rules, matching the screenshot in `specs/03` exactly rather than
an invented priority order: `stop` → `SEND_TO_MESSENGER` (`Send to messenger`), `stop` →
`MOVE_CONTACT` to the opt-out list (`Opt-out contact`), `ANY` → `EMAIL_USER` (`Default rule`), all
three enabled, all three `senderId = ANY`. `Send to messenger` and `Opt-out contact` both run on the
same keyword because rules never stop each other; a `stop` reaches the inbox and opts the sender out.

### DeliveryReportRule

`SK = DLRRULE#{rule_id}`, attributes `url`, `secret`, `enabled`, `createdAt`. The secret signs every
webhook body with HMAC-SHA256 at send time and is shown once at creation, but is kept in plaintext,
never hashed: unlike an API key, which the server only ever compares against a stored hash, a signing
secret must be read back to compute the HMAC on every delivery, so hashing it would make signing
impossible. This is a real value at rest with no analogue to `identity`'s key handling; treat it with
the same care as `STRIPE_WEBHOOK_SECRET`.

### Ledger

| Attribute | Example | Notes |
|---|---|---|
| `entryId` | `uuid7` | |
| `kind` | `TOPUP` | `ADJUSTMENT`, `REFUND`, `RENTAL`, `SEND`, `TOPUP`, `TRIAL` |
| `amountMicro` | `10000000` | signed: credits positive, debits negative |
| `balanceAfterMicro` | `11960000` | |
| `ref` | a campaign id, a sender id, a Stripe payment intent id | |
| `stripeInvoiceNumber`, `stripeInvoiceUrl` | `TOPUP` only | what the Transactions tab shows |
| `createdAt` | | |

A `SEND` row is written once per campaign at reservation, not once per message; a `REFUND` row is
written once per settlement with the unsent and failed count. The Transactions tab is the partition
filtered to `TOPUP`.

### StripeEvent, DailyCap, RateLimit, Idempotency

| Row | Attributes | Purpose |
|---|---|---|
| `txtlocal#EVENT#{event_id}` | `receivedAt`, `ttl` 30 days | put-if-absent inside the top-up transaction; a redelivered event loses the condition and answers 200 |
| `txtlocal#CAP#{a}#{yyyy-mm-dd}` | `n`, `ttl` 2 days | `ADD n :1` with `ReturnValues UPDATED_NEW`; `n > SMS_DAILY_CAP_PER_ACCOUNT` refuses |
| `txtlocal#RL#{user_id}#{yyyy-mm-ddTHH:MM}` | `n`, `ttl` 2 minutes | `ADD n :1`; `n > 60` answers 429 on `/api/v3` |
| `txtlocal#IDEM#{user_id}#{idempotency_key}` | `status` (`DONE`, `IN_FLIGHT`), `responseStatus`, `responseBody`, `ttl` 24 hours | put-if-absent as `IN_FLIGHT` before a `/api/v3` write runs, updated to `DONE` with the answer after; a repeat while `IN_FLIGHT` answers 409, a repeat after replays the stored answer |

### TrackedLink and LinkDay

| Row | Attributes | Notes |
|---|---|---|
| `txtlocal#LINK#{code}` / `#METADATA` | `url`, `accountId`, `campaignId`, `createdAt`, `clicksTotal`, `lastRollup`, `ttl` 400 days | `code` is 8 characters of `[a-z0-9]`, put-if-absent, 8 attempts; `GSI1PK = txtlocal#CAMPAIGN#{campaign_id}#LINKS`, `GSI1SK = {created_at}#{code}` |
| `txtlocal#LINK#{code}` / `DAY#{yyyy-mm-dd}` | `date`, `clicks`, `ttl` 90 days | full overwrite by the rollup |

One partition per code, unlike shorten's two, so a window of days is one `Query` with a `between` on
the sort key. The redirect reads the metadata row eventually consistently and answers `302` with the
URL. The rollup adds the day's clicks to `clicksTotal` under `ROLLUP_ONCE_PER_DAY =
attribute_exists(PK) AND (attribute_not_exists(lastRollup) OR lastRollup < :date)`, shorten's
condition.

### Usage

`PK = txtlocal#USAGE#{a}#{yyyy-mm}`, `SK = {yyyy-mm-dd}#{product}#{username}#{sender_id}#{country}`,
attributes `date`, `product` (`MMS`, `SMS`), `username`, `senderId`, `senderValue`, `country`,
`quantity`, `costMicro`, `ttl` 400 days. No index: the month partition makes the Usage tab one `Query`
and a Reporting date range one `Query` per month touched with a `between` on the day prefix, capped
at four months. Rows are full overwrites so a replayed day is idempotent.

### RollupMarker

`txtlocal#ROLLUP#{yyyy-mm-dd}` with `clicksDoneAt` and `usageDoneAt`. The marker is per day rather
than per account because the usage rollup is one Logs Insights query across every account; the
scheduled run skips a half already done and a replay payload with `force` redoes it. Correctness
does not rest on the marker, the overwrites do; the marker is what the alarm and the runbook read.

### Platform

| SK | Attributes | Notes |
|---|---|---|
| `RATE#{country}#{product}` | `priceMicro`, `currency` | `RATE#GB#SMS` is `42700` |
| `PACK#{code}` | `name`, `amountMicro`, `bonusMicro`, `savingsPct`, `estimateCountry` | the four boosts (`bonusMicro` 0) and three power packs; the credit granted is `amountMicro + bonusMicro` at the one rate per country, so no account carries a tiered rate |
| `SHAREDPOOL#{country}` | `providerIdentity`, `capabilities` | the pool every account's shared sender points at |
| `NUMBERS#{country}` | `numbers: [{value, priceMicro, capabilities}]` | the Buy A Number catalogue in `fake` mode; `live` asks the provider |

One `Query` on `txtlocal#PLATFORM` loads all of it; every process caches it for five minutes.

## Access patterns

| # | Need | Query |
|---|---|---|
| 1 | Sign-in: who is this username | `GSI1`, `GSI1PK = txtlocal#USERNAME#{username}` |
| 2 | `/api/v3` auth: who holds this key | `GSI2`, `GSI2PK = txtlocal#APIKEY#{sha256(key)}`, then constant-time compare |
| 3 | The account | `GetItem txtlocal#ACCOUNT#{a} / #METADATA` |
| 4 | Users of an account | `Query PK = account, begins_with(SK, "USER#")` |
| 5 | Lists | `begins_with(SK, "LIST#")` |
| 6 | Contacts of a list, a page of 20 | `Query PK = txtlocal#LIST#{list_id}`, cursor |
| 7 | Which lists hold this number | `GSI1`, `GSI1PK = txtlocal#ACCOUNT#{a}#MOBILE#{e164}` |
| 8 | The opt-out set for a campaign | `Query PK = txtlocal#LIST#{optout_list_id}`, every page, into a `set` |
| 9 | Senders and smart senders | `begins_with(SK, "SENDER#")`, `begins_with(SK, "SMART#")` |
| 10 | Who owns this inbound number | `GSI1`, `GSI1PK = txtlocal#NUMBER#{e164}` |
| 11 | Numbers due for renewal today | `GSI2`, `GSI2PK = txtlocal#RENEWALS`, filter `renewsAt <= :today` |
| 12 | History for a date range, newest first, 20 a page | one `Query` per month partition in the range, `SK between`, `ScanIndexForward = false`, filter on `to`/`from` when searching a number |
| 13 | The inbox | `GSI1`, `GSI1PK = txtlocal#ACCOUNT#{a}#CONV`, newest first |
| 14 | A thread | `GSI1`, `GSI1PK = txtlocal#CONV#{a}#{peer}`, newest first |
| 15 | Settle a delivery event | `UpdateItem` on the key `Context.messageKey` names |
| 16 | Campaigns | `begins_with(SK, "CAMPAIGN#")`, sorted by date in the page |
| 17 | What is due now | `GSI1`, `GSI1PK = txtlocal#DUE`, `GSI1SK <= now`, limit 25 |
| 18 | Rules in order | `begins_with(SK, "RULE#")`, sorted by `priority` |
| 19 | Transactions and the full ledger | `Query PK = txtlocal#ACCOUNT#{a}#LEDGER`, newest first |
| 20 | Has this Stripe event been applied | put-if-absent on `txtlocal#EVENT#{event_id}` |
| 21 | Daily cap and rate limit | `UpdateItem ADD n :1` with `ReturnValues UPDATED_NEW` |
| 21a | Developer idempotency | put-if-absent `txtlocal#IDEM#{user_id}#{key}` as `IN_FLIGHT`, `UpdateItem` to `DONE` |
| 22 | Redirect | `GetItem txtlocal#LINK#{code} / #METADATA`, eventually consistent |
| 23 | Clicks for a campaign over a window | `GSI1 txtlocal#CAMPAIGN#{campaign_id}#LINKS`, then one `Query PK = txtlocal#LINK#{code}, SK between DAY#{from} and DAY#{to}` per link |
| 24 | Usage for a month | `Query PK = txtlocal#USAGE#{a}#{yyyy-mm}` |
| 25 | Reporting for a range with filters | one `Query` per month, `SK between` day bounds, filters applied in the page |
| 26 | Rates, packs, pools, catalogue | `Query PK = txtlocal#PLATFORM`, cached five minutes |
| 27 | Websites awaiting review | `GSI2`, `GSI2PK = txtlocal#WEBSITES#UNDER_REVIEW` |
| 28 | Was this day rolled up | `GetItem txtlocal#ROLLUP#{day}` |
| 29 | API logs | no table read: Logs Insights over the `api` log group |

## Flows

### First sign-in (`api` Lambda)

1. The JWT is verified; `username` is the `email` claim.
2. Pattern 1 finds the user. Found: the request proceeds with `accountId` and `role`.
3. Not found: mint `accountId`; write in one transaction the account (`balanceMicro = 2000000`,
   `trialEndsAt = now + 14 days`), the owner user with a fresh API key hash, the opt-out list, the
   shared sender rows and smart senders for `GB`, the three default rules, and the `TRIAL` ledger row,
   every item put-if-absent.
4. A lost condition means a concurrent first request won; re-run pattern 1 and proceed.

### Quick send and campaign confirmation (`api` Lambda)

1. Parse recipients: contacts and lists resolve to E.164 through patterns 6 and 7; typed numbers are
   parsed against `settings.defaultCountry`. A `QUICK` send with more than 1,000 recipients is refused
   with `Send to at most 1,000 recipients at a time`.
2. `messaging.segments` computes `parts` and `encoding` from the body plus footer under
   `settings.maxParts` and `settings.unicodeMode`; the quote is `RATE#{country}#{product}.priceMicro ×
   parts` per recipient, summed.
3. `SendPolicy` runs per recipient for the country, trial and sender checks; the opt-out set is loaded
   once. Refused recipients are dropped and counted in `counts.refused`; a send with no recipients
   left is refused with the first refusal's message.
4. One transaction: debit the account under `DEBIT_IF_COVERED = balanceMicro >= :total`, put the
   `SEND` ledger row, put the campaign row put-if-absent with `status = SCHEDULED`, `scheduledAt` now or
   the chosen time, and `GSI1PK = txtlocal#DUE`. A lost debit condition answers 402 with
   `Your balance is £<x>; this send costs £<y>`.
5. The response is the confirm dialog's numbers: recipients, deliver time, cost.

### Claim and fan-out (`scheduler` Lambda, every minute, concurrency 1)

1. Pattern 17 returns up to 25 due campaigns, `SCHEDULED` ones to claim and `SENDING` ones whose
   fan-out did not finish.
2. A `SCHEDULED` campaign is claimed with `CLAIM_SCHEDULED = #status = :scheduled`, which flips it to
   `SENDING` and sets `claimedAt`; a lost condition means this tick's sibling won and the campaign is
   skipped. A `SENDING` campaign is resumed only if `claimedAt` is older than the function timeout, so
   two ticks never fan out the same page.
3. Recipients come from `recipients` for `QUICK` or pattern 6 page by page for `LIST`, starting at
   `fanoutCursor`; the opt-out set is loaded once; each recipient becomes one `send-jobs` message
   `{accountId, campaignId, messageId, to, country}` with a fresh `uuid7`, sent in batches of ten.
   After every batch one update `ADD`s `counts.queued` and `SET`s `fanoutCursor`, so a crash loses at
   most one batch, which the next tick re-enqueues and the worker's put-if-absent on the recipient
   row absorbs.
4. The update that brings `counts.queued` to `counts.recipients` removes `fanoutCursor` and the `DUE`
   keys.

### Send worker (`send-worker` Lambda, SQS batch of ten, maximum concurrency 2)

1. For each job, put the message row put-if-absent with `status = QUEUED`, `queuedAt = now`, the
   sender's value as `from`, the rendered body with placeholders from the contact row (pattern 7,
   first match). The put is also guarded by a campaign-scoped recipient marker,
   `SK = SENT#{campaign_id}#{e164}` on the campaign's account partition with a 2-day `ttl`, written in
   the same transaction, so a re-enqueued recipient with a fresh message id loses the condition. A lost
   condition reads the existing row: `SENT`, `DELIVERED` or `FAILED` means done; `QUEUED` older than 60
   seconds means a crashed attempt and the send proceeds on that row.
2. `SendPolicy` runs again for the daily cap (pattern 21) and opt-out, because time has passed since
   confirmation. A refusal settles the row `FAILED` with the refusal reason, `ADD counts.refused`, and
   enqueues nothing.
3. `SmsGateway.send_text` with `Context.messageKey = "{PK}|{SK}"`. `Upstream` raises so the message
   returns to the queue with jittered backoff; `BadRequest` settles `FAILED` with the reason.
4. On a receipt, `UpdateItem` `SET status = SENT, providerMessageId, sentAt` under `#status = :queued`,
   `ADD counts.sent :1` on the campaign with `ReturnValues ALL_NEW`, and one log line
   `event=message_accepted` with `account_id`, `user_id`, `campaign_id`, `message_id`, `product`,
   `sender_id`, `country`, `parts`, `price_micro`.
5. The worker that sees `counts.sent + counts.refused == counts.recipients` in the
   returned counts settles the campaign: `SENDING → SENT` under that condition, `settledMicro =
   quoteMicro × counts.sent`, `completedAt`, and one transaction crediting `reservedMicro −
   settledMicro` back to the balance with a `REFUND` ledger row when the difference is positive.
   Provider-accepted messages are billed whether or not they are later delivered, which is how the
   provider bills the platform.
6. Batch item failures are reported per message id, never for the whole batch.

### Delivery event (`delivery-events` Lambda, SNS)

1. Parse the event; `Context.messageKey` names the row; an event without one is logged
   `outcome=unattributed` and dropped.
2. Map the event name through `EVENT_STATUS` in `specs/02-sms-gateway.md` §6; unmapped names are
   logged `outcome=unmapped` and dropped.
3. `UpdateItem` under `status IN` the allowed predecessors, setting `deliveredAt` or
   `failureReason`. A lost condition is a late or repeated event and ends the flow.
4. A won transition `ADD`s `counts.delivered` or `counts.undelivered` on the campaign; nothing is
   refunded, because the provider billed the message on acceptance.
5. If the account has an enabled `DeliveryReportRule`, one `webhooks` job carries the status, the
   ids and the timestamps; the dispatcher signs the body with the rule's secret.

### Inbound (`inbound` Lambda, SNS)

1. Pattern 10 on `destinationNumber` finds a dedicated number's account; otherwise the account is the
   one whose message `previousPublishedMessageId` names, found by the provider id the send worker
   logged onto the row and carried in `Context` on the reply path; nothing found is logged
   `outcome=unattributed` and dropped.
2. Write the inbound message row with `direction = IN`, `status = RECEIVED`, `peer = originationNumber`,
   put-if-absent on `inboundMessageId` as the message id.
3. If the first word is `STOP`, `STOPALL`, `UNSUBSCRIBE`, `CANCEL`, `END` or `QUIT`, upsert the number
   into the opt-out list and `ADD contactCount :1` when the put wins.
4. Pattern 18 loads the rules; every enabled rule whose `senderId` and `match` fit runs its action,
   in creation order, and rules do not stop each other: `AUTO_REPLY` and `SMS` enqueue a `send-jobs`
   message as a `TRANSACTIONAL` quick send of one; `URL` enqueues a `webhooks` job; `MOVE_CONTACT`
   adds the sender to the list in `actionAddress`; `POLL` `ADD`s `votes.{keyword} :1` on the rule row;
   `EMAIL_USER` and `EMAIL_FIXED` log `outcome=email_unavailable` until SES arrives; `GROUP_SMS` fans
   out to the list as a `QUICK` campaign; `SEND_TO_MESSENGER` is a marker, since step 5 runs for every
   inbound.
5. Upsert the conversation: `SET lastPreview, lastAt, lastDirection = IN, status = OPEN ADD unread :1`
   with `GSI1SK = lastAt`.

### Top-up (`api` and `stripe-webhook` Lambdas)

1. `POST /api/app/billing/top-ups` with a pack code: find or create the Stripe customer, store
   `stripeCustomerId` if new, create a Checkout Session in payment mode for `amountMicro / 10000`
   pence with `invoice_creation.enabled`, `metadata.accountId`, `metadata.packCode`, `Idempotency-Key`
   the fresh `entryId`. Answer the session URL.
2. `checkout.session.completed`: verify the signature; one transaction of the `EVENT#{event_id}`
   put-if-absent, `ADD balanceMicro :credit SET hasToppedUp = true` where `:credit` is the pack's
   `amountMicro + bonusMicro` looked up by `metadata.packCode`, and the `TOPUP` ledger row carrying
   the amount paid, the bonus, the invoice number and hosted URL from the session's invoice. A lost
   event condition answers 200.
3. Every other event type answers 200 `Ignored`; a table error answers 500 so Stripe retries.

### Auto-recharge (`api`, `billing-renewals`, `billing-charge`)

1. After a debit, in the reservation transaction's caller or the renewal run, if `autoRecharge` and
   the returned `balanceMicro < lowBalanceThresholdMicro`, `SET rechargeInFlight = now` under
   `attribute_not_exists(rechargeInFlight)`; a win enqueues one `recharge` job.
2. `billing-charge` creates an off-session PaymentIntent for `rechargeAmountMicro` with
   `Idempotency-Key = recharge_{jobId}`, the id the job carried onto the queue, so a redelivery hours
   later is still the same key to Stripe; success credits through the same transaction shape as a
   top-up and removes `rechargeInFlight`; a decline removes `rechargeInFlight` and writes a ledger
   `ADJUSTMENT` of zero carrying the decline code so the page can show it. The credit is fenced on the
   PaymentIntent id, so the synchronous result and a later `payment_intent.succeeded` webhook credit
   the account exactly once between them. A `rechargeInFlight` older than an hour is treated as stale,
   so a crashed invocation cannot wedge auto-recharge for ever.
3. Independently, a debit that crosses `alertThresholdMicro` from at-or-above to below
   `SET lowBalanceAlertedAt = now` under `attribute_not_exists(lowBalanceAlertedAt)`; only the winner
   emails the billing contact, so repeated debits below the line and redelivered work send one
   email. A credit that lifts the balance to or above the threshold removes the attribute under
   `attribute_exists(lowBalanceAlertedAt)`, arming the next crossing.

### Renewals (`billing-renewals` Lambda, daily 06:30 UTC, concurrency 1)

1. Pattern 11 lists dedicated numbers with `renewsAt <= today`.
2. For each, debit `monthlyPriceMicro` under `DEBIT_IF_COVERED` with a `RENTAL` ledger row and
   advance `renewsAt` a month. A lost condition tries auto-recharge; after seven days past due the
   number is released through the gateway, the row becomes `REJECTED` with reason `UNPAID` and its
   `GSI2PK` is removed.

### Rollup (`rollup` Lambda, nightly 02:30 UTC, concurrency 1)

1. The payload names the day, yesterday by default; `{"date": "2026-09-18", "force": true}` replays.
2. Clicks: one Athena query over `aws_cloud.cloudfront_logs` for the day, `cs_uri_stem LIKE '/l/%'
   AND sc_status = 302 AND x_host_header = :host`, grouped by stem; poll to a 300-second deadline;
   for each code, overwrite `txtlocal#LINK#{code} / DAY#{day}` and `ADD clicksTotal` on the metadata
   row under `ROLLUP_ONCE_PER_DAY`, five writes a second with jittered retry on a throttle.
3. Usage: one Logs Insights query over the `send-worker` log group for the day, `filter event =
   "message_accepted" | stats count(*) as quantity, sum(price_micro) as cost_micro by account_id,
   user_id, product, sender_id, country`; poll to a 300-second deadline; overwrite one `Usage` row per
   result, paced the same way.
4. Write `clicksDoneAt` and `usageDoneAt` on the day's marker as each half completes; a run that
   finds a half already done and no `force` skips it.

### Developer API request (`api` Lambda, `/api/v3`)

1. Basic auth: pattern 2 with the SHA-256 of the presented key; compare in constant time; a miss
   answers 401 without saying which half was wrong.
2. Pattern 21 on `txtlocal#RL#{user_id}#{minute}`; over 60 answers 429.
3. A write with an `Idempotency-Key` header runs pattern 21a first: a lost put while `IN_FLIGHT`
   answers 409, a lost put on a `DONE` row replays `responseStatus` and `responseBody`.
4. The route runs against the same services the dashboard uses. `POST /api/v3/sms/send` accepts at
   most 1,000 messages, each with its own body and recipient; the reservation transaction writes an
   `API` campaign for the batch, then `api` enqueues one `send-jobs` message per recipient inline, in
   batches of ten, and answers with the message ids. The idempotency row is set to `DONE` with that
   answer.
5. One log line `event=api_request` with `account_id`, `user_id`, `method`, `route`, `status`,
   `latency_ms`, `request_id`; never the key, the query string or the body.

### API logs (`api` Lambda, `/api/app/developer/logs`)

1. Start a Logs Insights query on the `api` log group for the requested window within the last seven
   days, filtered to `event = "api_request"` and the account, optionally the user, route and status
   class; return the query id.
2. The page polls `/api/app/developer/logs/{queryId}`; results carry the rows and the three tile
   counts from a second `stats` query started alongside.

### Redirect (`redirect` Lambda, `/l/{code}`)

1. Refuse anything but 8 lowercase alphanumerics with a minimal 404 before any network call.
2. `GetItem`, eventually consistent; absent or expired answers the same 404.
3. `302 Location: url`, `Cache-Control: public, max-age=300`. Nothing is written.

## Retention

| Data | Retention | Mechanism |
|---|---|---|
| Messages | 120 days | `ttl` at write |
| Conversations | until closed and older than 120 days | `ttl` set when closed |
| Campaigns | 400 days | `ttl` at completion or cancellation |
| Ledger | no expiry | none; it is the money record |
| Usage | 400 days | `ttl` at rollup |
| Tracked links, link days | 400 days, 90 days | `ttl` at write |
| Daily cap, sent markers | 2 days | `ttl` at write |
| Rate limit | 2 minutes | `ttl` at write |
| Developer idempotency rows | 24 hours | `ttl` at write |
| Stripe events | 30 days | `ttl` at write |
| Rollup markers | 400 days | `ttl` at write |
| Accounts, users, lists, contacts, senders, templates, rules, websites | until the user deletes them | explicit delete |
| `api` log group | 7 days | log group retention in `aws-cloud` |
| `send-worker` log group | 120 days | log group retention in `aws-cloud` |
| CloudFront logs, Athena results | 90 days, 7 days | platform bucket lifecycles |

## Lambdas

| Lambda | Trigger | Role |
|---|---|---|
| `api` | function URL behind `/api*` | dashboard and `/api/v3`; reads and writes every account row, starts Logs Insights queries, talks to Stripe, Cognito admin and the gateway for verification codes and dry runs |
| `redirect` | function URL behind `/l*` | one eventually consistent `GetItem`, `302` |
| `stripe-webhook` | public function URL | signature check, top-up and recharge settlement |
| `send-worker` | SQS `send-jobs`, batch 10, max concurrency 2 | message rows, policy, gateway send, campaign settlement and refund, `message_accepted` log line |
| `delivery-events` | SNS `sms-events` | conditional status transitions, campaign counters, webhooks |
| `inbound` | SNS `sms-inbound` | attribution, opt-out keywords, rules, conversations |
| `scheduler` | `rate(1 minute)`, concurrency 1 | claims due campaigns, fans out `send-jobs` |
| `webhook-dispatch` | SQS `webhooks`, batch 1, max concurrency 2 | signs and posts webhook bodies, three attempts then the dead-letter queue |
| `billing-charge` | SQS `recharge`, concurrency 1 | off-session PaymentIntents |
| `billing-renewals` | `cron(30 6 * * ? *)`, concurrency 1 | dedicated number rental, release when unpaid |
| `rollup` | `cron(30 2 * * ? *)`, concurrency 1 | clicks through Athena, usage through Logs Insights, paced writes |

## Deliberate simplifications and their ceilings

- **Transactions sort by date only.** The tab is the ledger partition filtered to `TOPUP` and read by
  cursor, twenty evaluated rows a page; `order=asc|desc` flips `ScanIndexForward`, so both date
  orders are one `Query` per page with the same cursor. Sorting by invoice number, status or amount
  would mean reading every top-up the account ever made to order one page, an unbounded read, so
  those headers are not sortable. Past that, a GSI on the `TOPUP` rows keyed by amount, or a sort
  over the rows already loaded on the page, labelled as such.
- **The low-balance alert is an email, not an SMS.** The screen says `Email/SMS`; an SMS to the
  owner would be a billed send through `SmsGateway` from inside billing, which the slice boundary
  and the balance rules make a design of its own. Fine while owners read the billing email. Past
  that, billing publishes the crossing and messaging sends it as a system message to
  `Account.mobile`.

- **A campaign's delivered counter can fall short of its message rows.** The delivery event flips
  the message row and then adds to the campaign counter; if the counter write is lost to a throttle,
  the redelivery is refused by the row's own final-state guard and the counter never catches up. The
  per-message statuses stay correct and no money is involved, so the campaign report can read 99 of
  100 when all 100 arrived. Exactly-once needs the message row and the campaign counter in one
  transaction, which the slice boundary forbids, or a per-event marker row, which adds a write to the
  busiest path in the system. Past that, spend the marker.
- **A request that fails API-key authentication is logged without an account.** Authentication
  failed, so there is nobody to attribute it to, and the API Logs screen filters by account: a
  developer debugging a rejected key sees nothing there and relies on the 401 body instead. The lines
  are still in the log group for an operator to find. Attributing them would mean an unauthenticated
  lookup by username on every request, which is a request amplifier. Past that, an operator-facing
  search rather than a customer-facing one.
- **The table is shared three ways at the free 25 read and 25 write units, and the send worker is
  paced by an event source mapping concurrency of two.** Fine to about five messages a second, so a
  campaign of ten thousand takes half an hour and a quick send of five hundred about two minutes; the
  two other applications keep their share of the units. Past that, a dedicated on-demand table for
  this app, about ten cents a month at demo volume, and a higher worker concurrency in `aws-cloud`.
- **Messages live in monthly partitions and History reads at most five of them.** Fine for the
  4-month window the product promises; a range wider than the retention is clamped. Past that, a
  weekly partition and the same loop.
- **Searching History by number is a filter expression inside the partition.** Fine while an
  account's month holds tens of thousands of rows, since the read is still one partition. Past that,
  the thread index already answers "everything with this peer" in one query.
- **A quick send embeds at most 1,000 recipients on the campaign row.** Fine well inside the 400 KB
  item limit and the confirm dialog's patience. Past that, the page steers a bigger send into a list
  campaign, which pages the list.
- **The conversation list is one GSI1 partition per account.** Fine to tens of thousands of
  conversations; the partition is written once per message. Past that, shard the list key by month.
- **The due index is one platform-wide GSI1 partition.** Fine to thousands of scheduled campaigns,
  read 25 at a time once a minute. Past that, shard by the hour of `scheduledAt`.
- **Fan-out and send are at-least-once.** A worker that dies between claiming a row and receiving a
  receipt resends after 60 seconds, so a recipient can receive a duplicate once in a crash. The
  provider offers no idempotency token. Past that, a per-message outbox with a provider-side
  reference where a provider offers one.
- **Campaign counters are `ADD`s on one item.** Fine to about a thousand updates a second per
  campaign, far above the send pace. Past that, count from the message rows nightly.
- **The opt-out set is loaded whole at fan-out.** Fine to about fifty thousand opted-out numbers,
  a few pages of reads. Past that, a per-recipient index read, which is the mobile index.
- **Usage is next-day and a Reporting range spans at most four months.** The tabs show through
  yesterday because the rollup runs at 02:30, and a range is one `Query` per month touched, so the
  page clamps it to four. Past that, run the usage half hourly for the current day; the rows
  overwrite, and a longer range is a loop over more months.
- **A developer send is at most 1,000 messages and is fanned out inside the request.** A hundred
  `SendMessageBatch` calls fit the 29-second timeout with room. Past that, the batch becomes a
  `LIST`-shaped campaign the scheduler fans out.
- **API logs are Logs Insights at read time.** A page load takes a few seconds and the retention is
  the log group's seven days; concurrency is the account's thirty queries. Past that, a subscription
  filter to Firehose, S3 and Athena, which bills.
- **Locally, the clicks and usage rollups read the API's own log file instead of Athena and Logs
  Insights.** There is no CloudFront, no Glue table and no log group on a laptop. `redirect` emits one
  extra `event=redirect_hit` line (harmless in production too) alongside `message_accepted` and
  `api_request`, all three already landing in one process's log file locally since `send-worker` and
  `redirect` run in-process under `LocalBus`; `LocalUsageQueries` and `LocalClickQueries` filter and
  aggregate that file exactly as `LocalLogQueries` already does for API Logs, gated the same way
  (`AWS_ENDPOINT_URL_DYNAMODB` set). Past that, nothing changes: this is a dev-only substitution
  behind the same `UsageQueries`/`ClickQueries` ports the real Insights and Athena implementations
  satisfy, never reached when deployed.
- **Locally, media uploads are served by this API instead of a presigned S3 PUT and a CloudFront
  GET.** There is no sites bucket on a laptop. `LocalMediaStorage` hands back an upload URL on this
  same API; `PUT`/`GET /api/app/messaging/media/{key}` write and read the bytes under `.local/media/`,
  behind the same `MediaStorage` port `S3MediaStorage` satisfies for a real deployment, gated the same
  way every other local/real split in `wiring.py` is. Fine to the 1 MB, `image/jpeg`/`image/png`/
  `image/gif` ceiling Quick MMS already enforces. Past that, nothing changes: this is a dev-only
  substitution never reached when deployed.
- **One `SendTextMessage` per message; MMS is a link outside the United States and Canada.** The
  provider's limits, named in `specs/02-sms-gateway.md`.
- **Cognito's default sender emails fifty addresses a day.** Fine for a demo's sign-ups and
  invitations. Past that, SES as the pool's sender, which arrives in phase 6.
- **Trial credit is never clawed back.** An expired, never-topped-up account keeps £2.00 on its row
  and cannot spend it. Past that, a `TRIAL_EXPIRED` ledger debit written by `billing-renewals`.
- **API keys are shown once and stored as a hash**, a departure from the screenshot, which shows the
  key in the clear. There is no upgrade; the departure is the point.
- **There is no webhook delivery log.** A delivery that fails three times is on the dead-letter
  queue and in the logs; the page shows nothing. Past that, a `WEBHOOKATTEMPT#` row per attempt with a
  7-day `ttl`.
- **Website registration has no human review.** A registration is `UNDER_REVIEW` for 24 hours and the
  scheduler then sets `APPROVED`, in every mode; the `GSI2` queue is kept as the hook for an operator.
  Sending links never waits for approval. Past that, an operator approval endpoint or an automated
  reputation check.
- **Renewals read the whole `RENEWALS` partition and filter by date.** Fine to thousands of rented
  numbers. Past that, `GSI1` is taken by the number lookup, so a `RENEWAL#{date}` sort on a third
  index or a daily partition.
- **Platform rates are cached five minutes per process.** A price change reaches every function
  within five minutes. Past that, nothing; that is the point of a cache.
- **Sub-accounts are users of the same account with no credit allocation, roles or limits.** The
  screenshots show none. Past that, a `limits` map on the user row and a check in the policy.
- **No reseller, referral, automation builder, fax, voice, RCS or WhatsApp.** They are out of scope,
  not deferred.
- **Free-tier envelope this model lives in**: 25 read and 25 write units shared three ways, 400k
  GB-seconds and a million invocations a month of Lambda shared three ways (the scheduler alone is
  44k), the ten free alarms and ten free custom metrics already spent by `donation`, CloudFront's
  ten million requests, CloudWatch's five gigabytes of log ingestion, Cognito's ten thousand monthly
  active users, and Athena billed at the ten-megabyte minimum per nightly query.
- **A ledger row's `balanceAfterMicro` is computed from the balance read before its transaction.** The
  account row itself is always exact, because the debit and credit are server-side arithmetic under a
  condition; only the annotation on two rows written by interleaving debits can be off by the other's
  amount. Past that, an equality condition on the read balance with a bounded retry.
- **A delivery event's timestamps come from the receiving Lambda's clock, not the provider's
  `eventTimestamp`.** The two differ by the delivery lag, seconds at most, and one clock per row keeps
  History monotonic without trusting a field the provider may backdate. Past that, store both and
  render the provider's.
- **A delivery event that overtakes its own receipt fills the row in with `if_not_exists`.** Under
  `LocalBus` the fake gateway's event is handled before the `SENT` write returns, so the transition
  writes `providerMessageId` and `sentAt` only when they are still absent, and the later receipt write
  loses its condition harmlessly. Nothing is lost; the row is complete either way.
- **The MMS history filter is a `begins_with(kind)`, so `MMS` includes `MMS_AS_LINK`.** That is the
  product's intent: a message the customer composed as an MMS belongs on the MMS screen whatever the
  provider did with it. Past that, two filters and a column.
- **A campaign settles when its recipients are all accounted for, and a sweep catches the rest.** A
  send job that exhausts its retries and lands on the dead-letter queue is counted neither `sent` nor
  `refused`, so without a sweep the campaign would stay `SENDING` and its reservation would never be
  returned: the customer would have paid for recipients nobody reached. The scheduler settles a
  campaign whose fan-out finished and whose last progress is more than an hour old, at the same
  billing call and under the same one-refund-per-campaign key, so a late outcome cannot double-refund.
  Past that, a daily reconciliation that re-reads the ledger against the message rows, as the sibling
  payments app does.
- **A contact import counts new rows with a read before an unconditional batch write.** Two imports of
  the same new number at the same moment can leave `contactCount` one too high; the rows themselves are
  correct, because the key is the number. Past that, a conditional write per row, at one write unit
  each instead of a batch.
- **A list name is unique by a read then a write.** Two creates of the same name in the same instant
  both succeed. Past that, a `LISTNAME#` pointer row written put-if-absent in the same transaction.
- **Searching inside a list filters the page it read.** A match beyond the first page is not found.
  Past that, an index on the name, or a search service once a list outgrows a page.
- **A list is read in at most twelve query pages** for export, clean-up, opt-out loading and deletion.
  That covers the ten thousand a list may hold. Past that, the work moves to a paged background job.
