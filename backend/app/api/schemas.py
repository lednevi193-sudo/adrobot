"""DTO HTTP-контракта (Pydantic). Это не доменные объекты: форма — для фронта, правила — в домене.

Аналог request/response-моделей контроллеров ASP.NET; FastAPI валидирует вход по ним
и строит OpenAPI (Swagger на /docs).
"""

from pydantic import BaseModel, Field

# ---------- запросы ----------


class CreateCampaignRequest(BaseModel):
    name: str = Field(examples=["promo"])
    geos: str = Field(examples=["MX,AU,RO"], description="ISO-коды стран через запятую")
    offer_id: int = Field(examples=[18813])


class FetchRequest(BaseModel):
    discard_drafts: bool = False  # True — пользователь подтвердил потерю черновика (FR-2.3a)


class AddOfferRequest(BaseModel):
    offer_id: int


class PinRequest(BaseModel):
    share: int | None = Field(default=None, description="Не задан — закрепить текущий вес")


# ---------- ответы ----------


class OfferDto(BaseModel):
    id: int
    name: str


class CampaignSummaryDto(BaseModel):
    id: int
    name: str


class DraftChangeDto(BaseModel):
    stream_id: int
    offer: OfferDto
    kind: str  # add | remove | pin | unpin | share
    share_before: int | None
    share_after: int | None


class StreamOfferView(BaseModel):
    id: int
    name: str
    status: str  # active | pending_add | pending_remove | removed
    share: int
    pinned: bool
    keitaro_share: int | None = Field(description="Вес в Keitaro; None — оффера в Keitaro нет (FR-2.9a)")


class StreamView(BaseModel):
    id: int
    name: str
    position: int
    editable: bool
    has_draft: bool
    can_cancel: bool = Field(
        description="Есть что отменить. has_draft без can_cancel — закреплённый вес разошёлся с Keitaro (FR-2.9a)"
    )
    push_blocker: str | None = Field(description="Почему Push сейчас невозможен (FR-2.12) или None")
    offers: list[StreamOfferView]


class CampaignView(BaseModel):
    id: int
    name: str
    alias: str
    tracker_url: str | None
    is_ours: bool
    has_draft: bool
    version: int = Field(description="Версия для If-Match в командах: защита от правки устаревшей вкладки")
    streams: list[StreamView]


class OpenCampaignResponse(BaseModel):
    campaign: CampaignView
    keitaro_changes: list[str] = Field(
        description="Что поменяли прямо в Keitaro, пока в обёртке лежит черновик. Пусто — синхронизировано"
    )


class CancelResponse(BaseModel):
    campaign: CampaignView
    cancelled: list[DraftChangeDto]


class ErrorResponse(BaseModel):
    code: str
    message: str
