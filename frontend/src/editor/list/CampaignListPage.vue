<script setup lang="ts">
/** Выбор кампании (FR-2.1, Q2): по умолчанию наши, переключатель «все», открыть по ID. */
import { onMounted, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NInputNumber, NSpace, NSpin, NSwitch } from 'naive-ui'
import ErrorAlert from '@/shared/ui/ErrorAlert.vue'
import { asApiError } from '@/shared/api/errorTitle'
import type { ApiError } from '@/shared/api/apiError'
import { listCampaigns } from '../api/campaigns'
import type { CampaignSummaryDto } from '../api/types'

const router = useRouter()
const all = ref(false)
const campaigns = ref<CampaignSummaryDto[]>([])
const loading = ref(true) // список грузится сразу при открытии страницы
const error = shallowRef<ApiError | null>(null)
const openId = ref<number | null>(null)

let lastRequest = 0 // переключатель щёлкнули быстрее, чем ответил Keitaro, — старый ответ отбрасываем

async function load() {
  const current = ++lastRequest
  loading.value = true
  error.value = null
  try {
    const result = await listCampaigns(all.value)
    if (current === lastRequest) campaigns.value = result
  } catch (e) {
    if (current === lastRequest) error.value = asApiError(e)
  } finally {
    if (current === lastRequest) loading.value = false
  }
}

const open = (id: number) => router.push({ name: 'editor', params: { id } })
const openById = () => openId.value !== null && open(openId.value)

onMounted(load)
watch(all, load)
</script>

<template>
  <n-space vertical>
    <n-card size="small" title="Открыть по ID">
      <n-space>
        <n-input-number
          v-model:value="openId"
          :min="1"
          :precision="0"
          :show-button="false"
          placeholder="ID кампании"
          data-test="open-id"
          @keyup.enter="openById"
        />
        <n-button type="primary" :disabled="openId === null" data-test="open" @click="openById">Открыть</n-button>
      </n-space>
    </n-card>

    <n-card size="small" title="Кампании">
      <template #header-extra>
        <n-space align="center" size="small">
          <span>все кампании стенда</span>
          <n-switch v-model:value="all" data-test="all" />
        </n-space>
      </template>
      <ErrorAlert v-if="error" :error="error" @close="error = null" />
      <n-spin :show="loading">
        <table class="list">
          <thead>
            <tr>
              <th>ID</th>
              <th>Название</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in campaigns" :key="c.id" class="row" data-test="campaign-row" @click="open(c.id)">
              <td>{{ c.id }}</td>
              <td>{{ c.name }}</td>
            </tr>
            <tr v-if="!loading && !campaigns.length">
              <td colspan="2" class="empty">
                {{ all ? 'Кампаний нет' : 'Наших кампаний в обёртке пока нет — создайте или откройте по ID' }}
              </td>
            </tr>
          </tbody>
        </table>
      </n-spin>
    </n-card>
  </n-space>
</template>

<style scoped>
.list {
  width: 100%;
  border-collapse: collapse;
}
.list th {
  text-align: left;
  color: #666;
  font-weight: 500;
  border-bottom: 1px solid #eee;
  padding: 4px 8px;
}
.list td {
  padding: 6px 8px;
}
.row {
  cursor: pointer;
}
.row:hover {
  background: #f5f7fa;
}
.empty {
  color: #999;
}
</style>
