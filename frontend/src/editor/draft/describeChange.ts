/** Изменение черновика -> строка «Будет отменено: …» (FR-2.10a). */
import { formatOffer } from '@/offers/formatOffer'
import type { DraftChangeDto } from '../api/types'

const pct = (v: number | null) => (v === null ? '—' : `${v}%`)

export function describeChange(c: DraftChangeDto): string {
  const offer = formatOffer(c.offer)
  switch (c.kind) {
    case 'add':
      return `добавление оффера ${offer}`
    case 'remove':
      return `удаление оффера ${offer}`
    case 'pin':
      return `закрепление ${offer} на ${pct(c.share_after)}`
    case 'unpin':
      return `открепление ${offer}`
    case 'share':
      return `изменение веса ${offer}: ${pct(c.share_before)} → ${pct(c.share_after)}`
  }
}
