"""Push (FR-2.13, FR-2.14): опубликовать черновик потока в Keitaro.

Порядок — сначала Keitaro, потом наша БД. Если Keitaro принял, а наш commit упал,
поток останется жёлтым, и ближайший Fetch выровняет его (закреплённые веса не потеряются, Q7).
"""

from collections.abc import Sequence

from app.application.editor.loading import load_campaign
from app.application.errors import NotOurCampaign, PushNotConfirmed
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
) -> Campaign:
    campaign = load_campaign(repo, campaign_id)
    if not campaign.is_ours(prefix):
        raise NotOurCampaign(campaign_id)  # стенд общий: чужие потоки не публикуем (NFR-4)

    offers = campaign.offers_to_publish(stream_id)  # EmptyStreamPush, SharesDoNotSumTo100
    keitaro.publish_offers(stream_id, offers)  # ошибка Keitaro -> черновик не тронут (FR-2.14)

    differences = _differences(offers, keitaro.get_campaign(campaign_id), stream_id)
    if differences:
        raise PushNotConfirmed(stream_id, differences)

    campaign.mark_published(stream_id)
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
