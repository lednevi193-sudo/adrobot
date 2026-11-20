// Точка входа (≈ Program.cs): создаём приложение, подключаем роутер, монтируем в #app.
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'

createApp(App).use(router).mount('#app')
