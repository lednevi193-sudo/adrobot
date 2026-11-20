import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EditorPage from '@/editor/page/EditorPage.vue'
import { campaign, jsonResponse, stream } from '../fixtures'

vi.mock('naive-ui', async (original) => ({
  ...await original<typeof import('naive-ui')>(),
  useMessage: () => ({ success: vi.fn() }),
}))

let wrapper: ReturnType<typeof mount> | undefined
afterEach(() => {
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

async function clickDialog(text: string) {
  const button = [...document.body.querySelectorAll('button')].find((el) => el.textContent?.trim() === text)
  if (!button) throw new Error(`Dialog button missing: ${text}`)
  button.click()
  await flushPromises()
}

describe('EditorPage confirmations', () => {
  it.each(['cancel', 'fetch'] as const)('%s: отказ сохраняет черновик, согласие использует версию списка', async (action) => {
    const changes = [{ stream_id: 7, offer: { id: 18813, name: 'Pinned offer' }, kind: 'pin', share_before: 100, share_after: 50 }]
    const view = campaign({ version: 5, has_draft: true, streams: [stream({ has_draft: true, can_cancel: true })] })
    let finishRemove!: (value: Response) => void
    const fetchMock = vi.fn((input: string, init?: RequestInit) => {
      if (init?.method === 'DELETE') return new Promise<Response>((resolve) => { finishRemove = resolve })
      if (input.endsWith('/draft')) return Promise.resolve(jsonResponse(200, { version: 5, changes }))
      if (input.endsWith('/fetch')) {
        const discard = JSON.parse(String(init?.body)).discard_drafts
        return Promise.resolve(discard
          ? jsonResponse(200, campaign({ version: 7 }))
          : jsonResponse(409, { code: 'campaign_has_drafts', message: 'Есть черновики', changes, version: 5 }))
      }
      if (input.endsWith('/cancel')) return Promise.resolve(jsonResponse(200, { campaign: campaign({ version: 7 }), cancelled: changes }))
      return Promise.resolve(jsonResponse(200, { campaign: view, keitaro_changes: [] }))
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(EditorPage, { props: { id: 42 }, attachTo: document.body, global: { stubs: { OfferPicker: true } } })
    await flushPromises()
    const selector = action === 'cancel' ? '[data-test=cancel]' : '[data-test=fetch]'
    const destructiveCalls = () => fetchMock.mock.calls.filter(([url, init]) =>
      url.endsWith('/cancel') || (url.endsWith('/fetch') && JSON.parse(String(init?.body)).discard_drafts),
    )

    await wrapper.find(selector).trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Pinned offer')
    expect(destructiveCalls()).toHaveLength(0)
    await clickDialog('Не отменять')
    expect(destructiveCalls()).toHaveLength(0)

    // Поздний ответ другой команды не должен менять версию уже показанного списка.
    await wrapper.find('[data-test=remove]').trigger('click')
    await wrapper.find(selector).trigger('click')
    await flushPromises()
    finishRemove(jsonResponse(200, { ...view, version: 6 }))
    await flushPromises()
    await clickDialog(action === 'cancel' ? 'Отменить изменения' : 'Отбросить и синхронизировать')
    expect(destructiveCalls()).toHaveLength(1)
    const init = destructiveCalls()[0]![1]!
    expect(new Headers(init.headers).get('If-Match')).toBe('"5"')
  })
})
