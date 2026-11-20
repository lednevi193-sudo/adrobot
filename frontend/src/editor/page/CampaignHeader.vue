<script setup lang="ts">
// Шапка редактора: кампания, ссылка трекера, наша/чужая, Fetch streams.
import { NButton, NCard, NSpace, NTag } from 'naive-ui'
import type { CampaignView } from '../api/types'

defineProps<{ campaign: CampaignView; fetching: boolean }>()
const emit = defineEmits<{ fetch: [] }>()
</script>

<template>
  <n-card size="small">
    <template #header>
      {{ campaign.name }}
      <n-tag v-if="campaign.is_ours" size="small" type="success" class="tag">наша</n-tag>
      <n-tag v-else size="small" class="tag" data-test="foreign">чужая — Push запрещён</n-tag>
    </template>
    <template #header-extra>
      <n-button :loading="fetching" data-test="fetch" @click="emit('fetch')">Fetch streams</n-button>
    </template>
    <n-space vertical size="small">
      <div>ID: {{ campaign.id }}</div>
      <div v-if="campaign.tracker_url">
        Ссылка трекера:
        <a :href="campaign.tracker_url" target="_blank" rel="noopener noreferrer">{{ campaign.tracker_url }}</a>
      </div>
    </n-space>
  </n-card>
</template>

<style scoped>
.tag {
  margin-left: 8px;
}
</style>
