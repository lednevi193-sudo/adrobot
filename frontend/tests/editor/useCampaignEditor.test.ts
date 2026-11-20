import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/apiError'
import { useCampaignEditor } from '@/editor/useCampaignEditor'
import * as campaignsApi from '@/editor/api/campaigns'
import { streamsApi } from '@/editor/api/streams'
import type { DraftChangeDto } from '@/editor/api/types'
import { campaign, offer, stream } from './fixtures'

// ≈ Moq для typed-клиентов: composable проверяем без сети
vi.mock('@/editor/api/campaigns')
vi.mock('@/editor/api/streams', () => ({
  streamsApi: { push: vi.fn(), removeOffer: vi.fn(), cancel: vi.fn(), draft: vi.fn() },
}))

beforeEach(() => vi.resetAllMocks())

describe('useCampaignEditor', () => {
  it('подтверждения сохраняют версию списка после позднего ответа другой команды', async () => {
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: campaign({ version: 5 }), keitaro_changes: [] })
    vi.mocked(campaignsApi.fetchStreams).mockRejectedValueOnce(
      new ApiError(409, 'campaign_has_drafts', 'Есть черновики', { changes: [], version: 5 }),
    ).mockResolvedValueOnce(campaign({ version: 7 }))
    vi.mocked(streamsApi.draft).mockResolvedValue({ changes: [], version: 5 })
    let finish!: (view: ReturnType<typeof campaign>) => void
    vi.mocked(streamsApi.removeOffer).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    vi.mocked(streamsApi.cancel).mockResolvedValue({ campaign: campaign({ version: 8 }), cancelled: [] })
    const editor = useCampaignEditor(42)
    await editor.load()
    const pending = editor.stream.removeOffer(7, 18813)
    const fetchConfirmation = await editor.fetchStreams()
    const cancelConfirmation = await editor.stream.draft(7)
    finish(campaign({ version: 6 }))
    await pending
    expect(editor.campaign.value?.version).toBe(6)
    if (fetchConfirmation.kind !== 'needs_confirmation' || !cancelConfirmation) throw new Error('missing confirmation')
    await editor.fetchStreams(true, fetchConfirmation.version)
    await editor.stream.cancel(7, cancelConfirmation.version)
    expect(campaignsApi.fetchStreams).toHaveBeenLastCalledWith(42, true, 5)
    expect(streamsApi.cancel).toHaveBeenCalledWith({ campaignId: 42, streamId: 7, version: 5 })
  })
  it('load кладёт CampaignView и сортирует потоки по position', async () => {
    const view = campaign({ streams: [stream({ id: 2, position: 2 }), stream({ id: 1, position: 1 })] })
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: view, keitaro_changes: [] })
    const editor = useCampaignEditor(42)

    await editor.load()

    expect(editor.campaign.value).toBe(view)
    expect(editor.streams.value.map((s) => s.id)).toEqual([1, 2])
  })

  it('команда перерисовывает кампанию из ответа сервера', async () => {
    const after = campaign({
      has_draft: true,
      streams: [stream({ has_draft: true, offers: [offer({ status: 'pending_remove', share: 0 })] })],
    })
    vi.mocked(streamsApi.removeOffer).mockResolvedValue(after)
    const editor = useCampaignEditor(42)

    expect(await editor.stream.removeOffer(7, 18813)).toBe(true)

    expect(streamsApi.removeOffer).toHaveBeenCalledWith({ campaignId: 42, streamId: 7 }, 18813)
    expect(editor.campaign.value).toBe(after)
  })

  it('ошибка Push запоминается у потока, кампания перечитывается (версия могла измениться)', async () => {
    const before = campaign()
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: before, keitaro_changes: [] })
    vi.mocked(streamsApi.push).mockRejectedValue(new ApiError(403, 'not_our_campaign', 'Кампания не наша'))
    const editor = useCampaignEditor(42)
    await editor.load()

    expect(await editor.stream.push(7)).toEqual({ kind: 'failed' })

    expect(editor.campaign.value).toBe(before)
    expect(editor.lastError.value).toMatchObject({ streamId: 7, error: { code: 'not_our_campaign' } })
    expect(editor.busy.value).toBeNull()
  })

  it('Fetch при черновике: 409 campaign_has_drafts -> нужно подтверждение со списком changes', async () => {
    const changes: DraftChangeDto[] = [
      { stream_id: 7, offer: { id: 1, name: 'A' }, kind: 'add', share_before: null, share_after: 50 },
    ]
    vi.mocked(campaignsApi.fetchStreams).mockRejectedValueOnce(
      new ApiError(409, 'campaign_has_drafts', 'Есть черновики', { changes, version: 5 }),
    )
    const editor = useCampaignEditor(42)

    expect(await editor.fetchStreams()).toEqual({ kind: 'needs_confirmation', changes, version: 5 })
    expect(editor.lastError.value).toBeNull()
  })

  it('подтверждённый Fetch шлёт discard_drafts=true и версию, которую видел пользователь', async () => {
    const view = campaign()
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: campaign({ version: 5 }), keitaro_changes: [] })
    vi.mocked(campaignsApi.fetchStreams).mockResolvedValue(view)
    const editor = useCampaignEditor(42)
    await editor.load()

    expect(await editor.fetchStreams(true)).toEqual({ kind: 'done' })

    expect(campaignsApi.fetchStreams).toHaveBeenCalledWith(42, true, 5)
    expect(editor.campaign.value).toBe(view)
  })

  it('Fetch с ошибкой Keitaro — ошибка уровня кампании', async () => {
    vi.mocked(campaignsApi.fetchStreams).mockRejectedValue(new ApiError(504, 'keitaro_unavailable', 'таймаут'))
    const editor = useCampaignEditor(42)

    expect(await editor.fetchStreams()).toEqual({ kind: 'failed' })
    expect(editor.lastError.value).toMatchObject({ streamId: null, error: { status: 504 } })
  })

  it('изменения в Keitaro при черновике показываются до успешного Fetch', async () => {
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: campaign(), keitaro_changes: ['поток «Offers» удалён'] })
    vi.mocked(campaignsApi.fetchStreams).mockResolvedValue(campaign())
    const editor = useCampaignEditor(42)

    await editor.load()
    expect(editor.keitaroChanges.value).toEqual(['поток «Offers» удалён'])

    await editor.fetchStreams(true)
    expect(editor.keitaroChanges.value).toEqual([])
  })

  it('команда уходит с версией кампании из последнего ответа', async () => {
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue({ campaign: campaign({ version: 5 }), keitaro_changes: [] })
    vi.mocked(streamsApi.removeOffer).mockResolvedValue(campaign({ version: 6 }))
    vi.mocked(streamsApi.push).mockResolvedValue(campaign({ version: 7 }))
    const editor = useCampaignEditor(42)
    await editor.load()

    await editor.stream.removeOffer(7, 18813)
    await editor.stream.push(7)

    expect(streamsApi.removeOffer).toHaveBeenCalledWith({ campaignId: 42, streamId: 7, version: 5 }, 18813)
    expect(streamsApi.push).toHaveBeenCalledWith({ campaignId: 42, streamId: 7, version: 6 }, false)
  })

  it('409 concurrency_conflict: ошибка у потока и свежая версия кампании с сервера', async () => {
    const fresh = campaign({ version: 9 })
    vi.mocked(campaignsApi.openCampaign)
      .mockResolvedValueOnce({ campaign: campaign({ version: 5 }), keitaro_changes: [] })
      .mockResolvedValueOnce({ campaign: fresh, keitaro_changes: [] })
    vi.mocked(streamsApi.push).mockRejectedValue(new ApiError(409, 'concurrency_conflict', 'Кампанию изменили'))
    const editor = useCampaignEditor(42)
    await editor.load()

    expect(await editor.stream.push(7)).toEqual({ kind: 'failed' })

    expect(editor.lastError.value).toMatchObject({ streamId: 7, error: { code: 'concurrency_conflict' } })
    expect(editor.campaign.value).toBe(fresh)  // следующая команда уйдёт уже с version 9
  })

  it('Cancel берёт кампанию из CancelResponse', async () => {
    const view = campaign()
    vi.mocked(streamsApi.cancel).mockResolvedValue({ campaign: view, cancelled: [] })
    const editor = useCampaignEditor(42)

    await editor.stream.cancel(7)

    expect(editor.campaign.value).toBe(view)
  })
  it('поток поменяли в Keitaro после Fetch: нужно решение, кампания перечитана; подтверждение шлёт overwrite', async () => {
    const fresh = campaign({ version: 9 })
    vi.mocked(campaignsApi.openCampaign)
      .mockResolvedValueOnce({ campaign: campaign({ version: 5 }), keitaro_changes: [] })
      .mockResolvedValue({ campaign: fresh, keitaro_changes: [] })
    vi.mocked(streamsApi.push)
      .mockRejectedValueOnce(
        new ApiError(409, 'stream_changed_in_keitaro', 'Поток поменяли', { differences: ['в Keitaro удалён оффер [101]'] }),
      )
      .mockResolvedValueOnce(campaign({ version: 11 }))
    const editor = useCampaignEditor(42)
    await editor.load()

    expect(await editor.stream.push(7)).toEqual({ kind: 'needs_confirmation', differences: ['в Keitaro удалён оффер [101]'] })
    expect(editor.lastError.value).toBeNull()
    expect(editor.campaign.value).toBe(fresh)

    expect(await editor.stream.push(7, true)).toEqual({ kind: 'done' })
    expect(streamsApi.push).toHaveBeenLastCalledWith({ campaignId: 42, streamId: 7, version: 9 }, true)
  })
})
