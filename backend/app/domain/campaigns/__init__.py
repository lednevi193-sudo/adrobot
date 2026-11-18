"""Агрегат «Кампания»: публичный API пакета.

Снаружи импортируйте отсюда (`from app.domain.campaigns import Campaign`),
а не из внутренних модулей — их раскладка может меняться.
"""

from app.domain.campaigns.model.assignment import (
    AssignmentStatus,
    DesiredState,
    OfferAssignment,
    PublishedState,
)
from app.domain.campaigns.creation.blueprint import (
    CampaignBlueprint,
    GeoRedirectStreamSpec,
    OffersStreamSpec,
)
from app.domain.campaigns.model.campaign import Campaign
from app.domain.campaigns.services.changes import Change, ChangeKind
from app.domain.campaigns.sync.snapshots import KeitaroCampaign, KeitaroStream, PublishedOffer
from app.domain.campaigns.model.stream import Stream, StreamKind

__all__ = [
    "AssignmentStatus",
    "Campaign",
    "CampaignBlueprint",
    "Change",
    "ChangeKind",
    "DesiredState",
    "GeoRedirectStreamSpec",
    "KeitaroCampaign",
    "KeitaroStream",
    "OfferAssignment",
    "OffersStreamSpec",
    "PublishedOffer",
    "PublishedState",
    "Stream",
    "StreamKind",
]
