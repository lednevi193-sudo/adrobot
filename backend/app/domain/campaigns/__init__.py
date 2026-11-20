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
from app.domain.campaigns.model.campaign import Campaign, is_our_name
from app.domain.campaigns.model.draft import DraftChange, DraftChangeKind
from app.domain.campaigns.sync.snapshots import KeitaroCampaign, KeitaroStream, PublishedOffer
from app.domain.campaigns.model.stream import Stream, StreamKind
from app.domain.campaigns.model.push import PushLease
from app.domain.campaigns.sync.keitaro_changes import changes_in_keitaro

__all__ = [
    "AssignmentStatus",
    "Campaign",
    "CampaignBlueprint",
    "DraftChange",
    "DraftChangeKind",
    "DesiredState",
    "GeoRedirectStreamSpec",
    "KeitaroCampaign",
    "KeitaroStream",
    "OfferAssignment",
    "OffersStreamSpec",
    "PublishedOffer",
    "PublishedState",
    "PushLease",
    "Stream",
    "StreamKind",
    "changes_in_keitaro",
    "is_our_name",
]
