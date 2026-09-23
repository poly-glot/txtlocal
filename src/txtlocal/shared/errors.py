INTERNAL_MESSAGE = "Something went wrong on our side"
UPSTREAM_MESSAGE = "A service we depend on is unavailable"


class AppError(Exception):
    code = "internal"
    status = 500

    def public_message(self) -> str:
        return str(self)


class BadRequest(AppError):
    code = "bad_request"
    status = 400


class Unauthorized(AppError):
    code = "unauthorized"
    status = 401


class PaymentRequired(AppError):
    code = "payment_required"
    status = 402


class Forbidden(AppError):
    code = "forbidden"
    status = 403


class NotFound(AppError):
    code = "not_found"
    status = 404


class Conflict(AppError):
    code = "conflict"
    status = 409


class RateLimited(AppError):
    code = "rate_limited"
    status = 429

    def __init__(self, *args: object, retry_after: int | None = None) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


class Internal(AppError):
    code = "internal"
    status = 500

    def public_message(self) -> str:
        return INTERNAL_MESSAGE


class Upstream(AppError):
    code = "upstream"
    status = 502

    def public_message(self) -> str:
        return UPSTREAM_MESSAGE


class GatewayTimeout(AppError):
    code = "gateway_timeout"
    status = 504
