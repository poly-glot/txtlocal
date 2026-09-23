from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from txtlocal.slices.billing.service import BillingService
    from txtlocal.slices.campaigns.repo import CampaignsDynamoRepo, CampaignsRepo
    from txtlocal.slices.campaigns.service import (
        Billing,
        Contacts,
        Quoting,
        SenderResolution,
        Settings,
    )
    from txtlocal.slices.campaigns.tests.fakes import FakeContacts, InMemoryCampaignsRepo
    from txtlocal.slices.contacts.service import ContactsService
    from txtlocal.slices.identity.service import IdentityService
    from txtlocal.slices.messaging.service import MessagingService
    from txtlocal.slices.senders.service import SendersService


def _fits_billing(service: BillingService) -> Billing:
    return service


def _fits_contacts(service: ContactsService) -> Contacts:
    return service


def _fits_contacts_in_memory(service: FakeContacts) -> Contacts:
    return service


def _fits_quoting(service: MessagingService) -> Quoting:
    return service


def _fits_repo(repo: CampaignsDynamoRepo) -> CampaignsRepo:
    return repo


def _fits_repo_in_memory(repo: InMemoryCampaignsRepo) -> CampaignsRepo:
    return repo


def _fits_senders(service: SendersService) -> SenderResolution:
    return service


def _fits_settings(service: IdentityService) -> Settings:
    return service
