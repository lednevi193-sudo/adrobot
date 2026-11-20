<script setup lang="ts">
// Плашка ошибки API: заголовок по статусу, текст бэкенда и, если есть,
// список расхождений после Push (502 push_not_confirmed, FR-2.13 п. 3 / Q11).
import { computed } from 'vue'
import { NAlert } from 'naive-ui'
import type { ApiError } from '@/shared/api/apiError'
import { errorTitle } from '@/shared/api/errorTitle'

const props = defineProps<{ error: ApiError }>()
defineEmits<{ close: [] }>()

const title = computed(() => errorTitle(props.error))
const differences = computed(() => props.error.detail<string[]>('differences') ?? [])
</script>

<template>
  <n-alert type="error" :title="title" closable @close="$emit('close')">
    <div data-test="error-message">{{ error.message }}</div>
    <ul v-if="differences.length" data-test="error-details" class="details">
      <li v-for="d in differences" :key="d">{{ d }}</li>
    </ul>
  </n-alert>
</template>

<style scoped>
.details {
  margin: 8px 0 0;
  padding-left: 20px;
}
</style>
