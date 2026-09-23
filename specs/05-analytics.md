# Analytics: three feeds counted from logs, one nightly rollup

Nothing in a request path writes a counter. Clicks are counted from CloudFront's access logs through
Athena, exactly as shorten does; usage and the API log screen are counted from the functions' own
structured log lines through CloudWatch Logs Insights. One Lambda, `rollup`, runs nightly at 02:30 UTC
and turns yesterday's logs into rows the dashboard reads in one query. `docs/architecture.md` decision
9 is why; this file is the contracts: the two log lines, the three feeds, the rollup's idempotency, the
reads, the cost and the ceilings.

## 1. The two log lines

Both are emitted through `telemetry.log(event, **fields)` and land as one JSON object per line with
the fields at the top level. A field in this table is an interface: renaming one changes the query in
§3 or §4 in the same commit, and `analytics/tests/test_queries.py` asserts the field names the queries
use against the constants the emitters use.

### `message_accepted`, from `send-worker`

Emitted once per message the gateway accepted, after the `SENT` write won its condition, never before,
so a message that failed to leave is not usage.

| Field | Value |
|---|---|
| `event` | `message_accepted` |
| `account_id`, `user_id` | the sender's account and user |
| `message_id` | the row's id |
| `campaign_id` | the campaign's id, or `-` for a quick send, an API send, an auto-reply |
| `product` | `SMS`, `MMS`, `MMS_AS_LINK` |
| `sender_id`, `sender_kind` | the sender row's id and `SHARED`, `OWN`, `DEDICATED`, `ALPHA` |
| `country` | the destination's ISO code |
| `parts`, `encoding` | segments and `GSM7` or `UCS2` from `messaging.segments` |
| `price_micro` | the quoted price debited from the balance |
| `mode` | the `SMS_MODE` the send ran under |

No destination number, no body. The `send-worker` log group keeps 120 days, which covers the History
screen's four months and any replay window; the log group name is `/aws/lambda/txtlocal-send-worker`
and the rollup reads it by name from `SEND_LOG_GROUP`.

### `api_request`, from `api`

Emitted once per `/api/v3` request by the router middleware; fields are `event`, `request_id`,
`account_id`, `user_id`, `method`, `route`, `status`, `latency_ms`, `outcome`, as
`specs/04-developer-api.md` §3 defines them. The `api` log group keeps 7 days. This feed has no rollup
and no rows: the API Logs screen queries the group live (`specs/04-developer-api.md` §9).

## 2. Tracked links

### Codes

A tracked link is `LINK` row `txtlocal#LINK#{code}` with `url`, `account_id`, `campaign_id`,
`created_at`, `clicks_total`, `last_rollup` and a `ttl` of 400 days. `code` is ten characters from the
same alphabet as shorten, `a-z0-9` without `l`, `o`, `0`, `1`, drawn from `secrets.choice`; the put is
conditioned on `attribute_not_exists(PK)` and a collision draws a fresh code, up to eight attempts,
without backing off, because a collision is not a transient. The eighth failure raises `Internal`.

### Rewriting a body

`Shorten my URL` on Quick SMS and `Short URL` on a campaign call `analytics.service.shorten_urls(body,
account_id, campaign_id)` before `messaging.segments` counts the message. Every `https?://` token in
the body becomes `https://<PUBLIC_BASE_URL>/l/<code>`; one code per distinct URL per campaign, so a
campaign of ten thousand with one link makes one row, and a quick send makes one row per URL. The
rewritten body is what is stored, sent and shown in History; the original URL lives on the `LINK` row
only. Segment counting happens after the rewrite, which is why the Short URL toggle can lower a part
count.

### The redirect

`redirect` serves `GET /l/{code}` on the CloudFront behaviour `/l*`, cache policy keyed on the path
only, no cookies, no query strings. A code that fails the length or alphabet check is a 404 before any
network call. Otherwise one eventually consistent `GetItem`; an absent or expired row is the same
minimal 404 as an invalid code, because distinguishing them tells an enumerator which guesses were
close. A hit answers `302`, `Location: <url>`, `Cache-Control: public, max-age=300`. The function
touches nothing else: no counter, no log line beyond the runtime's own, no second read.

### Counting clicks

CloudFront standard logging v2 writes the distribution's requests to the shared logs bucket and the
platform's Glue table `aws_cloud.cloudfront_logs` reads them through partition projection on `year`,
`month`, `day`. The rollup runs, for yesterday:

