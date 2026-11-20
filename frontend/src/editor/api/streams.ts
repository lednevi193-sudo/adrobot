/**
 * Команды редактора потока (FR-2.6 – FR-2.14). Каждая возвращает CampaignView целиком.
 * StreamRef — адрес потока; так сигнатуры не превращаются в (number, number, number).
 */
import { http } from '@/shared/api/http'
import type { CampaignView, CancelResponse, DraftChangeDto } from './types'

export interface StreamRef {
  campaignId: number
  streamId: number
}

const base = (s: StreamRef) => `/campaigns/${s.campaignId}/streams/${s.streamId}`
const offer = (s: StreamRef, offerId: number) => `${base(s)}/offers/${offerId}`

export const streamsApi = {
  addOffer: (s: StreamRef, offerId: number) => http.post<CampaignView>(`${base(s)}/offers`, { offer_id: offerId }),
  removeOffer: (s: StreamRef, offerId: number) => http.delete<CampaignView>(offer(s, offerId)),
  bringBack: (s: StreamRef, offerId: number) => http.post<CampaignView>(`${offer(s, offerId)}/bring-back`),
  /** share не задан — закрепить текущий вес. */
  pin: (s: StreamRef, offerId: number, share?: number) =>
    http.put<CampaignView>(`${offer(s, offerId)}/pin`, { share: share ?? null }),
  unpin: (s: StreamRef, offerId: number) => http.delete<CampaignView>(`${offer(s, offerId)}/pin`),
  /** Что отменит Cancel — для окна подтверждения (FR-2.10a). */
  draft: (s: StreamRef) => http.get<DraftChangeDto[]>(`${base(s)}/draft`),
  cancel: (s: StreamRef) => http.post<CancelResponse>(`${base(s)}/cancel`),
  push: (s: StreamRef) => http.post<CampaignView>(`${base(s)}/push`),
}
