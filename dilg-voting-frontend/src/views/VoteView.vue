<!-- src/views/VoteView.vue -->
<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { countdownTo, formatDateTime, toMs } from '../utils/time'

const authStore = useAuthStore()

const election = ref(null)
const positions = ref([])
const candidatesByPosition = ref({})
const selections = ref({})
const candidatePlaceholder =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect width='80' height='80' rx='40' fill='%23dfe4ea'/><path d='M40 40a12 12 0 1 0-0.001-24.001A12 12 0 0 0 40 40zm0 8c-11.046 0-20 6.268-20 14v4h40v-4c0-7.732-8.954-14-20-14z' fill='%2390a4ae'/></svg>"
const hasVoted = ref(false)
const loading = ref(false)
const submitting = ref(false)
const statusMessage = ref('')
const errorMessage = ref('')
const consent = ref(false)
const now = ref(Date.now())
const lastElectionId = ref(null)
const lastSignature = ref(null)
const draftRestored = ref(false)

const isDemoMode = computed(() => election.value?.mode === 'demo')
const phase = computed(() => {
  if (isDemoMode.value && election.value?.demo_phase) {
    return election.value.demo_phase
  }
  return election.value?.phase || 'closed'
})
const votingOpen = computed(() => phase.value === 'voting')
const hasActiveElection = computed(() => !!election.value && election.value.is_active)
const hasTimeline = computed(() => {
  const e = election.value
  if (isDemoMode.value) return true
  if (!e || !e.is_active) return false
  const required = [e.nomination_start, e.nomination_end, e.voting_start, e.voting_end]
  return required.every((v) => {
    const ts = toMs(v)
    return ts !== null && !Number.isNaN(ts)
  })
})

const resultsPostedVisible = computed(() => {
  if (isDemoMode.value) return false
  if (!election.value?.results_published) return false
  return ['closed', 'closed_pending_results'].includes(phase.value)
})

const showBallot = computed(() => hasActiveElection.value && (hasTimeline.value || isDemoMode.value) && votingOpen.value)

const votingTiming = computed(() => {
  if (isDemoMode.value) {
    return {
      label: 'Demo mode',
      countdown: null,
      detail: `Phase: ${phase.value}`,
      tone: 'info',
    }
  }
  if (!hasActiveElection.value || !hasTimeline.value) return null
  const start = toMs(election.value.voting_start)
  const end = toMs(election.value.voting_end)
  const resultsAt = toMs(election.value.results_at)
  const current = now.value

  if (start && current < start) {
    return {
      label: 'Voting starts in',
      countdown: countdownTo(start, current),
      detail: formatDateTime(election.value.voting_start),
      tone: 'info',
    }
  }
  if (end && current <= end) {
    return {
      label: 'Voting ends in',
      countdown: countdownTo(end, current),
      detail: formatDateTime(election.value.voting_end),
      tone: 'success',
    }
  }
  if (resultsPostedVisible.value && resultsAt) {
    return {
      label: 'Results posted',
      countdown: null,
      detail: formatDateTime(election.value.results_at),
      tone: 'muted',
    }
  }
  if (resultsAt && !election.value.results_published) {
    return {
      label: 'Awaiting results',
      countdown: countdownTo(resultsAt, current),
      detail: formatDateTime(election.value.results_at),
      tone: 'warning',
    }
  }
  if (end) {
    return {
      label: 'Voting closed',
      countdown: null,
      detail: formatDateTime(election.value.voting_end),
      tone: 'muted',
    }
  }
  return null
})

const resetNotice = computed(() => {
  if (!election.value) return 'No active election. Waiting for admin to open nominations/voting.'
  if (isDemoMode.value) return 'Demo mode active. Phases are controlled manually by the admin.'
  if (!election.value.is_active) return 'Election timeline reset. Please check back once admin reactivates.'
  if (!hasTimeline.value) return 'Timeline not set. Waiting for admin to provide dates.'
  if (election.value.results_published && !resultsPostedVisible.value) {
    return 'Election was reset. Timeline updated; please review dates before voting.'
  }
  return ''
})

const loadElection = async () => {
  const res = await api.get('elections/current/')
  election.value = res.data?.election || null
}

const loadPositions = async () => {
  const res = await api.get('positions/')
  positions.value = res.data || []
}

const loadCandidatesForPosition = async (positionId) => {
  const res = await api.get('candidates/', { params: { position: positionId } })
  candidatesByPosition.value = {
    ...candidatesByPosition.value,
    [positionId]: res.data || [],
  }
}

