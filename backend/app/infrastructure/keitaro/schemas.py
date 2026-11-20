"""Форма ответов Keitaro — только поля, которые нужны обёртке.

extra="ignore": у Keitaro десятки полей (cookies_ttl, postbacks, …), и новые
не должны ломать чтение. Это контракт «что мы читаем», а не полная схема API.
"""

from pydantic import BaseModel, ConfigDict

ACTIVE = "active"  # state потока/оффера: участвует в работе
DELETED = "deleted"  # state потока: в архиве Keitaro


class _KeitaroModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class KeitaroCampaignJson(_KeitaroModel):
    id: int
    name: str
    alias: str
    domain: str | None = None  # полный URL домена, например "https://kylovoa.com/"
    state: str = "active"


class KeitaroStreamOfferJson(_KeitaroModel):
    offer_id: int
    share: int
    state: str = "active"


class KeitaroStreamJson(_KeitaroModel):
    id: int
    name: str
    position: int
    state: str = "active"
    offers: list[KeitaroStreamOfferJson] = []


class KeitaroOfferJson(_KeitaroModel):
    id: int
    name: str
    state: str = "active"
