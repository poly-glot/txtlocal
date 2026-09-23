from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from txtlocal.shared.model import Model


class Role(StrEnum):
    OWNER = "OWNER"
    SUB = "SUB"


class TokenUse(StrEnum):
    ACCESS = "access"
    ID = "id"


class UnicodeMode(StrEnum):
    AUTODETECT = "AUTODETECT"
    GSM_ONLY = "GSM_ONLY"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    INVITED = "INVITED"


@dataclass(frozen=True, slots=True)
class Principal:
    account_id: str
    role: Role
    user_id: str
    username: str


class MessagingSettings(Model):
    default_country: str = "GB"
    max_parts: int = 8
    show_business_name: bool = True
    show_own_number: bool = True
    unicode_mode: UnicodeMode = UnicodeMode.AUTODETECT


class Claims(Model):
    email: str | None = None
    email_verified: bool = False
    sub: str


class Account(Model):
    account_id: str
    balance_micro: int = 0
    created_at: datetime
    email: str
    has_topped_up: bool = False
    mobile: str | None = None
    name: str
    pricing_country: str = "GB"
    settings: MessagingSettings = MessagingSettings()
    timezone: str = "Europe/London"


class User(Model):
    account_id: str
    api_key_hash: str
    api_key_issued_at: datetime
    api_key_prefix: str
    cognito_sub: str | None = None
    created_at: datetime
    email_verified: bool = False
    first_name: str = ""
    last_name: str = ""
    notes: str | None = None
    phone: str | None = None
    role: Role
    status: UserStatus
    user_id: str
    username: str


class SubPointer(Model):
    account_id: str
    created_at: datetime
    sub: str
    user_id: str


class SessionRequest(Model):
    id_token: str


class Profile(Model):
    first_name: str
    last_name: str
    phone: str | None = None
    username: str


class ProfileUpdate(Model):
    first_name: str
    last_name: str
    phone: str | None = None


class AccountSettings(Model):
    default_country: str
    name: str
    timezone: str


class MeView(Model):
    account_id: str
    account_name: str
    balance_micro: int
    can_send: bool
    default_country: str
    first_name: str
    has_topped_up: bool
    last_name: str
    phone: str | None = None
    role: Role
    trial_days_left: int
    trial_ends_at: datetime | None
    user_id: str
    username: str


class HomeView(Model):
    balance_micro: int
    can_send: bool
    email_verified: bool
    first_name: str
    last_name: str
    number_verified: bool
    trial_days_left: int


class UserRow(Model):
    api_key_prefix: str
    created_at: datetime
    first_name: str
    last_name: str
    notes: str | None = None
    phone: str | None = None
    role: Role
    status: UserStatus
    user_id: str
    username: str


class CreateUser(Model):
    first_name: str = ""
    last_name: str = ""
    notes: str | None = None
    phone: str | None = None
    username: str


class UserUpdate(Model):
    notes: str | None = None
    phone: str | None = None
    status: UserStatus | None = None


class CreatedUser(Model):
    api_key: str
    user: UserRow


class IssuedKey(Model):
    api_key: str
    api_key_prefix: str
    user_id: str
