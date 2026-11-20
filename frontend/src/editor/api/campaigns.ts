/** Кампании: список, открыть, Fetch streams (FR-2.1 – FR-2.3a). */
import { http, query } from '@/shared/api/http'
import type { CampaignSummaryDto, CampaignView } from './types'

export function listCampaigns(all: boolean): Promise<CampaignSummaryDto[]> {
  return http.get('/campaigns' + query({ all }))
}

export function openCampaign(id: number): Promise<CampaignView> {
  return http.get(`/campaigns/${id}`)
}

/** 409 campaign_has_drafts (+ changes), если есть черновики и discardDrafts=false (FR-2.3a). */
export function fetchStreams(id: number, discardDrafts = false): Promise<CampaignView> {
  return http.post(`/campaigns/${id}/fetch`, { discard_drafts: discardDrafts })
}