const loadAllCandidates = async () => {
  candidatesByPosition.value = {}
  for (const pos of positions.value) {
    await loadCandidatesForPosition(pos.id)
  }
}

const clearBallot = () => {
  positions.value = []
  candidatesByPosition.value = {}
  selections.value = {}
  hasVoted.value = false
  consent.value = false
  draftRestored.value = false
}

const loadMyVotes = async () => {
  try {
    const res = await api.get('my-votes/')
    if (Array.isArray(res.data) && res.data.length) {
      hasVoted.value = true
      const map = {}
      res.data.forEach((v) => {
        map[v.position_id] = v.candidate_id
      })
      selections.value = map
    }
  } catch (err) {
    hasVoted.value = false
  }
}

const draftKey = () => {
  if (!authStore.voter || !election.value?.id) return null
  return `ballotDraft:${authStore.voter.voter_id}:${election.value.id}`
}

const saveDraft = () => {
  if (hasVoted.value) return
  const key = draftKey()
  if (!key) return
  const payload = {
    selections: Object.fromEntries(
      Object.entries(selections.value || {}).map(([pid, cid]) => [pid, Number(cid)]),
    ),
    consent: consent.value,
  }
  localStorage.setItem(key, JSON.stringify(payload))
}

const restoreDraft = () => {
  if (draftRestored.value) return
  const key = draftKey()
  if (!key) return
  const raw = localStorage.getItem(key)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    const restoredSelections = Object.fromEntries(
      Object.entries(parsed.selections || {}).map(([pid, cid]) => [Number(pid), Number(cid)]),
    )
    selections.value = restoredSelections
    consent.value = !!parsed.consent
    draftRestored.value = true
  } catch (_) {
    // ignore malformed draft
  }
}

const clearDraft = () => {
  const key = draftKey()
  if (key) localStorage.removeItem(key)
}

const submitBallot = async () => {
  if (!consent.value) {
    errorMessage.value = 'Please agree to the data processing consent.'
    return
  }
  const expected = positions.value.map((p) => String(p.id))
  const provided = Object.keys(selections.value || {})
  if (expected.some((id) => !provided.includes(id))) {
    errorMessage.value = 'Please select one candidate for every position.'
    return
  }

  submitting.value = true
  statusMessage.value = ''
  errorMessage.value = ''

  try {
    await api.post('ballot/submit/', { votes: selections.value })
    statusMessage.value = 'Ballot submitted. Thank you for voting!'
    hasVoted.value = true
    clearDraft()
  } catch (err) {
    console.error(err)
    errorMessage.value = err.response?.data?.error || 'Failed to submit ballot.'
  } finally {
    submitting.value = false
  }
}

let timerId
let countdownTimer
let refreshingElection = false

const buildSignature = () => {
  if (!election.value?.id) return null
  return [
    election.value.id,
    election.value.mode,
    election.value.demo_phase || '',
    election.value.phase || '',
    election.value.voting_start || '',
    election.value.voting_end || '',
    election.value.results_at || '',
    election.value.results_published ? '1' : '0',
  ].join('|')
}

const tick = async () => {
  now.value = Date.now()
  if (refreshingElection) return
  refreshingElection = true
  try {
    await loadElection()
    const currentId = election.value?.id || null
    const active = !!election.value?.is_active
    const timelineReady = hasTimeline.value
    const signature = buildSignature()
    if (!active || !currentId || !timelineReady) {
      clearBallot()
      lastElectionId.value = null
      lastSignature.value = null
      return
    }
    const changed =
      lastElectionId.value !== currentId ||
      lastSignature.value !== signature

    if (changed) {
      lastElectionId.value = currentId
      lastSignature.value = signature
      await loadPositions()
      await loadAllCandidates()
      await loadMyVotes()
      restoreDraft()
    } else {
      // Refresh candidates periodically so new photos/bios from admins appear without manual reload.
      await loadAllCandidates()
    }
  } catch (e) {
    // ignore transient errors on poll
  } finally {
    refreshingElection = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await loadElection()
    const currentId = election.value?.id || null
    if (currentId && election.value.is_active && hasTimeline.value) {
      lastElectionId.value = currentId
      lastSignature.value = buildSignature()
      await loadPositions()
      await loadAllCandidates()
      await loadMyVotes()
      restoreDraft()
    }
  } finally {
    loading.value = false
  }
  countdownTimer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
  timerId = setInterval(tick, 15000)
})

