<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const loading = ref(false)
const error = ref('')
const election = ref(null)

const loadStatus = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('election-status/')
    election.value = res.data
  } catch (err) {
    console.error('election-status error', err)
    error.value = 'Failed to load election status.'
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="mb-4">
    <!-- Error -->
    <div
      v-if="error"
      class="rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700 flex items-center justify-between"
    >
      <span>No election status available.</span>
      <span>{{ error }}</span>
    </div>

    <!-- Active election -->
    <div
      v-else-if="election && election.is_active"
      class="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 flex items-center justify-between"
    >
      <div>
        <span class="font-semibold">Election is active</span>
        <span class="ml-2 text-[11px] text-emerald-900/80">
          {{ election.name }}
        </span>
      </div>
    </div>

    <!-- No election -->
    <div
      v-else
      class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
    >
      No election configured.
    </div>
  </div>
</template>
