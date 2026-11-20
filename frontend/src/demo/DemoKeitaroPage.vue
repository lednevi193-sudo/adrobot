<script setup lang="ts">
import { computed, nextTick, onMounted, ref, shallowRef, watch } from 'vue'
import { NAlert, NButton, NCard, NInput, NInputNumber, NSelect, NSpace, NSwitch } from 'naive-ui'
import ErrorAlert from '@/shared/ui/ErrorAlert.vue'
import type { ApiError } from '@/shared/api/apiError'
import { asApiError } from '@/shared/api/errorTitle'
import { demoKeitaro, type DemoState, type DemoWeight } from './api'

const state = shallowRef<DemoState>({ offers: [], campaigns: [] })
const campaignId = ref<number | null>(null)
const streamId = ref<number | null>(null)
const name = ref('')
const entries = ref<DemoWeight[]>([])
const addId = ref<number | null>(null)
const busy = ref(false)
const saved = ref(false)
const error = shallowRef<ApiError | null>(null)
const campaign = computed(() => state.value.campaigns.find((c) => c.id === campaignId.value))
const stream = computed(() => campaign.value?.streams.find((s) => s.id === streamId.value))
const total = computed(() => entries.value.filter((o) => o.state === 'active').reduce((sum, o) => sum + o.share, 0))
const available = computed(() => state.value.offers.filter((o) => !entries.value.some((e) => e.offer_id === o.id)))
const label = (id: number) => `[${id}] ${state.value.offers.find((o) => o.id === id)?.name ?? ''}`

watch(campaign, (c) => {
  name.value = c?.name ?? ''
  streamId.value = c?.streams.find((s) => s.id === streamId.value)?.id
    ?? c?.streams.find((s) => s.offers.length)?.id ?? c?.streams[0]?.id ?? null
  saved.value = false
})
watch(stream, (s) => {
  entries.value = s?.offers.map((o) => ({ ...o })) ?? []
  addId.value = null
  saved.value = false
})

async function load() {
  if (busy.value) return
  busy.value = true
  error.value = null
  try {
    state.value = await demoKeitaro.read()
    if (!state.value.campaigns.some((c) => c.id === campaignId.value)) campaignId.value = state.value.campaigns[0]?.id ?? null
  } catch (e) { error.value = asApiError(e) }
  finally { busy.value = false }
}
onMounted(load)

function add() {
  if (addId.value === null || !available.value.some((o) => o.id === addId.value)) return
  entries.value.push({ offer_id: addId.value, share: entries.value.length ? 0 : 100, state: 'active' })
  addId.value = null
  saved.value = false
}
function move(index: number, delta: number) {
  const other = index + delta
  if (other < 0 || other >= entries.value.length) return
  const copy = [...entries.value]
  ;[copy[index], copy[other]] = [copy[other]!, copy[index]!]
  entries.value = copy
  saved.value = false
}
async function save() {
  if (busy.value || !campaign.value || !stream.value) return
  busy.value = true
  saved.value = false
  error.value = null
  try {
    state.value = await demoKeitaro.save(campaign.value.id, { name: name.value, stream_id: stream.value.id, offers: entries.value })
    // Watchers обновят форму из опубликованного снимка перед сообщением об успехе.
    await nextTick()
    saved.value = true
  } catch (e) { error.value = asApiError(e) }
  finally { busy.value = false }
}
</script>

<template>
  <n-space vertical>
    <n-alert type="info">
      Это имитация правки в админке Keitaro: меняется опубликованное состояние, черновик Adrobot сохраняется.
      После сохранения откройте редактор в другой вкладке или нажмите в нём Fetch streams.
    </n-alert>
    <ErrorAlert v-if="error" :error="error" @close="error = null" />
    <n-space align="center">
      <n-button :loading="busy" @click="load">Обновить из демо-Keitaro</n-button>
      <router-link v-if="campaign" :to="{ name: 'editor', params: { id: campaign.id } }" target="_blank" rel="noopener">
        Открыть в Adrobot ↗
      </router-link>
    </n-space>
    <n-card title="Редактирование в демо-Keitaro">
      <n-space vertical>
        <label>Кампания</label>
        <n-select v-model:value="campaignId" :disabled="busy" :options="state.campaigns.map((c) => ({ label: `[${c.id}] ${c.name}`, value: c.id }))" />
        <template v-if="campaign">
          <label>Название кампании</label>
          <n-input v-model:value="name" :disabled="busy" :maxlength="255" @update:value="saved = false" />
          <label>Поток</label>
          <n-select v-model:value="streamId" :disabled="busy" :options="campaign.streams.map((s) => ({ label: `#${s.position} ${s.name}`, value: s.id }))" />
          <table v-if="stream" class="offers">
            <thead><tr><th>Оффер</th><th>Включён</th><th>Вес, %</th><th>Порядок / удалить</th></tr></thead>
            <tbody>
              <tr v-for="(entry, index) in entries" :key="entry.offer_id" :class="{ inactive: entry.state === 'disabled' }">
                <td>{{ label(entry.offer_id) }}</td>
                <td><n-switch
                  :value="entry.state === 'active'" :disabled="busy" :aria-label="`Оффер ${entry.offer_id} включён`"
                  @update:value="(value) => { entry.state = value ? 'active' : 'disabled'; saved = false }"
                ><template #checked>Вкл.</template><template #unchecked>Выкл.</template></n-switch></td>
                <td><n-input-number :value="entry.share" :disabled="busy" :min="0" :max="100" :precision="0" @update:value="(value) => { entry.share = value ?? 0; saved = false }" /></td>
                <td><n-space>
                  <n-button :disabled="busy || index === 0" @click="move(index, -1)">↑</n-button>
                  <n-button :disabled="busy || index === entries.length - 1" @click="move(index, 1)">↓</n-button>
                  <n-button :disabled="busy" @click="entries.splice(index, 1); saved = false">Удалить</n-button>
                </n-space></td>
              </tr>
            </tbody>
          </table>
          <div>Сумма включённых весов: {{ total }}%. Выключенные офферы сохраняют свой вес, но не участвуют в раздаче.</div>
          <n-select v-model:value="addId" placeholder="Добавить оффер" :disabled="busy || !available.length" :options="available.map((o) => ({ label: label(o.id), value: o.id }))" />
          <n-button :disabled="busy || addId === null" @click="add">Добавить в список</n-button>
          <n-button type="primary" :loading="busy" :disabled="!stream || !name.trim()" @click="save">
            Сохранить в демо-Keitaro
          </n-button>
        </template>
      </n-space>
    </n-card>
    <n-alert v-if="saved" type="success">Опубликованное состояние изменено. В редакторе Adrobot можно проверить обнаружение изменений и Fetch.</n-alert>
  </n-space>
</template>

<style scoped>
.offers { width: 100%; border-collapse: collapse; }
.offers th, .offers td { text-align: left; padding: 8px 4px; }
.offers td:nth-child(3) { width: 160px; }
.offers .inactive td { color: #888; }
</style>
