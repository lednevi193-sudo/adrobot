import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StreamCard from '@/editor/stream/StreamCard.vue'
import { ApiError } from '@/shared/api/apiError'
import type { StreamView } from '@/editor/api/types'
import { offer, stream } from '../fixtures'

// OfferPicker ходит в сеть — в тестах карточки он не нужен
const mountCard = (props: { stream?: StreamView; error?: ApiError | null } = {}) =>
  mount(StreamCard, {
    props: { stream: stream(), busy: null, error: null, ...props },
    global: { stubs: { OfferPicker: true } },
  })

describe('StreamCard', () => {
  it('без черновика — белый, Push и Cancel заблокированы', () => {
    const w = mountCard()
    expect(w.find('[data-test=stream-card]').attributes('data-draft')).toBe('false')
    expect(w.find('[data-test=push]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-test=cancel]').attributes('disabled')).toBeDefined()
  })

  it('черновик — жёлтый, Push доступен', () => {
    const w = mountCard({ stream: stream({ has_draft: true }) })
    expect(w.find('[data-test=stream-card]').classes()).toContain('draft')
    expect(w.find('[data-test=draft-tag]').exists()).toBe(true)
    expect(w.find('[data-test=push]').attributes('disabled')).toBeUndefined()
  })

  it('push_blocker — предупреждение и заблокированный Push', () => {
    const w = mountCard({ stream: stream({ has_draft: true, push_blocker: 'В потоке не осталось офферов' }) })
    expect(w.find('[data-test=push-blocker]').text()).toContain('В потоке не осталось офферов')
    expect(w.find('[data-test=push]').attributes('disabled')).toBeDefined()
  })

  it('pending_add — пометка new; pending_remove — серый с Bring back; removed — в архиве', () => {
    const w = mountCard({
      stream: stream({
        offers: [
          offer({ id: 1, status: 'pending_add', share: 50, keitaro_share: null }),
          offer({ id: 2, status: 'pending_remove', share: 0, keitaro_share: 50 }),
          offer({ id: 3, status: 'removed', share: 0, keitaro_share: null }),
        ],
      }),
    })
    const rows = w.findAll('[data-test=offer-row]')
    const byStatus = (s: string) => rows.find((r) => r.attributes('data-status') === s)!

    expect(byStatus('pending_add').find('[data-test=new]').exists()).toBe(true)
    expect(byStatus('pending_remove').classes()).toContain('grey')
    expect(byStatus('pending_remove').find('[data-test=bring-back]').exists()).toBe(true)
    expect(byStatus('pending_remove').find('[data-test=remove]').exists()).toBe(false)
    expect(w.find('[data-test=archive]').text()).toContain('Архив (1)')
  })

  it('подсказка «в Keitaro сейчас N%», когда вес в Keitaro другой (FR-2.9a)', () => {
    const w = mountCard({ stream: stream({ offers: [offer({ share: 70, pinned: true, keitaro_share: 30 })] }) })
    expect(w.find('[data-test=keitaro-hint]').text()).toBe('в Keitaro сейчас 30%')
    expect(w.find('[data-test=pinned]').exists()).toBe(true)
    expect(w.find('[data-test=unpin]').exists()).toBe(true)
  })

  it('без расхождения подсказки нет', () => {
    expect(mountCard().find('[data-test=keitaro-hint]').exists()).toBe(false)
  })

  it('кнопки поднимают события с ID оффера', async () => {
    const w = mountCard({ stream: stream({ has_draft: true }) })
    await w.find('[data-test=remove]').trigger('click')
    await w.find('[data-test=push]').trigger('click')
    expect(w.emitted('remove')).toEqual([[18813]])
    expect(w.emitted('push')).toHaveLength(1)
  })

  it('ошибка Push показывается со списком расхождений', () => {
    const error = new ApiError(502, 'push_not_confirmed', 'Keitaro опубликовал другое', {
      differences: ['оффер 18813: отправили 50%, в Keitaro 40%'],
    })
    const w = mountCard({ error })
    expect(w.find('[data-test=error-message]').text()).toBe('Keitaro опубликовал другое')
    expect(w.find('[data-test=error-details]').text()).toContain('отправили 50%')
  })
})
