import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/emails',
  },
  {
    path: '/emails',
    name: 'emails',
    component: () => import('./pages/EmailsPage.vue'),
  },
  {
    path: '/emails/:id',
    name: 'email-detail',
    component: () => import('./pages/EmailsPage.vue'),
    props: true,
  },
  {
    path: '/scanner',
    name: 'scanner',
    component: () => import('./pages/ScannerPage.vue'),
  },
  {
    path: '/statistics',
    name: 'statistics',
    component: () => import('./pages/StatisticsPage.vue'),
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('./pages/LogsPage.vue'),
  },
  {
    path: '/projects',
    name: 'projects',
    component: () => import('./pages/ProjectsPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
