import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, ClientErrorCode } from '@/shared/api/apiError'
import { errorTitle } from '@/shared/api/errorTitle'
import { http } from '@/shared/api/http'
import { jsonResponse } from '../../editor/fixtures'

const mockFetch = (impl: () => Promise<Response>) => vi.stubGlobal('fetch', vi.fn(impl))
const failure = (p: Promise<unknown>) => p.then(() => null, (e: unknown) => e as ApiError)

afterEach(() => vi.unstubAllGlobals())

describe('http', () => {
  it('шлёт JSON на /api и возвращает тело', async () => {
    mockFetch(async () => jsonResponse(201, { id: 1 }))
    await expect(http.post('/campaigns', { name: 'x' })).resolves.toEqual({ id: 1 })

    const [url, init] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('/api/campaigns')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"name":"x"}')
    expect(init?.headers).toEqual({ 'Content-Type': 'application/json' })
  })

  it('ошибку бэкенда бросает как ApiError с code/message', async () => {
    mockFetch(async () => jsonResponse(502, { code: 'keitaro_error', message: 'Keitaro ответил 500: boom' }))
    const error = await failure(http.get('/offers'))
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 502, code: 'keitaro_error', message: 'Keitaro ответил 500: boom' })
    expect(errorTitle(error!)).toBe('Ошибка Keitaro')
  })

  it('504 — «Keitaro не отвечает»', async () => {
    mockFetch(async () => jsonResponse(504, { code: 'keitaro_unavailable', message: 'Keitaro не ответил вовремя' }))
    expect(errorTitle((await failure(http.get('/offers')))!)).toBe('Keitaro не отвечает')
  })

  it('сеть недоступна — ApiError со статусом 0', async () => {
    mockFetch(async () => Promise.reject(new TypeError('Failed to fetch')))
    const error = (await failure(http.get('/campaigns')))!
    expect(error.status).toBe(0)
    expect(error.code).toBe(ClientErrorCode.network)
    expect(errorTitle(error)).toBe('Нет связи с сервером')
  })

  it('ответ без JSON (прокси отдал HTML) — общая ошибка', async () => {
    mockFetch(async () => new Response('<html>Bad gateway</html>', { status: 502 }))
    expect((await failure(http.get('/campaigns')))!.code).toBe(ClientErrorCode.unexpected)
  })
})
