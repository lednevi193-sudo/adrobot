<script setup lang="ts">
/**
 * Поток с офферами (FR-2.2 – FR-2.14). Жёлтый при has_draft; removed — в архиве;
 * push_blocker — предупреждение и заблокированный Push. Сама ничего не вызывает:
 * поднимает события, а команды выполняет useCampaignEditor (≈ EventCallback в Blazor).
 */
import { computed, ref } from 'vue'
import { NAlert, NButton, NCard, NCollapse, NCollapseItem, NSpace, NTag } from 'naive-ui'
import OfferPicker from '@/offers/OfferPicker.vue'
import ErrorAlert from '@/shared/ui/ErrorAlert.vue'
import type { ApiError } from '@/shared/api/apiError'
import type { StreamView } from '../api/types'
import OfferRow from './OfferRow.vue'

const props = defineProps<{ stream: StreamView; busy: string | null; error: ApiError | null }>()
const emit = defineEmits<{
  add: [offerId: number]
  remove: [offerId: number]
  bringBack: [offerId: number]
  pin: [offerId: number, share: number]
  unpin: [offerId: number]
  push: []
  cancel: []
  clearError: []
}>()

const current = computed(() => props.stream.offers.filter((o) => o.status !== 'removed'))
const archive = computed(() => props.stream.offers.filter((o) => o.status === 'removed'))

const newOfferId = ref<number | null>(null)
function add() {
  if (newOfferId.value === null) return
  emit('add', newOfferId.value)
  newOfferId.value = null
}

const is = (action: string) => props.busy === `${action}:${props.stream.id}`
</script>

<template>
  <n-card
    :class="{ draft: stream.has_draft }"
    size="small"
    data-test="stream-card"
    :data-draft="stream.has_draft"
  >
    <template #header>
      <span>#{{ stream.position }} {{ stream.name }}</span>
      <n-tag v-if="stream.has_draft" size="small" type="warning" class="tag" data-test="draft-tag">черновик</n-tag>
    </template>
    <template #header-extra>
      <n-space size="small">
        <n-button
          size="small"
          :disabled="!stream.has_draft"
          :loading="is('draft') || is('cancel')"
          data-test="cancel"
          @click="emit('cancel')"
        >
          Cancel
        </n-button>
        <n-button
          size="small"
          type="primary"
          :disabled="!stream.has_draft || stream.push_blocker !== null"
          :loading="is('push')"
          data-test="push"
          @click="emit('push')"
        >
          Push
        </n-button>
      </n-space>
    </template>

    <n-space vertical>
      <n-alert v-if="stream.push_blocker" type="warning" :show-icon="true" data-test="push-blocker">
        {{ stream.push_blocker }}
      </n-alert>
      <ErrorAlert v-if="error" :error="error" @close="emit('clearError')" />

      <table class="offers">
        <thead>
          <tr>
            <th>Оффер</th>
            <th>Вес</th>
            <th>Состояние</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <OfferRow
            v-for="o in current"
            :key="o.id"
            :offer="o"
            :busy="busy"
            :stream-id="stream.id"
            @remove="emit('remove', o.id)"
            @bring-back="emit('bringBack', o.id)"
            @pin="(share) => emit('pin', o.id, share)"
            @unpin="emit('unpin', o.id)"
          />
          <tr v-if="!current.length">
            <td colspan="4" class="empty">В потоке не осталось офферов</td>
          </tr>
        </tbody>
      </table>

      <n-collapse v-if="archive.length">
        <n-collapse-item :title="`Архив (${archive.length})`" name="archive" data-test="archive">
          <table class="offers">
            <tbody>
              <OfferRow
                v-for="o in archive"
                :key="o.id"
                :offer="o"
                :busy="busy"
                :stream-id="stream.id"
                @bring-back="emit('bringBack', o.id)"
              />
            </tbody>
          </table>
        </n-collapse-item>
      </n-collapse>

      <div class="add">
        <OfferPicker v-model="newOfferId" placeholder="Добавить оффер: ID или часть названия" />
        <n-button :disabled="newOfferId === null" :loading="is('add')" data-test="add-offer" @click="add">
          Add offer
        </n-button>
      </div>
    </n-space>
  </n-card>
</template>

<style scoped>
.draft {
  background: #fff8db;
  border-color: #f0c000;
}
.tag {
  margin-left: 8px;
}
.offers {
  width: 100%;
  border-collapse: collapse;
}
.offers th {
  text-align: left;
  font-weight: 500;
  color: #666;
  padding: 4px 8px;
  border-bottom: 1px solid #eee;
}
.empty {
  color: #999;
  padding: 8px;
}
.add {
  display: flex;
  gap: 8px;
}
</style>
