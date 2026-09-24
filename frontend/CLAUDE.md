# Frontend

One single-page app: Vite, React 19, TypeScript strict, React Router, TanStack Query, CSS Modules. In
development `pnpm dev` serves it on port 3000 and proxies `/api` to the API on port 9000, exactly as
CloudFront does in production, so the page calls the same paths in both places. `pnpm build` writes
`dist/`, the deploy workflow syncs it to `s3://<sites>/txtlocal/` and invalidates the distribution.
Configuration is two build-time variables, `VITE_COGNITO_DOMAIN` and `VITE_COGNITO_CLIENT_ID`,
typed in `src/env.d.ts`; a third is a change to that file and to the deploy workflow in the same
commit. Payments need none: a top-up and a new card are Stripe Checkout pages the API hands back
as a URL. The API needs no variable: the client calls `/api` on the page's own origin, which
CloudFront and the Vite proxy both route to the backend. Node and pnpm run in the dev container
only. A change is checked by opening `http://localhost:3000` and by `pnpm check`, and it is not done
until `pnpm check` is green. The root `CLAUDE.md` binds here too; this file adds the page's own
rules.

## Commands

| Command | Does |
| --- | --- |
| `pnpm dev` | Vite on 3000 with the `/api` proxy |
| `pnpm check` | `typecheck`, `lint`, `format:check`, `test`, `check:api`, in that order; the gate |
| `pnpm typecheck` | `tsc --noEmit` over `src/` and over the config files |
| `pnpm lint` | `eslint .`; a warning is a review trigger the report must name |
| `pnpm format` / `pnpm format:check` | Prettier over everything but Markdown, the lockfile and generated code |
| `pnpm test` | Vitest, jsdom, once |
| `pnpm generate:api` | `openapi-typescript ../specs/openapi.app.json` into `src/api/generated/dashboard.d.ts` |
| `pnpm check:api` | regenerates into a cache and diffs; fails when the committed types are stale |

## Layout

`src/screens/` is the product as the user sees it, one folder per URL, and each screen keeps its pure
rules beside it in `rules.ts`. Beneath it, `src/api/` is the typed client generated from the spec, so
no endpoint needs a hand-written wrapper or hook. Files are organised by screen, never by kind, and a
file's stylesheet and test always sit beside it with the same base name.

