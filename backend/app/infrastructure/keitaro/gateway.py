"""HttpKeitaroGateway — реализация порта KeitaroGateway поверх Admin API (Anti-Corruption Layer).

Собирает из нескольких эндпоинтов Keitaro то, что домен понимает как одно целое:
кампания + потоки + имена офферов = снимок KeitaroCampaign.
"""

import secrets
import string
from collections.abc import Callable, Sequence
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.application.errors import CampaignNotFound, KeitaroError
from app.application.ports import CampaignSummary
from app.domain.campaigns import (
    GeoRedirectStreamSpec,
    KeitaroCampaign,
    OffersStreamSpec,
    PublishedOffer,
)
from app.domain.common.ids import CampaignId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.keitaro import from_keitaro, to_keitaro
from app.infrastructure.keitaro.client import Json, KeitaroClient
from app.infrastructure.keitaro.schemas import (
    KeitaroCampaignJson,
    KeitaroOfferJson,
    KeitaroStreamJson,
)
from app.infrastructure.keitaro.to_keitaro import CampaignPlacement

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

_ALIAS_ALPHABET = string.ascii_letters + string.digits
_ALIAS_LENGTH = 8  # как у алиасов, которые генерирует сам Keitaro (VrfMdGff)


def random_alias() -> str:
    return "".join(secrets.choice(_ALIAS_ALPHABET) for _ in range(_ALIAS_LENGTH))


class HttpKeitaroGateway:
    def __init__(
        self,
        client: KeitaroClient,
        placement: CampaignPlacement,
        alias_factory: Callable[[], str] = random_alias,
    ) -> None:
        self._client = client
        self._placement = placement
        self._alias_factory = alias_factory

    # ---------- чтение ----------

    def list_campaigns(self) -> list[CampaignSummary]:
        campaigns = _parse_list(KeitaroCampaignJson, self._client.get("/campaigns"))
        return [from_keitaro.campaign_summary(c) for c in campaigns]

    def get_campaign(self, campaign_id: CampaignId) -> KeitaroCampaign:
        try:
            raw = self._client.get(f"/campaigns/{campaign_id}")
        except KeitaroError as e:
            if e.status == 404:
                raise CampaignNotFound(campaign_id) from e
            raise
        campaign = _parse(KeitaroCampaignJson, raw)
        streams = _parse_list(KeitaroStreamJson, self._client.get(f"/campaigns/{campaign_id}/streams"))
        return from_keitaro.campaign_snapshot(campaign, streams, self._offer_names())

    def list_active_offers(self) -> list[OfferRef]:
        return [from_keitaro.offer_ref(o) for o in self._offers() if o.state == from_keitaro.ACTIVE]

    # ---------- создаватор ----------

    def create_campaign(self, name: str) -> CampaignId:
        body = to_keitaro.campaign_body(name, self._alias_factory(), self._placement)
        created = _parse(KeitaroCampaignJson, self._client.post("/campaigns", body))
        return CampaignId(created.id)

    def create_geo_stream(self, campaign_id: CampaignId, spec: GeoRedirectStreamSpec) -> None:
        self._client.post("/streams", to_keitaro.geo_stream_body(campaign_id, spec))

    def create_offers_stream(self, campaign_id: CampaignId, spec: OffersStreamSpec) -> None:
        self._client.post("/streams", to_keitaro.offers_stream_body(campaign_id, spec))

    def delete_campaign(self, campaign_id: CampaignId) -> None:
        self._client.delete(f"/campaigns/{campaign_id}")

    # ---------- редактор ----------

    def publish_offers(self, stream_id: StreamId, offers: Sequence[PublishedOffer]) -> None:
        """PUT заменяет offers[] целиком. Выключенные в Keitaro офферы обёртка не показывает
        и не трогает — их читаем прямо перед PUT и отправляем обратно как есть, иначе Push
        молча удалил бы их из потока."""
        current = _parse(KeitaroStreamJson, self._client.get(f"/streams/{stream_id}"))
        self._client.put(f"/streams/{stream_id}", to_keitaro.stream_offers_body(offers, current.offers))

    # ---------- внутреннее ----------

    def _offers(self) -> list[KeitaroOfferJson]:
        return _parse_list(KeitaroOfferJson, self._client.get("/offers"))

    def _offer_names(self) -> dict[int, str]:
        return {o.id: o.name for o in self._offers()}


def _parse(model: type[M], data: Json) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise KeitaroError(f"Неожиданный формат ответа Keitaro ({model.__name__}): {e.error_count()} ошибок") from e


def _parse_list(model: type[M], data: Json) -> list[M]:
    try:
        return TypeAdapter(list[model]).validate_python(data)  # type: ignore[valid-type]
    except ValidationError as e:
        raise KeitaroError(f"Неожиданный формат ответа Keitaro (список {model.__name__}): {e.error_count()} ошибок") from e
