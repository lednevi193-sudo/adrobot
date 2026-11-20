<script setup lang="ts">
/**
 * Поле выбора оффера с автодополнением (FR-1.2). Нужно и создаватору, и Add offer (FR-2.6).
 * v-model — выбранный ID оффера; поиск идёт на бэкенд с задержкой (debounce),
 * чтобы не дёргать Keitaro на каждую букву.
 */
import { ref } from 'vue'
import { NSelect } from 'naive-ui'
import type { SelectOption } from 'naive-ui'
import { searchOffers } from './api'
import { formatOffer } from './formatOffer'
import { asApiError } from '@/shared/api/errorTitle'

const model = defineModel<number | null>({ default: null })
defineProps<{ placeholder?: string; status?: 'error' }>()

const options = ref<SelectOption[]>([])
const loading = ref(false)
const searchError = ref<string | null>(null)

let timer: ReturnType<typeof setTimeout> | undefined
let lastQuery = 0 // номер последнего запроса: устаревшие ответы отбрасываем

function onSearch(q: string) {
  clearTimeout(timer)
  timer = setTimeout(() => void load(q), 300)
}

async function load(q: string) {
  const current = ++lastQuery
  loading.value = true
  try {
    const offers = await searchOffers(q.trim())
    if (current !== lastQuery) return
    options.value = offers.map((o) => ({ label: formatOffer(o), value: o.id }))
    searchError.value = null
  } catch (e) {
    if (current === lastQuery) searchError.value = asApiError(e).message
  } finally {
    if (current === lastQuery) loading.value = false
  }
}

function onFocus() {
  if (!options.value.length) void load('')
}
</script>

<template>
  <div class="picker">
    <n-select
      v-model:value="model"
      filterable
      remote
      clearable
      :options="options"
      :loading="loading"
      :placeholder="placeholder ?? 'ID или часть названия'"
      :status="status"
      @search="onSearch"
      @focus="onFocus"
    />
    <div v-if="searchError" class="search-error">{{ searchError }}</div>
  </div>
</template>

<style scoped>
.picker {
  width: 100%;
}
.search-error {
  color: var(--n-error-color, #d03050);
  font-size: 12px;
  margin-top: 4px;
}
</style>
