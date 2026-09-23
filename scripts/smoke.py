import base64
import hashlib
import os
import re
import secrets
import sys
import time
from typing import Any

import httpx

API = os.environ.get("SMOKE_API", "http://127.0.0.1:9000")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "local")
REDIRECT_URI = "http://localhost:3000/auth/callback"
USER = os.environ.get("SMOKE_USER", "demo@txtlocal.local")
AUTO_REPLY_BODY = "Thanks for your message."
DELIVERS = "+447400123105"
FAILS = "+447400123100"
POLL_SECONDS = 1.0
RATE_LIMITED_STATUS = 429
REPLY_PEER = "+447400123109"
SCHEDULER_DEADLINE_SECONDS = 45.0
SMS_MICRO = 42_700
STOP_PEER = "+447400123108"
TRACKED_URL = "https://example.com/pricing"
TRIAL_MICRO = 2_000_000


def challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign_in(client: httpx.Client) -> dict[str, Any]:
    verifier = secrets.token_urlsafe(48)
    params = {
        "client_id": CLIENT_ID,
        "code_challenge": challenge_of(verifier),
        "code_challenge_method": "S256",
        "login": USER,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email",
        "state": "smoke",
    }
    authorized = client.get(f"{API}/api/dev-idp/oauth2/authorize", params=params)
    location = authorized.headers["location"]
    code = httpx.URL(location).params["code"]

    tokens = client.post(
        f"{API}/api/dev-idp/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    tokens.raise_for_status()
    return dict(tokens.json())


def check(label: str, actual: object, expected: object) -> bool:
    ok = actual == expected
    mark = "ok  " if ok else "FAIL"
    sys.stdout.write(f"{mark} {label}: {actual!r}\n")
    return ok


def send_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    send = {"body": "Your code is 123456", "to": [DELIVERS, FAILS]}

    quote = client.post(f"{API}/api/app/messages/quote", json=send, headers=auth).json()
    sent = client.post(f"{API}/api/app/messages/send", json=send, headers=auth)
    sent.raise_for_status()

    history = client.get(f"{API}/api/app/messages", headers=auth).json()
    summary = client.get(f"{API}/api/app/billing/summary", headers=auth).json()
    status = {row["to"]: row["status"] for row in history["items"]}

    return [
        check("quote recipients", quote["recipients"], 2),
        check("quote cost", quote["costMicro"], 2 * SMS_MICRO),
        check("quote refusals", quote["refused"], []),
        check("send campaign", isinstance(sent.json()["campaignId"], str), expected=True),
        check("history rows", len(history["items"]), 2),
        check("delivered row", status.get(DELIVERS), "DELIVERED"),
        check("failed row", status.get(FAILS), "FAILED"),
        check("balance after send", summary["balanceMicro"], TRIAL_MICRO - 2 * SMS_MICRO),
    ]


def campaign_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    before = client.get(f"{API}/api/app/billing/summary", headers=auth).json()["balanceMicro"]

    made = client.post(f"{API}/api/app/lists", json={"name": f"Smoke {os.getpid()}"}, headers=auth)
    made.raise_for_status()
    list_id = made.json()["listId"]

    for mobile in (DELIVERS, FAILS):
        added = client.post(
            f"{API}/api/app/lists/{list_id}/contacts",
            json={"firstName": "Sam", "mobile": mobile},
            headers=auth,
        )
        added.raise_for_status()

    draft = client.post(
        f"{API}/api/app/campaigns",
        json={"body": "Hi {first_name}", "listId": list_id, "name": "Smoke campaign"},
        headers=auth,
    )
    draft.raise_for_status()
    campaign_id = draft.json()["campaignId"]

    quote = client.post(f"{API}/api/app/campaigns/{campaign_id}/quote", headers=auth).json()
    scheduled = client.post(
        f"{API}/api/app/campaigns/{campaign_id}/schedule", json={"now": True}, headers=auth
    )
    scheduled.raise_for_status()

    report = wait_for_sent(client, auth, campaign_id)
    counts = report["campaign"]["counts"]
    after = client.get(f"{API}/api/app/billing/summary", headers=auth).json()["balanceMicro"]

    listed = client.post(
        f"{API}/api/app/messages/quote",
        json={"body": "to the list", "listIds": [list_id], "to": []},
        headers=auth,
    ).json()
    unknown = client.post(
        f"{API}/api/app/messages/quote",
        json={"body": "nope", "listIds": ["missing"], "to": []},
        headers=auth,
    )

    return [
        check("list quote recipients", listed["recipients"], 2),
        check("list quote cost", listed["costMicro"], 2 * SMS_MICRO),
        check("unknown list refused", unknown.status_code, 404),
        check("campaign quote recipients", quote["recipients"], 2),
        check("campaign quote cost", quote["costMicro"], 2 * SMS_MICRO),
        check("campaign status", report["campaign"]["status"], "SENT"),
        check("campaign sent", counts["sent"], 2),
        check("campaign delivered", counts["delivered"], 1),
        check("campaign undelivered", counts["undelivered"], 1),
        check("campaign billed", before - after, 2 * SMS_MICRO),
    ]


def provider_id_of(client: httpx.Client, auth: dict[str, str], peer: str) -> str:
    history = client.get(
        f"{API}/api/app/messages", headers=auth, params={"field": "TO", "q": peer}
    ).json()
    row = next(row for row in history["items"] if row["to"] == peer)
    return str(row["providerMessageId"])


def inject_inbound(
    client: httpx.Client, auth: dict[str, str], peer: str, body: str, previous_message_id: str
) -> None:
    shared = client.get(f"{API}/api/app/senders", headers=auth).json()["senders"]["SHARED"][0]
    injected = client.post(
        f"{API}/api/app/demo/inbound",
        json={
            "body": body,
            "from": peer,
            "previousMessageId": previous_message_id,
            "to": shared["value"],
        },
    )
    injected.raise_for_status()


def two_way_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    client.post(
        f"{API}/api/app/messages/send", json={"body": "seed", "to": [STOP_PEER]}, headers=auth
    ).raise_for_status()
    inject_inbound(client, auth, STOP_PEER, "stop", provider_id_of(client, auth, STOP_PEER))

    quote = client.post(
        f"{API}/api/app/messages/quote", json={"body": "x", "to": [STOP_PEER]}, headers=auth
    ).json()
    stopped_conversation = client.get(
        f"{API}/api/app/conversations/{STOP_PEER}", headers=auth
    ).json()["conversation"]

    rule = client.post(
        f"{API}/api/app/rules/inbound",
        json={
            "action": "AUTO_REPLY",
            "actionAddress": AUTO_REPLY_BODY,
            "keyword": "hello",
            "matchKind": "KEYWORD",
            "name": "Smoke auto-reply",
        },
        headers=auth,
    )
    rule.raise_for_status()

    client.post(
        f"{API}/api/app/messages/send", json={"body": "seed", "to": [REPLY_PEER]}, headers=auth
    ).raise_for_status()
    inject_inbound(client, auth, REPLY_PEER, "hello", provider_id_of(client, auth, REPLY_PEER))

    reply_conversation = client.get(
        f"{API}/api/app/conversations/{REPLY_PEER}", headers=auth
    ).json()["conversation"]
    replies = client.get(
        f"{API}/api/app/messages", headers=auth, params={"field": "TO", "q": REPLY_PEER}
    ).json()["items"]
    auto_reply = next((row for row in replies if row["body"] == AUTO_REPLY_BODY), None)

    return [
        check("stop refuses a further send", quote["refused"][0]["reason"], "OPTED_OUT"),
        check("stop conversation unread", stopped_conversation["unread"], 1),
        check("hello conversation unread", reply_conversation["unread"], 1),
        check("auto-reply was sent", auto_reply is not None, expected=True),
        check("auto-reply body", auto_reply["body"] if auto_reply else None, AUTO_REPLY_BODY),
    ]


def v3_checks(client: httpx.Client, auth: dict[str, str], me: dict[str, Any]) -> list[bool]:
    issued = client.post(f"{API}/api/app/account/users/{me['userId']}/api-key", headers=auth).json()
    v3_auth = (str(me["username"]), str(issued["apiKey"]))
    idempotency_key = f"smoke-{os.getpid()}"

    unauthorized = client.get(f"{API}/api/v3/account", auth=(str(me["username"]), "wrong-key"))

    first_send = client.post(
        f"{API}/api/v3/sms/send",
        auth=v3_auth,
        headers={"Idempotency-Key": idempotency_key},
        json={"messages": [{"body": "v3 smoke", "customString": "order-1", "to": DELIVERS}]},
    )
    replayed_send = client.post(
        f"{API}/api/v3/sms/send",
        auth=v3_auth,
        headers={"Idempotency-Key": idempotency_key},
        json={"messages": [{"body": "v3 smoke", "customString": "order-1", "to": DELIVERS}]},
    )
    sent = first_send.json()
    message_id = sent["messages"][0]["messageId"]

    detail = client.get(f"{API}/api/v3/sms/{message_id}", auth=v3_auth).json()
    history = client.get(f"{API}/api/v3/sms/history", auth=v3_auth).json()
    in_history = any(row["messageId"] == message_id for row in history["messages"])
    balance = client.get(f"{API}/api/v3/account/balance", auth=v3_auth).json()

    rate_limited = next(
        (
            response
            for response in (
                client.get(f"{API}/api/v3/account/balance", auth=v3_auth) for _ in range(65)
            )
            if response.status_code == RATE_LIMITED_STATUS
        ),
        None,
    )

    return [
        check("v3 rejects the wrong key", unauthorized.status_code, 401),
        check(
            "v3 unauthorized envelope",
            unauthorized.json(),
            {"code": "UNAUTHORIZED", "message": "Invalid username or API key"},
        ),
        check("v3 send status", first_send.status_code, 201),
        check("v3 send custom string echoed", sent["messages"][0]["customString"], "order-1"),
        check(
            "v3 idempotent replay marked", replayed_send.headers.get("Idempotent-Replayed"), "true"
        ),
        check("v3 idempotent replay same body", replayed_send.json(), sent),
        check("v3 detail matches send", detail["messageId"], message_id),
        check("v3 message reaches history", in_history, expected=True),
        check(
            "v3 price has no currency symbol", "£" in sent["messages"][0]["price"], expected=False
        ),
        check("v3 balance has no currency symbol", "£" in balance["balance"], expected=False),
        check("v3 balance currency field", balance["currency"], "GBP"),
        check("v3 rate limit trips", rate_limited is not None, expected=True),
        check(
            "v3 rate limit retry-after present",
            "Retry-After" in rate_limited.headers if rate_limited else False,
            expected=True,
        ),
    ]


def analytics_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    sent = client.post(
        f"{API}/api/app/messages/send",
        json={"body": f"See {TRACKED_URL} for details", "shortenUrls": True, "to": [DELIVERS]},
        headers=auth,
    )
    sent.raise_for_status()

    history = client.get(f"{API}/api/app/messages", headers=auth).json()
    pattern = re.compile(r"https?://[^/\s]+/l/([a-z0-9]+)")
    matches = (pattern.search(row["body"]) for row in history["items"])
    match = next((found for found in matches if found is not None), None)
    code = match.group(1) if match else ""

    followed = client.get(f"{API}/l/{code}") if code else None
    missing = client.get(f"{API}/l/zzzzzzzzzz")

    return [
        check("shorten urls rewrites the tracked link", code != "", expected=True),
        check("redirect answers 302", followed.status_code if followed else None, 302),
        check(
            "redirect points at the original url",
            followed.headers.get("location") if followed else None,
            TRACKED_URL,
        ),
        check("an unknown code answers 404", missing.status_code, 404),
    ]


def billing_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    before = client.get(f"{API}/api/app/billing/summary", headers=auth).json()["balanceMicro"]
    packages = client.get(f"{API}/api/app/billing/packages?country=GB", headers=auth).json()

    created = client.post(
        f"{API}/api/app/billing/top-ups",
        json={"code": "BOOST_10", "kind": "BOOST"},
        headers=auth,
    ).json()
    checkout_path = httpx.URL(created["checkoutUrl"]).path
    paid = client.post(f"{API}{checkout_path}")

    status = client.get(f"{API}/api/app/billing/top-ups/{created['topUpId']}", headers=auth).json()
    after = client.get(f"{API}/api/app/billing/summary", headers=auth).json()["balanceMicro"]
    cards = client.get(f"{API}/api/app/billing/cards", headers=auth).json()

    general = client.put(
        f"{API}/api/app/billing/general",
        json={"mobile": "+447411972333", "name": "Smoke Co"},
        headers=auth,
    ).json()

    return [
        check("packages has a GB rate", packages["rateMicro"] > 0, expected=True),
        check("packages lists boosts", len(packages["boosts"]), 4),
        check("top-up checkout redirects", paid.status_code, 302),
        check("top-up status paid", status["status"], "PAID"),
        check("top-up credited amount", status["creditedMicro"], 10_000_000),
        check("balance credited by the top-up", after - before, 10_000_000),
        check("cards seeded by the fake gateway", len(cards), 2),
        check(
            "default card is the seed visa", any(card["isDefault"] for card in cards), expected=True
        ),
        check("general name updated", general["name"], "Smoke Co"),
        check("general mobile updated", general["mobile"], "+447411972333"),
    ]


def developer_checks(client: httpx.Client, auth: dict[str, str]) -> list[bool]:
    general = client.get(f"{API}/api/app/developer/general", headers=auth).json()
    logs = client.get(f"{API}/api/app/developer/logs", headers=auth).json()

    return [
        check("developer rate limit shown", general["rateLimitPerMinute"], 60),
        check("developer logs has tiles", "tiles" in logs, expected=True),
        check(
            "developer logs tile total covers api calls", logs["tiles"]["total"] > 0, expected=True
        ),
    ]


def wait_for_sent(client: httpx.Client, auth: dict[str, str], campaign_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + SCHEDULER_DEADLINE_SECONDS
    report: dict[str, Any] = {}
    while time.monotonic() < deadline:
        report = client.get(f"{API}/api/app/campaigns/{campaign_id}/report", headers=auth).json()
        if report["campaign"]["status"] != "SCHEDULED":
            counts = report["campaign"]["counts"]
            if counts["sent"] + counts["refused"] >= counts["recipients"]:
                return report
        time.sleep(POLL_SECONDS)

    return report


def main() -> int:
    with httpx.Client(timeout=10.0) as client:
        tokens = sign_in(client)
        auth = {"Authorization": f"Bearer {tokens['access_token']}"}

        session = client.post(
            f"{API}/api/app/session", json={"idToken": tokens["id_token"]}, headers=auth
        )
        session.raise_for_status()
        me = session.json()

        home = client.get(f"{API}/api/app/home", headers=auth).json()
        summary = client.get(f"{API}/api/app/billing/summary", headers=auth).json()
        senders = client.get(f"{API}/api/app/senders", headers=auth).json()

        shared = senders["senders"]["SHARED"]
        results = [
            check("username", me["username"], USER),
            check("role", me["role"], "OWNER"),
            check("trial balance", me["balanceMicro"], TRIAL_MICRO),
            check("trial days", me["trialDaysLeft"], 14),
            check("home balance", home["balanceMicro"], TRIAL_MICRO),
            check("can send", summary["canSend"], expected=True),
            check("shared senders", len(shared), 1),
            check("shared ready", shared[0]["status"] if shared else None, "READY"),
            check(
                "smart sender GB",
                senders["smart"].get("GB"),
                shared[0]["senderId"] if shared else None,
            ),
            *send_checks(client, auth),
            *campaign_checks(client, auth),
            *two_way_checks(client, auth),
            *v3_checks(client, auth, me),
            *developer_checks(client, auth),
            *billing_checks(client, auth),
            *analytics_checks(client, auth),
        ]

    sys.stdout.write("smoke: ok\n" if all(results) else "smoke: FAILED\n")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
