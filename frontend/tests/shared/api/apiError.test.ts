import { describe, expect, it } from 'vitest'
import { ClientErrorCode, toApiError } from '@/shared/api/apiError'

describe('toApiError', () => {
  it('берёт code и message из тела бэкенда и сохраняет детали', () => {
    const e = toApiError(409, { code: 'campaign_has_drafts', message: 'Есть черновики', changes: [1] })
    expect(e.status).toBe(409)
    expect(e.code).toBe('campaign_has_drafts')
    expect(e.message).toBe('Есть черновики')
    expect(e.detail<number[]>('changes')).toEqual([1])
  })

  it('422 самого FastAPI (detail[]) превращает в request_validation', () => {
    const e = toApiError(422, { detail: [{ loc: ['body', 'offer_id'], msg: 'Field required' }] })
    expect(e.code).toBe(ClientErrorCode.requestValidation)
    expect(e.message).toContain('Field required')
  })

  it('тело не JSON или чужой формат — общая ошибка со статусом', () => {
    const e = toApiError(500, null)
    expect(e.code).toBe(ClientErrorCode.unexpected)
    expect(e.message).toContain('500')
  })
})
