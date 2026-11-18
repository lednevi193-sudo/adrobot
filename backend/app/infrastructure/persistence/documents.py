"""Схема JSONB-документа с потоками кампании.

Pydantic здесь — контракт формата хранения: при чтении документ валидируется,
поэтому битые или устаревшие данные падают с понятной ошибкой, а не где-то в домене.
При смене формата — повысить SCHEMA_VERSION и научить загрузку поднимать старые версии.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 1


class _Doc(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DesiredDoc(_Doc):
    included: bool
    share: int
    pinned: bool


class PublishedDoc(_Doc):
    present: bool
    share: int
    pinned: bool


class AssignmentDoc(_Doc):
    offer_id: int
    offer_name: str
    seq: int
    desired: DesiredDoc
    published: PublishedDoc | None


class StreamDoc(_Doc):
    id: int
    name: str
    position: int
    kind: Literal["offers", "opaque"]
    assignments: list[AssignmentDoc]


class StreamsDocument(_Doc):
    schema_version: Literal[1] = SCHEMA_VERSION
    streams: list[StreamDoc]