| Directory | Owns |
| --- | --- |
| `src/app/` | The composition root: `App.tsx` (providers and the router), `routes.tsx` (the route table; every screen loads lazily), `navigation.ts` (the product map that the sidebar, the avatar menu and the route table all read) and `tokens.css` (the `:root` design tokens and the document reset), the only place a global selector may live. `shell/` is the frame every signed-in page sits in, laid out like a screen folder: `Shell.tsx` (the sign-in gate and the layout route) with `Sidebar` (its groups and links in `SidebarEntry`), `TopBar` (the title, the balance and the trial banner) and `AvatarMenu`, each with its stylesheet and test beside it; `rules.ts` for the page title and the menu entries; and `testing.tsx` for `renderShell`. |
| `src/components/<Name>/` | One generic component per folder: `Name.tsx`, `Name.module.css`, `Name.test.tsx`. The set is `ActionMenu`, `Badge`, `Button`, `Card`, `ComingSoon`, `ConfirmDeleteModal`, `CursorPager`, `EntriesSelect`, `FormModal`, `Icon`, `IconButton`, `Input`, `MediaUpload`, `MessageBody`, `Modal`, `Money`, `PagedRows`, `Panel`, `PhoneNumber`, `PhonePreview`, `RowAction`, `SearchForm`, `Section`, `Select`, `SettingsForm`, `Stack`, `StatusMessage`, `StatusPanel`, `Table`, `Tabs`, `Text`, `Toast`. `Panel` is the titled content card every page body sits in, and `StatusPanel` is that card saying "Loading…" or showing the request's error, so every loading and error early return is one line, and `StatusMessage` is the same line without the card, for a guard inside a card already on screen; `ActionMenu` is the one dropdown menu (text or icon trigger); `SearchForm` the one submit-on-Enter search; `PhonePreview` the one handset mock; `Modal.Title` heads every dialog; `FormModal` is the one dialog around a form, its notice in the body and its buttons in a footer slot; `ConfirmDeleteModal` is the one "are you sure" before a delete, showing the server's refusal in place; `Section` is the title-left, content-right group inside it (a collapsible or numbered variant composes its classes); `IconButton` is the only icon-only button; `RowAction` is the quiet link-style action in a table row, `tone="danger"` when it destroys; `EntriesSelect` owns the 20/50/100 page sizes and `CursorPager` the Previous/Next pair over `lib/useCursorTrail`; `PagedRows` pages a list the server returns whole, with both; `Table` owns the empty well and `align: "end"` numeric columns, and a hand-rolled table composes its classes; `MessageBody` is the labelled message textarea with a toolbar slot and a footer; `MediaUpload` is the one media picker, handed its upload function, `useMediaUpload` from `api/media`, rather than calling the API itself; `ComingSoon` is the one placeholder, for a tab not built yet. `Card` is CSS only: a card surface is `composes: card from "@/components/Card/Card.module.css"` plus its own padding, never a re-declared background, border and radius. `SettingsForm`, `Stack` and `Text` are CSS only too: a settings form composes `SettingsForm`'s `form`, `fields`, `actions` and `footer`, a column of panels or sections at the page's rhythm composes `stack`, and copy composes `Text`'s `secondary`, `muted`, `lead` (secondary at a 70ch measure) or `note` (secondary, small), while small muted help text composes `Input`'s `helper`. A component knows nothing about the API or a rule: it never imports `api/`, `app/`, `rules/` or `screens/`. |
| `src/rules/` | Only the rules that screens in different areas share: `segments.ts`, the GSM-7 and UCS-2 counts that Home, the inbox thread, quick send, templates, inbound rules and the messaging settings all use; `countries.ts`, the countries the account and the senders screens offer; and `senders.ts`, the empty senders view two areas fall back to. Every other rule lives in a screen's `rules.ts`. |
| `src/screens/<url>/` | One folder per URL, following the path: `/sms/websites` is `screens/sms/websites/`, `/billing/usage` is `screens/billing/usage/`, `/` is `screens/home/`. The entry is `<Name>Screen.tsx`, a tab with no URL of its own is `<Name>Tab.tsx`, the rest of the folder is the screen's parts, and `testing.tsx` holds its render helpers. `/mms/*` renders the SMS screens with `"MMS"` and has no folder of its own; the route table is the only file that knows. A screen reads and writes through `useApiQuery` and `useApiMutation` directly, with the path from the spec; a request that needs more than one call keeps a small hook beside the one screen that uses it: `useTransactions` pages by cursor, `useCampaignDraft` saves with a POST or a PUT, `useLogs` works out its window when it runs. `rules.ts` holds the screen's pure rules, with its table-driven `rules.test.ts` beside it. A rule is a function of its arguments: it imports generated types, `@/types`, the pure helpers in `lib/`, a component's type and the rules above it, and never the API client, React, `app/` or a screen. A rule lives in the nearest folder that covers every file using it: `sms/quick/recipients/rules.ts` serves the recipient field alone, `billing/rules.ts` the two usage screens, and `src/rules/` only screens in different areas. A type the spec has no schema for, a route's query parameters such as `HistoryQuery`, is derived from `paths` in the `rules.ts` that builds it. |
| `src/lib/` | Infrastructure only, no domain rule: `auth.ts` (the only module that knows Cognito; it calls the session route through `callApi`), `download.ts` (`saveCsv`, the one CSV download), `format.ts` (`dataOf`, which reads a `Result` with a fallback, and `dateTimeIn` and `minuteValue`, the two date formats), `notice.ts` (`noticeOf`, `refusalNotice`, `undismissedRefusalNotice`: every Result-to-Toast conversion), `paths.ts` (the paths several modules link to), `useAccountTimezone.ts` (the account's time zone, which ten screens format dates in), `useCursorTrail.ts` (the cursor stack every cursor-paged list keeps, reset when its scope changes) and `useDismiss.ts` (the Escape and click-outside close that `ActionMenu` and the avatar menu share). |
| `src/api/` | `generated/dashboard.d.ts` from `pnpm generate:api`, with every schema exported by name (`UserRow`, `MeView`); never edited by hand. `client.ts` is the only module that calls the API: `FetcherContext` (`fetch` unless a test provides a fake) with `useFetcher`, the bearer and its one refresh after a 401, and `callApi`, which types a call from the spec and answers a `Result`. `queries.ts` holds `useApiQuery` and `useApiMutation` over it, `apiKey`, the one key shape, and `createQueryClient`, whose mutation cache applies `INVALIDATES`, the one table of what each write makes stale; `invalidate` applies a list of reads by hand. `media.ts` is the one request that takes two calls, minting a media key and then putting the file where it points, and `useMediaUpload` hands it to `MediaUpload`. |
| `src/types.ts` | The few hand-written types two or more modules share, `Result` first among them. A type one module uses stays in that module. |
| `src/test/` | Infrastructure only: `setup.ts` (jest-dom matchers, a `matchMedia` that matches nothing because jsdom has none, and cleanup after each test), `render.tsx` (`renderWithProviders` for a screen, `renderHookWithProviders` for a hook), `fakeFetch.ts`, `signIn.ts`, and `fixtures/<slice>.ts`, the server payloads tests use, one module per backend slice. |

Nothing imports upward. A screen imports `api/`, `rules/`, components, `lib/`, its own folder and
the folders above it, and never `app/` or another screen: a part a second screen needs moves to the
screens' common folder, to `components/` when it is generic, or to `rules/` when it is a rule shared
across areas. `components/` imports none of `api/`, `rules/` or `screens/`. A `rules.ts`, beside a
screen or in `rules/`, imports no client, no React and no screen. `lib/` may call `api/`, as
`auth.ts` does for the session and `useAccountTimezone` for the settings, and imports none of
`components/`, `rules/` or `screens/`. `api/` is the bottom: it imports only the generated types and
`@/types`. A screen file imports its own folder and the folders above it relatively,
`./InboundRulesPanel`, `../rules`; everything else through `@/`. `eslint.config.js` enforces the
direction with `no-restricted-imports`, one block per tree and one for every `rules.ts`.

A folder over about twenty files is a split review, as R1 is for a file. The split follows the
resources on the screen, `inbound-rules/` and `delivery-rules/`, and every part keeps its stylesheet
and test beside it.

The `Table` component's `Column.header` is a `string`, so a column whose header is itself a control,
a select-all checkbox for instance, cannot use it; the contacts table renders its own `<table>` for
that reason. Widen `header` to `ReactNode` and give a column a way to opt out of the sort button
when a second table needs one, and move both onto the component in the same change.

## Navigation

The sidebar is the product's map and each entry is one screen folder. The slice named is the one
whose subagent owns the screen; a screen calls whichever routes it needs.

| Sidebar | URL | Screen folder | Slice |
| --- | --- | --- | --- |
| Home | `/` | `screens/home/` | `identity` |
| Contacts | `/contacts` | `screens/contacts/` | `contacts` |
| Sender IDs › Manage Senders | `/senders` | `screens/senders/` | `senders` |
| Sender IDs › Buy A Number | `/senders/buy` | `screens/senders/buy/` | `senders` |
| SMS › Quick SMS | `/sms/quick` | `screens/sms/quick/` | `messaging` |
| SMS › SMS Campaign | `/sms/campaigns` | `screens/sms/campaigns/` | `campaigns` |
| SMS › Website Registration | `/sms/websites` | `screens/sms/websites/` | `automation` |
| SMS › Templates | `/sms/templates` | `screens/sms/templates/` | `messaging` |
| SMS › Email SMS | `/sms/email` | `screens/sms/email/` | `automation` |
| SMS › Messenger | `/inbox` | `screens/inbox/` | `inbox` |
| SMS › History | `/sms/history` | `screens/sms/history/` | `messaging` |
| MMS › Quick MMS, MMS Campaign, History | `/mms/quick`, `/mms/campaigns`, `/mms/history` | the SMS screens, with `"MMS"` | as for SMS |
| Developers › API Credentials | `/developer/keys` | `screens/developer/keys/` | `identity` for Subaccounts, `developer` for General |
| Developers › API Logs | `/developer/logs` | `screens/developer/logs/` | `developer` |
| Developers › API Documentation, Libraries & SDKs | `/developer/docs` | `screens/developer/docs/` | `developer` |
| Developers › Webhooks | `/developer/webhooks` | `screens/developer/webhooks/` | `automation` |
| Avatar › My Profile | `/profile` | `screens/profile/` | `identity` |
| Avatar › Account Settings, Global Sending | `/account` | `screens/account/` | `identity` |
| Avatar › Messaging Settings | `/account/messaging` | `screens/account/messaging/` | `identity` |
| Avatar › Billing (seven tabs) | `/billing/<tab>` | `screens/billing/<tab>/` | `billing`, `analytics` for Usage and Usage Reporting |
| The sign-in callback | `/auth/callback` | `screens/auth/callback/` | `identity` |
| The landing page, for a signed-out visitor | `/` | `screens/landing/` | none: static, and its buttons start sign-in |

`Shell` shows the landing page instead of redirecting when a signed-out visitor is at `/`; every
other signed-out path still goes to sign-in.

Automation, Integrations, Reseller and Referrals are out of v1: neither the sidebar nor the avatar
menu shows them.

## Data

- `callApi(fetcher, method, path, init)` in `src/api/client.ts` returns `{ data, status: "OK" }` or
  `{ message, status: "ERROR" }`, never throws for an HTTP failure, and never leaks a `Response`.
  Every caller branches once on `result.status`. The method, path, parameters and body are checked
  against `dashboard.d.ts`, so a route the spec does not describe does not compile. The fetcher
  comes from `useFetcher()`; no component takes a `fetcher` prop, and nothing mocks the network
  globally.
- A screen reads with `useApiQuery(method, path, init, options)` and writes with
  `useApiMutation(method, path)`, whose `mutate` takes the request init: `{ body }`,
  `{ params: { path } }` or both, so every call names its route where it is made. There is no
  wrapper and no hook per endpoint; the only named hooks are the few above that need more than one
  call.
- A query's key is `apiKey(method, path, init)`: `"get /api/app/me"`, then the init. What a write
  makes stale lives in one place, `INVALIDATES` in `api/queries.ts`, which names the reads for each
  write; `createQueryClient`'s mutation cache applies it once the write settles, refused or not. A
  write that spends or releases credit stales `ME`, the signed-in views that show the balance.
  Nothing invalidates the whole cache.
- A query string is built by `searchOf`, which drops empty values and sorts the names, so a URL
  does not depend on the order an object was built in, and a test's fake route matches it.
- A query whose key follows an input on the same screen passes `placeholderData: keepPreviousData`.
  Without it each keystroke makes a new key with no data, the screen's loading early return
  replaces the page, and the input being typed in unmounts after one character.
- A server refusal is `{ code, message }` and the page renders `message` verbatim through `Toast`.
  The client checks only what saves a pointless round trip: required fields, the segment ceiling,
  a number's shape. Everything else is the server's sentence, so the two copies of a rule cannot
  drift.
- Money arrives as integer micro-pounds in fields ending `Micro` and is displayed only through
  `Money`, which owns the one division. No component adds, subtracts or formats money; a total the
  page needs is a field the API returns.
- Phone numbers arrive in E.164 and are displayed only through `PhoneNumber`. The API owns
  normalisation.
- Dates arrive as ISO strings in UTC and are formatted at the edge of the component that shows
  them, through `Intl.DateTimeFormat` with the account's time zone.
- Pagination is cursor-based: a page carries `nextCursor` or nothing, and a list keeps the cursor
  in the query key. No page numbers are computed on the client.

## Auth

`src/lib/auth.ts` implements the hosted-UI authorization code flow with PKCE against
`VITE_COGNITO_DOMAIN`. The code verifier lives in `sessionStorage` until the callback consumes it;
the access and refresh tokens live in memory in a module-level `let`; the refresh token is exchanged
at the token endpoint when a request answers 401 and the page redirects to sign-in when that fails.
Nothing about a session is written to `localStorage`, and the lint rule bans the name. `callApi`
attaches the access token; no component reads it.

## Component rules

The six rules of the frontend standard, with the check that proves each:

- **R1, size.** A component file over 100 non-blank lines is a decomposition review; the linter warns
  under `src/components/`, `src/screens/` and `src/app/shell/`. The question it asks is whether the file does more than
  one thing, so it does not run on a `*.test.tsx`, where covering several behaviours is the point. A
  component that legitimately exceeds is named in the report with the reason, since a comment cannot
  carry it here.
- **R2, no nested ternaries in JSX.** One level at most; the linter errors on the second. The
  extraction is a function that returns the element, `pickBadge(status)`, or a sub-component.
- **R3, guards not staircases.** Loading, error and empty states are early returns at the top; the
  main `return` is the happy path only. Check: the early returns read as a list.
- **R4, composition over configuration.** More than eight props, or any boolean named `is*Mode`,
  `show*`, `enable*` or `with*`, is a decomposition candidate; children and slots replace flags.
  `Modal` is `Modal`, `Modal.Header`, `Modal.Body`, `Modal.Footer`. Check: count the props.
- **R5, self-documenting names.** Comments are banned, so the name is the explanation. A helper
  that needs a sentence is renamed or split.
- **R6, one component per file.** Private sub-components used only here may share it; a second
  export that is a component is a second file. `react-refresh/only-export-components` enforces the
  export half.

Styles are CSS Modules: `Component.module.css` beside the component, imported as `styles`, classes
applied as `styles.name`. A stylesheet always has its component beside it with the same base name;
the CSS-only components, `Card`, `SettingsForm`, `Stack` and `Text`, are the one exception, a folder
with no `.tsx`. Design tokens are custom properties on `:root` in `src/app/tokens.css`, and a new
hex literal outside that file is a missing token. No global class exists outside `src/app/`, so one
screen's styles cannot reach another screen's markup.

## TypeScript

- **A function either works out a value or renders, never both.** `segmentsOf` returns the count;
  the counter component shows it. Split any function that does both before extending it.
- **Async work returns a `Result`.** No `try` in a component; `callApi` already caught the failure
  and named it.
- **A constant's name carries its unit.** `MICRO_PER_POUND`, `TRIAL_DAYS`, `POLL_MS`. A number with
  no unit in its name is a bug waiting to be misread.
- **User-facing copy is a module constant above the functions**, `NETWORK_MSG`, `OVER_LIMIT_MSG`,
  never a string literal inside control flow. A clause two messages share is one constant composed
  into both, so the number in the sentence cannot drift from the number in the check.
- **One builder per message shape.** `segmentSummary(segments)` writes "Approx. 42 characters/1 SMS
  per recipient" once; nobody copies the sentence to change a word.
- **Shared types live once in `src/types.ts`** and are imported with `import type`. Object shapes
  are `interface`, unions are `type`; a type used by one module stays private to it.
- **Generated types are the contract.** `callApi` and the hooks take every request and response
  type from `dashboard.d.ts` through `openapi-fetch`, and a module that names a shape imports it by
  its schema name, `import type { UserRow } from "@/api/generated/dashboard"`. Nothing checks a
  hand-written wire shape against the server; one let Home's test send show the refusal code
  instead of its sentence. The one shape derived by hand is a route's query parameters, which the
  spec gives no schema, taken from `paths` in the one module that builds them. Every route whose
  body the dashboard reads declares it, and every failure answers the `ErrorBody` the spec names as
  its `default` response.
- **Predicates read as questions**: `isRefusal`, `isWithinCeiling`, `hasToppedUp`.
- **`const` arrow for a one-expression helper, `function` for anything longer or exported.**
- **Alphabetical**: object keys, destructured parameters, named imports inside the braces, props in
  JSX, CSS custom properties. Import statements come in up to four groups, packages, `@/` paths,
  relative paths, then the stylesheet, each sorted by path, a blank line between.
- **No `any`, no non-null `!`, no `as` except on a generated type or `as const`.** A shape that
  arrives as `unknown` is narrowed by a predicate. The one other place is where `api/client.ts` and
  `api/queries.ts` hand a generic path to `openapi-fetch`: TypeScript cannot resolve a call whose
  method and path are still type parameters, so those files cast at that boundary and nowhere else.
- **No `eslint-disable`, no `@ts-ignore`, no `@ts-expect-error`.** `noInlineConfig` makes the first a
  no-op that fails the build; the others are comments and comments are banned. Fix the code or
  change the rule in `eslint.config.js` in its own change with the reason in the commit message.
- **No `localStorage`.** Remembered UI state that is worth keeping is worth a server field.
- **Visibility is the `hidden` attribute or conditional rendering**, never a `display` toggled from
  a class named `is-hidden`.

## CSS

- One declaration per line, always; properties alphabetical within a rule; nested selectors after
  the declarations, `&:disabled`, `&:focus-visible`, `&:hover` in alphabetical order; nested `@media`
  last, widest first.
- Colour, spacing, radius, border width and type come from the `:root` tokens, which are the Relay
  design system: `light-dark()` pairs so dark mode follows the OS, `font: var(--type-body)` and friends
  for type. A token is named for its role, `--on-brand`, `--border-input`, never its shade.
- The focus ring, `font: inherit` on controls, placeholder colour and link colour are global in
  `tokens.css`; a module never repeats them. Surfaces separate with a hairline and whitespace;
  `--shadow` is for things that float.
- Style with classes, never with ids and never with a bare element selector outside `tokens.css`.
  Ids are for `htmlFor`, `aria-labelledby` and tests; no stylesheet contains one.
- Every part of a component has a class, `.row`, `.label`, `.note`; no anonymous `div` or `span`
  stands in for a part.
- A class may exist only to name a part; the markup then says what the element is.

## Testing

- A pure rule gets a table-driven test beside it: `it.each([...] as const)("$label", …)` with a
  `label` per row, one behaviour per row, the expected value written out, never computed. Every
  ceiling is tested on both sides: 160 and 161, 1,224 and 1,225, 70 and 71.
- A component is tested by behaviour with Testing Library: render, act as a user would through
  `@testing-library/user-event`, assert what the user sees by role or text. Never assert markup,
  class names or component internals.
- Every user-facing sentence is asserted verbatim by at least one test, the page's own and the
  server's as rendered through `Toast`.
- A test sits beside its subject with the same base name and tests that subject: `X.test.tsx`
  renders `X.tsx`, `rules.test.ts` tests the `rules.ts` beside it, `api/queries.test.tsx` tests
  the invalidation table. A render helper lives in the screen folder's `testing.tsx`.
- A server payload lives in `src/test/fixtures/<slice>.ts`, the module of the backend slice whose
  route returns it, and is defined once. A test that wants a variant uses the owner's payload and
  asserts what it renders, `Example List (2)`, or spreads it inline,
  `{ ...EXAMPLE_LIST, contactCount: 12 }`. It never keeps a renamed copy. A payload that points at
  another slice's row names it through that slice's export, `listId: EXAMPLE_LIST_ID`,
  `userId: OWNER_ROW.userId`, so an id is written once.
- `callApi` is injected through `FetcherContext`. `renderWithProviders(ui, { fetcher, route })` and
  `renderHookWithProviders(hook, { fetcher })` provide the fake, and without one they provide
  `fakeFetch({})`, which answers every request 404. No test starts a mock server and no test
  reaches the network. A fake route is the exact URL, with its query names sorted.
- A test asserts one behaviour and its name says which. A name joined with "and" is two tests.
- A bug fix lands with the test that would have caught it, in the same change.

## The gate and the report

`pnpm check` is green before anything is called done, and every report pastes its last lines. For
every component created or substantially changed the report also pastes the numbers the standard's
self-check asks for:

- `wc -l <path>`;
- the props count, from the `Props` interface;
- `grep -nE '\?.*\?.*:' <path>`, pasted or "clean";
- the early returns at the top of the component, listed, or "none";
- where its CSS lives, and that no rule leaks;
- any `max-lines` warning, with the decision: split now, or defer with the reason.

Checkboxes are not enough. The numbers must be in the report.

## Working as a subagent

The protocol is root `CLAUDE.md` §10. Here its scope is `src/test/fixtures/<slice>.ts` and the
screen folders the Navigation table gives its slice, with their `rules.ts` and tests. A `rules.ts`
above those folders, such as `screens/sms/rules.ts`, is shared and changes through the orchestrator. A component that does not exist yet may be created, small and generic, in its own folder
under `src/components/`; an existing component's props are not changed, and a change there is a line
under "Needs from the orchestrator". Nothing in `src/api/`, `src/app/`, `src/lib/`, `src/rules/`,
`src/types.ts` or another slice's screens is edited by a slice subagent; a new write that makes a read stale is a line
for `INVALIDATES` under "Needs from the orchestrator". The report follows the root shape and adds
the numbers above.
