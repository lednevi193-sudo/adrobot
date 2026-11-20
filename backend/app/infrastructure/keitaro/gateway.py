"""HttpKeitaroGateway — реализация порта KeitaroGateway поверх Admin API (Anti-Corruption Layer).

Собирает из нескольких эндпоинтов Keitaro то, что домен понимает как одно целое:
кампания + потоки + имена офферов = снимок KeitaroCampaign.
"""

import secrets
import string
from collections.abc import Callable, Sequence
from typing import TypeVar
from threading import Lock
from time import monotonic

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.application.errors import CampaignNotFound, KeitaroError
from app.application.ports import CampaignSummary, InactiveStreamOffer, KeitaroStreamState
from app.domain.campaigns.errors import StreamNotInCampaign
from app.domain.campaigns import (
    GeoRedirectStreamSpec,
    KeitaroCampaign,
    OffersStreamSpec,
    PublishedOffer,
)
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.keitaro import from_keitaro, to_keitaro
from app.infrastructure.keitaro.client import Json, KeitaroClient
from app.infrastructure.keitaro.schemas import (
    KeitaroCampaignJson,
    KeitaroOfferJson,
    KeitaroStreamJson,
    KeitaroStreamOfferJson,
    KeitaroCampaignNameJson,
    KeitaroStreamStateJson,
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
        *,
        offers_ttl: float = 60.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._client = client
        self._placement = placement
        self._alias_factory = alias_factory
        self._offers_ttl = offers_ttl
        self._clock = clock
        self._offers_lock = Lock()
        self._offers_cache: tuple[KeitaroOfferJson, ...] | None = None
        self._offers_expires_at = 0.0

    # ---------- чтение ----------

    def list_campaigns(self) -> list[CampaignSummary]:
        campaigns = _parse_list(KeitaroCampaignJson, self._client.get("/campaigns"))
        return [from_keitaro.campaign_summary(c) for c in campaigns]

    def get_campaign(self, campaign_id: CampaignId) -> KeitaroCampaign:
        campaign = _parse(KeitaroCampaignJson, self._campaign_data(campaign_id))
        streams = _parse_list(KeitaroStreamJson, self._client.get(f"/campaigns/{campaign_id}/streams"))
        return from_keitaro.campaign_snapshot(campaign, streams, self._offer_names())

    def _campaign_data(self, campaign_id: CampaignId) -> Json:
        try:
            return self._client.get(f"/campaigns/{campaign_id}")
        except KeitaroError as e:
            if e.status == 404:
                raise CampaignNotFound(campaign_id) from e
            raise

    def get_campaign_name(self, campaign_id: CampaignId) -> str:
        return _parse(KeitaroCampaignNameJson, self._campaign_data(campaign_id)).name

    def get_stream(self, stream_id: StreamId) -> KeitaroStreamState:
        try:
            raw = self._client.get(f"/streams/{stream_id}")
        except KeitaroError as error:
            if error.status == 404:
                raise StreamNotInCampaign(stream_id) from error
            raise
        return _stream_state(stream_id, raw)

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

    def publish_offers(
        self, stream_id: StreamId, offers: Sequence[PublishedOffer], *, current: KeitaroStreamState | None = None,
    ) -> KeitaroStreamState:
        """PUT заменяет offers[] целиком. Выключенные в Keitaro офферы обёртка не показывает
        и не трогает — их читаем прямо перед PUT и отправляем обратно как есть, иначе Push
        молча удалил бы их из потока.

        Ответ PUT — поток в том виде, в каком Keitaro его сохранил, а не эхо запроса. Проверено
        на стенде 20.11.2026: два одинаковых оффера в запросе -> одна запись и в ответе PUT,
        и в последующем GET. Поэтому сверка Push идёт по ответу PUT, без отдельного GET.
        """
        current = current if current is not None else self.get_stream(stream_id)
        if current.id != stream_id:
            raise StreamNotInCampaign(stream_id)
        inactive = [KeitaroStreamOfferJson(offer_id=o.offer_id, share=o.share, state=o.state) for o in current.inactive_offers]
        saved = self._client.put(f"/streams/{stream_id}", to_keitaro.stream_offers_body(offers, inactive))
        return _stream_state(stream_id, saved)

    # ---------- внутреннее ----------

    def _offers(self) -> tuple[KeitaroOfferJson, ...]:
        with self._offers_lock:
            if self._offers_cache is None or self._clock() >= self._offers_expires_at:
                loaded = _parse_list(KeitaroOfferJson, self._client.get("/offers"))
                self._offers_cache = tuple(loaded)
                self._offers_expires_at = self._clock() + self._offers_ttl
            return self._offers_cache

    def _offer_names(self) -> dict[int, str]:
        return {o.id: o.name for o in self._offers()}


def _stream_state(stream_id: StreamId, raw: Json) -> KeitaroStreamState:
    """Ответ GET или PUT /streams/{id} -> снимок одного потока: активные офферы и неактивные строки."""
    stream = _parse(KeitaroStreamStateJson, raw)
    if stream.state == from_keitaro.DELETED:
        raise StreamNotInCampaign(stream_id)
    if stream.id != stream_id:
        raise KeitaroError("Keitaro вернул другой ID потока")
    return KeitaroStreamState(
        StreamId(stream.id), CampaignId(stream.campaign_id),
        tuple(PublishedOffer(OfferRef(OfferId(o.offer_id), ""), o.share) for o in stream.offers if o.state == from_keitaro.ACTIVE),
        tuple(InactiveStreamOffer(OfferId(o.offer_id), o.share, o.state) for o in stream.offers if o.state != from_keitaro.ACTIVE),
    )


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
