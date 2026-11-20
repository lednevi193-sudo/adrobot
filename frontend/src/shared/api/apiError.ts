/**
 * Ошибка HTTP-вызова к нашему бэкенду (≈ ApiException, которую бросает typed HttpClient
 * после EnsureSuccessStatusCode, только с разобранным телом).
 *
 * Бэкенд всегда отвечает {code, message, ...детали}: code — для логики фронта,
 * message — уже готовый текст для пользователя (в т. ч. текст ответа Keitaro, FR-1.8).
 */
export class ApiError extends Error {
  constructor(
    /** HTTP-статус; 0 — ответа не было вовсе (сеть, бэкенд не запущен). */
    readonly status: number,
    readonly code: string,
    message: string,
    /** Всё тело ответа: оттуда берутся детали вроде changes и differences. */
    readonly body: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** Деталь ответа по имени, например error.detail<DraftChangeDto[]>('changes'). */
  detail<T>(key: string): T | undefined {
    return this.body[key] as T | undefined
  }
}

/** Коды, которые не придумал домен, а назначил сам клиент. */
export const ClientErrorCode = {
  network: 'network_error',
  requestValidation: 'request_validation',
  unexpected: 'http_error',
} as const

/** Тело ответа -> ApiError. Отдельная функция, чтобы покрыть её тестами без fetch. */
export function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body) && typeof body.code === 'string' && typeof body.message === 'string') {
    return new ApiError(status, body.code, body.message, body)
  }
  // 422 самого FastAPI (Pydantic не принял тело): {detail: [{loc, msg}, ...]}
  if (isRecord(body) && Array.isArray(body.detail)) {
    const text = body.detail.map((d) => (isRecord(d) ? String(d.msg) : String(d))).join('; ')
    return new ApiError(status, ClientErrorCode.requestValidation, `Некорректный запрос: ${text}`, body)
  }
  return new ApiError(status, ClientErrorCode.unexpected, `Сервер ответил ${status}`, isRecord(body) ? body : {})
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
