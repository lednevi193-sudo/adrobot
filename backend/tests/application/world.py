"""Общий «мир» тестов сценариев: фейки всех портов и тестовые офферы."""

from dataclasses import dataclass

from app.domain.common.ids import OfferId
from app.domain.offers.offer_ref import OfferRef
from tests.fakes.campaign_repository import FakeUnitOfWork, InMemoryCampaignRepository
from tests.fakes.keitaro_gateway import FakeKeitaroGateway

PREFIX = "test_x_"
FLEXACIL = OfferRef(OfferId(18813), "18813 Flexacil")
OTHER = OfferRef(OfferId(25327), "25327 Other")


@dataclass
class World:
    repo: InMemoryCampaignRepository
    uow: FakeUnitOfWork
    keitaro: FakeKeitaroGateway


def make_world() -> World:
    repo = InMemoryCampaignRepository()
    return World(repo, FakeUnitOfWork(repo), FakeKeitaroGateway(offers=[FLEXACIL, OTHER]))
