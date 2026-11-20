<script setup lang="ts">
// В Keitaro что-то поменяли, а у нас черновик: показываем, что именно, и как подтянуть (FR-2.3a).
import { NAlert } from 'naive-ui'

defineProps<{ changes: string[] }>()
</script>

<template>
  <n-alert type="warning" title="В Keitaro есть изменения, которых нет в обёртке" data-test="keitaro-changes">
    <ul class="list">
      <li v-for="c in changes" :key="c">{{ c }}</li>
    </ul>
    <div>
      Обёртка их не подтянула, чтобы не потерять ваш черновик. Fetch streams подтянет изменения, но черновик будет
      отброшен. Push в изменённый поток сначала покажет, что поменяли в Keitaro, и спросит, публиковать ли черновик
      поверх.
    </div>
  </n-alert>
</template>

<style scoped>
.list {
  margin: 4px 0 8px;
  padding-left: 20px;
}
</style>
