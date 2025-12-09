<!-- src/views/AdminLoginView.vue -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminAuthStore } from '../stores/adminAuth'

const router = useRouter()
const adminAuth = useAdminAuthStore()

const username = ref('')
const password = ref('')
const localError = ref('')
const localMessage = ref('')

const handleSubmit = async () => {
  localError.value = ''
  localMessage.value = ''

  if (!username.value || !password.value) {
    localError.value = 'Please enter username and password.'
    return
  }

  try {
    await adminAuth.login(username.value, password.value)
    localMessage.value = `Welcome, ${adminAuth.admin.full_name || adminAuth.admin.username}.`
    router.push('/admin')
  } catch (e) {
    localError.value = adminAuth.error || 'Admin login failed.'
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <h1 class="text-lg font-semibold mb-1 text-slate-800">Admin Login</h1>
      <p class="text-xs text-slate-500 mb-4">
        Restricted area. For authorized election administrators only.
      </p>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label class="block text-xs font-medium text-slate-600 mb-1">Username</label>
          <input
            v-model="username"
            type="text"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-slate-600 mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <button
          type="submit"
          :disabled="adminAuth.loading"
          class="w-full inline-flex justify-center items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-black disabled:bg-slate-300 disabled:cursor-not-allowed"
        >
          <span v-if="adminAuth.loading">Signing in...</span>
          <span v-else>Sign in as Admin</span>
        </button>
      </form>

      <div class="mt-3 space-y-1">
        <p v-if="localMessage" class="text-xs text-emerald-600">
          {{ localMessage }}
        </p>
        <p v-if="localError" class="text-xs text-rose-600">
          {{ localError }}
        </p>
      </div>

      <p class="mt-4 text-[11px] text-slate-400">
        Not an admin?
        <router-link to="/login" class="underline">Go to voter login</router-link>.
      </p>
    </div>
  </div>
</template>
