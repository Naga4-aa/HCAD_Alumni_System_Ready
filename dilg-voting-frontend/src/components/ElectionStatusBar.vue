<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const loading = ref(false)
const error = ref('')
const info = ref({
  has_election: false,
  status: 'none',
  name: '',
  start_at: null,
  end_at: null,
})

const loadStatus = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('election-status/')
    info.value = res.data
  } catch (e) {
    console.error(e)
    error.value = 'Failed to load election status.'
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)

const statusLabel = () => {
  if (!info.value.has_election || info.value.status === 'none') {
    return 'No election configured'
  }
  if (info.value.status === 'upcoming') return 'Election not started yet'
  if (info.value.status === 'active') return 'Election is active'
  if (info.value.status === 'ended') return 'Election has ended'
  return info.value.status
}

const statusClass = () => {
  switch (info.value.status) {
    case 'active':
      return 'bg-emerald-50 border-emerald-200 text-emerald-800'
    case 'upcoming':
      return 'bg-amber-50 border-amber-200 text-amber-800'
    case 'ended':
      return 'bg-slate-100 border-slate-300 text-slate-700'
    default:
      return 'bg-slate-100 border-slate-300 text-slate-500'
  }
}
</script>

<template>
  <div
    class="mb-4 text-xs rounded-xl border px-3 py-2 flex items-center justify-between gap-3"
    :class="statusClass()"
  >
    <div>
      <p class="font-semibold">
        {{ statusLabel() }}
      </p>
      <p v-if="info.has_election && info.name" class="text-[11px] opacity-80">
        {{ info.name }}
      </p>
    </div>

    <div v-if="loading" class="text-[11px] opacity-70">Checking...</div>
    <div v-else-if="error" class="text-[11px] opacity-80">
      {{ error }}
    </div>
  </div>
</template>
