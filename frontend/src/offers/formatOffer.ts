/** Единый формат оффера во всём интерфейсе: «[id] name» (FR-1.2, FR-2.2). */
export function formatOffer(offer: { id: number; name: string }): string {
  return `[${offer.id}] ${offer.name}`
}
