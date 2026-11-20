"""Список кампаний редактора (FR-2.1): по умолчанию только наши, переключателем — все."""

from app.application.ports import CampaignSummary, KeitaroGateway
from app.domain.campaigns import is_our_name


def list_campaigns(keitaro: KeitaroGateway, *, prefix: str, only_ours: bool = True) -> list[CampaignSummary]:
    campaigns = keitaro.list_campaigns()
    if only_ours:
        campaigns = [c for c in campaigns if is_our_name(c.name, prefix)]
    return sorted(campaigns, key=lambda c: c.id, reverse=True)  # новые первыми
