/**
 * Состояние страницы редактора (≈ scoped-сервис страницы в Blazor: живёт, пока открыт компонент).
 *
 * Источник истины — сервер. Каждая команда возвращает CampaignView целиком, и он просто
 * заменяет campaign. Своих правил (веса, состояния, «жёлтый ли поток») здесь нет.
 * Ошибка команды запоминается вместе с потоком, к которому относится, — карточка потока
 * показывает её у себя.
 */
import { computed, ref, shallowRef } from 'vue'
import { ApiError } from '@/shared/api/apiError'
import { asApiError } from '@/shared/api/errorTitle'
import { fetchStreams as fetchStreamsApi, openCampaign } from './api/campaigns'
import { streamsApi, type StreamRef } from './api/streams'
import type { CampaignView, DraftChangeDto } from './api/types'

export const CAMPAIGN_HAS_DRAFTS = 'campaign_has_drafts'

export interface EditorError {
  /** null — ошибка кампании целиком (открыть, Fetch). */
  streamId: number | null
  error: ApiError
}

/** Итог Fetch: готово, или нужно подтверждение потери черновика (FR-2.3a). */
export type FetchOutcome = { kind: 'done' } | { kind: 'needs_confirmation'; changes: DraftChangeDto[] } | { kind: 'failed' }

export function useCampaignEditor(campaignId: number) {
  const campaign = shallowRef<CampaignView | null>(null)
  const lastError = ref<EditorError | null>(null)
  /** Какая команда сейчас выполняется: 'fetch', 'push:12', 'pin:12:18813'… — для спиннеров. */
  const busy = ref<string | null>(null)

  const streams = computed(() => [...(campaign.value?.streams ?? [])].sort((a, b) => a.position - b.position))

  async function run<T>(key: string, streamId: number | null, call: () => Promise<T>): Promise<T | undefined> {
    busy.value = key
    lastError.value = null
    try {
      return await call()
    } catch (e) {
      lastError.value = { streamId, error: asApiError(e) }
      return undefined
    } finally {
      busy.value = null
    }
  }

  /** Выполнить команду, вернувшую CampaignView, и перерисоваться из ответа. */
  async function apply(key: string, streamId: number | null, call: () => Promise<CampaignView>): Promise<boolean> {
    const view = await run(key, streamId, call)
    if (view) campaign.value = view
    return view !== undefined
  }

  const ref_ = (streamId: number): StreamRef => ({ campaignId, streamId })

  /** Изменения в Keitaro, которые не подтянуты из-за черновика. Fetch их подтягивает — и список пустеет. */
  const keitaroChanges = ref<string[]>([])

  async function load(): Promise<boolean> {
    const opened = await run('open', null, () => openCampaign(campaignId))
    if (!opened) return false
    campaign.value = opened.campaign
    keitaroChanges.value = opened.keitaro_changes
    return true
  }

  /** Fetch streams. При черновике бэкенд отвечает 409 со списком changes — его отдаём странице. */
  async function fetchStreams(discardDrafts = false): Promise<FetchOutcome> {
    busy.value = 'fetch'
    lastError.value = null
    try {
      campaign.value = await fetchStreamsApi(campaignId, discardDrafts)
      keitaroChanges.value = []
      return { kind: 'done' }
    } catch (e) {
      const error = asApiError(e)
      if (error.code === CAMPAIGN_HAS_DRAFTS && !discardDrafts) {
        return { kind: 'needs_confirmation', changes: error.detail<DraftChangeDto[]>('changes') ?? [] }
      }
      lastError.value = { streamId: null, error }
      return { kind: 'failed' }
    } finally {
      busy.value = null
    }
  }

  const stream = {
    addOffer: (sid: number, offerId: number) => apply(`add:${sid}`, sid, () => streamsApi.addOffer(ref_(sid), offerId)),
    removeOffer: (sid: number, oid: number) => apply(`remove:${sid}:${oid}`, sid, () => streamsApi.removeOffer(ref_(sid), oid)),
    bringBack: (sid: number, oid: number) => apply(`bring-back:${sid}:${oid}`, sid, () => streamsApi.bringBack(ref_(sid), oid)),
    pin: (sid: number, oid: number, share?: number) => apply(`pin:${sid}:${oid}`, sid, () => streamsApi.pin(ref_(sid), oid, share)),
    unpin: (sid: number, oid: number) => apply(`unpin:${sid}:${oid}`, sid, () => streamsApi.unpin(ref_(sid), oid)),
    push: (sid: number) => apply(`push:${sid}`, sid, () => streamsApi.push(ref_(sid))),
    /** Список для подтверждения Cancel (FR-2.10a); undefined — не удалось загрузить. */
    draft: (sid: number) => run(`draft:${sid}`, sid, () => streamsApi.draft(ref_(sid))),
    cancel: (sid: number) =>
      apply(`cancel:${sid}`, sid, async () => (await streamsApi.cancel(ref_(sid))).campaign),
  }

  const clearError = () => (lastError.value = null)

  return { campaign, streams, keitaroChanges, lastError, busy, load, fetchStreams, stream, clearError }
}

export type CampaignEditor = ReturnType<typeof useCampaignEditor>
