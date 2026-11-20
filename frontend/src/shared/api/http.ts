/**
 * Единственное место, где фронт ходит в сеть (≈ typed HttpClient с BaseAddress = "/api").
 * Сериализует JSON, а любой неуспех превращает в ApiError — вызывающий код
 * работает либо с типизированным результатом, либо с ApiError, третьего не бывает.
 */
import { ApiError, ClientErrorCode, toApiError } from './apiError'

const BASE = '/api'

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface RequestOptions {
  /** Версия ресурса, которую видел пользователь: не совпала — бэкенд ответит 409 concurrency_conflict. */
  ifMatch?: number
}

export async function request<T>(method: Method, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.ifMatch !== undefined) headers['If-Match'] = `"${options.ifMatch}"`

  let response: Response
  try {
    response = await fetch(BASE + path, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
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
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>('POST', path, body, options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>('PUT', path, body, options),
  delete: <T>(path: string, options?: RequestOptions) => request<T>('DELETE', path, undefined, options),
}

/** Значение для query-строки — с экранированием. */
export function query(params: Record<string, string | number | boolean>): string {
  return '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
}
