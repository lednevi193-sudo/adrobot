import { describe, expect, it } from 'vitest'
import { describeChange } from '@/editor/draft/describeChange'
import type { DraftChangeDto } from '@/editor/api/types'

const change = (c: Partial<DraftChangeDto>): DraftChangeDto => ({
  stream_id: 1,
  offer: { id: 25327, name: 'Offer B' },
  kind: 'add',
  share_before: null,
  share_after: null,
  ...c,
})

describe('describeChange', () => {
  it.each<[Partial<DraftChangeDto>, string]>([
    [{ kind: 'add' }, 'добавление оффера [25327] Offer B'],
    [{ kind: 'remove' }, 'удаление оффера [25327] Offer B'],
    [{ kind: 'pin', share_after: 50 }, 'закрепление [25327] Offer B на 50%'],
    [{ kind: 'unpin' }, 'открепление [25327] Offer B'],
    [{ kind: 'share', share_before: 34, share_after: 50 }, 'изменение веса [25327] Offer B: 34% → 50%'],
  ])('%o', (c, text) => {
    expect(describeChange(change(c))).toBe(text)
  })
})
