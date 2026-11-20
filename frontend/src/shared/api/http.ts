/**
 * Единственное место, где фронт ходит в сеть (≈ typed HttpClient с BaseAddress = "/api").
 * Сериализует JSON, а любой неуспех превращает в ApiError — вызывающий код
 * работает либо с типизированным результатом, либо с ApiError, третьего не бывает.
 */
import { ApiError, ClientErrorCode, toApiError } from './apiError'

const BASE = '/api'

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, ClientErrorCode.network, 'Сервер обёртки недоступен — проверьте, что бэкенд запущен')
  }

  const payload = await readJson(response)
  if (!response.ok) throw toApiError(response.status, payload)
  return payload as T
}

/** Тело как JSON; null — тела нет или это не JSON (например, HTML-страница прокси). */
async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

/** Значение для query-строки — с экранированием. */
export function query(params: Record<string, string | number | boolean>): string {
  return '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
}
