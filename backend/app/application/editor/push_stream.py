"""Push (FR-2.13, FR-2.14): опубликовать черновик потока в Keitaro.

Порядок — сначала Keitaro, потом наша БД. Если Keitaro принял, а сохранить не удалось:
- из-за параллельной правки (ConcurrencyConflict) — перечитываем кампанию и, если её черновик
  потока совпадает с опубликованным, отмечаем его опубликованным в свежей версии;
- из-за любого другого сбоя — ошибка уходит пользователю, а ближайший Fetch увидит, что
  черновик уже лежит в Keitaro, и примет его как опубликованный (Stream.adopt_published),
  не предлагая «отменить» и не теряя закреплённые веса.
"""

from collections.abc import Sequence

from app.application.editor.loading import load_campaign
from app.application.errors import ConcurrencyConflict, NotOurCampaign, PushNotConfirmed
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign, KeitaroCampaign, PublishedOffer
from app.domain.common.ids import CampaignId, StreamId


def push_stream(
    repo: CampaignRepository,
    keitaro: KeitaroGateway,
    uow: UnitOfWork,
    campaign_id: CampaignId,
    stream_id: StreamId,
    *,
    prefix: str,
    expected_version: int | None = None,
) -> Campaign:
    campaign = load_campaign(repo, campaign_id, expected_version)
    if not campaign.is_ours(prefix):
        raise NotOurCampaign(campaign_id)  # стенд общий: чужие потоки не публикуем (NFR-4)

    offers = campaign.offers_to_publish(stream_id)  # EmptyStreamPush, SharesDoNotSumTo100
    keitaro.publish_offers(stream_id, offers)  # ошибка Keitaro -> черновик не тронут (FR-2.14)

    differences = _differences(offers, keitaro.get_campaign(campaign_id), stream_id)
    if differences:
        raise PushNotConfirmed(stream_id, differences)

    campaign.mark_published(stream_id)
    try:
        repo.save(campaign)
        uow.commit()
    except ConcurrencyConflict:
        uow.rollback()
        campaign = load_campaign(repo, campaign_id)
        if not campaign.adopt_published(stream_id, offers):
            raise  # поток успели изменить после Push — пусть пользователь посмотрит свежую версию
        repo.save(campaign)
        uow.commit()
    return campaign


def _differences(sent: Sequence[PublishedOffer], actual: KeitaroCampaign, stream_id: StreamId) -> list[str]:
    """Сверка FR-2.13 п. 3: в Keitaro ровно отправленные офферы с отправленными весами."""
    stream = next((s for s in actual.streams if s.id == stream_id), None)
    if stream is None:
        return [f"поток {stream_id} пропал из Keitaro"]

    expected = {o.offer.id: o.share for o in sent}
    published = {o.offer.id: o.share for o in stream.offers}
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
