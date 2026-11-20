import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { NInputNumber, NSelect, NSwitch } from 'naive-ui'
import DemoKeitaroPage from '@/demo/DemoKeitaroPage.vue'
import { demoKeitaro, type DemoState } from '@/demo/api'
import { ApiError } from '@/shared/api/apiError'

vi.mock('@/demo/api', () => ({ demoKeitaro: { read: vi.fn(), save: vi.fn() } }))
const initial = (): DemoState => ({
  offers: [{ id: 101, name: 'A' }, { id: 102, name: 'B' }, { id: 103, name: 'C' }],
  campaigns: [{ id: 1, name: 'demo_2_offers', streams: [
    { id: 11, name: 'Geo', position: 1, offers: [] },
    { id: 12, name: 'Offers', position: 2, offers: [{ offer_id: 101, share: 50, state: 'active' }, { offer_id: 102, share: 50, state: 'active' }] },
  ] }],
})
const mountPage = () => mount(DemoKeitaroPage, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
let wrapper: ReturnType<typeof mountPage>
const button = (text: string) => {
  const found = wrapper.findAll('button').find((b) => b.text() === text)
  if (!found) throw new Error(`Missing button: ${text}`)
  return found
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(demoKeitaro.read).mockResolvedValue(initial())
})
afterEach(() => wrapper?.unmount())

describe('DemoKeitaroPage', () => {
  it('выключает и включает офферы, сохраняя вес; позволяет выключить все', async () => {
    vi.mocked(demoKeitaro.save).mockImplementation(async (_, body) => {
      const state = initial()
      state.campaigns[0]!.streams[1]!.offers = body.offers.map((o) => ({ ...o }))
      return state
    })
    wrapper = mountPage()
    await flushPromises()
    wrapper.findAllComponents(NSwitch)[0]!.vm.$emit('update:value', false)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Сумма включённых весов: 50%')
    expect(wrapper.findAllComponents(NInputNumber)[0]!.props('value')).toBe(50)
    await button('Сохранить в демо-Keitaro').trigger('click')
    await flushPromises()
    expect(demoKeitaro.save).toHaveBeenNthCalledWith(1, 1, {
      name: 'demo_2_offers', stream_id: 12,
      offers: [{ offer_id: 101, share: 50, state: 'disabled' }, { offer_id: 102, share: 50, state: 'active' }],
    })
    expect(wrapper.findAllComponents(NSwitch)[0]!.props('value')).toBe(false)
    wrapper.findAllComponents(NSwitch)[0]!.vm.$emit('update:value', true)
    await wrapper.vm.$nextTick()
    await button('Сохранить в демо-Keitaro').trigger('click')
    await flushPromises()
    expect(demoKeitaro.save).toHaveBeenNthCalledWith(2, 1, expect.objectContaining({
      offers: [{ offer_id: 101, share: 50, state: 'active' }, { offer_id: 102, share: 50, state: 'active' }],
    }))
    wrapper.findAllComponents(NSwitch).forEach((toggle) => toggle.vm.$emit('update:value', false))
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Сумма включённых весов: 0%')
    expect(button('Сохранить в демо-Keitaro').attributes('disabled')).toBeUndefined()
    await button('Сохранить в демо-Keitaro').trigger('click')
    await flushPromises()
    expect(vi.mocked(demoKeitaro.save).mock.calls[2]![1].offers.every((o) => o.state === 'disabled')).toBe(true)
  })

  it('редактирует опубликованные веса и порядок отдельным API', async () => {
    vi.mocked(demoKeitaro.save).mockImplementation(async (_, body) => {
      const state = initial()
      state.campaigns[0]!.streams[1]!.offers = body.offers.map((o) => ({ ...o }))
      return state
    })
    wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('[101] A')
    expect(wrapper.text()).toContain('[102] B')
    const weights = wrapper.findAllComponents(NInputNumber)
    weights[0]!.vm.$emit('update:value', 30)
    weights[1]!.vm.$emit('update:value', 70)
    await wrapper.vm.$nextTick()
    await wrapper.findAll('button').filter((b) => b.text() === '↑')[1]!.trigger('click')
    await button('Сохранить в демо-Keitaro').trigger('click')
    await flushPromises()
    expect(demoKeitaro.save).toHaveBeenCalledExactlyOnceWith(1, {
      name: 'demo_2_offers', stream_id: 12,
      offers: [{ offer_id: 102, share: 70, state: 'active' }, { offer_id: 101, share: 30, state: 'active' }],
    })
    expect(wrapper.text()).toContain('Опубликованное состояние изменено')
  })

  it('добавляет третий оффер и показывает ошибку сохранения', async () => {
    vi.mocked(demoKeitaro.save).mockRejectedValue(new ApiError(502, 'demo_error', 'Не удалось сохранить'))
    wrapper = mountPage()
    await flushPromises()
    wrapper.findAllComponents(NInputNumber)[0]!.vm.$emit('update:value', 60)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Сумма включённых весов: 110%')
    expect(demoKeitaro.save).not.toHaveBeenCalled()
    wrapper.findAllComponents(NInputNumber)[1]!.vm.$emit('update:value', 40)
    wrapper.findAllComponents(NSelect).at(-1)!.vm.$emit('update:value', 103)
    await wrapper.vm.$nextTick()
    await button('Добавить в список').trigger('click')
    expect(wrapper.text()).toContain('[103] C')
    await button('Сохранить в демо-Keitaro').trigger('click')
    await flushPromises()
    expect(demoKeitaro.save).toHaveBeenCalledWith(1, expect.objectContaining({
      offers: [{ offer_id: 101, share: 60, state: 'active' }, { offer_id: 102, share: 40, state: 'active' }, { offer_id: 103, share: 0, state: 'active' }],
    }))
    expect(wrapper.text()).toContain('Не удалось сохранить')
  })
})
