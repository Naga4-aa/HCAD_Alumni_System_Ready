<!-- src/views/InfoView.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const election = ref(null)
const loading = ref(true)

const formatDate = (value) => {
  if (!value) return null
  try {
    return new Date(value).toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
  } catch (e) {
    return value
  }
}

const formatRange = (start, end) => {
  if (!start || !end) return 'To be announced'
  return `${formatDate(start)} -> ${formatDate(end)}`
}

const loadElection = async () => {
  try {
    const res = await api.get('elections/current/')
    election.value = res.data?.election || null
  } catch (err) {
    election.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadElection()
})
</script>

<template>
  <div class="space-y-4">
    <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <h2 class="text-xl font-semibold text-slate-900">Registration instructions</h2>
      <p class="text-sm text-slate-600 mt-2">
        Alumni can now enter with <strong>full name + batch/year</strong> (quick entry). Provide your campus/chapter and contact
        details to help COMELEC verify you. Consent is required to proceed.
      </p>
      <ul class="text-sm text-slate-700 list-disc list-inside mt-3 space-y-1">
        <li>Use your exact full name and batch/year so your record can be verified.</li>
        <li>Optional: add campus/chapter and contact info to help admins confirm identity.</li>
        <li>You must check the consent box: "I agree to the processing of my personal data for the purpose of elections."</li>
        <li>If admins disable quick entry, they may issue Voter IDs/PINs for manual login.</li>
      </ul>
    </div>

    <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-2 text-sm text-slate-700">
      <h3 class="text-lg font-semibold text-slate-900">Key rules</h3>
      <ul class="list-disc list-inside space-y-1">
        <li>
          Nomination period:
          <strong>{{ formatRange(election?.nomination_start, election?.nomination_end) }}</strong>
          (one nomination per voter).
        </li>
        <li>
          Voting period:
          <strong>{{ formatRange(election?.voting_start, election?.voting_end) }}</strong>
          (one vote per position, one ballot submission).
        </li>
        <li>Eligible voters: all verified alumni (no pre-loaded roster).</li>
        <li>Nominee data: name, position, batch/year, campus/chapter, contact, reason, photo.</li>
        <li>
          Results are visible to admins/Comelec only during voting;
          <span v-if="election?.results_at">official on {{ formatDate(election.results_at) }}.</span>
          <span v-else>official date to be announced.</span>
        </li>
      </ul>
      <p v-if="loading" class="text-[11px] text-slate-500">Loading schedule...</p>
    </div>
  </div>
</template>
