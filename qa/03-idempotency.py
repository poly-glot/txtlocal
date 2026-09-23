import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from lib import assert_eq, assert_true, base_parser, finish, note, sign_in_session

from txtlocal.shared import runtime

CONCURRENCY = 8
SMS_MICRO = 42_700
REPLAYED_HEADER = "Idempotent-Replayed"

USAGE = """
qa/03-idempotency.py fires the same Idempotency-Key at /api/v3/sms/send CONCURRENTLY, not one after
another. developer/router.py's `idempotent()` claims the key with a conditional write and falls back
to a Conflict when the claim is lost to a request still in flight; smoke.py only ever proves the
sequential replay case (send, then resend), which every unit test can already reach through a
single event loop. A real race between two live sockets is the one thing that path exists to
survive, and the one thing nothing before this script has ever actually produced.
"""


async def fire(
    client: httpx.AsyncClient,
    base_url: str,
    auth: tuple[str, str],
    key: str,
    body: dict[str, object],
) -> httpx.Response:
    return await client.post(
        f"{base_url}/api/v3/sms/send",
        auth=auth,
        headers={"Idempotency-Key": key},
        json=body,
    )


async def burst(
    base_url: str, auth: tuple[str, str], key: str, body: dict[str, object]
) -> list[httpx.Response]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await asyncio.gather(
            *(fire(client, base_url, auth, key, body) for _ in range(CONCURRENCY))
        )


def main() -> int:
    args = base_parser(USAGE).parse_args()
    tag = os.getpid()
    order_tag = f"qa-idempotency-{tag}"

    with httpx.Client(timeout=10.0) as client:
        auth_header, me = sign_in_session(client, args.base_url, args.client_id, args.user)
        issued = client.post(
            f"{args.base_url}/api/app/account/users/{me['userId']}/api-key", headers=auth_header
        ).json()
        v3_auth = (str(me["username"]), str(issued["apiKey"]))

        before = client.get(f"{args.base_url}/api/app/billing/summary", headers=auth_header).json()
        before_balance = before["balanceMicro"]

        body = {
            "messages": [
                {
                    "body": "qa concurrent idempotency",
                    "customString": order_tag,
                    "to": "+447400123177",
                }
            ]
        }
        responses = runtime.run(burst(args.base_url, v3_auth, order_tag, body))

    statuses = [response.status_code for response in responses]
    fresh = [r for r in responses if r.status_code == 201 and REPLAYED_HEADER not in r.headers]
    replayed = [r for r in responses if REPLAYED_HEADER in r.headers]
    conflicted = [r for r in responses if r.status_code == 409]

    note(f"outcomes: {sorted(statuses)}")
    assert_eq(len(fresh), 1, "exactly one concurrent request actually sent")
    assert_eq(
        len(fresh) + len(replayed) + len(conflicted),
        CONCURRENCY,
        "every concurrent request lands on a known outcome, none fall through as a raw error",
    )
    assert_true(
        all(response.status_code in (201, 409) for response in responses),
        "no concurrent request answers with anything but 201 or 409",
    )

    with httpx.Client(timeout=10.0) as client:
        after = client.get(f"{args.base_url}/api/app/billing/summary", headers=auth_header).json()
        history = client.get(
            f"{args.base_url}/api/v3/sms/history", auth=v3_auth, params={"limit": 50}
        ).json()

    matching = [row for row in history["messages"] if row["customString"] == order_tag]
    assert_eq(
        before_balance - after["balanceMicro"], SMS_MICRO, "balance is debited for exactly one send"
    )
    assert_eq(len(matching), 1, "history carries exactly one message for the race, not eight")

    return finish("03-idempotency")


if __name__ == "__main__":
    raise SystemExit(main())
