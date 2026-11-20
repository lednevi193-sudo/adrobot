"""Справочник офферов Keitaro: автодополнение (FR-1.2) и поиск выбранного по ID."""

from app.application.errors import OfferNotFound
from app.application.ports import KeitaroGateway
from app.domain.common.ids import OfferId
from app.domain.offers.offer_ref import OfferRef

SEARCH_LIMIT = 20


def search_offers(keitaro: KeitaroGateway, query: str) -> list[OfferRef]:
    """По ID и подстроке названия без учёта регистра; только активные; не больше 20."""
    q = query.strip().casefold()
    found = [o for o in keitaro.list_active_offers() if not q or q in str(o.id) or q in o.name.casefold()]
    return found[:SEARCH_LIMIT]


def find_offer(keitaro: KeitaroGateway, offer_id: OfferId) -> OfferRef:
    """Оффер, выбранный в автодополнении. Имя берём из Keitaro, а не со слов клиента."""
    offer = next((o for o in keitaro.list_active_offers() if o.id == offer_id), None)
    if offer is None:
        raise OfferNotFound(offer_id)
    return offer
