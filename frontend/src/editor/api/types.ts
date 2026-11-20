/**
 * DTO редактора — 1:1 с backend/app/api/schemas.py (≈ response-модели контроллера).
 * Только форма данных: все правила (веса, push_blocker, keitaro_share) считает бэкенд.
 */
import type { OfferDto } from '@/offers/types'

export interface CampaignSummaryDto {
  id: number
  name: string
}

/** Состояние оффера в потоке (FR-2.4). */
export type AssignmentStatus = 'active' | 'pending_add' | 'pending_remove' | 'removed'

export interface StreamOfferView {
  id: number
  name: string
  status: AssignmentStatus
  /** Вес в обёртке, %. */
  share: number
  /** Закреплённый вес (FR-2.9). */
  pinned: boolean
  /** Вес в Keitaro; null — оффера в Keitaro нет (FR-2.9a). */
  keitaro_share: number | null
}

export interface StreamView {
  id: number
  name: string
  position: number
  /** true — поток с офферами; false — любой другой, показываем только имя и позицию. */
  editable: boolean
  /** Поток жёлтый: желаемое расходится с Keitaro (FR-2.5). */
  has_draft: boolean
  /** Есть что отменить Cancel. has_draft без can_cancel — закреплённый вес поменяли в Keitaro (FR-2.9a). */
  can_cancel: boolean
  /** Почему Push сейчас невозможен (FR-2.12), или null. */
  push_blocker: string | null
  offers: StreamOfferView[]
}

export interface CampaignView {
  id: number
  name: string
  alias: string
  tracker_url: string | null
  /** Наша кампания — с префиксом CAMPAIGN_PREFIX (Q5). */
  is_ours: boolean
  has_draft: boolean
  /** Версия кампании: уходит в If-Match с каждой командой — защита от правки из устаревшей вкладки. */
  version: number
  streams: StreamView[]
}

/** Вид изменения черновика. */
export type DraftChangeKind = 'add' | 'remove' | 'pin' | 'unpin' | 'share'

/** Строка подтверждения Cancel/Fetch: «будет отменено: …» (FR-2.10a). */
export interface DraftChangeDto {
  stream_id: number
  offer: OfferDto
  kind: DraftChangeKind
  share_before: number | null
  share_after: number | null
}

/** Открытие кампании: сверено с Keitaro (FR-2.1). */
export interface OpenCampaignResponse {
  campaign: CampaignView
  /** Что поменяли прямо в Keitaro, пока в обёртке лежит черновик; пусто — синхронизировано. */
  keitaro_changes: string[]
}

export interface CancelResponse {
  campaign: CampaignView
  cancelled: DraftChangeDto[]
}

export interface DraftResponse {
  version: number
  changes: DraftChangeDto[]
}
