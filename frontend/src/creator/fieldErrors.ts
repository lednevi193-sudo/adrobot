/**
 * Ошибка создания -> поле формы (FR-1.8: «ошибки валидации — у полей»).
 * Правила проверки живут в домене; здесь только «куда приклеить сообщение».
 */
import type { ApiError } from '@/shared/api/apiError'

export type CreatorField = 'name' | 'geos' | 'offer'

const FIELD_BY_CODE: Record<string, CreatorField> = {
  invalid_campaign_name: 'name',
  invalid_geo: 'geos',
  offer_not_found: 'offer',
}

export type FieldErrors = Partial<Record<CreatorField, string>>

/** null — ошибка не про конкретное поле (Keitaro, сеть): показать общей плашкой. */
export function fieldErrorsOf(error: ApiError): FieldErrors | null {
  const field = FIELD_BY_CODE[error.code]
  return field ? { [field]: error.message } : null
}

/** Пустые поля ловим до запроса: обязательность — свойство формы, а не правило домена. */
export function requiredFieldErrors(form: { name: string; geos: string; offerId: number | null }): FieldErrors {
  const errors: FieldErrors = {}
  if (!form.name.trim()) errors.name = 'Введите название'
  if (!form.geos.trim()) errors.geos = 'Укажите хотя бы одну страну, например AU или MX,AU,RO'
  if (form.offerId === null) errors.offer = 'Выберите оффер'
  return errors
}
