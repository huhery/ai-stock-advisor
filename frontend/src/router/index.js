import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/Home.vue') },
  { path: '/chat', component: () => import('../views/Chat.vue') },
  { path: '/screening', component: () => import('../views/Screening.vue') },
  { path: '/freedom', component: () => import('../views/Freedom.vue') },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/backtest', component: () => import('../views/Backtest.vue') },
  { path: '/rules', component: () => import('../views/Rules.vue') },
  { path: '/news', component: () => import('../views/News.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes
})
