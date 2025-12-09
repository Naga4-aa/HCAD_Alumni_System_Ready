<!-- src/views/LoginView.vue -->
<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const fullName = ref('')
const batchYear = ref('')
const campus = ref('Digos City')
const consent = ref(false)
const localError = ref('')
const localMessage = ref('')

const handleLogin = async () => {
  localError.value = ''
  localMessage.value = ''

  if (!fullName.value.trim() || !batchYear.value) {
    localError.value = 'Full name and batch year are required.'
    return
  }

  if (!consent.value) {
    localError.value = 'Please confirm the consent checkbox.'
    return
  }

  try {
    await authStore.quickLogin(fullName.value.trim(), Number(batchYear.value), campus.value.trim(), consent.value)
    localMessage.value = `Welcome, ${authStore.voter.name}. Redirecting...`
    router.push('/vote')
  } catch (error) {
    localError.value = authStore.error || 'Login failed.'
  }
}
</script>

<template>
  <div class="min-h-[70vh] flex items-center justify-center px-4">
    <div class="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
      <div class="text-center space-y-1">
        <p class="text-xs uppercase tracking-wide text-emerald-600 font-semibold">HCAD Alumni</p>
        <h1 class="text-2xl font-semibold">Quick Entry</h1>
        <p class="text-xs text-slate-500">Enter your name and batch year to continue to nomination or voting.</p>
      </div>

      <div class="space-y-3">
        <div>
          <label class="block text-xs font-semibold text-slate-600 mb-1">Full name</label>
          <input
            v-model="fullName"
            type="text"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder="e.g. Juan Dela Cruz"
          />
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-600 mb-1">Batch year</label>
          <input
            v-model="batchYear"
            type="number"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder="e.g. 2005"
          />
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-600 mb-1">Campus / Chapter</label>
          <input
            v-model="campus"
            type="text"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-slate-50 text-slate-600 cursor-not-allowed"
            placeholder="Digos City"
            disabled
          />
        </div>

        <label class="flex items-center gap-2 text-[11px] text-slate-600">
          <input type="checkbox" v-model="consent" />
          I consent to participate and agree to the election data policy.
        </label>

        <button
          @click="handleLogin"
          :disabled="authStore.loading"
          class="w-full inline-flex justify-center items-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-emerald-700"
        >
          <span v-if="authStore.loading">Logging in...</span>
          <span v-else>Login</span>
        </button>

        <div class="min-h-[32px]">
          <p v-if="localMessage" class="text-xs text-emerald-600">
            {{ localMessage }}
          </p>
          <p v-if="localError" class="text-xs text-rose-600">
            {{ localError }}
          </p>
        </div>
      </div>

      <div class="text-[11px] text-slate-500 text-center space-y-1">
        <p>Admins / COMELEC: please use the admin login to manage voters, nominations, and results.</p>
        <RouterLink to="/admin-login" class="text-emerald-700 font-semibold">Go to admin login</RouterLink>
      </div>
    </div>
  </div>
</template>
