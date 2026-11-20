<script setup lang="ts">
/**
 * Pin с вводом веса (FR-2.9): поповер с полем «закреплённый вес, %».
 * Тот же поповер редактирует уже закреплённый вес. Сумму закреплённых ≤ 100 проверяет домен.
 */
import { ref } from 'vue'
import { NButton, NInputNumber, NPopover, NSpace } from 'naive-ui'

const props = defineProps<{ share: number; pinned: boolean; loading?: boolean }>()
const emit = defineEmits<{ pin: [share: number] }>()

const show = ref(false)
const value = ref<number | null>(props.share)

function onShow(visible: boolean) {
  show.value = visible
  if (visible) value.value = props.share
}

function submit() {
  if (value.value === null) return
  emit('pin', value.value)
  show.value = false
}
</script>

<template>
  <n-popover trigger="click" :show="show" @update:show="onShow">
    <template #trigger>
      <n-button size="small" :loading="loading" data-test="pin">{{ pinned ? 'Edit pin' : 'Pin' }}</n-button>
    </template>
    <n-space vertical size="small">
      <div>Закреплённый вес, %</div>
      <n-input-number
        v-model:value="value"
        :min="0"
        :max="100"
        :precision="0"
        size="small"
        data-test="pin-share"
        @keyup.enter="submit"
      />
      <n-button type="primary" size="small" block :disabled="value === null" data-test="pin-submit" @click="submit">
        Закрепить
      </n-button>
    </n-space>
  </n-popover>
</template>
