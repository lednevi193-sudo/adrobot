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
export const CONCURRENCY_CONFLICT = 'concurrency_conflict'
export const STREAM_CHANGED_IN_KEITARO = 'stream_changed_in_keitaro'

/** Итог Push: готово, нужно решение пользователя (поток поменяли в Keitaro после Fetch) или ошибка. */
export type PushOutcome = { kind: 'done' } | { kind: 'needs_confirmation'; differences: string[] } | { kind: 'failed' }

export interface EditorError {
  /** null — ошибка кампании целиком (открыть, Fetch). */
  streamId: number | null
  error: ApiError
}

/** Итог Fetch: готово, или нужно подтверждение потери черновика (FR-2.3a). */
export type FetchOutcome = { kind: 'done' } | { kind: 'needs_confirmation'; changes: DraftChangeDto[]; version: number } | { kind: 'failed' }

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
      const error = asApiError(e)
      lastError.value = { streamId, error }
      if (error.code === CONCURRENCY_CONFLICT) await refresh()
      return undefined
    } finally {
      busy.value = null
    }
  }

  /** Кампанию изменили в другой вкладке: показать свежую версию, ошибка остаётся на экране. */
  async function refresh(): Promise<void> {
    try {
      const opened = await openCampaign(campaignId)
      campaign.value = opened.campaign
      keitaroChanges.value = opened.keitaro_changes
    } catch {
      // не вышло — останется исходная ошибка конфликта, пользователь обновит страницу сам
    }
  }

  /** Выполнить команду, вернувшую CampaignView, и перерисоваться из ответа. */
  async function apply(key: string, streamId: number | null, call: () => Promise<CampaignView>): Promise<boolean> {
    const view = await run(key, streamId, call)
    if (view) campaign.value = view
    return view !== undefined
  }

  const ref_ = (streamId: number): StreamRef => ({ campaignId, streamId, version: campaign.value?.version })

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
  async function fetchStreams(discardDrafts = false, confirmedVersion?: number): Promise<FetchOutcome> {
    busy.value = 'fetch'
    lastError.value = null
    try {
      campaign.value = await fetchStreamsApi(campaignId, discardDrafts, confirmedVersion ?? campaign.value?.version)
      keitaroChanges.value = []
      return { kind: 'done' }
    } catch (e) {
      const error = asApiError(e)
      const version = error.detail<number>('version')
      if (error.code === CAMPAIGN_HAS_DRAFTS && !discardDrafts && typeof version === 'number') {
        return { kind: 'needs_confirmation', changes: error.detail<DraftChangeDto[]>('changes') ?? [], version }
      }
      lastError.value = { streamId: null, error }
      if (error.code === CONCURRENCY_CONFLICT) await refresh()
      return { kind: 'failed' }
    } finally {
      busy.value = null
    }
  }

  /**
   * Push. Неудачный Push всё равно меняет версию кампании (отметка «Push выполняется» ставится
   * и снимается в БД), поэтому после любой ошибки перечитываем кампанию — иначе следующая
   * команда уйдёт со старой версией и получит ложный конфликт.
   */
  async function push(sid: number, overwrite = false): Promise<PushOutcome> {
    busy.value = `push:${sid}`
    lastError.value = null
    try {
      campaign.value = await streamsApi.push(ref_(sid), overwrite)
      // Плашка «в Keitaro есть изменения» могла устареть: Push их перекрыл — сверяемся заново.
      if (keitaroChanges.value.length) await refresh()
      return { kind: 'done' }
    } catch (e) {
      const error = asApiError(e)
      await refresh()
      if (error.code === STREAM_CHANGED_IN_KEITARO && !overwrite) {
        return { kind: 'needs_confirmation', differences: error.detail<string[]>('differences') ?? [] }
      }
      lastError.value = { streamId: sid, error }
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
    push,
    /** Список для подтверждения Cancel (FR-2.10a); undefined — не удалось загрузить. */
    draft: (sid: number) => run(`draft:${sid}`, sid, () => streamsApi.draft(ref_(sid))),
    cancel: (sid: number, version = campaign.value?.version) =>
      apply(`cancel:${sid}`, sid, async () => (await streamsApi.cancel({ campaignId, streamId: sid, version })).campaign),
  }

  const clearError = () => (lastError.value = null)

  return { campaign, streams, keitaroChanges, lastError, busy, load, fetchStreams, stream, clearError }
}

export type CampaignEditor = ReturnType<typeof useCampaignEditor>
