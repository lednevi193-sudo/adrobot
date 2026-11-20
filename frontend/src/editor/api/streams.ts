/**
 * Команды редактора потока (FR-2.6 – FR-2.14). Каждая возвращает CampaignView целиком.
 * StreamRef — адрес потока и версия кампании; так сигнатуры не превращаются в (number, number, number).
 * Версия уходит в If-Match: если кампанию изменили в другой вкладке, бэкенд ответит 409.
 */
import { http } from '@/shared/api/http'
import type { CampaignView, CancelResponse, DraftResponse } from './types'

export interface StreamRef {
  campaignId: number
  streamId: number
  /** Версия кампании, которую видит пользователь (CampaignView.version). */
  version?: number
}

const base = (s: StreamRef) => `/campaigns/${s.campaignId}/streams/${s.streamId}`
const offer = (s: StreamRef, offerId: number) => `${base(s)}/offers/${offerId}`
const v = (s: StreamRef) => ({ ifMatch: s.version })

export const streamsApi = {
  addOffer: (s: StreamRef, offerId: number) =>
    http.post<CampaignView>(`${base(s)}/offers`, { offer_id: offerId }, v(s)),
  removeOffer: (s: StreamRef, offerId: number) => http.delete<CampaignView>(offer(s, offerId), v(s)),
  bringBack: (s: StreamRef, offerId: number) => http.post<CampaignView>(`${offer(s, offerId)}/bring-back`, undefined, v(s)),
  /** share не задан — закрепить текущий вес. */
  pin: (s: StreamRef, offerId: number, share?: number) =>
    http.put<CampaignView>(`${offer(s, offerId)}/pin`, { share: share ?? null }, v(s)),
  unpin: (s: StreamRef, offerId: number) => http.delete<CampaignView>(`${offer(s, offerId)}/pin`, v(s)),
  /** Что отменит Cancel — для окна подтверждения (FR-2.10a). */
  draft: (s: StreamRef) => http.get<DraftResponse>(`${base(s)}/draft`),
  cancel: (s: StreamRef) => http.post<CancelResponse>(`${base(s)}/cancel`, undefined, v(s)),
  /** overwrite — опубликовать поверх правок в Keitaro, которые показал 409 stream_changed_in_keitaro. */
  push: (s: StreamRef, overwrite = false) =>
    http.post<CampaignView>(`${base(s)}/push`, overwrite ? { overwrite_keitaro_changes: true } : undefined, v(s)),
}
