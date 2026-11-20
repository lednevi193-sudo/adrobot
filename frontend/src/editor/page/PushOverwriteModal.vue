<script setup lang="ts">
/**
 * Push упёрся в правку, сделанную прямо в Keitaro после Fetch (409 stream_changed_in_keitaro).
 * Выбор пользователя: опубликовать черновик поверх этой правки или закрыть окно и сделать Fetch
 * (тогда черновик будет отброшен, FR-2.3a).
 */
import { NButton, NModal, NSpace } from 'naive-ui'

defineProps<{ show: boolean; differences: string[]; loading?: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; confirm: [] }>()
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="Поток поменяли в Keitaro"
    style="max-width: 560px"
    data-test="push-overwrite"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <p>После последнего Fetch в Keitaro изменилось:</p>
    <ul class="list">
      <li v-for="d in differences" :key="d">{{ d }}</li>
    </ul>
    <p>
      Push заменит это вашим черновиком. Чтобы сначала принять изменения из Keitaro, закройте окно и нажмите
      Fetch streams — черновик при этом будет отброшен.
    </p>
    <template #footer>
      <n-space justify="end">
        <n-button @click="emit('update:show', false)">Закрыть</n-button>
        <n-button type="warning" :loading="loading" data-test="push-overwrite-confirm" @click="emit('confirm')">
          Опубликовать поверх Keitaro
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.list {
  margin: 4px 0 8px;
  padding-left: 20px;
}
</style>
