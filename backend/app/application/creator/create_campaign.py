"""Создаватор (FR-1.3 – FR-1.7): кампания и два потока в Keitaro, затем — в нашу БД.

Распределённой транзакции между Keitaro и Postgres нет, поэтому целостность держит
компенсация (≈ шаг саги): любой сбой после создания кампании — перенос её в архив Keitaro.
"""

from app.application.errors import CampaignCreationFailed
from app.application.offers.search_offers import find_offer
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign, CampaignBlueprint
from app.domain.common.ids import CampaignId, OfferId


def create_campaign(
    repo: CampaignRepository,
    keitaro: KeitaroGateway,
    uow: UnitOfWork,
    *,
    prefix: str,
    name: str,
    geos: str,
    offer_id: OfferId,
) -> Campaign:
    # 1. Всё, что можно проверить без записи в Keitaro (FR-1.8: ошибки формы не доходят до Keitaro)
    offer = find_offer(keitaro, offer_id)
    blueprint = CampaignBlueprint.create(prefix, name, geos, offer)

    # 2. Первая запись. Упала — откатывать нечего, ошибка Keitaro уходит пользователю как есть
    campaign_id = keitaro.create_campaign(blueprint.name)

    # 3. Остальное — под компенсацией
    try:
        keitaro.create_geo_stream(campaign_id, blueprint.geo_stream)
        keitaro.create_offers_stream(campaign_id, blueprint.offers_stream)
        campaign = Campaign.from_keitaro(keitaro.get_campaign(campaign_id))
        repo.add(campaign)
        uow.commit()
    except Exception as e:  # noqa: BLE001 — откатываем при любом сбое, затем пробрасываем
        uow.rollback()
        raise CampaignCreationFailed(_reason(e), compensated=_compensate(keitaro, campaign_id)) from e
    return campaign


def _compensate(keitaro: KeitaroGateway, campaign_id: CampaignId) -> bool:
    try:
        keitaro.delete_campaign(campaign_id)
    except Exception:  # noqa: BLE001 — сообщаем пользователю, что убрать руками
        return False
    return True


def _reason(e: Exception) -> str:
    return getattr(e, "message", None) or str(e) or type(e).__name__
