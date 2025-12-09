import { defineStore } from 'pinia'
import api, { setAuthToken } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    // Use sessionStorage so each browser tab keeps its own voter session instead of sharing
    token: sessionStorage.getItem('voterToken') || '',
    voter: sessionStorage.getItem('voterData') ? JSON.parse(sessionStorage.getItem('voterData')) : null,
    loading: false,
    error: '',
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
  },

  actions: {
    initFromStorage() {
      if (this.token) {
        setAuthToken(this.token)
      }
    },

    async login(voter_id, pin) {
      this.loading = true
      this.error = ''

      try {
        const res = await api.post('voter/login/', { voter_id, pin })

        this.token = res.data.token
        this.voter = res.data.voter

        sessionStorage.setItem('voterToken', this.token)
        sessionStorage.setItem('voterData', JSON.stringify(this.voter))

        setAuthToken(this.token)
      } catch (error) {
        console.error(error)
        if (error.response?.data?.error) {
          this.error = error.response.data.error
        } else {
          this.error = 'Login failed. Please try again.'
        }
        throw error
      } finally {
        this.loading = false
      }
    },

    async quickLogin(name, batch_year, campus_chapter, privacy_consent) {
      this.loading = true
      this.error = ''

      try {
        const payload = {
          name,
          batch_year,
          campus_chapter,
          privacy_consent,
        }
        const res = await api.post('voter/quick-login/', payload)

        this.token = res.data.token
        this.voter = res.data.voter

        sessionStorage.setItem('voterToken', this.token)
        sessionStorage.setItem('voterData', JSON.stringify(this.voter))

        setAuthToken(this.token)
      } catch (error) {
        console.error(error)
        if (error.response?.data?.error) {
          this.error = error.response.data.error
        } else {
          this.error = 'Login failed. Please try again.'
        }
        throw error
      } finally {
        this.loading = false
      }
    },

    logout() {
      this.token = ''
      this.voter = null
      this.error = ''
      sessionStorage.removeItem('voterToken')
      sessionStorage.removeItem('voterData')
      setAuthToken(null)
    },
  },
})
