"""Что поменяли прямо в Keitaro с тех пор, как обёртка последний раз его видела.

Сравнивается опубликованное состояние агрегата (published) со снимком Keitaro —
черновик в сравнении не участвует. Нужно при открытии кампании с черновиком:
синхронизировать её нельзя без потери черновика (FR-2.3a), но предупредить можно.
"""

from app.domain.campaigns.model.campaign import Campaign
from app.domain.campaigns.model.stream import Stream
from app.domain.campaigns.sync.snapshots import KeitaroCampaign, KeitaroStream
from app.domain.offers.offer_ref import OfferRef


def changes_in_keitaro(campaign: Campaign, snapshot: KeitaroCampaign) -> list[str]:
    """Пустой список — Keitaro совпадает с тем, что знает обёртка."""
    changes: list[str] = []
    if campaign.name != snapshot.name:
        changes.append(f"кампания переименована: «{campaign.name}» → «{snapshot.name}»")
    if (campaign.alias, campaign.domain_url) != (snapshot.alias, snapshot.domain_url):
        changes.append("изменилась ссылка трекера")

    ours = {s.id: s for s in campaign.streams}
    for ks in snapshot.streams:
        stream = ours.pop(ks.id, None)
        if stream is None:
            changes.append(f"новый поток «{ks.name}»")
        else:
            changes.extend(_stream_changes(stream, ks))
    changes.extend(f"поток «{s.name}» удалён" for s in ours.values())
    return changes


def _stream_changes(stream: Stream, ks: KeitaroStream) -> list[str]:
    changes: list[str] = []
    if stream.name != ks.name:
        changes.append(f"поток «{stream.name}» переименован в «{ks.name}»")
    if stream.position != ks.position:
        changes.append(f"поток «{ks.name}» перемещён на позицию {ks.position}")

    published = {a.offer.id: (a.offer, a.published.share) for a in stream.assignments if a.is_published and a.published}
    in_keitaro = {o.offer.id: (o.offer, o.share) for o in ks.offers}
    where = f"поток «{ks.name}»"
    for offer_id in sorted(published.keys() | in_keitaro.keys()):
        was, now = published.get(offer_id), in_keitaro.get(offer_id)
        if was is None and now is not None:
            changes.append(f"{where}: добавлен оффер {_offer(now[0])} ({now[1]}%)")
        elif now is None and was is not None:
            changes.append(f"{where}: удалён оффер {_offer(was[0])}")
        elif was is not None and now is not None and was[1] != now[1]:
            changes.append(f"{where}: вес оффера {_offer(now[0])} {was[1]}% → {now[1]}%")
    return changes


def _offer(offer: OfferRef) -> str:
    return f"[{offer.id}] {offer.name}"
