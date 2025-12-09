import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '../views/LandingView.vue'
import LoginView from '../views/LoginView.vue'
import InfoView from '../views/InfoView.vue'
import VoteView from '../views/VoteView.vue'
import NominationView from '../views/NominationView.vue'
import ResultsView from '../views/ResultsView.vue'
import AdminDashboard from '../views/AdminDashboard.vue'
import AdminLoginView from '../views/AdminLoginView.vue'
import { useAuthStore } from '../stores/auth'
import { useAdminAuthStore } from '../stores/adminAuth'

const routes = [
  { path: '/', name: 'home', component: LandingView },
  { path: '/info', name: 'info', component: InfoView },
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/vote',
    name: 'vote',
    component: VoteView,
    meta: { requiresVoter: true },
  },
  {
    path: '/nomination',
    name: 'nomination',
    component: NominationView,
    meta: { requiresVoter: true },
  },
  {
    path: '/results',
    name: 'results',
    component: ResultsView,
    meta: { requiresVoter: true },
  },
  { path: '/admin-login', name: 'admin-login', component: AdminLoginView },
  {
    path: '/admin',
    name: 'admin',
    component: AdminDashboard,
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const adminAuth = useAdminAuthStore()

  if (to.meta.requiresVoter && !authStore.isAuthenticated) {
    return next({ name: 'login' })
  }

  if (to.meta.requiresAdmin && !adminAuth.isAuthenticated) {
    return next({ name: 'admin-login' })
  }

  if (to.name === 'login' && authStore.isAuthenticated) {
    return next({ name: 'vote' })
  }

  if (to.name === 'admin-login' && adminAuth.isAuthenticated) {
    return next({ name: 'admin' })
  }

  next()
})

export default router
