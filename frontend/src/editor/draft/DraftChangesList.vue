<script setup lang="ts">
// Список того, что будет отброшено. Потоки подписываем, если изменений из нескольких потоков (Fetch).
import { computed } from 'vue'
import type { DraftChangeDto } from '../api/types'
import { describeChange } from './describeChange'

const props = defineProps<{ changes: DraftChangeDto[]; streamNames?: Record<number, string> }>()

const groups = computed(() => {
  const byStream = new Map<number, DraftChangeDto[]>()
  for (const c of props.changes) byStream.set(c.stream_id, [...(byStream.get(c.stream_id) ?? []), c])
  return [...byStream.entries()].map(([streamId, items]) => ({
    streamId,
    title: props.streamNames?.[streamId] ?? `Поток ${streamId}`,
    items: items.map(describeChange),
  }))
})
const showTitles = computed(() => groups.value.length > 1 || props.streamNames !== undefined)
</script>

<template>
  <div v-if="!changes.length" data-test="no-changes">Изменений нет.</div>
  <div v-for="g in groups" :key="g.streamId" data-test="change-group">
    <div v-if="showTitles" class="title">{{ g.title }}</div>
    <ul>
      <li v-for="(text, i) in g.items" :key="i" data-test="change">{{ text }}</li>
    </ul>
  </div>
</template>

<style scoped>
.title {
  font-weight: 600;
  margin-top: 8px;
}
ul {
  margin: 4px 0;
  padding-left: 20px;
}
</style>
