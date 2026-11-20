import { describe, expect, it } from 'vitest'
import { ApiError } from '@/shared/api/apiError'
import { fieldErrorsOf, requiredFieldErrors } from '@/creator/fieldErrors'

describe('fieldErrorsOf', () => {
  it.each([
    ['invalid_campaign_name', 'name'],
    ['invalid_geo', 'geos'],
    ['offer_not_found', 'offer'],
  ])('%s -> поле %s', (code, field) => {
    expect(fieldErrorsOf(new ApiError(422, code, 'текст'))).toEqual({ [field]: 'текст' })
  })

  it('ошибка Keitaro не привязана к полю', () => {
    expect(fieldErrorsOf(new ApiError(502, 'keitaro_error', 'boom'))).toBeNull()
  })
})

describe('requiredFieldErrors', () => {
  it('пустые поля — ошибки до запроса', () => {
    expect(Object.keys(requiredFieldErrors({ name: ' ', geos: '', offerId: null }))).toEqual(['name', 'geos', 'offer'])
  })

  it('заполненная форма — без ошибок', () => {
    expect(requiredFieldErrors({ name: 'promo', geos: 'AU', offerId: 1 })).toEqual({})
  })
})
