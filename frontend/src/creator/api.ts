/** Создаватор (FR-1.3). */
import { http } from '@/shared/api/http'
import type { CampaignView } from '@/editor/api/types'

export interface CreateCampaignRequest {
  name: string
  /** ISO-коды через запятую: разбирает и проверяет домен (Q1). */
  geos: string
  offer_id: number
}

export function createCampaign(body: CreateCampaignRequest): Promise<CampaignView> {
  return http.post('/campaigns', body)
}