```sql
SELECT cs_uri_stem, count(*) AS clicks
FROM "aws_cloud"."cloudfront_logs"
WHERE year = :year AND month = :month AND day = :day
  AND x_host_header = :host
  AND cs_uri_stem LIKE '/l/%'
  AND sc_status = 302
GROUP BY 1
```

`:host` is `PUBLIC_HOST`, this distribution's domain, because shorten's logs share the table and the
bucket. `sc_status = 302` excludes the 404s and the site's own paths; `GROUP BY` keeps the result
proportional to links, not clicks. The query runs in workgroup `ATHENA_WORKGROUP` with output
`ATHENA_OUTPUT`, polled with `table.backoff` to a 300 s deadline, results paged by `NextToken` to at
most 200 pages, the header row skipped. A stem whose code fails the alphabet check is tallied as
`discarded_clicks` in the run summary and dropped.

Each row becomes `LINKDAY` row `txtlocal#LINK#{code}` / `DAY#{yyyy-mm-dd}` with `clicks` and a 90-day
`ttl`, written as an unconditional put so a replay overwrites the day, followed by
`ADD clicks_total :clicks SET last_rollup = :day` on the `LINK` row under
`ROLLUP_ONCE_PER_DAY = "attribute_exists(PK) AND (attribute_not_exists(last_rollup) OR last_rollup <
:day)"`, so a replay of an older day rewrites the day row but never double-counts the total. Zero-click
days write no row and are absent from reads; the page fills the gaps.

## 3. Usage

### The query

Over `SEND_LOG_GROUP` for the UTC day, `StartQuery` with `startTime` and `endTime` at the day's
bounds:

```
fields account_id, user_id, product, sender_id, country, price_micro
| filter event = "message_accepted"
| stats count() as quantity, sum(price_micro) as cost_micro
    by account_id, user_id, product, sender_id, country
```

`GetQueryResults` is polled with `table.backoff` until `status` is `Complete`, to a 240 s deadline;
`Failed`, `Cancelled` and `Timeout` raise `Internal` with the status. Results arrive as rows of
`{field, value}` pairs and are narrowed into `UsageLine(account_id, user_id, product, sender_id,
country, quantity, cost_micro)` at the edge; a row missing a field is counted as `discarded_lines` and
dropped.

### The rows

Each line becomes `USAGE` row `txtlocal#USAGE#{account_id}#{yyyy-mm}` /
`{yyyy-mm-dd}#{product}#{user_id}#{sender_id}#{country}` with `quantity`, `cost_micro`, `day` and a
400-day `ttl`, written as an unconditional put so a replay overwrites. The partition is the account's
month, so a month is one `Query` and a day is a `begins_with` on the sort key; no index is involved. Writes are paced at five a
second, a 200 ms sleep before each, and a `ProvisionedThroughputExceededException` retries with
`table.backoff` up to eight times; the table is shared three ways and shorten's rollup finished a
quarter of an hour earlier.

### Once per feed per day

The run starts by putting `txtlocal#ROLLUP#{yyyy-mm-dd}` / `FEED#{feed}` with
`attribute_not_exists(PK)` for each feed it is about to run, `clicks` and `usage`; a lost condition
means that feed already finished for that day and is skipped. The marker is written before the feed
runs and removed if the feed raises, so a crash mid-feed reruns it the next night or on replay. The
scheduled event carries no payload and means yesterday and both feeds; a manual invocation with
`{"date": "2026-09-18", "feeds": ["usage"]}` deletes that day's marker for the named feeds first and
reruns them, which is the replay path. The run summary
`event=rollup_done day=… feeds=… link_rows=… usage_rows=… discarded_clicks=… discarded_lines=…` is
the last line every run logs, and `txtlocal-rollup-failed` breaches when a night has no run at all.

## 4. Reads

- **Usage tab.** Month `yyyy-mm` for an account is one `Query` on `txtlocal#USAGE#{account}#{yyyy-mm}`.
  The Lambda sums by `product` and `user_id` and answers `month, product, userId, quantity,
  costMicro`, the screenshot's five columns, money as integer micro-pounds. The page's `EXPORT`
  writes the cost as the decimal pounds text the table showed before, trailing zeros trimmed to at
  least two places, at most four.
