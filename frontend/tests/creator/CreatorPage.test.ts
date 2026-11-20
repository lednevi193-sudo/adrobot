import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import CreatorPage from '@/creator/CreatorPage.vue'
import { campaign, jsonResponse } from '../editor/fixtures'

// Вместо автодополнения — кнопка, которая «выбирает» оффер 18813
const OfferPickerStub = defineComponent({
  emits: ['update:modelValue'],
  setup: (_, { emit }) => () =>
    h('button', { 'data-test': 'pick-offer', type: 'button', onClick: () => emit('update:modelValue', 18813) }),
})

const mountPage = () =>
  mount(CreatorPage, {
    global: { stubs: { OfferPicker: OfferPickerStub, RouterLink: { template: '<a><slot /></a>' } } },
  })

async function fillAndSubmit(w: ReturnType<typeof mountPage>) {
  await w.find('[data-test=field-name] input').setValue('promo')
  await w.find('[data-test=field-geos] input').setValue('MX,ZZ')
  await w.find('[data-test=pick-offer]').trigger('click')
  await w.find('form').trigger('submit')
  await flushPromises()
}

const respond = (status: number, body: unknown) => vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(status, body)))

afterEach(() => vi.unstubAllGlobals())

describe('CreatorPage', () => {
  it('повторный submit во время Create не создаёт вторую кампанию', async () => {
    let resolve!: (response: Response) => void
    const fetchMock = vi.fn(() => new Promise<Response>((done) => { resolve = done }))
    vi.stubGlobal('fetch', fetchMock)
    const w = mountPage()
    await fillAndSubmit(w)
    await w.find('form').trigger('submit')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolve(jsonResponse(201, campaign({ id: 99 })))
    await flushPromises()
    expect(w.find('[data-test=created-id]').text()).toBe('99')
    w.unmount()
  })
  it('пустая форма — ошибки у полей, запрос не уходит', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const w = mountPage()
    await w.find('form').trigger('submit')
    expect(w.find('[data-test=field-name]').text()).toContain('Введите название')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('422 invalid_geo — сообщение у поля Geo', async () => {
    respond(422, { code: 'invalid_geo', message: 'Неизвестный код страны ZZ' })
    const w = mountPage()
    await fillAndSubmit(w)
    expect(w.find('[data-test=field-geos]').text()).toContain('Неизвестный код страны ZZ')
    expect(w.find('[data-test=error-message]').exists()).toBe(false)

    await w.find('[data-test=field-geos] input').setValue('MX')
    expect(w.find('[data-test=field-geos]').text()).not.toContain('Неизвестный код страны ZZ')
  })

  it('502 Keitaro — общая плашка с текстом Keitaro', async () => {
    respond(502, { code: 'campaign_creation_failed', message: 'Кампанию создать не удалось: 500' })
    const w = mountPage()
    await fillAndSubmit(w)
    expect(w.text()).toContain('Ошибка Keitaro')
    expect(w.find('[data-test=error-message]').text()).toContain('Кампанию создать не удалось')
  })

  it('успех — ID, ссылка трекера и переход в редактор', async () => {
    respond(201, campaign({ id: 99 }))
    const w = mountPage()
    await fillAndSubmit(w)
    expect(w.find('[data-test=created-id]').text()).toBe('99')
    expect(w.text()).toContain('https://kylovoa.com/AbCd')
    expect(w.find('[data-test=go-editor]').exists()).toBe(true)
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0]![1]!.body))
    expect(body).toEqual({ name: 'promo', geos: 'MX,ZZ', offer_id: 18813 })
  })
})
