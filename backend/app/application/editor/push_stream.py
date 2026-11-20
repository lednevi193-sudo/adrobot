"""Push: короткий захват в БД, Keitaro без транзакции, короткая фиксация результата."""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from uuid import uuid4

from app.application.editor.loading import load_campaign
from app.application.editor.push_state import DEFAULT_LEASE_SECONDS, ensure_available, utc_now
from app.application.errors import ConcurrencyConflict, NotOurCampaign, PushNotConfirmed, StreamChangedInKeitaro
from app.application.ports import CampaignRepository, KeitaroGateway, KeitaroStreamState, UnitOfWork
from app.domain.campaigns import Campaign, PublishedOffer, PushLease, is_our_name
from app.domain.campaigns.errors import StreamNotInCampaign
from app.domain.common.errors import DomainError
from app.domain.common.ids import CampaignId, StreamId

logger = logging.getLogger(__name__)


def push_stream(
    repo: CampaignRepository,
    keitaro: KeitaroGateway,
    uow: UnitOfWork,
    campaign_id: CampaignId,
    stream_id: StreamId,
    *,
    prefix: str,
    expected_version: int | None = None,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    request_timeout: float = 20.0,
    clock: Callable[[], datetime] = utc_now,
    overwrite_keitaro_changes: bool = False,
) -> Campaign:
    """overwrite_keitaro_changes=True — пользователь видел StreamChangedInKeitaro и решил
    опубликовать черновик поверх правок в Keitaro. Иначе выбор один: Fetch, а он отбросит черновик."""
    # 1. Версия и захват проверяются до первого HTTP-запроса.
    campaign = load_campaign(repo, campaign_id, expected_version)
    ensure_available(campaign, lease_seconds=lease_seconds, now=clock())
    if not campaign.is_ours(prefix):
        raise NotOurCampaign(campaign_id)
    offers = campaign.offers_to_publish(stream_id)
    # Что лежало в Keitaro при последнем Fetch или Push: с этим сравниваем поток перед записью.
    seen = {a.offer.id: a.published.share for a in campaign.stream(stream_id).assignments if a.is_published and a.published}
    lease = PushLease(stream_id, clock(), uuid4().hex)
    campaign.push_in_progress = lease
    try:
        repo.save(campaign)
        uow.commit()  # соединение возвращено в пул до обращения к Keitaro
    except Exception:
        uow.rollback()
        raise

    try:
        # 2. Никаких чтений БД или открытой транзакции во время HTTP.
        # Временная страховка для тестового стенда: кампанию могли переименовать в Keitaro
        # после последнего Fetch. В боевой версии этот запрос убрать и проверять префикс
        # по названию из нашей БД (campaign.is_ours) — минус запрос на каждый Push.
        if not is_our_name(keitaro.get_campaign_name(campaign_id), prefix):
            raise NotOurCampaign(campaign_id)
        current = keitaro.get_stream(stream_id)
        if current.campaign_id != campaign_id:
            raise StreamNotInCampaign(stream_id)
        # Keitaro не умеет «записать, только если не изменилось», поэтому сравниваем сами:
        # поток поменяли руками после Fetch — не затираем правку. Окно между этим GET и PUT остаётся.
        if not overwrite_keitaro_changes and (changed := _changes_since_fetch(seen, current)):
            raise StreamChangedInKeitaro(stream_id, changed)
        # Задержанное чтение не даёт прежнему владельцу права на поздний PUT.
        # Оставляем запас четырёх HTTP-таймаутов на запись и независимую сверку.
        if not lease.is_live(clock() + timedelta(seconds=4 * request_timeout), lease_seconds):
            raise ConcurrencyConflict(campaign_id)
        keitaro.publish_offers(stream_id, offers, current=current)
        # Если проверка на стенде подтвердит, что ответ PUT совпадает с последующим GET,
        # сверку можно делать по ответу PUT — минус ещё один запрос.
        actual = keitaro.get_stream(stream_id)
        if actual.campaign_id != campaign_id:
            raise StreamNotInCampaign(stream_id)
        differences = _differences(offers, actual)
        if differences:
            raise PushNotConfirmed(stream_id, differences)
        # 3. Свежий агрегат сохраняет правки других потоков; гонка save проверяется версией.
        return _finish(repo, uow, campaign_id, lease, offers)
    except Exception:
        uow.rollback()
        try:
            _release(repo, uow, campaign_id, lease.token)
        except Exception:
            uow.rollback()
            logger.exception("Не удалось снять отметку Push кампании %s; она протухнет по TTL", campaign_id)
        raise


def _finish(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId,
    lease: PushLease, offers: Sequence[PublishedOffer],
) -> Campaign:
    for attempt in range(2):
        campaign = load_campaign(repo, campaign_id)
        if campaign.push_in_progress is None or campaign.push_in_progress.token != lease.token:
            raise ConcurrencyConflict(campaign_id)
        try:
            desired = campaign.offers_to_publish(lease.stream_id)
        except DomainError as error:
            raise ConcurrencyConflict(campaign_id) from error
        if _weights(desired) != _weights(offers):
            raise ConcurrencyConflict(campaign_id)
        if not attempt or not campaign.adopt_published(lease.stream_id, offers):
            campaign.mark_published(lease.stream_id)
        campaign.push_in_progress = None
        try:
            repo.save(campaign)
            uow.commit()
            return campaign
        except ConcurrencyConflict:
            uow.rollback()
            if attempt:
                raise
    raise AssertionError("unreachable")


def _release(repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, token: str) -> None:
    for attempt in range(2):
        campaign = repo.get(campaign_id)
        if campaign is None or campaign.push_in_progress is None or campaign.push_in_progress.token != token:
            uow.rollback()
            return
        campaign.push_in_progress = None
        try:
            repo.save(campaign)
            uow.commit()
            return
        except ConcurrencyConflict:
            uow.rollback()
            if attempt:
                raise


def _weights(offers: Sequence[PublishedOffer]) -> dict[int, int]:
    return {o.offer.id: o.share for o in offers}


def _changes_since_fetch(seen: dict[int, int], current: KeitaroStreamState) -> list[str]:
    """Активные офферы и веса в Keitaro против тех, что обёртка видела при последнем Fetch или Push."""
    now = _weights(current.offers)
    changes: list[str] = []
    for offer_id in sorted(seen.keys() | now.keys()):
        was, got = seen.get(offer_id), now.get(offer_id)
        if was == got:
            continue
        if was is None:
            changes.append(f"в Keitaro добавлен или включён оффер [{offer_id}] ({got}%)")
        elif got is None:
            changes.append(f"в Keitaro удалён или выключен оффер [{offer_id}]")
        else:
            changes.append(f"в Keitaro у оффера [{offer_id}] вес {was}% → {got}%")
    return changes


def _differences(sent: Sequence[PublishedOffer], actual: KeitaroStreamState) -> list[str]:
    """Сверка FR-2.13: только активные офферы одного потока, имена не нужны."""
    expected, published = _weights(sent), _weights(actual.offers)
    diffs: list[str] = []
    for offer_id in sorted(expected.keys() | published.keys()):
        want, got = expected.get(offer_id), published.get(offer_id)
        if want == got:
            continue
        if got is None:
            diffs.append(f"оффера [{offer_id}] нет в потоке")
        elif want is None:
            diffs.append(f"оффер [{offer_id}] остался в потоке с весом {got}%")
        else:
            diffs.append(f"у оффера [{offer_id}] вес {got}% вместо {want}%")
    return diffs
