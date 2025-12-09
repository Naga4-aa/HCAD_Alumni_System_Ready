<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { useAdminAuthStore } from '../stores/adminAuth'

const adminAuth = useAdminAuthStore()

const loading = ref(false)
const error = ref('')
const tally = ref([])

const loadTally = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('tally/', {
      headers: {
        'X-Admin-Token': adminAuth.token,
      },
    })
    tally.value = res.data
  } catch (err) {
    console.error(err)
    if (err.response?.status === 403) {
      error.value = 'Admin access required. Please log in as admin.'
    } else {
      error.value = 'Failed to load tally.'
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadTally)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-slate-800">Election Tally</h2>
      <button
        @click="loadTally"
        :disabled="loading"
        class="text-xs rounded-lg border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-60"
      >
        {{ loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <p class="text-xs text-slate-500">Aggregated votes grouped by position and candidate.</p>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

    <div v-if="loading" class="text-sm text-slate-500">Loading tally...</div>

    <div v-else class="space-y-4">
      <div
        v-for="position in tally"
        :key="position.position_id"
        class="bg-white rounded-2xl shadow-sm border border-slate-200 p-4"
      >
        <div class="flex items-center justify-between mb-2">
          <div>
            <h3 class="text-sm font-semibold text-slate-800">
              {{ position.position }}
            </h3>
            <p class="text-[11px] text-slate-500">Level: {{ position.level || 'N/A' }}</p>
          </div>
        </div>

        <table class="w-full text-xs border-t border-slate-100 mt-2">
          <thead>
            <tr class="text-left text-slate-500">
              <th class="py-2 pr-2">Candidate</th>
              <th class="py-2 pr-2">Party</th>
              <th class="py-2 text-right">Votes</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in position.candidates"
              :key="c.candidate_id"
              class="border-t border-slate-100"
            >
              <td class="py-1 pr-2 text-slate-800">
                {{ c.full_name }}
              </td>
              <td class="py-1 pr-2 text-slate-500">
                {{ c.party || '—' }}
              </td>
              <td class="py-1 text-right font-semibold">
                {{ c.votes }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="tally.length === 0" class="text-xs text-slate-500">
        No tally data yet. Cast some votes first.
      </p>
    </div>
  </div>
</template>
