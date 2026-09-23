from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from txtlocal.shared.model import Model
from txtlocal.shared.money import Micro
from txtlocal.slices.messaging.model import Product

CODE_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
CODE_LENGTH = 10
MAX_CODE_ATTEMPTS = 8
NO_CAMPAIGN = ""

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
MAX_REPORTING_MONTHS = 4


class RollupFeed(StrEnum):
    CLICKS = "clicks"
    USAGE = "usage"


def is_valid_code(code: str) -> bool:
    return len(code) == CODE_LENGTH and all(char in CODE_ALPHABET for char in code)


@dataclass(frozen=True, slots=True)
class TrackedLink:
    account_id: str
    campaign_id: str
    clicks_total: int
    code: str
    created_at: datetime
    last_rollup: str | None
    url: str


@dataclass(frozen=True, slots=True)
class UsageLine:
    account_id: str
    cost_micro: Micro
    country: str
    day: str
    product: Product
    quantity: int
    sender_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class ClickDay:
    clicks: int
    code: str
    day: str


@dataclass(frozen=True, slots=True)
class RollupSummary:
    day: str
    discarded_clicks: int = 0
    discarded_lines: int = 0
    feeds: tuple[RollupFeed, ...] = ()
    link_rows: int = 0
    usage_rows: int = 0


class UsageTabRow(Model):
    cost_micro: Micro
    month: str
    product: Product
    quantity: int
    user_id: str


class UsageTabPage(Model):
    rows: list[UsageTabRow]


class ReportingQuery(Model):
    countries: list[str] = Field(default_factory=list)
    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE
    products: list[Product] = Field(default_factory=list)
    sender_ids: list[str] = Field(default_factory=list)
    since: date
    until: date
    user_ids: list[str] = Field(default_factory=list)


class ReportingRow(Model):
    country: str
    day: date
    price_micro: Micro
    product: Product
    quantity: int
    sender_id: str
    total_micro: Micro
    user_id: str


class ReportingPage(Model):
    page: int
    page_size: int
    rows: list[ReportingRow]
    total_results: int
