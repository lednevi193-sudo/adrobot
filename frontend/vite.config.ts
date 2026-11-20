/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// В разработке Vite отдаёт фронт на :5173 и проксирует /api на FastAPI (NFR-1) —
// браузер видит один origin, CORS не нужен (≈ dev-прокси SPA в ASP.NET Core).
// Собранную статику (dist/) раздаёт сам FastAPI.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    // Naive UI целиком — ~530 КБ; для внутреннего инструмента без code splitting это нормально
    chunkSizeWarningLimit: 800,
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
  },
})
