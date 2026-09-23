import asyncio
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from lib import assert_eq, assert_true, base_parser, finish, note, sign_in_session

from txtlocal.shared import runtime

DEFAULT_RATE = 20
DEFAULT_DURATION = 15.0
P99_BUDGET_SECONDS = 0.5
TRACKED_URL = "https://example.com/pricing"

USAGE = """
qa/04-load.py sends RATE requests a second for DURATION seconds at the redirect path, the one route
this app shares capacity on with two other apps on the same DynamoDB table (CLAUDE.md: "the redirect
path is exactly one eventually consistent GetItem and nothing else"). It asserts the success ratio,
p99 latency, and zero 5xx responses.

It CANNOT assert zero table throttles: scripts/local-table.sh creates the local table
PAY_PER_REQUEST, not the shared account's provisioned 25/25 units, so a real throttle cannot be
produced here even by a broken deploy. Re-run this against the deployed stack, watching
ReadThrottleEvents on the shared table, before trusting a "no throttles" claim in production.
"""


def mint_tracked_link(client: httpx.Client, base_url: str, auth: dict[str, str]) -> str:
    sent = client.post(
        f"{base_url}/api/app/messages/send",
        json={
            "body": f"See {TRACKED_URL} for details",
            "shortenUrls": True,
            "to": ["+447400123188"],
        },
        headers=auth,
    )
    sent.raise_for_status()
    history = client.get(f"{base_url}/api/app/messages", headers=auth).json()
    pattern = re.compile(r"https?://[^/\s]+/l/([a-z0-9]+)")
    for row in history["items"]:
        match = pattern.search(row["body"])
        if match:
            return match.group(1)
    raise RuntimeError("no tracked link came back in history")


async def paced_get(
    client: httpx.AsyncClient, url: str, start: float, index: int, rate: int
) -> tuple[float, int]:
    target = start + index / rate
    delay = target - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)

    began = time.monotonic()
    try:
        response = await client.get(url, follow_redirects=False)
        status = response.status_code
    except httpx.HTTPError:
        status = 0
    return time.monotonic() - began, status


async def run_load(base_url: str, code: str, rate: int, duration: float) -> list[tuple[float, int]]:
    url = f"{base_url}/l/{code}"
    total = int(rate * duration)
    async with httpx.AsyncClient(timeout=5.0) as client:
        start = time.monotonic()
        return list(
            await asyncio.gather(*(paced_get(client, url, start, i, rate) for i in range(total)))
        )


def main() -> int:
    parser = base_parser(USAGE)
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    args = parser.parse_args()

    with httpx.Client(timeout=10.0) as client:
        auth, _me = sign_in_session(client, args.base_url, args.client_id, args.user)
        code = mint_tracked_link(client, args.base_url, auth)

    note(f"firing {args.rate} req/s for {args.duration}s at /l/{code}")
    results = runtime.run(run_load(args.base_url, code, args.rate, args.duration))

    latencies = sorted(latency for latency, _status in results)
    statuses = [status for _latency, status in results]
    successes = sum(1 for status in statuses if status == 302)
    server_errors = sum(1 for status in statuses if status >= 500)
    p99 = latencies[int(len(latencies) * 0.99) - 1] if latencies else float("inf")

    note(f"{len(results)} requests, {successes} succeeded, {server_errors} server errors")
    note(f"p50 {latencies[len(latencies) // 2]:.3f}s, p99 {p99:.3f}s")

    assert_true(successes / len(results) >= 0.999, "success ratio is at least 0.999")
    assert_eq(server_errors, 0, "zero 5xx responses under load")
    assert_true(p99 < P99_BUDGET_SECONDS, f"p99 latency is under {P99_BUDGET_SECONDS}s")
    note("NOT asserted: table throttles — the local table is on-demand, see USAGE above")

    return finish("04-load")


if __name__ == "__main__":
    raise SystemExit(main())
