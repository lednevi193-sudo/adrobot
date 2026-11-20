// Построители DTO для тестов (≈ test data builders): значения по умолчанию + переопределения.
import type { CampaignView, StreamOfferView, StreamView } from '@/editor/api/types'

export const offer = (o: Partial<StreamOfferView> = {}): StreamOfferView => ({
  id: 18813,
  name: 'Offer A',
  status: 'active',
  share: 100,
  pinned: false,
  keitaro_share: 100,
  ...o,
})

export const stream = (s: Partial<StreamView> = {}): StreamView => ({
  id: 7,
  name: 'Offers',
  position: 2,
  editable: true,
  has_draft: false,
  can_cancel: false,
  push_blocker: null,
  offers: [offer()],
  ...s,
})

export const campaign = (c: Partial<CampaignView> = {}): CampaignView => ({
  id: 42,
  name: 'test_x_promo',
  alias: 'AbCd',
  tracker_url: 'https://kylovoa.com/AbCd',
  is_ours: true,
  has_draft: false,
  version: 3,
  streams: [stream({ id: 6, name: 'Geo → Google', position: 1, editable: false, offers: [] }), stream()],
  ...c,
})

/** Ответ fetch с JSON-телом. */
export const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