- **Usage Reporting tab.** A date range of at most 120 days touches at most five account-month
  partitions: one `Query` per month with the sort key `BETWEEN` the first and last day in that month,
  filtered in the Lambda by the products, sub-accounts, sender ids and countries
  the request names, sorted by day descending, paged ten a page from the assembled list. `EXPORT`
  streams the unfiltered-by-page list as CSV with the eight columns of the screen, `price` as decimal
  pounds to at most four places and `total` rounded to two, in the CSV only. The API answers
  `priceMicro` and `totalMicro`, integer micro-pounds, never rounded.
- **Campaign clicks.** The campaign's `LINK` rows (at most a handful per campaign, listed through
  GSI1 `txtlocal#CAMPAIGN#{id}#LINKS`) and, for a window, one chunked `BatchGetItem` of `LINKDAY` keys,
  100 a chunk, unprocessed keys re-queued with backoff up to eight rounds, leftovers raising `Internal`
  rather than answering a partial count. The campaign list column shows `clicks_total`.
- **API logs.** Live Insights, no rows, `specs/04-developer-api.md` §9.

## 5. Cost

| Item | Monthly |
|---|---|
| Thirty Athena queries, almost all at the 10 MB minimum | about $0.01 |
| Thirty nightly Insights queries and the API Logs screen's queries, $0.005 per GB scanned, megabytes scanned | rounds to $0 |
| Logs ingestion, well inside 5 GB | $0 |
| Log storage at 120 days of `send-worker` lines | under a cent |
| Athena results, 7-day lifecycle | under a cent |

The workgroup's 1 GB scan cutoff turns a mistaken query into a failure rather than a bill; the
`LINKDAY` and `USAGE` writes are inside the shared 25 units because they are paced.

## 6. IAM

All of it lands in `aws-cloud`'s `terraform/apps/txtlocal.tf` by setting `analytics` on the module
and by two additions the module does not yet make:

| Function | Beyond the table |
|---|---|
| `rollup` | `athena:StartQueryExecution`, `GetQueryExecution`, `GetQueryResults` on workgroup `aws-cloud-analytics`; `glue:GetTable`, `GetDatabase`, `GetPartitions` on `aws_cloud.cloudfront_logs`; `s3:GetObject`, `ListBucket` on the logs bucket; `s3:GetObject`, `PutObject`, `ListBucket` on the results bucket; `logs:StartQuery`, `GetQueryResults`, `StopQuery` on the `send-worker` log group |
| `api` | `logs:StartQuery`, `GetQueryResults`, `StopQuery` on its own log group |

The module's `analytics` block already grants the Athena, Glue and bucket set to a function named in
it; the `logs:*Query` grants on named groups and the 7-day and 120-day `retention_in_days` per function
are the two module inputs `tasks/plan.md` asks for.

## 7. Ceilings

- **Usage is next-day.** The Usage tab shows through yesterday. Past that, a second schedule runs the
  usage feed hourly for today with the marker keyed by hour and the day's rows overwritten.
- **Insights returns 10,000 rows and allows 30 concurrent queries per account.** A night with more
  than 10,000 distinct account-user-product-sender-country lines truncates; a busy API Logs screen
  competes with the rollup. Past that, a subscription filter on the group into Firehose, S3 and Athena,
  and the same rows written from the Athena result.
- **Clicks are next-day.** Past that, CloudFront real-time logs into Kinesis, which bills.
- **No per-recipient click attribution.** One code per campaign per URL; the campaign knows its
  clicks, not who clicked. Past that, a code per recipient at one `LINK` row each, and the redirect's
  cache key unchanged.
- **CloudFront logs share one bucket, one Glue table and shorten's partition scheme.** The `:host`
  filter is what keeps the two apart, and the platform's query scans both apps' logs for the day.
  Past that, a `delivery` per distribution into its own prefix and a second Glue table.
- **The rollup is one sequential Lambda.** About 1,400 paced writes fit the 900 s timeout after the
  two queries' worst-case waits; plan for half. Past that, the usage feed and the clicks feed become
  two functions on two schedules.
- **A log line lost is usage lost.** A crash between the `SENT` write and the log line under-reports
  usage by one; the balance is unaffected because it was debited in the transaction, never from the
  log. Past that, emit the line from the delivery event instead, at the cost of counting only delivered
  messages.
