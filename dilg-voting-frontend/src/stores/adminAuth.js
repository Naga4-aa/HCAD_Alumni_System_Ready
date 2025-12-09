import { defineStore } from 'pinia'
import api, { setAdminToken } from '../api'

export const useAdminAuthStore = defineStore('adminAuth', {
  state: () => ({
    token: localStorage.getItem('adminToken') || '',
    admin: localStorage.getItem('adminData') ? JSON.parse(localStorage.getItem('adminData')) : null,
    loading: false,
    error: '',
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
  },

  actions: {
    initFromStorage() {
      if (this.token) {
        setAdminToken(this.token)
      }
    },

    async login(username, password) {
      this.loading = true
      this.error = ''

      try {
        const res = await api.post('admin/login/', { username, password })

        this.token = res.data.token
        this.admin = res.data.admin

        localStorage.setItem('adminToken', this.token)
        localStorage.setItem('adminData', JSON.stringify(this.admin))

        setAdminToken(this.token)
      } catch (error) {
        console.error(error)
        if (error.response?.data?.error) {
          this.error = error.response.data.error
        } else {
          this.error = 'Admin login failed. Please try again.'
        }
        throw error
      } finally {
        this.loading = false
      }
    },

    logout() {
      this.token = ''
      this.admin = null
      this.error = ''
      localStorage.removeItem('adminToken')
      localStorage.removeItem('adminData')
      setAdminToken(null)
    },
  },
})
