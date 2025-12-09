<!-- src/views/NominationsView.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import ElectionStatusBar from '../components/ElectionStatusBar.vue'

const authStore = useAuthStore()

const loading = ref(true)
const error = ref('')
const message = ref('')

const positions = ref([])
const sections = ref([])

// helper: get numeric grade from section.grade_level.name (e.g. "Grade 7")
const getGradeNumber = (section) => {
  const name = section.grade_level?.name || ''
  const match = name.match(/(\d+)/)
  if (!match) return null
  return parseInt(match[1], 10)
}

// filter sections shown for a given position, based on its level
const getSectionsForPosition = (position) => {
  if (!position) return sections.value

  const level = (position.level || '').toLowerCase()

  return sections.value.filter((s) => {
    const g = getGradeNumber(s)
    if (!g) return true // if we can't detect the grade, don't hide it

    if (level === 'junior high') {
      return g >= 7 && g <= 10
    }
    if (level === 'senior high') {
      return g >= 11 && g <= 12
    }
    if (level === 'whole school') {
      return true
    }
    // any other level → show everything
    return true
  })
}

// map: position_id -> nomination (for THIS voter)
const myNominations = ref({})

// local form state per position id
const formByPosition = ref({}) // { [posId]: { name, sectionId, reason } }

// track submit in progress per position
const submittingFor = ref({})

// election status (same rule as before: nominations open while now < start_at)
const election = ref(null)
const nominationsClosed = computed(() => {
  if (!election.value) return true
  const now = new Date()
  return now >= new Date(election.value.start_at)
})

/* ---------- helpers ---------- */

const initFormForPosition = (posId) => {
  if (!formByPosition.value[posId]) {
    formByPosition.value[posId] = {
      nominee_name: '',
      nominee_section_id: null,
      reason: '',
    }
  }
}

/* ---------- API ---------- */

const loadElection = async () => {
  const res = await api.get('election-status/')
  if (res.data?.has_election && res.data?.is_active) {
    election.value = res.data
  } else {
    election.value = null
  }
}

const loadPositions = async () => {
  const res = await api.get('positions/')
  positions.value = res.data || []
  positions.value.forEach((p) => initFormForPosition(p.id))
}

const loadSections = async () => {
  const res = await api.get('sections/')
  sections.value = res.data || []
}

const loadMyNominations = async () => {
  try {
    const res = await api.get('nominations/')
    const map = {}
    ;(res.data || []).forEach((n) => {
      map[n.position_id] = n
    })
    myNominations.value = map
  } catch (err) {
    console.error(err)
  }
}

/* ---------- SUBMIT ---------- */

const submitNomination = async (positionId) => {
  if (nominationsClosed.value) return

  const form = formByPosition.value[positionId]
  if (!form || !form.nominee_name || !form.nominee_section_id) {
    error.value = 'Please fill in nominee name and section.'
    return
  }

  error.value = ''
  message.value = ''
  submittingFor.value = { ...submittingFor.value, [positionId]: true }

  try {
    const res = await api.post('nominations/', {
      position_id: positionId,
      nominee_name: form.nominee_name,
      nominee_section_id: form.nominee_section_id,
      reason: form.reason || '',
    })

    // store this as "locked" nomination for this position
    const n = res.data
    myNominations.value = {
      ...myNominations.value,
      [positionId]: n,
    }

    message.value = 'Nomination submitted.'
  } catch (err) {
    console.error(err)
    error.value =
      err.response?.data?.error ||
      'Failed to submit nomination. You can only nominate once per position.'
  } finally {
    submittingFor.value = { ...submittingFor.value, [positionId]: false }
  }
}

/* ---------- COMPUTED ---------- */

const isSubmittingFor = (posId) => !!submittingFor.value[posId]

const isLockedFor = (posId) => !!myNominations.value[posId]

