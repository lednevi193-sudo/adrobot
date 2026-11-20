/**
 * Как показывать состояние оффера в потоке (FR-2.4): подпись, серый ли, какие кнопки.
 * Это вид, а не правила: можно ли действие на самом деле, решает бэкенд (422 при нарушении).
 */
import type { AssignmentStatus, StreamOfferView } from '../api/types'

export const STATUS_LABEL: Record<AssignmentStatus, string> = {
  active: 'опубликован',
  pending_add: 'добавлен, не опубликован',
  pending_remove: 'удалён, не опубликован',
  removed: 'в архиве',
}

/** В раздаче — участвует в дележе трафика потока. */
export const isInRotation = (o: StreamOfferView) => o.status === 'active' || o.status === 'pending_add'

/** Серые строки: pending_remove и removed. */
export const isGrey = (o: StreamOfferView) => !isInRotation(o)

/** Подсказка FR-2.9a: в Keitaro сейчас другой вес. */
export function keitaroHint(o: StreamOfferView): string | null {
  return o.keitaro_share !== null && o.keitaro_share !== o.share ? `в Keitaro сейчас ${o.keitaro_share}%` : null
}
