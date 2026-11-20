/**
 * Заголовок для окна/плашки ошибки: чья это ошибка и что делать.
 * Сам текст (message) пишет бэкенд — здесь только «рамка» по статусу.
 */
import { ApiError, ClientErrorCode } from './apiError'

export function errorTitle(error: ApiError): string {
  if (error.code === ClientErrorCode.network) return 'Нет связи с сервером'
  switch (error.status) {
    case 403:
      return 'Действие запрещено'
    case 404:
      return 'Не найдено'
    case 409:
      return 'Конфликт'
    case 422:
      return 'Проверьте данные'
    case 502:
      return 'Ошибка Keitaro'
    case 504:
      return 'Keitaro не отвечает'
    default:
      return 'Ошибка сервера'
  }
}

/** Любое пойманное исключение -> ApiError (программные ошибки тоже показываем, а не глотаем). */
export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  const message = error instanceof Error ? error.message : String(error)
  return new ApiError(-1, 'client_error', message)
}
