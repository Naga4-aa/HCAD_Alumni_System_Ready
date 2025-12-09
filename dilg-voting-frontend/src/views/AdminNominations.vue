<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { useAdminAuthStore } from '../stores/adminAuth'

const admin = useAdminAuthStore()

const nominations = ref([])

async function loadNominations() {
  const res = await api.get('admin/nominations/', {
    headers: { 'X-Admin-Token': admin.token },
  })
  nominations.value = res.data
}

async function promote(id) {
  try {
    const res = await api.post(
      `admin/nominations/${id}/promote/`,
      {},
      { headers: { 'X-Admin-Token': admin.token } },
    )
    alert(`Promoted: ${res.data.candidate.full_name}`)
  } catch (err) {
    alert('Promotion failed.')
  }
}

onMounted(loadNominations)
</script>

<template>
  <div class="p-4">
    <h1 class="text-xl font-bold mb-4">Nominations</h1>

    <table class="w-full text-sm border">
      <thead class="bg-slate-100">
        <tr>
          <th class="p-2">Position</th>
          <th class="p-2">Nominee</th>
          <th class="p-2">Section</th>
          <th class="p-2">Reason</th>
          <th class="p-2"></th>
        </tr>
      </thead>

      <tbody>
        <tr v-for="n in nominations" :key="n.id" class="border-t">
          <td class="p-2">{{ n.position.name }}</td>
          <td class="p-2">{{ n.nominee_name }}</td>
          <td class="p-2">{{ n.nominee_section?.name || '—' }}</td>
          <td class="p-2">{{ n.reason || '—' }}</td>
          <td class="p-2">
            <button
              @click="promote(n.id)"
              class="px-3 py-1 bg-emerald-600 text-white rounded text-xs"
            >
              Promote to Candidate
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
