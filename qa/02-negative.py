import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from lib import assert_eq, base_parser, finish

USAGE = """
qa/02-negative.py checks refusals that only mean something over a real socket: wrong or missing
operator secrets, a route hit with the wrong HTTP verb, and an unauthenticated dashboard call. A
pytest TestClient would answer these the same way in principle, but this is the same check with zero
trust placed in that principle.
"""


def main() -> int:
    args = base_parser(USAGE).parse_args()

    with httpx.Client(timeout=10.0) as client:
        no_secret = client.post(
            f"{args.base_url}/api/operator/accounts/x/websites/example.test/approve"
        )
        assert_eq(no_secret.status_code, 401, "operator route refuses a missing secret")

        wrong_secret = client.post(
            f"{args.base_url}/api/operator/accounts/x/websites/example.test/approve",
            headers={"X-Operator-Secret": "definitely-wrong"},
        )
        assert_eq(wrong_secret.status_code, 401, "operator route refuses a wrong secret")
        assert_eq(
            wrong_secret.json(),
            {"code": "unauthorized", "message": "Invalid operator secret"},
            "operator refusal body is the fixed sentence",
        )

        not_found = client.post(
            f"{args.base_url}/api/operator/accounts/x/websites/example.test/approve",
            headers={"X-Operator-Secret": args.operator_secret},
        )
        assert_eq(not_found.status_code, 404, "the right secret still 404s a real not-found")

        wrong_verb = client.get(f"{args.base_url}/api/app/session")
        assert_eq(
            wrong_verb.status_code,
            404,
            "the wrong HTTP verb answers 404, same as an unknown route: 405 is not in the error "
            "contract in CLAUDE.md section 4, and this app never emits one",
        )

        unauthenticated = client.get(f"{args.base_url}/api/app/senders")
        assert_eq(unauthenticated.status_code, 401, "a dashboard route refuses no bearer token")

    return finish("02-negative")


if __name__ == "__main__":
    raise SystemExit(main())
