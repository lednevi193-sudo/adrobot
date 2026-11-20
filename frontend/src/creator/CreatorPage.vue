<script setup lang="ts">
/**
 * Создаватор (FR-1.1 – FR-1.8). Ошибки валидации — у полей (code -> поле),
 * ошибки Keitaro и сети — общей плашкой с текстом ответа.
 */
import { reactive, ref, shallowRef, watch } from 'vue'
import { NButton, NCard, NForm, NFormItem, NInput, NResult, NSpace } from 'naive-ui'
import OfferPicker from '@/offers/OfferPicker.vue'
import ErrorAlert from '@/shared/ui/ErrorAlert.vue'
import type { ApiError } from '@/shared/api/apiError'
import { asApiError } from '@/shared/api/errorTitle'
import type { CampaignView } from '@/editor/api/types'
import { createCampaign } from './api'
import { fieldErrorsOf, requiredFieldErrors, type CreatorField, type FieldErrors } from './fieldErrors'

const form = reactive({ name: '', geos: '', offerId: null as number | null })
const fieldErrors = ref<FieldErrors>({})
const error = shallowRef<ApiError | null>(null)
const creating = ref(false)
const created = shallowRef<CampaignView | null>(null)

// Поле поправили — его ошибка больше не актуальна
function clearOnEdit(field: CreatorField, source: () => unknown) {
  watch(source, () => {
    const { [field]: _, ...rest } = fieldErrors.value
    fieldErrors.value = rest
  })
}
clearOnEdit('name', () => form.name)
clearOnEdit('geos', () => form.geos)
clearOnEdit('offer', () => form.offerId)

async function submit() {
  if (creating.value) return
  error.value = null
  fieldErrors.value = requiredFieldErrors(form)
  if (Object.keys(fieldErrors.value).length || form.offerId === null) return

  creating.value = true
  try {
    created.value = await createCampaign({ name: form.name.trim(), geos: form.geos, offer_id: form.offerId })
  } catch (e) {
    const apiError = asApiError(e)
    const byField = fieldErrorsOf(apiError)
    if (byField) fieldErrors.value = byField
    else error.value = apiError
  } finally {
    creating.value = false
  }
}

function reset() {
  created.value = null
  Object.assign(form, { name: '', geos: '', offerId: null })
}

const status = (field: CreatorField) => (fieldErrors.value[field] ? 'error' : undefined)
</script>

<template>
  <n-card v-if="created" data-test="created">
    <n-result status="success" title="Кампания создана">
      <n-space vertical align="center">
        <div>
          ID: <b data-test="created-id">{{ created.id }}</b> — {{ created.name }}
        </div>
        <div v-if="created.tracker_url">
          Ссылка трекера:
          <a :href="created.tracker_url" target="_blank" rel="noopener noreferrer">{{ created.tracker_url }}</a>
        </div>
      </n-space>
      <template #footer>
        <n-space justify="center">
          <router-link :to="{ name: 'editor', params: { id: created.id } }">
            <n-button type="primary" data-test="go-editor">Открыть в редакторе</n-button>
          </router-link>
          <n-button @click="reset">Создать ещё</n-button>
        </n-space>
      </template>
    </n-result>
  </n-card>

  <n-card v-else title="Новая кампания" class="creator">
    <n-space vertical>
      <ErrorAlert v-if="error" :error="error" @close="error = null" />
      <n-form label-placement="top" @submit.prevent="submit">
        <n-form-item label="Name" :validation-status="status('name')" :feedback="fieldErrors.name" data-test="field-name">
          <n-input v-model:value="form.name" :maxlength="100" placeholder="promo" />
        </n-form-item>
        <n-form-item
          label="Geo"
          :validation-status="status('geos')"
          :feedback="fieldErrors.geos ?? 'ISO-коды стран через запятую: AU или MX,AU,RO'"
          data-test="field-geos"
        >
          <n-input v-model:value="form.geos" placeholder="MX,AU,RO" />
        </n-form-item>
        <n-form-item
          label="Offer"
          :validation-status="status('offer')"
          :feedback="fieldErrors.offer"
          data-test="field-offer"
        >
          <OfferPicker v-model="form.offerId" :status="status('offer')" />
        </n-form-item>
        <n-button type="primary" attr-type="submit" :loading="creating" data-test="create">Create</n-button>
      </n-form>
    </n-space>
  </n-card>
</template>

<style scoped>
.creator {
  max-width: 560px;
}
</style>
