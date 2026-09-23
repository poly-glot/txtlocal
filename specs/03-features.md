# Features

txtlocal is an SMS platform, UK first. An account holds a GBP balance and spends it on
messages; contacts live in lists; a message leaves from a sender the account owns, rents or shares;
replies land in an inbox and can trigger rules; developers get an API with keys and webhooks; billing
is Stripe; usage and clicks are counted from logs. This file transcribes the 46 screenshots in
`screenshots/` into a functional specification, slice by slice, in the order of
`docs/architecture.md` §3. Labels, limits, defaults, statuses and copy are quoted as the screens show
them, with txtlocal as the product name throughout. Where a screen was cropped or
not captured the text says "not captured; decision: …" and picks the simplest faithful behaviour.
Where this product departs from the screens on purpose the departure is stated where it applies.

## Navigation

- Sidebar
  - `Home`
  - `Automation` (excluded from v1, see the end of this file)
  - `Contacts`
  - `Sender IDs` › `Manage Senders` (tabs `Smart Senders` | `My Numbers` | `Alpha Tags`), `Buy A Number`
  - `SMS` › `Quick SMS`, `SMS Campaign`, `Website Registration`, `Templates`, `Email SMS`, `Messenger`, `History`
  - `MMS` › `Quick MMS`, `MMS Campaign`, `History`
  - `Integrations` (excluded from v1)
  - `Developers` › `API Credentials`, `API Logs`, `API Documentation`, `Libraries & SDKs`, `Webhooks`
  - collapse chevron bottom-left
- Avatar menu: `User ID: <id>`, `My Profile`, `Account Settings`, `Messaging Settings`, `Billing`,
  `Global Sending`, `Reseller Clients` (excluded), `Reseller Settings` (excluded), `Referrals`
  (excluded), `Logout`
- Billing tab strip, page header `Billing`: `Top Up Account`, `Manage Credit Cards`, `Transactions`,
  `Usage`, `Usage Reporting`, `General`, `Upcoming Charges`
- API Credentials tabs: `Subaccounts`, `General`
- Messaging Settings, page header `Messaging Settings`, tab `SMS & MMS`, sub-tabs: `Inbound Rules`,
  `Delivery Report Rules`, `General`, `Email SMS`. The sidebar entry `Developers › Webhooks` lands here.

Global chrome on every page: the top bar shows the page title; while the account is in trial a banner
reads `Only <n> days to use your free trial credit. Top up for full access.` with the link
`Top up now`; the right side shows `Balance: £<x.xx>` followed by a `+` that opens Top Up Account, a
help icon, a bell, a key icon (opens API Credentials), the avatar with a presence dot and a language
pill `English`. The balance is shown to two decimal places and refreshes after every send and top-up.

Two API faces serve the product from the one `api` Lambda: `/api/app/*` for the dashboard,
authenticated with the Cognito access token, and `/api/v3/*` for developers, authenticated with HTTP
Basic `username:api_key`. The endpoint tables below are the dashboard face; `specs/04-developer-api.md`
owns the developer face. Money on the wire is micro-pounds in `*Micro` fields, a departure from the
screens' decimal pounds, and the page formats it.

## identity

Owns the account, its users and sub-accounts, sign-in mapping, the profile, and the messaging settings.

### Screens

#### Home

Onboarding dashboard for a trial account. Left column: a welcome card `Welcome to txtlocal <First>
<Last>!` with a video tile `Learn to use your Dashboard` `2 Mins`; a strip `Send some test messages
with your free trial credit. You've got <n> days to try it out.`; tabs `SEND A TEST MESSAGE` (active)
| `GET STARTED WITH TXTLOCAL`; the test-send form; a card `Finish setting up your profile`, `A few quick
steps and you're ready to send.`, with the checklist `Verify your number` → `All done. Your number is
verified.` and `Verify your email` → `Email verified. Your account is good to go.`, each struck
through when done, and the link `Not sending from the dashboard? Switch your view` (not captured;
decision: links to API Documentation). Right column: a phone preview headed `SENDER ID` whose body
reads `Type a message to see preview` until the form has text; a stats card `Trial Days Left` `<n>`,
`Messages Sent` `<n>` and the link `Add Credits`.

Test-send form:

| Field | Type | Details |
|---|---|---|
| `Recipient` | text | placeholder `Enter phone number`; helper `Start typing a number. You can enter multiple numbers separated by a comma.` |
| `Sender ID` | read-only | value `txtlocal Sender ID`; helper `This is your temporary Sender ID for testing. You can set up your own whenever you're ready.` |
| `Message content` (required) | textarea | placeholder `Type a test message to check out how it works.`; footer left `£<balance> credit`; footer right counter `<chars> / 1224` with an info icon |
| submit | button | not captured; decision: label `SEND TEST MESSAGE`, disabled until a recipient and text exist, submits through Quick SMS with the shared sender |

`Messages Sent` is the sum of this month's `USAGE` day rows plus today's daily-cap counter, so it is
exact for today and next-day for the month (see analytics).

#### Profile

Reached from `My Profile`. One card, `Save` at the bottom.

| Field | Type | Details |
|---|---|---|
| `First Name` | text | required, 1–50 characters |
| `Last Name` | text | required, 1–50 characters |
| `Username / Email` | text, disabled | the Cognito username; immutable |
| `Phone` | text | E.164 after normalisation with the account's default country |

#### Account Settings

Not captured; decision: one card with `Account Name`, `Timezone` (IANA name, default
`Europe/London`), `Default Country Code` (ISO 3166 alpha-2, default `GB`, shared with Messaging
Settings › General), and a `Delete account` button that is out of scope in v1 and not rendered.

#### Subaccounts

Reached from `API Credentials` › tab `Subaccounts` (the `General` tab belongs to developer). Actions:
`ADD SUBACCOUNT` (primary) and a `Search` input. Table, every header sortable: `USERNAME` | `API KEY` |
`EMAIL ADDRESS` | `PHONE NUMBER` | `NOTES`. The owner appears as the first row. The `API KEY` cell shows
the key's first eight characters followed by an ellipsis, with the inline link `Regenerate`; `Copy` is
offered only in the modal that shows the key at the moment of creation or regeneration. Departure from the screens: the
screens show every key in full for ever; here a key is shown once, in a modal, on creation and on
regeneration, because the platform stores only its hash.

`ADD SUBACCOUNT` modal (not captured; decision): `Username / Email` (email, required, unique across the
platform), `First Name`, `Last Name`, `Phone Number` (optional), `Notes` (optional, 200 characters),
button `ADD`. Creating a sub-account creates a Cognito user, sends the invitation with a temporary
password, and shows the new API key once.

#### Messaging Settings › General

Sections, each with its own `Save`:

- `From Options`: `Show the 'Your Number' option on the dashboard:` toggle `No`/`Yes`, default `Yes`;
  `Show the 'Business Name' option on the dashboard:` toggle `No`/`Yes`, default `Yes`.
- `Character Limit`: `Max number of message parts:` select; options `1 = 160 characters` through
  `8 = 1224 characters` (the parts × 153 for two or more parts); default `8 = 1224 characters`.
- `Unicode`: `Select Unicode SMS:` radios `Autodetect` (default) | `Force non unicode (GSM Characters
  only)`; info box `Autodetect: Will allow normal GSM characters and unicode characters (e.g. English,
  French and Chinese Characters)` / `Force non-unicode: Will only allow GSM characters
  http://en.wikipedia.org/wiki/GSM_03.38`.
- `Default Country Code`: `If the recipient phone number isn't formatted in international format,
  we'll automatically format it for you. This will` (cropped; decision: the sentence ends `use the
  country below.` and the control is an ISO country select, default `GB`).

### Rules

1. Sign-up creates an account and its owner user in one transaction; the account starts with a
   `TRIAL` ledger row of £2.00 (2,000,000 micro-pounds), `trial_ends_at = now + 14 days`,
   `has_topped_up = false`, currency `GBP`, pricing country `GB`.
2. `is_within_trial(account, now)` is `now < trial_ends_at`; `can_send(account, now)` is
   `has_topped_up or is_within_trial`. The banner's `<n>` is the whole days left, floored, never below 0.
3. The username is the Cognito username and never changes; profile edits touch first name, last name
   and phone only.
4. A sub-account is a user with role `SUB` in the same account and pool; it signs in with its own
   password, owns its own API key, sends from the account's senders and spends the account's balance.
   The owner has role `OWNER`; a sub-account cannot create sub-accounts or see Billing.
5. Usernames are unique across the platform: creating a user whose email exists anywhere answers
   `Conflict` with `That email address already has an account`.
6. Cognito's default sender delivers verification and invitation emails, 50 a day per pool; the
   ceiling and its upgrade path (SES, phase 6) are in the data model spec.
7. `max_message_parts` bounds every quote for the account: a body that needs more parts is refused
   with `Message needs <n> parts; your limit is <max>`.
8. `unicode_mode = GSM_ONLY` refuses a body containing a character outside GSM 03.38 with
   `Character "<c>" is not available in GSM mode`; `AUTODETECT` switches the encoding to UCS-2.
9. The default country normalises any number not starting with `+`: `07411972333` with `GB` becomes
   `+447411972333`; a number that cannot be normalised is refused with `Enter the number in
   international format, for example +447400123123`. A number that already carries its country code
   (`+44…`, `0044…`) but whose digits are not valid there, such as the reserved `+447700900123`, is
   refused with `That is not a valid +44 number; check the digits` instead, because its format is
   not the problem.

