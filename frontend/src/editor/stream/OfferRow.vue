<script setup lang="ts">
// Строка оффера в потоке: [id] name, вес, состояние, действия (FR-2.2, FR-2.4, FR-2.6 – FR-2.9a).
import { computed } from 'vue'
import { NButton, NSpace, NTag } from 'naive-ui'
import { formatOffer } from '@/offers/formatOffer'
import type { StreamOfferView } from '../api/types'
import { STATUS_LABEL, isGrey, isInRotation, keitaroHint } from './offerStatus'
import PinShareButton from './PinShareButton.vue'

const props = defineProps<{ offer: StreamOfferView; busy: string | null; streamId: number }>()
const emit = defineEmits<{ remove: []; bringBack: []; pin: [share: number]; unpin: [] }>()

const inRotation = computed(() => isInRotation(props.offer))
const hint = computed(() => keitaroHint(props.offer))
const isBusy = (action: string) => props.busy === `${action}:${props.streamId}:${props.offer.id}`
</script>

<template>
  <tr :class="{ grey: isGrey(offer) }" data-test="offer-row" :data-status="offer.status">
    <td>
      {{ formatOffer(offer) }}
      <n-tag v-if="offer.status === 'pending_add'" size="small" type="success" data-test="new">new</n-tag>
      <n-tag v-if="offer.pinned" size="small" type="info" data-test="pinned">закреплён</n-tag>
    </td>
    <td class="share">
      <span data-test="share">{{ offer.share }}%</span>
      <div v-if="hint" class="hint" data-test="keitaro-hint">{{ hint }}</div>
    </td>
    <td>{{ STATUS_LABEL[offer.status] }}</td>
    <td>
      <n-space size="small" :wrap="false">
        <template v-if="inRotation">
          <n-button size="small" :loading="isBusy('remove')" data-test="remove" @click="emit('remove')">Remove</n-button>
          <PinShareButton
            :share="offer.share"
            :pinned="offer.pinned"
            :loading="isBusy('pin')"
            @pin="(share) => emit('pin', share)"
          />
          <n-button v-if="offer.pinned" size="small" :loading="isBusy('unpin')" data-test="unpin" @click="emit('unpin')">
            Unpin
          </n-button>
        </template>
        <n-button v-else size="small" :loading="isBusy('bring-back')" data-test="bring-back" @click="emit('bringBack')">
          Bring back
        </n-button>
      </n-space>
    </td>
  </tr>
</template>

<style scoped>
.grey td {
  color: #999;
}
.share {
  white-space: nowrap;
}
.hint {
  font-size: 12px;
  color: #b58105;
}
td {
  padding: 6px 8px;
  vertical-align: middle;
}
</style>
