"""Список кампаний редактора (FR-2.1): по умолчанию только наши, переключателем — все.

Наши — из нашей БД, без обращения к Keitaro: список открывается мгновенно.
Цена: кампания с нашим префиксом, созданная прямо в Keitaro, появится здесь
только после того, как её откроют по ID; свежесть деталей проверяет open_campaign.
Все — из Keitaro: чужие кампании живут только там.
"""

from app.application.ports import CampaignRepository, CampaignSummary, KeitaroGateway
from app.domain.campaigns import is_our_name


def list_campaigns(
    repo: CampaignRepository, keitaro: KeitaroGateway, *, prefix: str, only_ours: bool = True
) -> list[CampaignSummary]:
    if only_ours:
        campaigns = [CampaignSummary(c.id, c.name) for c in repo.list() if is_our_name(c.name, prefix)]
    else:
        campaigns = keitaro.list_campaigns()
    return sorted(campaigns, key=lambda c: c.id, reverse=True)  # новые первыми
