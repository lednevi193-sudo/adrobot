"""Порты — интерфейсы, которые слой приложения ждёт от инфраструктуры. Один порт — один модуль."""

from app.application.ports.campaign_repository import CampaignRepository
from app.application.ports.keitaro_gateway import CampaignSummary, KeitaroGateway

__all__ = ["CampaignRepository", "CampaignSummary", "KeitaroGateway"]