onUnmounted(() => {
  if (timerId) clearInterval(timerId)
  if (countdownTimer) clearInterval(countdownTimer)
})

watch(
  () => selections.value,
  () => saveDraft(),
  { deep: true },
)

watch(
  () => consent.value,
  () => saveDraft(),
)
</script>

<template>
  <div class="space-y-4">
    <div class="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-3">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-wide text-emerald-600 font-semibold">Voting</p>
          <h2 class="text-lg font-semibold leading-tight">Cast your ballot</h2>
          <p class="text-xs text-slate-500">One vote per position. Submit once.</p>
        </div>
        <div class="text-xs text-slate-600 space-y-0.5 sm:text-right">
          <p class="font-semibold">Phase: {{ hasTimeline ? phase : 'N/A' }}</p>
          <p v-if="resetNotice" class="text-amber-700">{{ resetNotice }}</p>
          <p v-else-if="votingTiming?.countdown" :class="votingTiming.tone === 'success' ? 'text-emerald-700' : 'text-amber-700'">
            {{ votingTiming.label }} <span class="font-semibold">{{ votingTiming.countdown.text }}</span>
          </p>
          <p v-else-if="votingTiming?.detail" class="text-amber-700">
            {{ votingTiming.label }}
            <span v-if="votingTiming.detail">({{ votingTiming.detail }})</span>
          </p>
          <p v-else-if="!votingOpen" class="text-amber-600">Voting window closed</p>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-sm text-slate-500">Loading ballot.</div>

    <div v-else-if="!hasActiveElection" class="text-sm text-slate-600 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
      No active election. Please check back once the admin reopens voting.
    </div>

    <div v-else-if="!hasTimeline" class="text-sm text-slate-600 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
      Timeline not set. Waiting for admin to provide dates.
    </div>

    <div v-else-if="showBallot" class="grid gap-4">
      <div
        v-for="pos in positions"
        :key="pos.id"
        class="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm space-y-3"
      >
        <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-0.5">
            <h3 class="text-sm font-semibold">{{ pos.name_display || pos.name }}</h3>
            <p class="text-[11px] text-slate-500">Select one candidate</p>
          </div>
          <div v-if="selections[pos.id]" class="text-[11px] text-emerald-700 font-semibold">
            Selected
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label
            v-for="cand in candidatesByPosition[pos.id] || []"
            :key="cand.id"
            class="border rounded-xl p-3 flex gap-3 cursor-pointer hover:border-[rgba(196,151,60,0.6)]"
            :class="{
              'border-[var(--hcad-gold)] bg-[rgba(196,151,60,0.12)]': selections[pos.id] === cand.id,
              'opacity-60 pointer-events-none': hasVoted,
            }"
          >
            <input
              type="radio"
              class="mt-1"
              :name="`pos-${pos.id}`"
              :value="cand.id"
              v-model="selections[pos.id]"
              :disabled="hasVoted || !votingOpen"
            />
            <div class="flex gap-3 items-start w-full">
              <div class="h-10 w-10 rounded-full border border-slate-200 bg-white overflow-hidden flex-shrink-0">
                <img :src="cand.photo_url || candidatePlaceholder" alt="Candidate photo" class="h-full w-full object-cover" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-semibold truncate">{{ cand.full_name }}</p>
                <p class="text-[11px] text-slate-500">Batch {{ cand.batch_year }} - {{ cand.campus_chapter || 'Campus/Chapter not set' }}</p>
                <p class="text-[11px] text-slate-600 mt-1 whitespace-pre-line">{{ cand.bio || 'No bio provided' }}</p>
              </div>
            </div>
          </label>
        </div>
      </div>

      <div class="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm space-y-3">
        <div class="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" v-model="consent" :disabled="hasVoted" />
          <span>I agree to the processing of my personal data for the purpose of elections.</span>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            @click="submitBallot"
            :disabled="submitting || hasVoted || !votingOpen"
            class="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm shadow-sm disabled:bg-slate-300"
          >
            {{ submitting ? 'Submitting.' : hasVoted ? 'Ballot Submitted' : 'Submit Ballot' }}
          </button>
        </div>
        <p v-if="statusMessage" class="text-sm text-emerald-700">{{ statusMessage }}</p>
        <p v-if="errorMessage" class="text-sm text-rose-600">{{ errorMessage }}</p>
      </div>
    </div>

    <div v-else class="text-sm text-slate-600 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
      Voting is not open right now. Please return during the voting window.
    </div>
  </div>
</template>
