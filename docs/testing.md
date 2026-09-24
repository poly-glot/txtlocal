# Testing

These rules bind exactly as `CLAUDE.md` does. Read them before writing or changing a test.

## Where a test lives and what it touches

- A pure rule gets a unit test beside it, in the slice's `tests/` directory, importing the module
  directly: `slices/messaging/tests/test_segments.py` tests `segments.py` and nothing else.
- Anything touching the table gets an integration test through `shared.testing.local_repo_table`,
  which skips the test itself when `AWS_ENDPOINT_URL_DYNAMODB` is unset, creates a table with fresh
  entropy in its name, and deletes it on exit. A test body opens with
  `async with local_repo_table("messaging") as table:` and nothing else stands between that line and
  the behaviour. CI sets the endpoint, so the integration tests run there rather than skip; a green
  suite that skipped everything is worse than no suite, because it is believed.
- A gateway, a bus or a payment provider is never called from a test. Each has an in-memory reference
  implementation in `shared/testing.py` with the same conditional semantics as the real one: a
  put-if-absent that returns `False` the second time, a send that returns receipts in order. The real
  adapter has one test per error mapping through `botocore.stub.Stubber`, and nothing more.
- A repository's reference implementation in tests mirrors DynamoDB's conditions, never its
  convenience: if the real method is put-if-absent, the fake refuses the second put too.

## The shape of a test

- **Table-driven, one label per case.** `pytest.mark.parametrize` with an `ids` list whose entries read
  as the behaviour: `gsm-161-needs-two`, `half-rounds-up`. A label turns a failure from "assertion
  failed at line 214" into a sentence naming what broke.
- **One behaviour per test, named for it.** A test whose name needs "and" is two tests. A parametrized
  test is one behaviour across many inputs, which is the only way a test grows.
- **Assert the type, never `Exception`.** `pytest.raises(BadRequest)`, never `pytest.raises(Exception)`
  and never `pytest.raises(AppError)` when a subclass is the point.
- **Assert every public message verbatim.** A `BadRequest` message is copy the page renders; a test
  compares `str(caught.value)` to the module constant, and the constant is the one the code raises,
  so the two cannot drift. `pytest.raises(match=)` is a regular expression; use it only for a fragment
  and prefer the equality.
- **A ceiling is tested on both sides.** The last value accepted and the first refused: 1,224
  characters and 1,225, eight parts and nine, 160 and 161. A limit tested on one side is a limit whose
  other side is a guess.
- **Never a compound boolean.** `assert a and not b` says nothing about which half broke. Two
  assertions, or compare a tuple, so the failure names the field.
- **Expect the value the system produced, not a constant restating it.** Compare against the
  module's own constant when the constant is the contract, against a literal when the literal is the
  behaviour a person reads.
- **Fixtures are named for their role, never their value.** `paid_order`, `trial_account`,
  `verified_number`; never `order_1`, `account_a`.
- **An invariant of an endpoint belongs in the helper every test fetches through**, not in the one
  test that happened to notice it. A repeated read-and-unwrap chain becomes a helper named for the
  question it answers.
- **Build rows through the helpers in `shared/testing.py`** rather than hand-rolling a struct a
  helper already produces, so a new field breaks one function instead of thirty.
- **Randomness and time are injected.** A service takes `rng` and `clock`; a test passes
  `Random(seed)` and a fixed `datetime`, the way `examples/test_raffle_draw.py` does, and never
  patches the clock.
- **Async tests are plain `async def`.** `asyncio_mode = "auto"` runs them; nothing calls
  `asyncio.run`, which `ruff` bans outside `shared.runtime`.

## What a test does not do

- No mocks of the module under test, no `unittest.mock.patch` on a collaborator that has a reference
  implementation, no assertion on how many times something was called. Assert the state that resulted.
- No sleeping. A test that waits for time to pass passes a later clock.
- No network. A test that needs AWS opens with `local_repo_table`; a test that needs Stripe uses
  `FakePaymentGateway` from `billing/tests/fakes.py`, or `StripeGateway` over an
  `httpx.MockTransport` when the request Stripe receives is the point.
- No `# noqa`, `# type: ignore` or `pragma`. Tests obey `ruff` and `mypy --strict` like everything
  else; `tests/` may use `assert`, hard-coded numbers and hard-coded secrets, and nothing else extra.

## Running

`scripts/check.sh` formats, lints, types, checks imports and runs the suite, in that order, and is the
pre-commit hook and the CI job. `uv run pytest -k segments` runs one area while iterating; the gate
runs everything before anything is called done.

A bug fix lands with the test that would have caught it, in the same change. A fix without one is a
promise that the bug was understood, with nothing holding the promise.
