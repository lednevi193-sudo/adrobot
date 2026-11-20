<script setup lang="ts">
// Поток без офферов (editable=false): только имя и позиция (FR-2.2).
import { NCard, NTag } from 'naive-ui'
import type { StreamView } from '../api/types'

defineProps<{ stream: StreamView }>()
</script>

<template>
  <n-card size="small" data-test="other-stream">
    <template #header>#{{ stream.position }} {{ stream.name }}</template>
    <template #header-extra>
      <n-tag size="small">не поток с офферами — только просмотр</n-tag>
    </template>
  </n-card>
</template>
