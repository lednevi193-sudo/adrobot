from datetime import UTC, datetime

from app.application.errors import PushInProgress
from app.domain.campaigns import Campaign
from app.domain.common.ids import StreamId

DEFAULT_LEASE_SECONDS = 300.0


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_available(
    campaign: Campaign, stream_id: StreamId | None = None, *,
    lease_seconds: float = DEFAULT_LEASE_SECONDS, now: datetime | None = None,
) -> None:
    lease = campaign.push_in_progress
    if lease is None:
        return
    if not lease.is_live(now if now is not None else utc_now(), lease_seconds):
        campaign.push_in_progress = None
        return
    if stream_id is None or lease.stream_id == stream_id:
        raise PushInProgress(lease.stream_id)
