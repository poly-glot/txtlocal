import os
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from lib import assert_eq, assert_true, base_parser, finish, note, sign_in_session

RECIPIENT = "+447400123199"

USAGE = """
qa/01-routing.py proves the phase-7 operator and email-to-SMS wiring end to end, against a real
running server: website registration, operator-driven approve and reject, an allowed email address,
and an inbound email that must turn into a real queued SMS. None of this crosses the API-process
boundary in a pytest run; it only runs for real when a real server answers real HTTP.
"""


def marked(client: httpx.Client, base_url: str, auth: dict[str, str], marker: str) -> int:
    page = client.get(
        f"{base_url}/api/app/messages", headers=auth, params={"field": "TO", "q": RECIPIENT}
    ).json()
    return sum(1 for row in page["items"] if row["body"] == marker)


def main() -> int:
    args = base_parser(USAGE).parse_args()
    tag = os.getpid()

    with httpx.Client(timeout=10.0) as client:
        auth, me = sign_in_session(client, args.base_url, args.client_id, args.user)
        account_id = me["accountId"]
        operator = {"X-Operator-Secret": args.operator_secret}

        approved_domain = f"qa-routing-{tag}-approve.test"
        rejected_domain = f"qa-routing-{tag}-reject.test"
        registered = client.post(
            f"{args.base_url}/api/app/websites",
            json={"domains": [approved_domain, rejected_domain]},
            headers=auth,
        )
        assert_eq(registered.status_code, 201, "website registration accepted")
        assert_true(
            all(row["status"] == "UNDER_REVIEW" for row in registered.json()),
            "both websites start under review",
        )

        approved = client.post(
            f"{args.base_url}/api/operator/accounts/{account_id}/websites/{approved_domain}/approve",
            headers=operator,
        )
        assert_eq(approved.status_code, 200, "operator approve succeeds")
        assert_eq(approved.json()["status"], "APPROVED", "approved website is APPROVED")

        rejected = client.post(
            f"{args.base_url}/api/operator/accounts/{account_id}/websites/{rejected_domain}/reject",
            json={"reason": "qa: automated rejection"},
            headers=operator,
        )
        assert_eq(rejected.status_code, 200, "operator reject succeeds")
        assert_eq(rejected.json()["status"], "REJECTED", "rejected website is REJECTED")
        assert_eq(
            rejected.json()["rejectedReason"], "qa: automated rejection", "rejection reason echoed"
        )

        senders = client.get(f"{args.base_url}/api/app/senders", headers=auth).json()
        sender_id = senders["senders"]["SHARED"][0]["senderId"]
        sender_email = f"qa-{tag}@{approved_domain}"

        added = client.post(
            f"{args.base_url}/api/app/email-senders",
            json={"email": sender_email, "senderId": sender_id, "userId": me["userId"]},
            headers=auth,
        )
        assert_eq(added.status_code, 201, "allowed email address registered")

        marker = f"qa routing check {tag}"

        matched = client.post(
            f"{args.base_url}/api/app/demo/inbound-email",
            json={"body": marker, "numbers": [RECIPIENT], "senderEmail": sender_email},
        )
        assert_eq(matched.status_code, 202, "inbound email from an allowed address is accepted")

        deadline = time.monotonic() + 5.0
        sent = 0
        while time.monotonic() < deadline:
            sent = marked(client, args.base_url, auth, marker)
            if sent:
                break
            time.sleep(0.25)
        assert_eq(sent, 1, "a matched inbound email queues exactly one SMS")

        unmatched = client.post(
            f"{args.base_url}/api/app/demo/inbound-email",
            json={
                "body": marker,
                "numbers": [RECIPIENT],
                "senderEmail": f"nobody-{tag}@unregistered.test",
            },
        )
        assert_eq(
            unmatched.status_code, 202, "inbound email from an unknown address still answers 202"
        )
        time.sleep(0.5)
        assert_eq(
            marked(client, args.base_url, auth, marker),
            1,
            "an unmatched sender queues nothing, silently",
        )

        removed = client.delete(
            f"{args.base_url}/api/app/email-senders/{urllib.parse.quote(sender_email, safe='')}",
            headers=auth,
        )
        assert_eq(removed.status_code, 204, "fixture email address removed")
        note(f"left behind: websites {approved_domain} and {rejected_domain} (no delete endpoint)")

    return finish("01-routing")


if __name__ == "__main__":
    raise SystemExit(main())
