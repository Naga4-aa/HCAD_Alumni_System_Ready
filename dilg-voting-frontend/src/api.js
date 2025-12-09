// src/api.js
import axios from 'axios'
import { useAuthStore } from './stores/auth'
import { useAdminAuthStore } from './stores/adminAuth'
import router from './router'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/',
})

// set / clear session token header
export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common['X-Session-Token'] = token
  } else {
    delete api.defaults.headers.common['X-Session-Token']
  }
}

export function setAdminToken(token) {
  if (token) {
    api.defaults.headers.common['X-Admin-Token'] = token
  } else {
    delete api.defaults.headers.common['X-Admin-Token']
  }
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const authStore = useAuthStore()
      const adminStore = useAdminAuthStore()
      const currentRoute = router.currentRoute.value
      const isAdminRoute =
        currentRoute?.meta?.requiresAdmin ||
        currentRoute?.name?.toString().startsWith('admin') ||
        currentRoute?.path?.startsWith('/admin')

      if (isAdminRoute) {
        if (adminStore?.isAuthenticated) {
          adminStore.logout()
        }
        router.push('/admin-login')
      } else {
        // Always send voter-side routes to voter login to avoid crossing contexts
        if (authStore?.isAuthenticated) {
          authStore.logout()
        }
        router.push('/login')
      }
    }
    return Promise.reject(error)
  },
)

export default api
