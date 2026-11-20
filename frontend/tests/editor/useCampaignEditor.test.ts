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
  it('load кладёт CampaignView и сортирует потоки по position', async () => {
    const view = campaign({ streams: [stream({ id: 2, position: 2 }), stream({ id: 1, position: 1 })] })
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue(view)
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

  it('ошибка Push запоминается у потока, кампания не меняется', async () => {
    const before = campaign()
    vi.mocked(campaignsApi.openCampaign).mockResolvedValue(before)
    vi.mocked(streamsApi.push).mockRejectedValue(new ApiError(403, 'not_our_campaign', 'Кампания не наша'))
    const editor = useCampaignEditor(42)
    await editor.load()

    expect(await editor.stream.push(7)).toBe(false)

    expect(editor.campaign.value).toBe(before)
    expect(editor.lastError.value).toMatchObject({ streamId: 7, error: { code: 'not_our_campaign' } })
    expect(editor.busy.value).toBeNull()
  })

  it('Fetch при черновике: 409 campaign_has_drafts -> нужно подтверждение со списком changes', async () => {
    const changes: DraftChangeDto[] = [
      { stream_id: 7, offer: { id: 1, name: 'A' }, kind: 'add', share_before: null, share_after: 50 },
    ]
    vi.mocked(campaignsApi.fetchStreams).mockRejectedValueOnce(
      new ApiError(409, 'campaign_has_drafts', 'Есть черновики', { changes }),
    )
    const editor = useCampaignEditor(42)

    expect(await editor.fetchStreams()).toEqual({ kind: 'needs_confirmation', changes })
    expect(editor.lastError.value).toBeNull()
  })

  it('подтверждённый Fetch шлёт discard_drafts=true', async () => {
    const view = campaign()
    vi.mocked(campaignsApi.fetchStreams).mockResolvedValue(view)
    const editor = useCampaignEditor(42)

    expect(await editor.fetchStreams(true)).toEqual({ kind: 'done' })

    expect(campaignsApi.fetchStreams).toHaveBeenCalledWith(42, true)
    expect(editor.campaign.value).toBe(view)
  })

  it('Fetch с ошибкой Keitaro — ошибка уровня кампании', async () => {
    vi.mocked(campaignsApi.fetchStreams).mockRejectedValue(new ApiError(504, 'keitaro_unavailable', 'таймаут'))
    const editor = useCampaignEditor(42)

    expect(await editor.fetchStreams()).toEqual({ kind: 'failed' })
    expect(editor.lastError.value).toMatchObject({ streamId: null, error: { status: 504 } })
  })

  it('Cancel берёт кампанию из CancelResponse', async () => {
    const view = campaign()
    vi.mocked(streamsApi.cancel).mockResolvedValue({ campaign: view, cancelled: [] })
    const editor = useCampaignEditor(42)

    await editor.stream.cancel(7)

    expect(editor.campaign.value).toBe(view)
  })
})
