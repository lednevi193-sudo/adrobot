<script setup lang="ts">
/**
 * Подтверждение потери черновика: Cancel потока (FR-2.10a) и Fetch при черновике (FR-2.3a).
 * Одно окно на оба сценария — в обоих пользователь соглашается отбросить одно и то же.
 */
import { NModal } from 'naive-ui'
import type { DraftChangeDto } from '../api/types'
import DraftChangesList from './DraftChangesList.vue'

const show = defineModel<boolean>('show', { required: true })
defineProps<{
  title: string
  lead: string
  confirmText: string
  changes: DraftChangeDto[]
  streamNames?: Record<number, string>
  loading?: boolean
}>()
const emit = defineEmits<{ confirm: [] }>()

// false — окно не закрывается само: его закроет родитель, когда команда выполнится (виден loading)
function onConfirm() {
  emit('confirm')
  return false
}
</script>

<template>
  <n-modal
    v-model:show="show"
    preset="dialog"
    type="warning"
    :title="title"
    :positive-text="confirmText"
    negative-text="Не отменять"
    :loading="loading"
    @positive-click="onConfirm"
  >
    <p>{{ lead }}</p>
    <DraftChangesList :changes="changes" :stream-names="streamNames" />
  </n-modal>
</template>
