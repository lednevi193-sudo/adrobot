/** Кампании: список, открыть, Fetch streams (FR-2.1 – FR-2.3a). */
import { http, query } from '@/shared/api/http'
import type { CampaignSummaryDto, CampaignView, OpenCampaignResponse } from './types'

/** all=false — наши из БД обёртки (быстро, без Keitaro); all=true — все кампании стенда из Keitaro. */
export function listCampaigns(all: boolean): Promise<CampaignSummaryDto[]> {
  return http.get('/campaigns' + query({ all }))
}

/** Открыть и сверить с Keitaro: без черновика бэкенд синхронизирует сам, с черновиком — вернёт keitaro_changes. */
export function openCampaign(id: number): Promise<OpenCampaignResponse> {
  return http.get(`/campaigns/${id}`)
}

/** 409 campaign_has_drafts (+ changes), если есть черновики и discardDrafts=false (FR-2.3a). */
export function fetchStreams(id: number, discardDrafts = false): Promise<CampaignView> {
  return http.post(`/campaigns/${id}/fetch`, { discard_drafts: discardDrafts })
}
