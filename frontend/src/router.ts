/** Маршруты SPA (≈ @page-директивы Razor-компонентов, только собранные в одном месте). */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import CreatorPage from './creator/CreatorPage.vue'
import CampaignListPage from './editor/list/CampaignListPage.vue'
import EditorPage from './editor/page/EditorPage.vue'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/campaigns' },
  { path: '/create', name: 'creator', component: CreatorPage },
  { path: '/campaigns', name: 'campaigns', component: CampaignListPage },
  {
    path: '/campaigns/:id(\\d+)',
    name: 'editor',
    component: EditorPage,
    // ≈ model binding: строку из URL превращаем в number-проп страницы
    props: (route) => ({ id: Number(route.params.id) }),
  },
  { path: '/:pathMatch(.*)*', redirect: '/campaigns' },
]

export const router = createRouter({ history: createWebHistory(), routes })
