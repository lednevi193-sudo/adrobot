"""Anti-Corruption Layer к Keitaro: транспорт, перевод JSON <-> домен, реализация порта."""

from app.config import Settings
from app.infrastructure.keitaro.client import KeitaroClient
from app.infrastructure.keitaro.gateway import HttpKeitaroGateway
from app.infrastructure.keitaro.to_keitaro import CampaignPlacement


def build_keitaro_gateway(settings: Settings) -> HttpKeitaroGateway:
    """Сборка из настроек — сюда смотрит DI (Depends) на шаге API."""
    placement = CampaignPlacement(
        domain_id=settings.keitaro_domain_id,
        group_id=settings.keitaro_group_id,
        traffic_source_id=settings.keitaro_traffic_source_id,
    )
    return HttpKeitaroGateway(KeitaroClient.from_settings(settings), placement, offers_ttl=settings.keitaro_offers_ttl)


__all__ = ["CampaignPlacement", "HttpKeitaroGateway", "KeitaroClient", "build_keitaro_gateway"]
