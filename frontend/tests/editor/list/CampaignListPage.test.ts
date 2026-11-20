import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CampaignListPage from '@/editor/list/CampaignListPage.vue'
import * as campaignsApi from '@/editor/api/campaigns'
import type { CampaignSummaryDto } from '@/editor/api/types'

vi.mock('@/editor/api/campaigns')
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

afterEach(() => vi.resetAllMocks())

/** Обещание, которое тест разрешает сам, — чтобы управлять порядком ответов. */
function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

describe('CampaignListPage', () => {
  it('по умолчанию запрашивает наши кампании', async () => {
    vi.mocked(campaignsApi.listCampaigns).mockResolvedValue([{ id: 1, name: 'test_x_a' }])
    const w = mount(CampaignListPage)
    await flushPromises()
    expect(campaignsApi.listCampaigns).toHaveBeenCalledWith(false)
    expect(w.findAll('[data-test=campaign-row]')).toHaveLength(1)
  })

  it('запоздавший ответ «наших» не перетирает список «всех»', async () => {
    const ours = deferred<CampaignSummaryDto[]>()
    const all = deferred<CampaignSummaryDto[]>()
    vi.mocked(campaignsApi.listCampaigns).mockImplementation((a) => (a ? all.promise : ours.promise))
    const w = mount(CampaignListPage)

    await w.find('[data-test=all]').trigger('click')
    all.resolve([
      { id: 1, name: 'a' },
      { id: 2, name: 'b' },
    ])
    await flushPromises()
    ours.resolve([])
    await flushPromises()

    expect(w.findAll('[data-test=campaign-row]')).toHaveLength(2)
  })
})
