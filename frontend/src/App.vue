<script setup lang="ts">
// Каркас приложения (≈ MainLayout.razor): провайдеры Naive UI, навигация, место для страницы.
import { NConfigProvider, NDialogProvider, NLayout, NLayoutContent, NLayoutHeader, NMessageProvider, NSpace } from 'naive-ui'
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <n-dialog-provider>
        <n-layout>
          <n-layout-header bordered class="header">
            <n-space align="center" :size="24">
              <b>Adrobot</b>
              <router-link to="/campaigns">Кампании</router-link>
              <router-link to="/create">Создать кампанию</router-link>
            </n-space>
          </n-layout-header>
          <n-layout-content class="content" content-style="max-width: 1100px; margin: 0 auto;">
            <!-- key: при переходе между кампаниями страница создаётся заново со своим состоянием -->
            <router-view :key="$route.fullPath" />
          </n-layout-content>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
</style>

<style scoped>
.header {
  padding: 12px 24px;
}
.content {
  padding: 16px 24px;
  min-height: calc(100vh - 50px);
  background: #f5f6f8;
}
.header a {
  text-decoration: none;
  color: #2080f0;
}
.header a.router-link-active {
  font-weight: 600;
}
</style>
