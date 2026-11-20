"""Сохранённый захват публикации: владелец, поток и время начала."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.common.ids import StreamId


@dataclass(frozen=True, slots=True)
class PushLease:
    stream_id: StreamId
    started_at: datetime
    token: str

    def is_live(self, now: datetime, ttl_seconds: float) -> bool:
        return (now - self.started_at).total_seconds() < ttl_seconds
