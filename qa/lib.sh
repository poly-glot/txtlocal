ACCOUNT="${ACCOUNT:-}"
FUNCTIONS="${FUNCTIONS:-txtlocal-api txtlocal-redirect txtlocal-stripe-webhook txtlocal-send-worker txtlocal-delivery-events txtlocal-inbound txtlocal-scheduler txtlocal-webhook-dispatch txtlocal-billing-charge txtlocal-billing-renewals txtlocal-rollup}"
TABLE="${TABLE:-aws-cloud}"

FAILURES=0

pass() {
    printf 'ok    %s\n' "$*"
}

note() {
    printf '      %s\n' "$*"
}

fail() {
    printf 'FAIL  %s\n' "$*" >&2
    FAILURES=$((FAILURES + 1))
}

die() {
    printf 'ERROR %s\n' "$*" >&2
    exit 2
}

assert_eq() {
    if [ "$1" = "$2" ]; then
        pass "$3"
        return 0
    fi

    fail "$3: expected [$1], got [$2]"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "$1 is required and is not on PATH"
}

discover_account() {
    require_command aws
    [ -n "$ACCOUNT" ] && return 0

    ACCOUNT=$(aws sts get-caller-identity --query Account --output text) || die "could not read the account id; pass --account"
    note "account $ACCOUNT"
}

finish() {
    if [ "$FAILURES" -ne 0 ]; then
        printf '\n%s: %d assertion(s) failed\n' "$(basename "$0")" "$FAILURES" >&2
        exit 1
    fi

    printf '\n%s: every assertion passed\n' "$(basename "$0")"
}
