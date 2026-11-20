import { http } from '@/shared/api/http'
import type { OfferDto } from '@/offers/types'

export interface DemoWeight {
  offer_id: number
  share: number
  state: 'active' | 'disabled'
}
export interface DemoStream {
  id: number
  name: string
  position: number
  offers: DemoWeight[]
}
export interface DemoCampaign {
  id: number
  name: string
  streams: DemoStream[]
}
export interface DemoState {
  offers: OfferDto[]
  campaigns: DemoCampaign[]
}

export const demoKeitaro = {
  read: () => http.get<DemoState>('/demo/keitaro'),
  save: (id: number, body: { name: string; stream_id: number; offers: DemoWeight[] }) =>
    http.put<DemoState>(`/demo/keitaro/campaigns/${id}`, body),
}
