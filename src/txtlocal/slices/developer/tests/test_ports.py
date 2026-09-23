from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from txtlocal.slices.billing.model import Balance
    from txtlocal.slices.billing.service import BillingService
    from txtlocal.slices.campaigns.service import CampaignsService
    from txtlocal.slices.contacts.service import ContactsService
    from txtlocal.slices.developer.repo import (
        DeveloperDynamoRepo,
        DeveloperRepo,
        InsightsLogQueries,
        LocalLogQueries,
        LogQueries,
    )
    from txtlocal.slices.developer.service import (
        AccountLookup,
        BalanceView,
        Billing,
        CampaignLanding,
        Contacts,
        Messaging,
        Senders,
        Settings,
    )
    from txtlocal.slices.identity.service import IdentityService
    from txtlocal.slices.messaging.service import MessagingService
    from txtlocal.slices.senders.service import SendersService


def _fits_account_lookup(service: IdentityService) -> AccountLookup:
    return service


def _fits_settings(service: IdentityService) -> Settings:
    return service


def _fits_billing(service: BillingService) -> Billing:
    return service


def _fits_balance_view(balance: Balance) -> BalanceView:
    return balance


def _fits_campaign_landing(service: CampaignsService) -> CampaignLanding:
    return service


def _fits_contacts(service: ContactsService) -> Contacts:
    return service


def _fits_messaging(service: MessagingService) -> Messaging:
    return service


def _fits_senders(service: SendersService) -> Senders:
    return service


def _fits_repo(repo: DeveloperDynamoRepo) -> DeveloperRepo:
    return repo


def _fits_insights_log_queries(queries: InsightsLogQueries) -> LogQueries:
    return queries


def _fits_local_log_queries(queries: LocalLogQueries) -> LogQueries:
    return queries
