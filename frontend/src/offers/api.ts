/** Справочник офферов: автодополнение (FR-1.2). */
import { http, query } from '@/shared/api/http'
import type { OfferDto } from './types'

export function searchOffers(q: string): Promise<OfferDto[]> {
  return http.get<OfferDto[]>('/offers' + query({ q }))
}
