<script setup lang="ts">
/**
 * Редактор кампании (FR-2.x). Страница только связывает: состояние и команды —
 * в useCampaignEditor, вид потоков — в StreamCard, подтверждения — ConfirmDiscardModal.
 */
import { computed, onMounted, ref } from 'vue'
import { NSpace, NSpin, useMessage } from 'naive-ui'
import ErrorAlert from '@/shared/ui/ErrorAlert.vue'
import type { DraftChangeDto } from '../api/types'
import ConfirmDiscardModal from '../draft/ConfirmDiscardModal.vue'
import OtherStreamCard from '../stream/OtherStreamCard.vue'
import StreamCard from '../stream/StreamCard.vue'
import { useCampaignEditor } from '../useCampaignEditor'
import CampaignHeader from './CampaignHeader.vue'
import KeitaroChangesAlert from './KeitaroChangesAlert.vue'

const props = defineProps<{ id: number }>()
const editor = useCampaignEditor(props.id)
const { campaign, streams, keitaroChanges, lastError, busy, stream: cmd } = editor
const message = useMessage()

onMounted(editor.load)

const campaignError = computed(() => (lastError.value?.streamId === null ? lastError.value.error : null))
const errorFor = (sid: number) => (lastError.value?.streamId === sid ? lastError.value.error : null)
const streamNames = computed(() =>
  Object.fromEntries((campaign.value?.streams ?? []).map((s) => [s.id, `#${s.position} ${s.name}`])),
)

// ---- Fetch streams (FR-2.2, FR-2.3a) ----
const fetchConfirm = ref<DraftChangeDto[] | null>(null)
async function onFetch() {
  const outcome = await editor.fetchStreams()
  if (outcome.kind === 'needs_confirmation') fetchConfirm.value = outcome.changes
  else if (outcome.kind === 'done') message.success('Потоки синхронизированы с Keitaro')
}
async function confirmFetch() {
  const outcome = await editor.fetchStreams(true)
  fetchConfirm.value = null
  if (outcome.kind === 'done') message.success('Черновики отброшены, потоки синхронизированы с Keitaro')
}

// ---- Cancel (FR-2.10, FR-2.10a) ----
const cancelConfirm = ref<{ streamId: number; changes: DraftChangeDto[] } | null>(null)
async function onCancel(streamId: number) {
  const changes = await cmd.draft(streamId)
  if (changes) cancelConfirm.value = { streamId, changes }
}
async function confirmCancel() {
  if (!cancelConfirm.value) return
  const ok = await cmd.cancel(cancelConfirm.value.streamId)
  cancelConfirm.value = null
  if (ok) message.success('Черновик потока отменён')
}

// ---- Push (FR-2.13, FR-2.14) ----
async function onPush(streamId: number) {
  if (await cmd.push(streamId)) message.success('Опубликовано в Keitaro')
}

const modalShow = (target: typeof fetchConfirm | typeof cancelConfirm) =>
  computed({
    get: () => target.value !== null,
    set: (v: boolean) => {
      if (!v) target.value = null
    },
  })
const showFetchConfirm = modalShow(fetchConfirm)
const showCancelConfirm = modalShow(cancelConfirm)
</script>

<template>
  <n-space vertical>
    <ErrorAlert v-if="campaignError" :error="campaignError" @close="editor.clearError" />
    <n-spin v-if="!campaign && busy === 'open'" />

    <template v-if="campaign">
      <CampaignHeader :campaign="campaign" :fetching="busy === 'fetch'" @fetch="onFetch" />
      <KeitaroChangesAlert v-if="keitaroChanges.length" :changes="keitaroChanges" />

      <template v-for="s in streams" :key="s.id">
        <StreamCard
          v-if="s.editable"
          :stream="s"
          :busy="busy"
          :error="errorFor(s.id)"
          @add="(oid) => cmd.addOffer(s.id, oid)"
          @remove="(oid) => cmd.removeOffer(s.id, oid)"
          @bring-back="(oid) => cmd.bringBack(s.id, oid)"
          @pin="(oid, share) => cmd.pin(s.id, oid, share)"
          @unpin="(oid) => cmd.unpin(s.id, oid)"
          @push="onPush(s.id)"
          @cancel="onCancel(s.id)"
          @clear-error="editor.clearError"
        />
        <OtherStreamCard v-else :stream="s" />
      </template>
      <div v-if="!streams.length">В обёртке ещё нет потоков этой кампании — нажмите Fetch streams.</div>
    </template>
  </n-space>

  <ConfirmDiscardModal
    v-model:show="showFetchConfirm"
    title="Fetch streams отбросит черновики"
    lead="В кампании есть неопубликованные изменения. Перед синхронизацией с Keitaro будет отменено:"
    confirm-text="Отбросить и синхронизировать"
    :changes="fetchConfirm ?? []"
    :stream-names="streamNames"
    :loading="busy === 'fetch'"
    @confirm="confirmFetch"
  />
  <ConfirmDiscardModal
    v-model:show="showCancelConfirm"
    title="Отменить черновик потока?"
    lead="Поток вернётся к опубликованному в Keitaro состоянию. Будет отменено:"
    confirm-text="Отменить изменения"
    :changes="cancelConfirm?.changes ?? []"
    :loading="busy?.startsWith('cancel:')"
    @confirm="confirmCancel"
  />
</template>