const buttonLabelFor = (posId) => {
  if (nominationsClosed.value) return 'Nominations closed'
  if (isLockedFor(posId)) return 'Nomination submitted'
  if (isSubmittingFor(posId)) return 'Submitting…'
  return 'Submit Nomination'
}

/* ---------- MOUNT ---------- */

onMounted(async () => {
  loading.value = true
  try {
    await loadElection()
    if (election.value) {
      await Promise.all([loadPositions(), loadSections(), loadMyNominations()])
    }
  } catch (err) {
    console.error(err)
    error.value = 'Failed to load nominations.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="px-3 py-4 sm:px-6 sm:py-6 max-w-4xl mx-auto">
    <h2 class="text-xl font-semibold mb-1">Nominations</h2>
    <p class="text-xs text-slate-500 mb-4">
      You may nominate candidates for each position before the election begins.
    </p>

    <ElectionStatusBar class="mb-4" />

    <div v-if="loading" class="text-sm text-slate-500">Loading…</div>

    <div v-else>
      <p v-if="!election" class="text-sm text-slate-500">
        There is currently no active election configured.
      </p>

      <p
        v-else-if="nominationsClosed"
        class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3"
      >
        Nominations are closed because the election has already started. You can still vote, but you
        can no longer submit new nominations.
      </p>

      <div v-else class="space-y-4">
        <p class="text-xs text-slate-500">
          One nomination per position. After you submit, the nomination is locked for that position.
        </p>

        <div
          v-for="pos in positions"
          :key="pos.id"
          class="bg-white border border-slate-200 rounded-2xl px-4 py-3"
        >
          <h3 class="text-sm font-semibold mb-1">{{ pos.name }}</h3>
          <p class="text-[11px] text-slate-500 mb-3">Level: {{ pos.level || 'Whole School' }}</p>

          <!-- form -->
          <div class="space-y-2">
            <input
              v-model="formByPosition[pos.id].nominee_name"
              type="text"
              class="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
              placeholder="Nominee full name"
              :disabled="isLockedFor(pos.id) || nominationsClosed"
            />

            <select
              v-model.number="formByPosition[pos.id].nominee_section_id"
              class="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-slate-50"
              :disabled="isLockedFor(pos.id) || nominationsClosed"
            >
              <option :value="null">Select section</option>
              <option v-for="s in getSectionsForPosition(pos)" :key="s.id" :value="s.id">
                {{ s.grade_level?.name }} - {{ s.name }}
              </option>
            </select>

            <textarea
              v-model="formByPosition[pos.id].reason"
              rows="2"
              class="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
              placeholder="Reason for nomination (optional)"
              :disabled="isLockedFor(pos.id) || nominationsClosed"
            />

            <button
              class="mt-1 inline-flex items-center justify-center rounded-lg px-4 py-1.5 text-xs font-medium text-white bg-emerald-600 disabled:bg-slate-300 disabled:cursor-not-allowed"
              @click="submitNomination(pos.id)"
              :disabled="isLockedFor(pos.id) || isSubmittingFor(pos.id) || nominationsClosed"
            >
              {{ buttonLabelFor(pos.id) }}
            </button>
          </div>

          <!-- existing nomination -->
          <div v-if="myNominations[pos.id]" class="mt-3 text-[11px] text-slate-500">
            <p class="font-semibold text-slate-600 mb-1">Your nomination:</p>
            <p>
              {{ myNominations[pos.id].nominee_name }} –
              {{ myNominations[pos.id].nominee_section_name || 'Section N/A' }}
            </p>
            <p v-if="myNominations[pos.id].reason">Reason: {{ myNominations[pos.id].reason }}</p>
          </div>
        </div>
      </div>

      <div class="mt-3 min-h-[20px]">
        <p v-if="message" class="text-emerald-600 text-xs">{{ message }}</p>
        <p v-if="error" class="text-rose-600 text-xs">{{ error }}</p>
      </div>
    </div>
  </div>
</template>