### Statuses

`UserRole`: `OWNER`, `SUB`. `UserStatus`: `INVITED` → `ACTIVE` (first sign-in), `DISABLED`
(owner action; not captured, kept for the sub-account row menu). `UnicodeMode`: `AUTODETECT`,
`GSM_ONLY`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/me` | current user, role, account summary, trial days, balance |
| GET | `/api/app/home` | the dashboard card values and checklist |
| PATCH | `/api/app/me/profile` | first name, last name, phone |
| GET, PUT | `/api/app/account/settings` | account name, timezone, default country |
| GET, PUT | `/api/app/account/settings/messaging` | from options, max parts, unicode mode |
| GET | `/api/app/account/users?q=` | sub-account rows |
| POST | `/api/app/account/users` | create a sub-account, returns the key once |
| PATCH | `/api/app/account/users/{userId}` | notes, phone, status |

### Acceptance

- [ ] Sign-up produces exactly one account, one `OWNER`, one `TRIAL` row; the balance reads £2.00.
- [ ] `can_send` is tested at `trial_ends_at - 1s` (allowed) and `trial_ends_at` (refused) with and
      without a top-up.
- [ ] Max parts tested at 8 parts accepted and 9 refused with the verbatim message; force-GSM tested
      with `£` (GSM, accepted), `€` (GSM extension, accepted) and `😀` (refused, verbatim message).
- [ ] Number normalisation tested for `07411972333`, `+447411972333`, `447411972333`, `abc`.
- [ ] A `SUB` gets `Forbidden` on every `/api/app/billing/*` and on creating users.
- [ ] Duplicate email answers 409 with the verbatim message.

## billing

Owns the balance, the ledger, rates and packs, top-ups, cards, auto-recharge, renewals and the
Transactions, General, Upcoming Charges and Manage Credit Cards screens. Usage and Usage Reporting sit
under the Billing tab strip but are read models owned by analytics.

### Screens

#### Top Up Account

Header `Current credit balance: £<x.xx> GBP` with a badge `Auto Recharge OFF` or `Auto Recharge ON`.
Copy: `Use your credit for any txtlocal product, including dedicated numbers.` / `Prices are shown in
British Pounds.` Select `Show prices for` with a help icon, default the account's pricing country
(`United Kingdom`); changing it re-prices every estimate.

`Credit boost`: rate line `£0.0427` (help icon) `/ SMS`; four cards with a `+` button: `Top-up £10` `~
234 SMS to United Kingdom`, `Top-up £30` `~ 702 SMS to United Kingdom`, `Top-up £50` `~ 1,170 SMS to
United Kingdom`, `Top-up £100` `~ 2,341 SMS to United Kingdom`.

`Power packs`, `Bigger top-ups. Bigger savings.`: three cards, each a name, a savings badge, a rate,
an amount select, a `Top-up` button and an estimate: `Growth pack` `Save 9%` `£0.0387 / SMS` `£300` `~
7,751 SMS to United Kingdom`; `Scale pack` `Save 19%` `£0.0343 / SMS` `£1,500` `~ 43,731 SMS to United
Kingdom`; `Enterprise pack` `Save 26%` `£0.0313 / SMS` `£4,000` `~ 127,795 SMS to United Kingdom`.
Other amounts in the selects were not captured; decision: each pack offers exactly the one amount
shown. Side panel `Sending over 100K SMS?` `You might be able to save big with our premium rates.` link
`Speak to sales` (mailto). Footer card `Use your credit for any product` listing `Automation Builder:
£0.0009` (excluded product; the line is not rendered in v1).

Pressing `+` or `Top-up` creates a Stripe Checkout Session and redirects; returning to
`/billing?topup=<id>` shows `Payment received. £<x> added to your balance.` once the webhook has
credited it, or `Waiting for your payment to confirm…` with polling until then.

#### Manage Credit Cards

Action `ADD NEW CARD` (Stripe Checkout in setup mode, then back). Table `CREDIT CARD` | `CARDHOLDER
NAME` | `EXP. DATE`; row actions (not captured; decision) `Make default`, `Remove`; a `Default` chip on
the default card. Empty state `No card`.

#### Transactions

Table `INVOICE #` | `DATE` | `STATUS` | `AMOUNT`; each row is a paid top-up with the Stripe invoice
number linking to Stripe's hosted invoice. Empty state `No transactions`. 20 per page, read by cursor.
Decision: only `DATE` is sortable, newest first by default; pressing it flips the order and reloads
from the first page. The ledger is one partition read by cursor in sort-key order, so date order in
either direction is the one order a page can answer without reading every row; the other columns
are not sortable, a deliberate simplification recorded in `specs/01-dynamodb-data-model.md`.

#### General

Section `Billing Contact`: `Account Name`, `Account Email`, `Account Mobile`, `Save`. Section `Balance
Management`: helper `If you purchase a dedicated number, auto recharge will be automatically enabled at
the end of each month. This can be stopped by cancelling the number.`; toggle `Automatically top up my
account:` default off; when on, two further controls (not captured; decision) `Top up by` select of the
four boost amounts, default `£10`, and `when my balance goes below` select `£5.00` | `£10.00` |
`£20.00` | `£50.00`, default `£5.00`; select `Send me an Email/SMS when my account balance goes
below:` same options, default `£5.00`; `Save`. Both sections collapse to their headers. The two
controls are hidden while the toggle is off. The three selects are
`rechargeAmountMicro`, `lowBalanceThresholdMicro` (the recharge trigger) and `alertThresholdMicro`
(the alert), each refused with `BadRequest` outside its choices: `Choose a recharge amount of
£10.00, £30.00, £50.00 or £100.00`, `Choose a recharge threshold of £5.00, £10.00, £20.00 or
£50.00`, `Choose a balance alert of £5.00, £10.00, £20.00 or £50.00`. A value equal to the account's
saved one is accepted even outside the choices, so an amount saved before the choices existed
survives a save that leaves it alone; its select lists that saved amount as one more option, in
amount order, labelled with its amount (`£15.00`).

#### Upcoming Charges

Rows: `NUMBER` | `NEXT CHARGE` | `AMOUNT` for every dedicated number the account rents. Empty state
`There's nothing here right now`.

### Rules

1. Money is integer micro-pounds; a rate is `RATE#{country}#{product}` with `price_micro`; SMS to GB
   is 42,700. Estimates are `floor(amount_micro / price_micro)`; savings badges are
   `floor(100 × (1 − pack_rate / base_rate))`, which reproduces 9, 19 and 26.
2. A boost credits its face value. A pack credits `amount_micro × base_rate / pack_rate`, rounded
   down, so `£300` at `£0.0387` credits 331,007,751 micro-pounds and the account still buys 7,751 SMS
   at the one GB rate. The ledger row records both `paid_micro` and `credited_micro`. Departure from
   the screens' implied tiered rate: one rate per country, bonus credit instead of a tier, the same
   number of messages.
3. A top-up is a Stripe Checkout Session in payment mode with `invoice_creation` enabled and
   `metadata.accountId` and `metadata.topUpId`; `checkout.session.completed` credits the balance,
   writes the `TOPUP` ledger row and sets `has_topped_up = true` in one transaction guarded by an
   `EVENT#{stripeEventId}` put-if-absent, so a redelivered event changes nothing.
4. The balance changes only through billing: `reserve(quote)` debits under the condition
   `balance_micro >= :amount`, answering `PaymentRequired` with `Your balance is £<x>; this send costs
   £<y>` when the condition is lost; `settle(campaign)` runs once, at campaign settlement, bills every
   message the provider accepted at its actual parts, and credits the rest of the reservation back in
   one `REFUND` row: the recipients refused before acceptance and the recipients never reached. A
   message the provider accepted stays billed even if it later fails. Every change writes a ledger row
   in the same transaction.
5. The low-balance alert fires once per crossing of `alert_threshold_micro`, which is independent of
   the recharge threshold: when a debit takes the balance from at or above the alert threshold to
   below it, the conditional set of `low_balance_alerted_at` decides the one winner and that winner
   emails the billing contact; a credit that lifts the balance back to or above the alert threshold
   clears it. The alert is email only (decision), a deliberate simplification recorded in
   `specs/01-dynamodb-data-model.md`.
6. Auto-recharge: after a debit that leaves the balance below the recharge threshold with the toggle
   on and a default card present, one `recharge` job is enqueued if `recharge_in_flight` was absent
   (conditional set); `billing-charge` creates an off-session PaymentIntent for the boost amount with
   idempotency key `recharge_{accountId}_{yyyymmddHH}`; the webhook credits it and clears the flag; a
   decline clears the flag and turns the toggle off with an alert.
7. Buying a dedicated number turns auto-recharge on; cancelling the last number does not turn it off
   (the screen says it "can be stopped by cancelling the number", read as permission, not automation).
8. `billing-renewals` debits a `RENTAL` ledger row of 2,650,000 micro-pounds on each number's `renews_at`;
   on `PaymentRequired` it enqueues a recharge and retries the next day for seven days, then the
   number is released and its sender row set `RELEASED`.
9. Trial credit is never clawed back. After the trial ends without a top-up the balance stays visible
   and `can_send` is false; the first top-up makes it spendable again.
10. A sub-account never sees Billing; every `/api/app/billing/*` answers `Forbidden` to role `SUB`.

### Statuses

`LedgerKind`: `ADJUSTMENT`, `REFUND`, `RENTAL`, `SEND`, `TOPUP`, `TRIAL`.
`TopUpStatus`: `PENDING` → `PAID` | `EXPIRED`. `RechargeState`: absent | `IN_FLIGHT`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/billing/summary` | balance, auto-recharge, thresholds, trial |
| GET | `/api/app/billing/packages?country=GB` | boosts and packs priced for a country |
| POST | `/api/app/billing/top-ups` | `{ "kind": "BOOST"|"PACK", "code": "..." }` → Checkout URL |
| GET | `/api/app/billing/top-ups/{topUpId}` | status for the return page |
| GET | `/api/app/billing/cards` | saved cards from Stripe |
| POST | `/api/app/billing/cards` | setup-mode Checkout URL |
| PUT | `/api/app/billing/cards/{paymentMethodId}/default` | make default |
| DELETE | `/api/app/billing/cards/{paymentMethodId}` | detach |
| GET | `/api/app/billing/transactions?cursor=&order=desc` | paid top-ups; `order` is `asc` or `desc` (default) by date |
| GET, PUT | `/api/app/billing/general` | billing contact and balance management |
| GET | `/api/app/billing/upcoming-charges` | number renewals |
| POST | function URL `stripe-webhook` | Stripe events |

### Acceptance

- [ ] Estimates and savings for all seven cards equal the screen's numbers exactly.
- [ ] A redelivered `checkout.session.completed` credits once.
- [ ] `reserve` at balance = quote succeeds; at balance = quote − 1 answers 402 with the verbatim message.
- [ ] Renewal on day 1 through 7 of failure keeps the number; day 8 releases it.
- [ ] Auto-recharge enqueues once per crossing, never while in flight.
- [ ] Role `SUB` gets 403 on every billing route.

## contacts

Owns lists, contacts, the opt-out list, import and clean-up.

### Screens

#### Contacts

Two panels. Left, `Lists`: a search input `Search...`, a blue `+` split button (not captured;
decision: `New list` and `Import contacts`), and one card per list showing the name, `<n> contacts` and
a `...` menu (not captured; decision: `Rename`, `Export`, `Delete`; the opt-out list offers `Export`
only). Two lists exist from sign-up: `Example List` with one contact (the owner) and `Opt-Out List`
with none. Right, the selected list: its name, a blue `+` (add contact), a search input `Search...`,
and the actions `Send to All`, `Group SMS`, `Clean Up` (dropdown; not captured; decision: `Remove
invalid numbers`, `Remove opted-out contacts`).

Table: select-all checkbox; sortable columns `DATE UPDATED` | `FIRST NAME` | `LAST NAME` | `MOBILE` |
`EMAIL` | `(CF1)` | `(CF2)` | `(CF3)` | `(CF4)`; a checkbox per row. Bulk toolbar when rows are
selected (not captured; decision): `Delete`, answering `Removed <n> contacts`, and `Move to opt-out`,
answering `Moved <n> contacts to the opt-out list`; both say `contact` when the count is one.
Footer `Show` `20` `Entries` with options 20, 50, 100. Empty state (not captured; decision): `No contacts in this list yet.`

Add contact form (not captured; decision): `First Name`, `Last Name`, `Mobile` (required), `Email`,
`CF1`–`CF4`, `ADD`. Import (not captured; decision): a CSV with a header row; columns are mapped by
name to `mobile` (required), `first_name`, `last_name`, `email`, `cf1`–`cf4`; the page uploads in
chunks of 500 rows and shows `Imported <n>, updated <u>, skipped <m> invalid`.

### Rules

1. A mobile is normalised to E.164 with the account's default country and is unique within a list:
   adding or importing a number already in the list updates that contact and its `DATE UPDATED` rather
   than creating a second, and the import report counts it under `Updated`.
2. `Opt-Out List` is a system list per account, `is_opt_out = true`, cannot be renamed or deleted; a
   number in it is refused by the send policy with `This contact has opted out`, and an inbound `STOP`
   moves the sender there before any rule runs.
3. `Send to All` and `Group SMS` both open Quick SMS with the list preselected as the recipient.
4. `Clean Up › Remove invalid numbers` deletes rows whose mobile fails E.164 validation; `Remove
   opted-out contacts` deletes rows whose mobile is in the opt-out list. Each answers `Removed <n>
   contacts`, or `Removed 1 contact` when it removed one.
5. A list's `contact_count` is an `ADD` counter kept in the same transaction as the contact write.
6. Names are 1–50 characters, custom fields 0–100, email optional and validated for an `@`; a list
   name is 1–100 characters and unique within the account.
7. Search within a list is a server-side filter on mobile prefix or name substring, paginated by
   cursor; the ceiling and its upgrade path (a search index) are in the data model spec.
8. Import is at most 500 rows per request and 10,000 rows per list; row 10,001 is refused with
   `A list holds up to 10,000 contacts`.
9. Placeholders in messages resolve from `first_name`, `last_name`, `mobile`, `email`, `cf1`–`cf4`;
   a raw number recipient resolves every placeholder to an empty string.

### Statuses

None beyond membership; a contact is in a list or it is not. `ListKind`: `OPT_OUT`, `STANDARD`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/lists?q=` | lists with counts |
| POST | `/api/app/lists` | create |
| PATCH, DELETE | `/api/app/lists/{listId}` | rename, delete |
| GET | `/api/app/lists/{listId}/contacts?q=&cursor=&limit=` | page |
| POST | `/api/app/lists/{listId}/contacts` | add one |
| POST | `/api/app/lists/{listId}/contacts/import` | up to 500 rows |
| PATCH, DELETE | `/api/app/lists/{listId}/contacts/{contactId}` | edit, remove |
| POST | `/api/app/lists/{listId}/contacts/bulk` | `{ "action": "DELETE"|"OPT_OUT", "contactIds": [] }` |
| POST | `/api/app/lists/{listId}/clean-up` | `{ "action": "INVALID"|"OPTED_OUT" }` |
| GET | `/api/app/lists/{listId}/export` | CSV |

### Acceptance

- [ ] Duplicate mobile within a list updates, not inserts; the same mobile in two lists is two rows.
- [ ] Importing a number already in the list is counted under `Updated`, not `Imported`.
- [ ] Opt-out list refuses rename and delete with 409.
- [ ] Import tested at 500 rows accepted and 501 refused; list tested at 10,000 and 10,001.
- [ ] Each clean-up action's count message asserted verbatim.

## senders

Owns smart senders, own numbers and their verification, the shared pool, dedicated numbers and alpha
tags. `specs/02-sms-gateway.md` §7 maps each to a provider identity.

### Screens

#### Manage Senders › Smart Senders

Copy: `We've automatically set the safest and best senders for each country — that's why they're
called Smart Senders. You can update them if needed. We'll only show senders that are compliant for
each location. You can use Smart Senders in our SMS products.` Links `Learn about Smart Senders` |
`Enable more countries via Global Sending` (the second opens Account Settings; Global Sending is
excluded). Table `Sending to` | `Smart Sender` | `Use for`; one row per enabled country, `🇬🇧 United
Kingdom +44` | select defaulting to `Shared Numbers` whose options are the account's `READY` senders
for that country plus `Shared Numbers` | `SMS`.

#### Manage Senders › My Numbers

Three sections. `Dedicated Numbers`: `Purchase a dedicated phone number that is used by your business
only.`, button `+ Purchase` (opens Buy A Number), table (not captured; decision) `Country` | `Number` |
`Use for` | `Renews` | `Status` | `⋮` with `Cancel number`. `Own Numbers`: `Connect your own mobile
numbers with txtlocal for easy messaging.`, button `+ Add`, table `Country` | `Name` | `Number` | `Last
verified` | `Status` | `⋮` (not captured; decision: `Re-verify`, `Remove`); status badge `Ready to
use`. `Shared Numbers` with a help icon: `Use free shared numbers for cost effective SMS. Ideal for bulk
messaging and promotions.`, table `Country` | `Name` | `Use for` | `Status`; one row `🌐` | `Shared
number` | `MMS, SMS` | `Ready to use`, no actions.

#### Manage Senders › Alpha Tags

Heading `Alpha Tags` with a help icon, copy `Create unique sender names to brand your messages.`,
button `+ Add`. Table (not captured; decision) `Country` | `Alpha Tag` | `Use case` | `Status` |
`Registered`; empty area with no copy when there are none.

#### Register an alpha tag (modal)

Copy: `You must register your alpha tag in order to start sending. Customers cannot reply to alpha
tags. Some countries may need additional registration or block alpha tags.` link `Check country rules.`

| Field | Type | Details |
|---|---|---|
| `Sending to` (help icon) | select | countries in the allow-list; default the account's country (the screen defaulted to Australia; decision: default to the account's pricing country) |
| `Alpha Tag` (help icon) | text | placeholder `eg. Your business or product name`; hint `3-11 characters. Numbers, letters, pluses only.` |
| `Your Use Case` (help icon) | select | placeholder `Select an option`; options not captured; decision: `Marketing`, `Notifications`, `Two-factor authentication`, `Customer service`, `Other` |

Button `Register Alpha Tag`, disabled until valid; footer `Having an issue? Contact Support`.

#### Add your own number (modal)

Copy: `Follow the steps below to add your own number. We'll send you a code to verify your number.`

| Field | Type | Details |
|---|---|---|
| `Nickname` | text, `Optional` | placeholder `eg. "Sam's Phone"` |
| `Your Own Number` (help icon) | country select + text | country default the account's country (the screen showed US; decision as above); placeholder `Enter your number`; inline button `Send Code` disabled until a number parses; hint `Standard SMS charges apply.` |
| `Verification Code` | text | placeholder `Enter your 6-digit code`; disabled until a code was sent |

Button `Add Number`, disabled until six digits are entered. Success closes the modal and the number
appears under Own Numbers with `Last verified` today and status `Ready to use`.

#### Buy A Number

Heading `Buy A Number`, copy `Send messages globally and boost customer recognition with purchased
numbers.` Filters: `Country` (`What country are your customers in?`, default `United Kingdom`), `Use
for` (`What type of messages are you sending?`, default `SMS`; options `SMS`, `MMS`, `SMS & MMS`),
`Filter results` (`Only show results with these numbers`, placeholder `eg. 123`, digit substring).
Table `Available numbers`: `Number` | `Country` | `Use for` | `Price` | `Buy`; rows like
`+447984390718` | `🇬🇧 United Kingdom` | `SMS` | `£2.65 / Month` | `Buy`; pagination `<` `1` `2` `3`
`4` `>`. `Buy` opens a confirmation (not captured; decision: `Rent +44… for £2.65 a month, charged now
and every month from your balance. Auto recharge will be turned on.` with `CANCEL` | `BUY`).

### Rules

1. `smart_sender(account, country)` returns the account's override for the country, else the
   platform's shared pool. Only senders whose `status = READY` and whose country matches are offered.
2. Shared numbers are free, belong to the platform pool, and are `READY` for every allowed country.
3. An own number is verified by a six-digit code sent as a `TRANSACTIONAL` message; the code expires
   after 10 minutes and allows 3 attempts, then `Send Code` must be pressed again; at most 5 codes per
   account per day, the sixth refused with `Verification limit reached; try again tomorrow`. The code
   is free to the account in v1 and counts toward the daily send cap. In `sandbox` mode the verified
   number is also registered as an AWS verified destination.
4. `Own number` senders display as "from" where the destination country permits; in `sandbox` mode
   they are additionally the only destinations allowed (`NOT_VERIFIED` refusal).
5. A dedicated number costs 2,650,000 micro-pounds a month, debited on purchase and on each
   `renews_at`; purchase turns auto-recharge on; `Cancel number` sets `RELEASED` at the end of the paid
   month and no further charge. Insufficient balance at renewal follows billing rule 8.
6. Buying is refused while `can_send` is false with `Top up to rent a number`.
7. An alpha tag is 3–11 characters from `[A-Za-z0-9+]`; the United Kingdom requires registration, so
   a new tag is `UNDER_REVIEW` until the provider registration completes, then `READY` or `REJECTED`
   with the provider's reason. Departure from the screens: none of this is instant; in `fake` mode
   the scheduler completes it on the next tick.
8. Alpha tags cannot receive replies; a campaign from an alpha tag with opt-out mode `Reply STOP` is
   refused with `Replies are not possible from an alpha tag; choose Unsubscribe Link`.
9. The Buy A Number catalogue comes from the gateway's number search; in `fake` mode it is a seeded
   list of forty `+447…` numbers with `Use for` alternating `SMS` and `SMS & MMS`, paged 13 a page as
   the screen shows.

### Statuses

`SenderKind`: `ALPHA`, `DEDICATED`, `OWN`, `SHARED`. `SenderStatus`: `PENDING_VERIFICATION` → `READY`
(own); `PROVISIONING` → `READY` → `RELEASED` (dedicated); `UNDER_REVIEW` → `READY` | `REJECTED`
(alpha); `READY` (shared). Display names: `Ready to use`, `Pending verification`, `Under review`,
`Rejected`, `Released`, `Provisioning`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/senders` | all senders grouped by kind, plus smart sender per country |
| PUT | `/api/app/senders/smart/{country}` | set the smart sender for a country |
| POST | `/api/app/senders/own` | `{ nickname, number }` → sends the code |
| POST | `/api/app/senders/own/{senderId}/verify` | `{ code }` |
| DELETE | `/api/app/senders/{senderId}` | remove own, cancel dedicated |
| POST | `/api/app/senders/alpha` | register |
| GET | `/api/app/numbers?country=GB&useFor=SMS&contains=123&page=1` | catalogue |
| POST | `/api/app/numbers/{number}/buy` | rent |

### Acceptance

- [ ] Alpha tag length tested at 2, 3, 11 and 12 characters; `+` accepted, `-` and space refused.
- [ ] Code attempts tested at 3 wrong then correct (refused) and 2 wrong then correct (accepted).
- [ ] Daily verification limit tested at 5 and 6.
- [ ] Buying while trial-ended refused with the verbatim message; purchase turns auto-recharge on.
- [ ] `smart_sender` returns the override when set and the pool otherwise.

## messaging

Owns segment counting and encoding, the cost quote, Quick SMS, Quick MMS, templates, media upload,
History, and the gateway (`specs/02-sms-gateway.md`). Every quick send is executed by campaigns as a
`QUICK` campaign, so scheduling, fan-out, counters and refunds are one code path; messaging owns the
compose experience and the message rows.

### Screens

#### Quick SMS

| Field | Type | Details |
|---|---|---|
| `To` | typeahead with chips | placeholder `Search Contact/List or enter Mobile number`; suggestions show the contact name over its number; a raw entry becomes a chip showing the number as typed (`07411972333 ×`), a contact chip shows name and number, a list chip shows the list name and count; at most 1,000 recipients after expanding lists, refused with `Send to at most 1,000 recipients at a time` |
| `From` | select, grouped | default `Smart Senders`; groups `Smart Senders`, `Dedicated Numbers` (inline link `Purchase` when empty), `Alpha Tags` (inline `Add`), `Own Numbers` (inline `Add`); entries like `+447411972333 (Own Number)`; helper `The best sender has been auto-selected from Smart Senders. Reset the Smart Sender for each country. Or select an approved number or sender above.` |
| `Message` | textarea | toolbar `Placeholder` (enabled only when a list or contact chip is present), `Template`, `Emoji`; footer `Approx. <n> characters/<m> SMS per recipient.` with an info icon |
| `Shorten my URL` | toggle, default off, badge `NEW` | replaces each URL in the body with a tracked link when on |
| `Send Time` | radios | `Now` (default) | `Later`; `Later` reveals a date-time picker (not captured; decision: account timezone, minimum five minutes ahead, maximum twelve months) |

Right-hand phone preview headed `REPLY NUM` (the sender's display name) mirrors the body live. Button
`PREVIEW AND CONFIRM`, disabled until `To` and `Message` are filled, opens `Confirm SMS Send`:
`Recipients:` `<n>`, `Deliver:` `Immediately` or the chosen time, `Cost deducted:` `£<x.xxxx>`;
buttons `CLOSE`, `SEND`. After `SEND` a toast `Success` / `Your message is on its way.` (not captured;
decision) and the balance updates.

#### Quick MMS

Notice `MMS is not supported in all countries. See supported countries here` (link). Fields `To` as
above; `From` default `A Shared Number` with helper `Replies will be forwarded to you as setup in SMS
Reply Settings` (link to Messaging Settings); `Subject` (placeholder `Subject`, 0–40 characters);
`Message` as a dropzone `Drop file here or click to upload` with link `Accepted file specs here.` and a
textarea with toolbar `Placeholder` `Template` `Emoji` and counter `Approx. <n> characters/1500
characters allowed`; `Send Time` `Now` | `Later`; button `PREVIEW AND CONFIRM`. Accepted media (not
captured; decision): `image/jpeg`, `image/png`, `image/gif`, at most 1 MB, one file.

#### Templates

Empty state: a document icon and the link `Click here to add your first SMS template`. Populated:
heading `SMS Templates`, a blue `+`, `Search...`; table `NAME ⇕` | `BODY ⇕`, both sortable; row
actions (not captured; decision) `Edit`, `Delete`. Add/edit modal: `Template Name` (1–100), `Body`
(textarea with an edit icon and an emoji icon; footer `Approx. <n> characters/<m> SMS per recipient.`
with info icon), buttons `CLOSE`, `ADD` (disabled until both filled), `×`. Toast `Success` / `New
template has been saved.`

#### History

Title `SMS History`. Filters: `From` and `To` dates (placeholder `Enter Date`), three preset buttons
(not captured; decision: `Today`, `Last 7 days`, `Last 30 days`), a red clear button, a field select
defaulting to `To` (options `To`, `From`), an input `Search in international format`, and `EXPORT ▾`
(formats not captured; decision: `CSV` only). Note under the filters: `Historical data is retained for
4 months.` Table, every header sortable: `USERNAME` | `DATE` | `FROM` | `TO` | `STATUS` | `BODY`.
Inbound rows put the peer in `FROM` and the account's sender in `TO` with status `Received`; a peer that
is a contact renders by name. Footer `Show` `20` `Entries`. `MMS History` is the same screen filtered
to `kind` MMS with empty copy `No results`. Row detail (not captured; decision): clicking a row opens a
drawer with every field, parts, price, provider id, failure reason.

### Rules

1. `segments_of(body, mode)`: GSM 03.38 text is 160 characters in one part and 153 per part after
   that, extension characters (`€ ^ { } [ ] ~ \ |`) counting twice; any other character makes the
   body UCS-2, 70 in one part and 67 per part after. The result is `(encoding, parts, chars)` and is
   what the `Approx.` counter shows. Eight parts, 1,224 GSM characters, is the product ceiling and the
   account's `max_message_parts` may lower it.
2. The counter is computed on the unresolved body; placeholders are resolved per recipient at
   fan-out and the final count is shown on confirmation, per the campaign copy `Custom fields are
   calculated and final count shown on confirmation.`
3. Placeholders are `{first_name}`, `{last_name}`, `{mobile}`, `{email}`, `{cf1}`–`{cf4}`; an unknown
   placeholder is refused with `Unknown placeholder {name}`.
4. `quote(recipients, body, sender)` is the sum over recipients of `parts × rate(country, product)`,
   using each recipient's country; recipients not in the allow-list are dropped from the send and
   counted in the confirmation as `<n> recipients skipped (country not enabled)`.
5. Recipients are deduplicated by E.164 across chips and lists and capped at 1,000 per send, the same
   cap as the developer send endpoint; 1,001 is refused with `Send to at most 1,000 recipients at a
   time`. Opted-out numbers are removed at fan-out; the provider never accepted them, so their share
   of the reservation is refunded once, at settlement.
6. `Shorten my URL` replaces every `http(s)://` URL in the body with `https://<site>/l/<code>` before
   counting, one tracked link per distinct URL per send, created through analytics.
7. Every quick send is a campaign of kind `QUICK` with its recipients embedded. With Send Time `Now`,
   `api` reserves the cost and fans the send out in the request, so in `fake` mode the demo shows
   delivery within a second; with `Later` it appears in the SMS Campaigns list as `Scheduled` and is
   cancelled there. Message rows are written by the worker as it sends them, so History shows a row
   only once it has been sent.
8. Quick MMS to a recipient outside the gateway's `mms_countries` is delivered as an SMS whose body is
   the text followed by a blank line and the media URL, recorded with `kind = MMS_AS_LINK` and priced
   as SMS by its parts; the confirmation says `Delivered as a text with a link where MMS is not
   available`.
9. Media uploads are stored under the app's media prefix in the sites bucket and served through the
   site; the URL is stable for the row's lifetime.
10. History is a query over the account's month partitions between the two dates, newest first,
    at most four months back; the default range is the last 7 days; searching applies an exact match
    of the normalised number on the selected field. Export streams at most 10,000 rows of the current
    filter as CSV; row 10,001 is not included and the file ends with `# truncated at 10000 rows`.
11. Message rows carry `ttl = created_at + 120 days`, which is the 4 months the screen promises.
12. Templates belong to the account, are visible to every user in it, and `Template` in a toolbar
    replaces the body with the chosen template's body after a confirm if the body was not empty.
13. A message the provider accepted is billed at its actual parts even if a later delivery event marks
    it `FAILED`; History shows `Failed` with the failure reason. Only a recipient refused before
    acceptance, by the policy or by the gateway, or never reached because its campaign was cancelled,
    is refunded, once, at campaign settlement.

### Statuses

`MessageStatus`: `QUEUED` → `SENT` → `DELIVERED` | `FAILED`; `RECEIVED` for inbound. Scheduling and
cancellation are campaign statuses; a message row exists only once the worker has dispatched it.
`MessageKind`: `MMS`, `MMS_AS_LINK`, `SMS`. `Encoding`: `GSM7`, `UCS2`. Display:
`Queued`, `Sent`, `Delivered`, `Failed`, `Received`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/app/messages/quote` | `{ to, senderId, body, shortenUrls, kind }` → parts, cost, skipped |
| POST | `/api/app/messages/send` | same plus `sendAt` → message id or campaign id |
| GET | `/api/app/messages?from=&to=&field=&q=&kind=&cursor=` | history page |
| GET | `/api/app/messages/{messageId}` | detail |
| GET | `/api/app/messages/export?…` | CSV |
| GET, POST | `/api/app/templates` | list, create |
| PUT, DELETE | `/api/app/templates/{templateId}` | edit, delete |
| POST | `/api/app/media` | upload one image, returns its URL |
| POST | `/api/app/demo/inbound` | fake mode only: `{ from, to, body }` |

### Acceptance

- [ ] `segments_of` tested at 160/161 and 306/307 GSM, 70/71 and 134/135 UCS-2, and one extension
      character at position 160.
- [ ] Max parts tested at the account's limit and one over, with the verbatim message.
- [ ] Quote for two GB recipients at one part equals 85,400 micro-pounds, displayed `£0.0854`.
- [ ] Opted-out recipient removed at fan-out and refunded once at settlement; skipped country counted
      in the confirmation.
- [ ] A message accepted then failed by a delivery event stays billed and shows `Failed` with its
      reason; a gateway refusal before acceptance is refunded once.
- [ ] A `Later` quick send appears in SMS Campaigns as `Scheduled` and writes no History row until it
      runs.
- [ ] Recipients tested at 1,000 accepted and 1,001 refused with the verbatim message.
- [ ] MMS to `+44` becomes `MMS_AS_LINK`; to `+1` stays `MMS`.
- [ ] History default range, four-month cap (refused with `History covers the last 4 months`),
      and export truncation marker.

## campaigns

Owns the campaign lifecycle, scheduling, fan-out, per-campaign counts and the opt-out footer, for SMS
and MMS campaigns and for `QUICK` sends handed over by messaging.

### Screens

#### SMS Campaigns

Empty: heading `SMS Campaigns`, a document icon and the button `CLICK HERE TO ADD YOUR FIRST SMS
CAMPAIGN`. Populated: heading, a blue `+`, `Search...`; table `CAMPAIGN ⇅` | `STATUS ⇅` | `DATE ⇅` |
`FROM ⇅` | `RECIPIENTS`; row like `Helloworld` | badge `Scheduled` | `Jul 31, 2027 11:59 PM` | `Shared
Number` | `1`; footer `Show` `20` `Entries`. Row actions (not captured; decision): `Open` (report for
sent, editor for draft), `Cancel` while `Scheduled`, `Duplicate`. `MMS Campaigns` is the same list
for `kind = MMS` with the empty button `CLICK HERE TO ADD YOUR FIRST MMS CAMPAIGN`.

#### Campaign editor

Header: input placeholder `Campaign name...` with the link `Edit name` beneath; button `SAVE DRAFT`
top right, always enabled. Three stacked sections with a completion marker each (empty circle,
green tick):

- `To` / `Your Recipients`: `List` select, placeholder `Select List`; once chosen the summary reads
  `<List name> <n> recipient(s)`. Lists only; no ad-hoc numbers.
- `From` / `Select your Sender ID` (MMS: `Your Sender Details`): the same grouped select as Quick
  SMS, default `Smart Senders`, complete by default; MMS shows the link `Where do contacts' replies
  go?`.
- `Message` / `Your SMS Content` (MMS: `Your MMS Content`): textarea with toolbar `Placeholder`,
  `Template`, `Short URL`, `Emoji`; counter `Approx. <n> characters/<m> SMS per recipient.` (MMS: `1
  MMS per recipient.`); italic `Custom fields are calculated and final count shown on confirmation.`;
  opt-out radios `Reply STOP` (default) | `Unsubscribe Link` with an editable footer input holding
  `Reply STOP to opt-out` (or `Unsubscribe: <link>` when the link mode is chosen); MMS adds `Subject`
  and the media dropzone; button `NEXT`.

Button `SEND NOW` with a clock half; the main half schedules for now, the clock opens the date-time
picker. Both are disabled until `NEXT` has been pressed with every section complete. Preview: a
phone headed `REPLY NUM` with the caption `Placeholders will be replaced for all contacts in a list.
This is an example of the first contact.`, showing the body then the footer as two bubbles.

Confirmation modal, title the campaign name: `From:` `<sender display>` with italic `Replies will
return to your txtlocal account if supported in your country.` (`your country` links to the country
rules), `Total Recipients:` `<n>`, `Date:` `31 Jul 2027 (in 10 months)` or `Now`, `Cost:` `£<x.xxx>`;
buttons `CLOSE`, `SCHEDULE` (or `SEND`).

Leaving the editor with unsaved changes opens `Save as a draft?` / `Come back to finalize and send
your campaign later.` with `DISCARD DRAFT`, `SAVE DRAFT`, `×`. `DISCARD DRAFT` deletes an unsaved new
campaign and reverts an existing draft to its saved state; nothing sent is ever affected.

### Rules

1. A campaign has one list; recipients are the list's contacts at fan-out time, deduplicated by
   mobile, minus the opt-out list, minus countries outside the allow-list.
2. The footer is appended to every message after a line break: `Reply STOP to opt-out` (editable) or
   the unsubscribe sentence with a per-recipient link `https://<site>/api/u/<token>` where the token is
   an HMAC of account and contact; opening it moves the contact to the opt-out list and shows a plain
   page `You have been unsubscribed.` Both count toward the message length.
3. `Reply STOP` requires a sender that can receive replies (shared or dedicated); an alpha tag with
   `Reply STOP` is refused per senders rule 8.
4. Confirmation quotes `recipients × parts × rate` using the longest resolved body among the list's
   first 100 contacts as the parts estimate, and reserves that amount. Settlement runs once, when the
   campaign reaches `SENT` or `CANCELLED`: every message the provider accepted is billed at its actual
   parts, and the rest of the reservation, covering recipients refused before acceptance by the policy
   or the gateway and recipients never reached, is refunded in one `REFUND` row. A message accepted and
   later marked `FAILED` stays billed.
5. Scheduling requires `send_at` between five minutes and twelve months ahead, in the account's
   timezone; `SEND NOW` is `send_at = now`. The list shows the exact time (the screen's `11:59 PM` is
   not reproduced).
6. `scheduler` claims a due campaign with the conditional flip `SCHEDULED → SENDING`, loads the
   opt-out set once, and enqueues one `send-jobs` message per recipient in batches of ten; the last
   batch carries `final = true` so the worker that finishes it flips `SENDING → SENT` when
   `sent + refused = recipients`, which triggers settlement.
7. `Cancel` is allowed while `SCHEDULED`: the conditional flip `SCHEDULED → CANCELLED` settles the
   campaign, and since no recipient was reached the whole reservation is refunded once; a campaign
   already `SENDING` cannot be cancelled and answers `Conflict` with `This campaign is already sending`.
8. Counts on the campaign row are `ADD` counters: `recipients` at claim; `sent` when the provider
   accepts and `refused` when the policy or the gateway refuses, at dispatch; `delivered` and
   `undelivered` as delivery events arrive. A message accepted and later failed counts as `undelivered`
   and stays billed. The report shows them with click counts from analytics.
9. `QUICK` campaigns are created by messaging with an explicit recipient list stored on the campaign,
   at most 1,000 recipients (messaging already refused more with `Send to at most 1,000 recipients at
   a time`), and appear in the SMS Campaigns list with the name `Quick SMS <date time>`.
10. `Duplicate` copies name with ` (copy)`, list, sender, body, opt-out mode and footer into a new
    `DRAFT`.

### Statuses

`CampaignStatus`: `DRAFT` → `SCHEDULED` → `SENDING` → `SENT`; `SCHEDULED` → `CANCELLED`; `SENDING` →
`FAILED` when fan-out itself fails (the scheduler logs and the alarm on the dead-letter queue
catches it). `CampaignKind`: `API`, `LIST`, `QUICK`; the product, `SMS` or `MMS`, is a separate field,
so the MMS Campaign screen lists `LIST` campaigns whose product is `MMS`. `OptOutMode`: `REPLY_STOP`,
`UNSUBSCRIBE_LINK`.
Display: `Draft`, `Scheduled`, `Sending`, `Sent`, `Cancelled`, `Failed`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/campaigns?kind=&q=&cursor=` | list |
| POST | `/api/app/campaigns` | create draft |
| GET, PUT, DELETE | `/api/app/campaigns/{campaignId}` | read, save draft, delete draft |
| POST | `/api/app/campaigns/{campaignId}/quote` | recipients, parts, cost |
| POST | `/api/app/campaigns/{campaignId}/schedule` | `{ sendAt }` or `{ now: true }` |
| POST | `/api/app/campaigns/{campaignId}/cancel` | cancel while scheduled |
| POST | `/api/app/campaigns/{campaignId}/duplicate` | new draft |
| GET | `/api/app/campaigns/{campaignId}/report` | counts and clicks |
| GET | `/api/u/{token}` | public unsubscribe |

### Acceptance

- [ ] Schedule tested at now + 4m59s (refused), now + 5m (accepted), now + 12 months (accepted), + 1 day (refused).
- [ ] Two concurrent schedulers claim one campaign once (conditional flip loses on the second).
- [ ] Cancel while `SCHEDULED` refunds the whole reservation once; cancel while `SENDING` answers 409
      with the verbatim message.
- [ ] A `Later` quick send is a `QUICK` campaign, listed as `Scheduled` and cancellable from the list.
- [ ] Footer counted in length; `Reply STOP` with an alpha tag refused.
- [ ] `QUICK` recipients tested at 1,000 and 1,001.
- [ ] Settlement of a list with mixed part counts, one policy refusal and one accepted-then-failed
      message bills the accepted messages at actual parts, refunds the refusal's share once, and does
      not refund the failed message.

## inbox

Owns conversations, inbound threading and replies.

### Screens

#### Inbox

Title `Inbox`. Left pane header: `+` (new conversation), `Status ▾` filter (not captured; decision:
`Open`, `Closed`, `All`; default `Open`), `⋮` menu (not captured; decision: `Mark all as read`). Search
bar: `Type a name, mobile number or phrase to find or start a conversation`. Thread rows: an avatar of
initials (`JA`), the contact name or the number, a relative time (`10m`), the last message preview;
unread rows bold with a count badge. Right pane empty state: an illustration and `Select a conversation
to start sending`. Open thread (not captured; decision): the peer's name and number in the header with
`Close conversation`; bubbles by direction, outbound with a status tick and time, inbound on the left;
a composer at the bottom with a `From` select defaulting to the sender the peer last wrote to, a
textarea with the `Approx.` counter, and `SEND`. `+` opens the composer against a typed number.

### Rules

1. A conversation is keyed by account and peer E.164; the first inbound or outbound message creates
   it. Inbound sets `last_at`, `preview`, increments `unread`; outbound sets `last_at` and `preview`.
2. The peer's display name is resolved from the contacts' mobile index at read time; a number in no
   list renders as the number.
3. Search matches name prefix or number prefix over the account's conversations, newest first, up to
   the 200 most recent; a phrase match over message bodies is not built in v1 (the placeholder copy is
   kept; a phrase that matches nothing offers `Start a conversation with <number>` only when it parses
   as a number).
4. A reply is a single-recipient quick send from the sender chosen in `From`, which defaults to the
   sender the peer last wrote to; `Smart Senders` sends no sender and the smart sender for the
   peer's country is used. It follows every send rule and appears in History too.
5. Replies can only arrive on a shared number when the peer replies to the last message sent to them,
   or on a dedicated two-way number; the inbox shows a hint `Replies to this number reach you only when
   the contact replies to your last message` for shared-number conversations.
6. Opening a conversation sets `unread = 0`; `Close conversation` sets `CLOSED` and a new inbound
   reopens it.

### Statuses

`ConversationStatus`: `OPEN` ↔ `CLOSED`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/conversations?status=&q=&cursor=` | list |
| GET | `/api/app/conversations/{peer}?cursor=` | messages, newest first |
| POST | `/api/app/conversations/{peer}/messages` | reply |
| POST | `/api/app/conversations/{peer}/read` | mark read |
| POST | `/api/app/conversations/{peer}/close`, `/reopen` | status |
| POST | `/api/app/conversations/read-all` | mark all read |

### Acceptance

- [ ] Inbound to an unknown peer creates the conversation with `unread = 1`; a second increments.
- [ ] Name resolves from contacts and falls back to the number.
- [ ] Reply refused by the policy surfaces the policy's verbatim message.
- [ ] Close then inbound reopens.

## automation

Owns inbound rules and their actions, delivery report rules, website registration and email-to-SMS
allowed addresses. The `Developers › Webhooks` sidebar entry lands on Messaging Settings, whose
`General` sub-tab belongs to identity.

### Screens

#### Messaging Settings › Inbound Rules

Button `ADD NEW RULE`; footer `Show` `20` `Entries`. Table `DEDICATED NUMBER` | `RULE NAME` | `ACTION`
| `ACTION ADDRESS` | `MATCH FOR` | `ENABLED`; `ENABLED` is a green check or nothing (row actions not
captured; decision: `Edit`, `Disable`/`Enable`, `Delete`). Every account starts with three rules:
`ANY` | `Send to messenger` | `SEND_TO_MESSENGER` | — | `stop` | ✓; `ANY` | `Opt-out contact` |
`MOVE_CONTACT` | `<opt-out list id>` | `stop` | ✓; `ANY` | `Default rule` | `EMAIL_USER` | — | — | ✓.

#### Add Inbound Rule (modal)

| Field | Type | Details |
|---|---|---|
| `Rule Name` | text | helper `This is for your reference only` |
| `Dedicated Number` | select | default `Any`; helper `A txtlocal number you've purchased (optional)`; options are the account's dedicated numbers |
| `Match For` | select | default `Any message`; helper `A match on the incoming SMS`; the other option is `Keyword`, which reveals a text input (not captured; decision) |
| prompt | | `If there's a match as specified above choose the action to run:` |
| `Action` | select | default `EMAIL_USER`; options `AUTO_REPLY`, `EMAIL_USER`, `EMAIL_FIXED`, `URL`, `SMS`, `POLL`, `GROUP_SMS`, `MOVE_CONTACT`, `SEND_TO_MESSENGER` |
| action field | varies | `EMAIL_USER`: `Back-up Email Address` with helper `This email will be forwarded to only in case account user email cannot be found.`; `EMAIL_FIXED`: `Email Address`; `URL`: `URL` (https only); `SMS`: `Forward to number`; `AUTO_REPLY`: `Reply message` with the `Approx.` counter; `GROUP_SMS`: `List` select; `MOVE_CONTACT`: `List` select; `POLL` and `SEND_TO_MESSENGER`: none (fields other than the back-up email were not captured; decision as listed) |

Buttons `CLOSE`, `ADD` (disabled until the name, and the action's field where it has one, are filled).

#### Messaging Settings › Delivery Report Rules

Not captured; decision: table `RULE NAME` | `URL` | `EVENTS` | `ENABLED`, button `ADD NEW RULE`, modal
with `Rule Name`, `URL` (https), `Events` (`All`, `Delivered only`, `Failed only`), `Secret` shown once.

#### Website Registration

Card `Registered websites` with copy `Register websites and subdomains, not single webpages (URLs).
Ie: Once you have registered txtlocal.com, you don't need to register txtlocal.com/about.` Empty hero:
`Register websites for speedy delivery` / `If you're adding a link to messages for the first time, we
need to review your website for safety. Speed up delivery by registering websites before you send
messages with links.`, button `Register a website`, link `Learn about website registration`.
Populated: button `+ Register a website`; table `Website` | `Date Registered` | `Status`; row
`junaid.guru` | `19 September 2026` | chip `Under review`; pager `<` `>`.

Modal `Register a website`: copy `Registering websites keeps customers safe, reduces spam and speeds
up delivery.`; field `Website Domain` with a help icon; hint `You can register up to 3 different
websites at once.`; link `Add another website +` adding a row up to three; button `Register`; footer
`Having an issue? Contact Support`.

#### Email SMS

Heading `Email SMS`. Steps: `1 Enter your contact's mobile number followed by @sms.<domain>`, `2 Enter
the message in the subject or body of the email.`, `3 Message is sent from your Email Inbox, straight
to their mobile.` Illustration: an email to `1234567890@sms.<domain>, 0987654321@sms.<domain>` with
subject `Re: Sales Report` and body `Please give me a call on 0400000000 Regards, Jan`, and a phone
showing subject and body concatenated. FAQ links: `How can I strip email signatures from SMS?`, `How
can I email SMS to contacts group?`, `Where do replies to my emailed SMS go?`, `How can I send
authenticated email-to-SMS from any email?`, `How can I send SMS from a generic/shared email?`
Section `Allowed Addresses`: button `ADD`; notice `Allowed email address settings are shared between
SMS/Fax/Voice` (rendered as `Allowed email address settings apply to every channel`); table `SUBACCOUNT
NAME` | `EMAIL ADDRESS` | `SENDER NUMBER`; footer `Show` `20` `Entries`. Add modal (not captured;
decision): `Subaccount` select, `Email Address`, `Sender` select of the account's `READY` senders.

### Rules

1. On every inbound: if the first word, case-insensitively, is one of `STOP`, `STOPALL`,
   `UNSUBSCRIBE`, `CANCEL`, `END`, `QUIT`, the sender is moved to the opt-out list first, in every mode,
   before any rule runs.
2. Every enabled rule whose `Dedicated Number` is `Any` or equals the destination, and whose `Match
   For` is `Any message` or whose keyword equals the first word case-insensitively, runs, in creation
   order. Rules do not stop each other; the seeded `stop` rules both run.
3. Actions: `AUTO_REPLY` sends the reply text to the sender from the destination number as a quick
   send; `EMAIL_USER` emails the inbound to the receiving user, falling back to the back-up address;
   `EMAIL_FIXED` emails the fixed address; `URL` enqueues a signed webhook (`specs/04`); `SMS` forwards
   the body to the number; `POLL` increments `votes[keyword]` on the rule and does nothing else;
   `GROUP_SMS` forwards the body to every contact in the list as a `QUICK` campaign; `MOVE_CONTACT`
   adds the sender to the list (creating the contact with mobile only if absent); `SEND_TO_MESSENGER`
   is a marker, since every inbound reaches the inbox regardless.
4. `EMAIL_USER` and `EMAIL_FIXED` require SES (phase 6); until then the action logs
   `outcome=email_unavailable` and the rule row shows a chip `Email not yet available`.
5. A delivery report rule enqueues one signed webhook per matching delivery event with the payload in
   `specs/04-developer-api.md`; three attempts with backoff, then the dead-letter queue.
6. A website domain is normalised by stripping the scheme, path, query and trailing dot, lowercasing,
   and validating as a hostname; `junaid.guru` and `www.junaid.guru` are two registrations. At most 3
   per submission; a fourth row is refused with `You can register up to 3 websites at once`. A duplicate
   answers `Conflict` with `<domain> is already registered`.
7. Registration is `UNDER_REVIEW` for 24 hours, then the scheduler sets `APPROVED`. Departure from the
   screens: there is no human review in v1, and link sending is not gated on registration; the registry
   exists so the gate can be added without a data change.
8. Email-to-SMS ingress arrives in phase 7 through SES; until then the Allowed Addresses table can be
   managed and the steps are shown with the note `Email to SMS is coming soon` under the heading.
9. An allowed address is unique per account; the sender must be `READY`; the address's messages are
   attributed to the chosen sub-account in History and usage.

### Statuses

`RuleAction`: `AUTO_REPLY`, `EMAIL_FIXED`, `EMAIL_USER`, `GROUP_SMS`, `MOVE_CONTACT`, `POLL`,
`SEND_TO_MESSENGER`, `SMS`, `URL`. `MatchKind`: `ANY`, `KEYWORD`. `WebsiteStatus`: `UNDER_REVIEW` →
`APPROVED`. `DeliveryEvents`: `ALL`, `DELIVERED`, `FAILED`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/api/app/rules/inbound` | list, create |
| PUT, DELETE | `/api/app/rules/inbound/{ruleId}` | edit (including `enabled`), delete |
| GET, POST | `/api/app/rules/delivery` | list, create (returns secret once) |
| PUT, DELETE | `/api/app/rules/delivery/{ruleId}` | edit, delete |
| GET, POST | `/api/app/websites` | list, register up to 3 |
| GET, POST | `/api/app/email-senders` | list, add |
| DELETE | `/api/app/email-senders/{id}` | remove |

### Acceptance

- [ ] Each opt-out keyword tested; `stop please` opts out (first word), `please stop` does not.
- [ ] Rule matching tested for number `Any` and specific, keyword case-insensitivity, creation order.
- [ ] Each action tested with a recording bus or gateway; `POLL` increments per keyword.
- [ ] Website normalisation tested for scheme, path, case, `www.` distinctness; 3 accepted, 4 refused.
- [ ] Delivery webhook enqueued once per event; signature verified in the test.

## developer

Owns API keys, the `/api/v3` face, the API Logs screen and webhook signing and dispatch. The developer
face itself is specified in `specs/04-developer-api.md`.

### Screens

#### API Credentials › Subaccounts

The Subaccounts table is specified under identity; this slice owns the `API KEY` column's `Copy` and
`Regenerate` behaviour and the key modal: `Your new API key` with the key in a read-only input, a
`Copy` button, the sentence `Store this key now. For your security we cannot show it again.`, and
`Done`. `Regenerate` asks `Regenerate the API key for <username>? Integrations using the current key
will stop working.` with `CANCEL` | `REGENERATE`.

#### API Credentials › General

Not captured; decision: read-only card with `API base URL` `https://<site>/api/v3`, `Authentication`
`HTTP Basic with your username and API key`, a link to `API Documentation`, and `Rate limit` `60
requests per minute per key`.

#### API Logs

Page header `Developer Tools`, section `Your recent activity`, links `API Documentation` and `Guide to
API Logs`, note `Logs are retained for 7 days`. Tiles `<n> Total requests` | `<n> Successful` | `<n>
Failed`. Filters (four, matching `specs/04-developer-api.md` §9): selects `Status` (`All`, `Successful`,
`Failed`), `Endpoint` (the `/api/v3` routes), `Subaccount`, `Date Range` (`Last 24 hours`, `Last 7
days`, custom, at most 7 days); `Results per page` `20`; `<n> Results`; button `Refresh table`. There
is no free-text search field; `specs/04` names exactly these four filters. Table (columns not
captured; decision): `DATE` | `SUBACCOUNT` | `METHOD` | `ENDPOINT` | `STATUS` | `DURATION` | `REQUEST
ID`. Empty state: `No SMS activity yet.` `Kick things off — send your first message.` with the last
three words linking to Quick SMS. The first query shows `Loading…` in the panel; a later one keeps the
current rows on screen until its answer arrives, so a filter keeps its focus while the table refreshes.

#### API Documentation

Departure from the screens: not FastAPI's built-in Swagger UI, per `specs/04-developer-api.md` §8,
which the developer slice actually implements. The screen lives in
`frontend/src/screens/developer/docs/` and renders the committed `specs/openapi.v3.json` with a small
client-side renderer, no third-party viewer;
`Libraries & SDKs` links to the same page (excluded as a page of its own).

### Rules

1. An API key is 30 random bytes rendered as a 40-character base64url string; only its SHA-256 is
   stored, with the first eight characters as `key_prefix` for display. It is returned exactly once by
   the create and regenerate endpoints. Departure from the screens, which show a UUID-shaped key in
   full for ever.
2. Regeneration replaces the hash atomically; a request with the old key answers `Unauthorized` on
   the next call.
3. `/api/v3` authenticates HTTP Basic `username:api_key`: the user row is found through GSI2 by the
   key's hash, the username must match, and the comparison is constant-time. A missing or wrong
   credential answers 401 with `{ "code": "UNAUTHORIZED", "message": "Invalid username or API key" }`.
4. Rate limit per key: an `ADD` counter on `RL#{userId}#{minute}` with a two-day TTL; the 61st request
   in a minute answers 429 with `Rate limit of 60 requests per minute reached` and `Retry-After`.
   Departure from the screens (300/minute): `specs/04-developer-api.md` §2 is the number actually
   built and tested.
5. Every `/api/v3` request logs one `event=api_request` line with `user_id`, `account_id`, `method`,
   `route` (the template, not the path), `status`, `latency_ms`, `request_id`, `outcome`; never the
   key, the query string, the body or a phone number.
6. The API Logs screen is one dashboard request, `GET /api/app/developer/logs`, not a client-polled
   pair of endpoints. The service starts a Logs Insights query (or scans the local JSONL file on a
   laptop) and polls it server-side with jittered backoff for up to 20 seconds before answering with
   the rows and tiles, or 504 `The log search took too long, try a narrower range` past that deadline;
   the client's own `Refresh table` button is a plain re-request, not a resumed poll. Tiles are counted
   from the same capped 400-row result, not a second query. Sub-accounts see their own rows; the owner
   sees all.
7. Webhook signing: every outbound webhook carries `X-Txtlocal-Signature: t=<unix>,v1=<hex HMAC-SHA256
   of "<t>.<body>">` with the rule's secret, and `X-Txtlocal-Event`; receivers reject a `t` older than
   five minutes. Delivery is `POST` with JSON, 10-second timeout, three attempts with backoff, then the
   dead-letter queue and a log line `outcome=webhook_dead`.

### Statuses

`ApiKeyState`: present | absent (a user without a key cannot use `/api/v3`).

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/app/account/users/{userId}/api-key` | create or regenerate, returns the key once |
| GET | `/api/app/developer/general` | base URL, docs link, rate limit |
| GET | `/api/app/developer/logs` | filtered rows and tiles, or 504 past the query deadline |

### Acceptance

- [ ] Key format matches `^[A-Za-z0-9_-]{40}$`; the stored row holds no plaintext and `key_prefix`
      is its first eight characters.
- [ ] Old key rejected after regeneration.
- [ ] Rate limit tested at 60 and 61 with the verbatim message and a `Retry-After` header.
- [ ] `api_request` log line asserted for field set and for the absence of the key.
- [ ] Signature verified by a reference receiver in the test; `t` skew of 301 seconds rejected.

## analytics

Owns tracked links and the redirect, the nightly rollup, and the Usage, Usage Reporting and campaign
click read models. `specs/05-analytics.md` holds the queries and row shapes.

### Screens

#### Billing › Usage

Controls: a month picker showing `2026-09`, a filter icon (not captured; decision: `Product`,
`Username`), `EXPORT` (CSV). Table `DATE` | `PRODUCT` ⇕ | `USERNAME` ⇕ | `QUANTITY` ⇕ | `COST` ⇕; row
`09/2026` | `SMS` | `<username>` | `1` | `£0.0427`. One row per month × product × username; the API
answers `costMicro`, integer micro-pounds, and the page shows it to four decimals. Note under the table (decision): `Usage is updated nightly.`

#### Billing › Usage Reporting

Filters: date from and to (defaults: the first day of the month two months before today, and today;
the screen showed `01/07/2026` → `19/09/2026`), selects with placeholders `Products`, `Subaccounts`,
`Sender IDs`, `Countries`, button `EXPORT` with an info icon (`Exports the current filter as CSV`).
List controls: `10 per page` select (10, 25, 50), `<n> results`, pager first | `1` | last. Table
`Date` (help icon, default descending) | `Product` | `Subaccount` | `Sender ID` | `Country` | `Price`
⇕ | `Quantity` ⇕ | `Total` ⇕; row `19/09/2026` | `SMS` | `<username>` | `+447908661626` | `🇬🇧 United
Kingdom` | `£0.0427` | `1` | `£0.04`. The API answers `priceMicro` (the unit price, the row's cost
floored over its quantity) and `totalMicro`, integer micro-pounds; the page shows `Price` to four
decimals and `Total` to two.

#### Campaign report

Reached from a sent campaign: the counts (`Recipients`, `Sent`, `Refused`, `Delivered`, `Undelivered`) and, when the
body carried tracked links, a table `Link` | `Clicks` | `Last 7 days` with clicks per day. Note:
`Clicks are counted nightly.`

### Rules

1. A tracked link is `https://<site>/l/<code>` with a seven-character code from `[a-z0-9]`, created
   by messaging when `Shorten my URL` or `Short URL` is used, one per distinct target URL per send or
   campaign, with a one-year TTL. `redirect` answers one eventually consistent `GetItem` with `302`,
   `Location`, `Cache-Control: public, max-age=300`; an unknown or expired code is a minimal `404`.
2. Clicks are counted nightly from CloudFront standard logs through Athena, `cs_uri_stem LIKE '/l/%'
   AND sc_status = 302` on this app's host, into `LINKDAY` rows; the campaign report sums them.
3. Usage rows are written nightly from the `message_accepted` log lines grouped by account,
   sub-account, product, sender and destination country, with `quantity` (messages, not parts) and
   `cost_micro` (the settled price); the Usage tab sums the month's day rows; Usage Reporting reads
   the day rows in the range, filtered, paged.
4. Product is `SMS`, `MMS` or `MMS_AS_LINK` (shown as `SMS` with the MMS subject count in a tooltip;
   decision: shown as `SMS`).
5. Ranges are at most 4 months back, the same as History; a longer range is refused with `Reports
   cover the last 4 months`.
6. Exports stream CSV of the current filter, at most 10,000 rows, with the same truncation marker as
   History.
7. Today's usage appears tomorrow; the note says so. The ceiling and its hourly upgrade are in the
   data model spec.

### Statuses

None; rows are facts.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/app/usage?month=2026-09&product=&userId=` | monthly rows |
| GET | `/api/app/usage/export?month=` | CSV |
| GET | `/api/app/reporting?from=&to=&product=&userId=&senderId=&country=&page=&perPage=` | day rows |
| GET | `/api/app/reporting/export?…` | CSV |
| GET | `/api/app/campaigns/{campaignId}/clicks` | per-link, per-day clicks |
| GET | `/l/{code}` | public redirect (the `redirect` Lambda) |

### Acceptance

- [ ] Code alphabet and length; unknown and expired codes both answer the same 404 body.
- [ ] Rollup of a fixture log day produces the expected `USAGE` and `LINKDAY` rows and is idempotent.
- [ ] Monthly sums equal the sum of day rows for a seeded month.
- [ ] Range tested at 4 months and 4 months + 1 day with the verbatim message.

## Excluded from v1

- `Automation` and the Automation Builder (the `£0.0009` product line is not rendered).
- `Integrations`.
- `Reseller Clients`, `Reseller Settings`, `Referrals`.
- `Global Sending` beyond the country allow-list `SMS_ALLOWED_COUNTRIES`; the link in Smart Senders
  opens Account Settings, which shows the enabled countries read-only.
- Fax and Voice, including the channel wording on the Email SMS notice.
- `Libraries & SDKs` as a page; the sidebar entry links to API Documentation.
- RCS, WhatsApp and any channel other than SMS and MMS.
- Human review of website registrations; human approval of alpha tags beyond the provider's own
  registration outcome.
- Phrase search over message bodies in the inbox.
- Account deletion, two-factor settings, session management and password change pages; Cognito's
  hosted UI handles the password.

## Demo mode

`SMS_MODE=fake` is the public demo, the laptop and CI, and nothing in it can reach AWS
(`specs/02-sms-gateway.md` §3):

- Every send is accepted with a provider id `fake-<uuid7>` and a delivery event chosen by the
  destination's last two digits: `00` fails as `TEXT_INVALID`, `01` as `TEXT_CARRIER_UNREACHABLE`, `02`
  as `TEXT_BLOCKED`, `03` as `TEXT_SPAM`, anything else is `TEXT_DELIVERED`. Locally the event is
  handled before the send returns; on the deployed demo it arrives within a second, so History shows
  `Delivered` and `Failed` rows without a network and the campaign counters move.
- `POST /api/app/demo/inbound` with `{ "from": "+447400123123", "to": "<sender number>", "body":
  "..." }` injects an inbound message: the inbox threads it, the opt-out keywords act, the rules run.
  The endpoint exists only in this mode.
- Own number verification accepts `000000`.
- The Buy A Number catalogue is forty seeded `+447…` numbers priced `£2.65 / Month`; buying one
  provisions it instantly and it can receive demo inbound messages.
- Alpha tag registration and website registration complete on the next scheduler tick instead of
  after the provider's review or 24 hours.
- Stripe runs in test mode with the same webhook path; `4242 4242 4242 4242` completes a top-up.
- The nightly rollup can be run on demand with `scripts/rollup.sh <date>` against a fixture log day
  so Usage and clicks are populated on a laptop.

`scripts/seed.sh` creates, idempotently:

- one account `Demo Ltd`, pricing country `GB`, timezone `Europe/London`, owner
  `demo@example.com` (password from `.env`), `TRIAL` £2.00, `trial_ends_at` 14 days out;
- the system `Opt-Out List` and `Example List` holding `Junaid Ahmed +447411972300` (fails on send,
  suffix `00`) and `Sam Patel +447411972305` (delivers);
- one template `Welcome` / `Hi {first_name}, welcome to Demo Ltd. Reply STOP to opt-out`;
- one own number `+447411972333` nicknamed `Own Number`, verified today;
- the three seeded inbound rules and the platform `RATE#GB#SMS` at 42,700 and `RATE#GB#MMS` at 42,700
  (MMS is priced as SMS outside `mms_countries`; `RATE#US#MMS` at 150,000 for completeness).
