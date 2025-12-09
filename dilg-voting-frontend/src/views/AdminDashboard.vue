<!-- src/views/AdminDashboard.vue -->
<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import api from '../api'
import { useAdminAuthStore } from '../stores/adminAuth'
import { useRouter, useRoute } from 'vue-router'

const adminStore = useAdminAuthStore()
const router = useRouter()
const route = useRoute()

const stats = ref(null)
const tally = ref([])
const nominations = ref([])
const reminders = ref([])
const loading = ref(false)
const errorMessage = ref('')
const promotingId = ref(null)
const election = ref(null)
const timelineMode = ref('timeline') // 'timeline' | 'demo'
const timelineLocked = ref(false)
const savingElection = ref(false)
const electionError = ref('')
const electionMessage = ref('')
const electionBannerVisible = ref(false)
const publishingResults = ref(false)
const publishedResults = ref(null)
const loadingPublishedResults = ref(false)
const demoMessage = ref('')
const demoError = ref('')
const tallyTab = ref(null)
const nominationsTimer = ref(null)
const nominationsSeen = ref(new Set())
const hasNewNominations = ref(false)
const lastNewNominations = ref([])
const activeTally = computed(() => {
  return tally.value?.find((p) => p.position_id === tallyTab.value) || null
})
const tallyTotalVotes = computed(() => {
  if (!activeTally.value || !activeTally.value.candidates?.length) return 0
  return activeTally.value.candidates.reduce((sum, c) => sum + (c.votes || 0), 0)
})
const publishedResultsTab = ref(null)
const activePublishedPosition = computed(() => {
  return publishedResults.value?.positions?.find((p) => p.position_id === publishedResultsTab.value) || null
})
const electionForm = ref({
  name: '',
  description: '',
  nomination_start: '',
  nomination_end: '',
  voting_start: '',
  voting_end: '',
  results_at: '',
  is_active: true,
  auto_publish_results: true,
})
const notifications = ref([])
const unreadNotifications = ref(0)
const notificationsLoading = ref(false)
const notificationsError = ref('')
const notificationsCollapsed = ref(false)
const showHistory = ref(false)
const candidatePhotoUploading = ref({})
const candidatePlaceholder =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect width='80' height='80' rx='40' fill='%23dfe4ea'/><path d='M40 40a12 12 0 1 0-0.001-24.001A12 12 0 0 0 40 40zm0 8c-11.046 0-20 6.268-20 14v4h40v-4c0-7.732-8.954-14-20-14z' fill='%2390a4ae'/></svg>"
const voterSearch = ref('')

// Voters
const voters = ref([])
const loadingVoters = ref(false)
const voterError = ref('')
const resettingVoters = ref(false)
const resettingElection = ref(false)
let voterTimer = null
let tallyTimer = null
let electionMessageTimer = null

// Themed confirm dialog
const confirmDialog = ref({
  open: false,
  title: '',
  message: '',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  tone: 'neutral', // 'neutral' | 'danger'
})
let confirmResolver = null

const askConfirm = (options = {}) => {
  if (confirmResolver) confirmResolver(false)
  return new Promise((resolve) => {
    confirmResolver = resolve
    confirmDialog.value = {
      open: true,
      title: 'Please confirm',
      message: '',
      confirmText: 'Confirm',
      cancelText: 'Cancel',
      tone: 'neutral',
      ...options,
    }
  })
}

const handleConfirm = (result) => {
  if (confirmResolver) {
    confirmResolver(result)
  }
  confirmResolver = null
  confirmDialog.value = { ...confirmDialog.value, open: false }
}

// UI state: show one section at a time
const activeSection = ref(localStorage.getItem('adminActiveSection') || 'stats')
const sections = [
  { key: 'stats', label: 'Overview' },
  { key: 'tally', label: 'Tally' },
  { key: 'timeline', label: 'Timeline' },
  { key: 'nominations', label: 'Nominations' },
  { key: 'reminders', label: 'Reminders' },
  { key: 'voters', label: 'Voters' },
]

watch(
  () => activeSection.value,
  (val) => localStorage.setItem('adminActiveSection', val),
  { immediate: true },
)

watch(
  () => activeSection.value,
  (val) => {
    if (val === 'nominations' && hasNewNominations.value) {
      hasNewNominations.value = false
      lastNewNominations.value = []
    }
  },
)

watch(
  () => electionMessage.value,
  (val) => {
    if (!val) return
    if (electionMessageTimer) clearTimeout(electionMessageTimer)
    electionMessageTimer = setTimeout(() => {
      electionMessage.value = ''
    }, 5000)
  },
)

const clearNewNominations = () => {
  hasNewNominations.value = false
  lastNewNominations.value = []
}

const showElectionMessage = (text) => {
  electionMessage.value = text
  electionBannerVisible.value = true
  if (electionMessageTimer) clearTimeout(electionMessageTimer)
  electionMessageTimer = setTimeout(() => {
    electionBannerVisible.value = false
  }, 5000)
}

const toInput = (val) => {
  if (!val) return ''
  return String(val).slice(0, 16)
}

const formatDateTime = (val) => {
  if (!val) return ''
  const d = new Date(val)
  return d.toLocaleString()
}

const loadStats = async () => {
  const res = await api.get('admin/stats/')
  stats.value = res.data
}

const TIMELINE_LOCK_KEY = 'adminTimelineLocked'
const loadTimelineLock = () => {
  try {
    const raw = localStorage.getItem(TIMELINE_LOCK_KEY)
    timelineLocked.value = raw === '1'
  } catch (_) {
    timelineLocked.value = false
  }
}

const saveTimelineLock = (locked) => {
  timelineLocked.value = !!locked
  try {
    localStorage.setItem(TIMELINE_LOCK_KEY, timelineLocked.value ? '1' : '0')
  } catch (_) {
    // ignore storage issues
  }
}

const toggleTimelineLock = async () => {
  const next = !timelineLocked.value
  const confirmed = await askConfirm({
    title: next ? 'Lock timeline' : 'Unlock timeline',
    message: next
      ? 'Lock the saved timeline so dates and settings cannot be edited until you unlock?'
      : 'Unlock the timeline to allow edits?',
    confirmText: next ? 'Lock timeline' : 'Unlock timeline',
    cancelText: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  saveTimelineLock(next)
  electionMessage.value = next ? 'Timeline locked. Editing disabled.' : 'Timeline unlocked. You can edit again.'
  electionError.value = ''
}

const loadTally = async () => {
  const res = await api.get('admin/tally/')
  tally.value = res.data || []
}

const uploadCandidatePhoto = async (candidateId, file) => {
  if (!file) return
  candidatePhotoUploading.value = { ...candidatePhotoUploading.value, [candidateId]: true }
  try {
    const form = new FormData()
    form.append('photo', file)
    await api.post(`admin/candidates/${candidateId}/photo/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    await loadTally()
  } catch (err) {
    alert(err.response?.data?.error || 'Failed to upload photo.')
  } finally {
    candidatePhotoUploading.value = { ...candidatePhotoUploading.value, [candidateId]: false }
  }
}

const removeCandidatePhoto = async (candidateId) => {
  candidatePhotoUploading.value = { ...candidatePhotoUploading.value, [candidateId]: true }
  try {
    await api.delete(`admin/candidates/${candidateId}/photo/`)
    await loadTally()
  } catch (err) {
    alert(err.response?.data?.error || 'Failed to remove photo.')
  } finally {
    candidatePhotoUploading.value = { ...candidatePhotoUploading.value, [candidateId]: false }
  }
}

watch(
  () => tally.value,
  (list) => {
    if (!list?.length) {
      tallyTab.value = null
      return
    }
    const stillExists = list.some((p) => p.position_id === tallyTab.value)
    tallyTab.value = stillExists ? tallyTab.value : list[0]?.position_id
  },
  { immediate: true },
)

watch(
  () => publishedResults.value?.positions,
  (list) => {
    if (!list?.length) {
      publishedResultsTab.value = null
      return
    }
    const exists = list.some((p) => p.position_id === publishedResultsTab.value)
    publishedResultsTab.value = exists ? publishedResultsTab.value : list[0]?.position_id
  },
  { immediate: true },
)

const loadPublishedResults = async () => {
  loadingPublishedResults.value = true
  try {
    const res = await api.get('elections/results/')
    publishedResults.value = res.data?.published ? res.data : null
  } catch (err) {
    publishedResults.value = null
  } finally {
    loadingPublishedResults.value = false
  }
}

const loadNominations = async () => {
  const res = await api.get('admin/nominations/')
  const incoming = res.data || []
  const incomingIds = new Set(incoming.map((n) => n.id))
  const newOnes = incoming.filter((n) => !nominationsSeen.value.has(n.id))
  const unseen = newOnes.length > 0
  nominations.value = incoming
  if (unseen) {
    hasNewNominations.value = true
    lastNewNominations.value = newOnes.map((n) => `${n.nominee_full_name} (${n.position_name})`)
  }
  nominationsSeen.value = incomingIds
  if (activeSection.value === 'nominations') {
    hasNewNominations.value = false
    lastNewNominations.value = []
  }
}

const rejectNomination = async (nom) => {
  const reason = window.prompt(`Reject ${nom.nominee_full_name}? Enter reason:`, '')
  if (!reason) return
  try {
    await api.post(`admin/nominations/${nom.id}/reject/`, { reason })
    await loadNominations()
  } catch (err) {
    alert(err.response?.data?.error || 'Failed to reject nomination.')
  }
}

const loadReminders = async () => {
  try {
    const res = await api.get('admin/reminders/')
    reminders.value = res.data || []
  } catch (err) {
    reminders.value = []
  }
}

const loadNotifications = async () => {
  notificationsLoading.value = true
  try {
    const res = await api.get(`admin/notifications/${showHistory.value ? '?history=1' : ''}`)
    notifications.value = res.data?.items || []
    unreadNotifications.value = res.data?.unread_count || 0
    notificationsError.value = ''
  } catch (err) {
    notificationsError.value = err.response?.data?.error || 'Failed to load notifications.'
  } finally {
    notificationsLoading.value = false
  }
}

const markAllNotificationsRead = async () => {
  try {
    await api.post('admin/notifications/', { action: 'mark_all_read' })
    await loadNotifications()
  } catch (err) {
    notificationsError.value = err.response?.data?.error || 'Failed to mark notifications as read.'
  }
}

const deleteAllNotifications = async () => {
  const confirmed = await askConfirm({
    title: 'Delete notifications',
    message: 'Delete all notifications? This cannot be undone.',
    confirmText: 'Delete all',
    tone: 'danger',
  })
  if (!confirmed) return
  try {
    await api.post('admin/notifications/', { action: 'delete_all' })
    await loadNotifications()
  } catch (err) {
    notificationsError.value = err.response?.data?.error || 'Failed to delete notifications.'
  }
}

const dismissNotification = async (id) => {
  try {
    await api.post('admin/notifications/', { action: 'dismiss', ids: [id] })
    await loadNotifications()
  } catch (err) {
    notificationsError.value = err.response?.data?.error || 'Failed to dismiss notification.'
  }
}

const deleteNotification = async (id) => {
  try {
    await api.post('admin/notifications/', { action: 'delete', ids: [id] })
    await loadNotifications()
  } catch (err) {
    notificationsError.value = err.response?.data?.error || 'Failed to delete notification.'
  }
}

const deleteNomination = async (nom) => {
  const confirmed = await askConfirm({
    title: 'Delete nomination',
    message: `Delete nomination for ${nom.nominee_full_name}? This removes the record from the list but does not undo any promoted candidates.`,
    confirmText: 'Delete nomination',
    cancelText: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return
  try {
    await api.delete(`admin/nominations/${nom.id}/delete/`)
    await loadNominations()
  } catch (err) {
    errorMessage.value = err.response?.data?.error || 'Failed to delete nomination.'
  }
}

const resetVoterPin = async (voter) => {
  const confirmed = await askConfirm({
    title: 'Reset PIN',
    message: `Reset PIN for ${voter.name}? This will end any active session.`,
    confirmText: 'Reset PIN',
    tone: 'danger',
  })
  if (!confirmed) return
  try {
    const res = await api.post(`admin/voters/${voter.id}/reset-pin/`)
    alert(`PIN reset.\nVoter ID: ${res.data.voter_id}\nPIN: ${res.data.pin}`)
    await loadVoters()
  } catch (err) {
    alert(err.response?.data?.error || 'Failed to reset PIN.')
  }
}

const clearTimelineDates = () => {
  if (timelineLocked.value) {
    electionError.value = 'Timeline is locked. Unlock to clear dates.'
    return
  }
  electionForm.value.nomination_start = ''
  electionForm.value.nomination_end = ''
  electionForm.value.voting_start = ''
  electionForm.value.voting_end = ''
  electionForm.value.results_at = ''
  electionForm.value.is_active = false
  saveElection()
}

const loadElection = async () => {
  try {
    const res = await api.get('admin/election/active/')
    election.value = res.data
    timelineMode.value = res.data.mode || 'timeline'
    loadTimelineLock()
    electionForm.value = {
      name: res.data.name || '',
      description: res.data.description || '',
      nomination_start: toInput(res.data.nomination_start),
      nomination_end: toInput(res.data.nomination_end),
      voting_start: toInput(res.data.voting_start),
      voting_end: toInput(res.data.voting_end),
      results_at: toInput(res.data.results_at),
      is_active: res.data.is_active,
      auto_publish_results: res.data.auto_publish_results ?? true,
    }
    electionError.value = ''
  } catch (err) {
    if (err.response?.status === 404) {
      // No election yet; allow creating from the dashboard UI.
      election.value = null
      timelineMode.value = 'timeline'
      loadTimelineLock()
      electionForm.value = {
        name: '',
        description: '',
        nomination_start: '',
        nomination_end: '',
        voting_start: '',
        voting_end: '',
        results_at: '',
        is_active: true,
        auto_publish_results: true,
      }
      electionError.value = ''
    } else {
      electionError.value = err.response?.data?.error || 'Failed to load election timeline.'
      election.value = null
    }
  }
}

const saveElection = async () => {
  if (!electionForm.value.name.trim()) {
    electionError.value = 'Election name is required.'
    return
  }
  if (timelineLocked.value) {
    electionError.value = 'Timeline is locked. Unlock to make changes.'
    return
  }
  savingElection.value = true
  electionError.value = ''
  electionMessage.value = ''
  try {
    const isUpdate = !!election.value
    const payload = {
      name: electionForm.value.name,
      description: electionForm.value.description,
      nomination_start: electionForm.value.nomination_start,
      nomination_end: electionForm.value.nomination_end,
      voting_start: electionForm.value.voting_start,
      voting_end: electionForm.value.voting_end,
      results_at: electionForm.value.results_at,
      is_active: electionForm.value.is_active,
      auto_publish_results: electionForm.value.auto_publish_results,
      mode: 'timeline',
    }
    const res = isUpdate
      ? await api.put('admin/election/active/', payload)
      : await api.post('admin/election/active/', payload)
    election.value = res.data
    timelineMode.value = res.data.mode || 'timeline'
    showElectionMessage(isUpdate ? 'Timeline saved.' : 'Election created.')
  } catch (err) {
    electionError.value = err.response?.data?.error || 'Failed to save timeline.'
  } finally {
    savingElection.value = false
  }
}

const publishResults = async (publishFlag) => {
  const confirmed = await askConfirm({
    title: publishFlag ? 'Publish results' : 'Unpublish results',
    message: publishFlag
      ? 'Publish election results for all voters? This will make results visible immediately.'
      : 'Unpublish results and hide them from voters?',
    confirmText: publishFlag ? 'Publish' : 'Unpublish',
    cancelText: 'Cancel',
    tone: 'danger',
  })
  if (!confirmed) return

  publishingResults.value = true
  electionError.value = ''
  try {
    const res = await api.post('admin/election/publish/', { publish: publishFlag })
    election.value = res.data
    showElectionMessage(publishFlag ? 'Results published.' : 'Results unpublished.')
    await loadPublishedResults()
  } catch (err) {
    electionError.value = err.response?.data?.error || 'Failed to update results status.'
  } finally {
    publishingResults.value = false
  }
}

const triggerDemoPhase = async (action) => {
  demoError.value = ''
  demoMessage.value = ''
  try {
    const res = await api.post('admin/election/demo-phase/', { action })
    election.value = res.data
    timelineMode.value = res.data.mode || timelineMode.value
    electionForm.value = {
      name: res.data.name || '',
      description: res.data.description || '',
      nomination_start: toInput(res.data.nomination_start),
      nomination_end: toInput(res.data.nomination_end),
      voting_start: toInput(res.data.voting_start),
      voting_end: toInput(res.data.voting_end),
      results_at: toInput(res.data.results_at),
      is_active: res.data.is_active,
    }
    demoMessage.value = action === 'exit_demo' ? 'Returned to timeline mode.' : 'Demo phase updated.'
  } catch (err) {
    demoError.value = err.response?.data?.error || 'Failed to update demo phase.'
  }
}

const switchMode = async (mode) => {
  if (!election.value || mode === timelineMode.value) return
  if (timelineLocked.value) {
    electionError.value = 'Unlock the timeline to change mode.'
    return
  }

  const toDemo = mode === 'demo'
  const confirmed = await askConfirm({
    title: 'Switch election mode',
    message: toDemo
      ? 'Switch to Demo mode? Timeline dates will be hidden and phases will be controlled manually until you return to timeline mode.'
      : 'Switch back to Timeline mode and follow the scheduled dates? Demo controls will be hidden.',
    confirmText: toDemo ? 'Switch to Demo' : 'Switch to Timeline',
    cancelText: 'Stay on current mode',
    tone: 'danger',
  })
  if (!confirmed) return

  demoError.value = ''
  demoMessage.value = ''
  electionError.value = ''
  try {
    const res = await api.put('admin/election/active/', { mode })
    election.value = res.data
    timelineMode.value = res.data.mode || mode
    electionForm.value = {
      name: res.data.name || '',
      description: res.data.description || '',
      nomination_start: toInput(res.data.nomination_start),
      nomination_end: toInput(res.data.nomination_end),
      voting_start: toInput(res.data.voting_start),
      voting_end: toInput(res.data.voting_end),
      results_at: toInput(res.data.results_at),
      is_active: res.data.is_active,
    }
    demoMessage.value = mode === 'demo'
      ? 'Demo mode enabled. Use the buttons below to jump phases.'
      : 'Returned to timeline mode.'
  } catch (err) {
    const msg = err.response?.data?.error || 'Failed to change mode.'
    demoError.value = msg
    electionError.value = msg
  }
}

const resetElection = async () => {
  const confirmReset = await askConfirm({
    title: 'Reset election',
    message: 'Reset votes, nominations, and voter statuses for this election?',
    confirmText: 'Reset election',
    tone: 'danger',
  })
  if (!confirmReset) return
  resettingElection.value = true
  try {
    const res = await api.post('admin/reset-election/', {})
    alert(res.data?.message || 'Election reset.')
    await Promise.all([loadTally(), loadPublishedResults(), loadNominations(), loadStats(), loadElection(), loadVoters()])
  } catch (err) {
    alert(err.response?.data?.error || 'Failed to reset election.')
  } finally {
    resettingElection.value = false
  }
}

const promote = async (nom) => {
  promotingId.value = nom.id
  try {
    const res = await api.post(`admin/nominations/${nom.id}/promote/`)
    const created = !!res.data?.created
    await Promise.all([loadTally(), loadPublishedResults(), loadNominations()])
    if (created) {
      alert('Nomination promoted to candidate.')
    } else {
      alert('Already a candidate for this position.')
    }
  } catch (err) {
    errorMessage.value = err.response?.data?.error || 'Failed to promote nomination.'
  } finally {
    promotingId.value = null
  }
}

const logout = () => {
  adminStore.logout()
  router.push('/admin-login')
}

const loadVoters = async () => {
  if (loadingVoters.value) return
  loadingVoters.value = true
  try {
    const res = await api.get('admin/voters/')
    voters.value = res.data || []
  } catch (err) {
    voterError.value = 'Failed to load voters.'
  } finally {
    loadingVoters.value = false
  }
}

const filteredVoters = computed(() => {
  const term = voterSearch.value.trim().toLowerCase()
  if (!term) return voters.value
  return voters.value.filter((v) => {
    const name = (v.name || '').toLowerCase()
    const id = (v.voter_id || '').toLowerCase()
    const batch = String(v.batch_year || '').toLowerCase()
    return name.includes(term) || id.includes(term) || batch.includes(term)
  })
})

const focusVoterFromQuery = (val) => {
  if (!val) return
  const trimmed = String(val).trim()
  if (!trimmed) return
  activeSection.value = 'voters'
  voterSearch.value = trimmed
}

watch(
  () => route.query.focusVoter,
  (val) => focusVoterFromQuery(val),
  { immediate: true },
)

onMounted(async () => {
  adminStore.initFromStorage()
  loadTimelineLock()

  if (!adminStore.isAuthenticated) {
    router.push('/admin-login')
    return
  }
  loading.value = true
  try {
    await Promise.all([
      loadStats(),
      loadTally(),
      loadPublishedResults(),
      loadNominations(),
      loadReminders(),
      loadElection(),
      loadVoters(),
    ])
  } catch (err) {
    errorMessage.value = 'Failed to load admin data.'
  } finally {
    loading.value = false
  }

  // Auto-refresh tally/stats so timeline/demo changes reflect without manual refresh
  tallyTimer = setInterval(() => {
    loadTally()
    loadStats()
  }, 10000)

  // Auto-refresh nominations so new submissions appear without manual refresh
  nominationsTimer.value = setInterval(() => {
    loadNominations()
  }, 10000)

  // Auto-refresh voters so new sign-ins/creations appear without manual refresh
  voterTimer = setInterval(() => {
    loadVoters()
  }, 10000)
})

onUnmounted(() => {
  if (tallyTimer) clearInterval(tallyTimer)
  if (voterTimer) clearInterval(voterTimer)
  if (nominationsTimer.value) clearInterval(nominationsTimer.value)
  if (electionMessageTimer) clearTimeout(electionMessageTimer)
})
</script>

<template>
  <div class="admin-dashboard space-y-6 w-full max-w-full mx-0 px-0 sm:px-2 lg:px-3">
    <div class="flex flex-col lg:grid lg:grid-cols-[360px_minmax(0,1fr)] gap-4 lg:gap-6 w-full">
      <aside class="w-full lg:w-auto lg:sticky lg:top-16 bg-white/95 border border-emerald-100 rounded-2xl shadow-sm p-4 space-y-4 lg:min-h-[calc(100vh-140px)] overflow-auto flex flex-col lg:min-w-[360px]">
        <div class="space-y-1">
          <p class="text-[11px] uppercase tracking-wide text-emerald-600 font-semibold">Admin</p>
          <h2 class="text-lg font-semibold leading-tight">COMELEC Dashboard</h2>
          <p class="text-xs text-slate-500">Live turnout, tallies, and nominations.</p>
        </div>
        <div class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold px-1">Navigation</div>
        <div class="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible px-1">
          <button
            v-for="s in sections"
            :key="s.key"
            @click="activeSection = s.key"
            class="text-sm w-full text-left px-3 py-2 rounded-xl border transition flex items-center gap-2 whitespace-nowrap"
            :class="activeSection === s.key ? 'bg-[var(--hcad-navy)] text-white border-[var(--hcad-gold)] shadow-sm' : 'border-[rgba(196,151,60,0.45)] text-slate-700 hover:bg-[rgba(196,151,60,0.12)]'"
          >
            <span>{{ s.label }}</span>
            <span
              v-if="s.key === 'nominations' && hasNewNominations"
              class="ml-1 inline-flex items-center justify-center text-[10px] px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 border border-rose-200"
            >
              New
            </span>
          </button>
        </div>
        <div class="flex-1"></div>
        <div class="flex flex-col gap-2 pt-2">
          <button @click="resetElection" :disabled="resettingElection" class="text-sm px-3 py-2 rounded-lg border border-rose-400 text-rose-700 bg-rose-50 hover:bg-rose-100 disabled:opacity-60">
            {{ resettingElection ? 'Resetting.' : 'Reset election' }}
          </button>
          <button @click="logout" class="text-sm px-3 py-2 rounded-lg border border-slate-300 hover:bg-slate-100">
            Logout
          </button>
        </div>
      </aside>

    <div class="flex-1 space-y-6 min-w-0 w-full">
      <div
        v-if="hasNewNominations && lastNewNominations.length"
        class="sticky top-2 z-20 flex flex-col gap-2 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-xl px-4 py-3 shadow-sm"
      >
        <div class="flex items-center justify-between gap-3">
          <p class="text-sm font-semibold">New nomination{{ lastNewNominations.length > 1 ? 's' : '' }} received</p>
          <button
            class="text-[11px] px-2 py-1 rounded border border-emerald-200 bg-white hover:bg-emerald-50"
            @click="clearNewNominations"
          >
            Dismiss
          </button>
        </div>
        <ul class="text-xs text-emerald-900 list-disc list-inside">
          <li v-for="item in lastNewNominations" :key="item">{{ item }}</li>
        </ul>
        <p class="text-[11px] text-emerald-700">Tap “Nominations” to review and promote.</p>
      </div>
        <div v-if="loading" class="text-sm text-slate-500">Loading dashboard.</div>
        <p v-if="errorMessage" class="text-sm text-rose-600">{{ errorMessage }}</p>


    <div v-if="activeSection === 'stats' && stats" id="stats" class="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full">
      <div class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm">
        <p class="text-xs text-slate-500">Total voters</p>
        <p class="text-2xl font-semibold">{{ stats.total_voters }}</p>
      </div>
      <div class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm">
        <p class="text-xs text-slate-500">Voted</p>
        <p class="text-2xl font-semibold">{{ stats.voted_count }}</p>
      </div>
      <div class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm">
        <p class="text-xs text-slate-500">Turnout</p>
        <p class="text-2xl font-semibold">{{ stats.turnout_percent }}%</p>
      </div>
    </div>

    <div v-if="activeSection === 'tally'" id="tally" class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm">
      <h3 class="text-sm font-semibold mb-3">Per-position tally</h3>
      <div class="flex flex-wrap gap-2 mb-3">
        <button
          v-for="pos in tally"
          :key="pos.position_id"
          class="px-3 py-1.5 rounded-lg text-xs border"
          :class="tallyTab === pos.position_id ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm' : 'border-slate-300 bg-white hover:bg-emerald-50'"
          @click="tallyTab = pos.position_id"
        >
          {{ pos.position }}
        </button>
      </div>
      <div v-if="tallyTab && activeTally" class="border border-emerald-100 rounded-xl p-3 space-y-3 bg-white/90 shadow-sm">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-sm font-semibold">{{ activeTally.position }}</p>
            <span class="text-[11px] text-slate-500">{{ activeTally.candidates.length }} candidate(s)</span>
          </div>
        </div>
        <div v-if="activeTally.candidates.length" class="overflow-x-auto pb-2">
          <div class="flex gap-4 min-h-[320px]">
            <div
              v-for="cand in activeTally.candidates"
              :key="cand.candidate_id"
              class="bg-[#f7f8fa] border border-slate-200 rounded-2xl shadow-sm p-3 flex flex-col gap-3 min-w-[240px] max-w-[260px]"
            >
              <div class="rounded-xl overflow-hidden bg-white border border-slate-200 h-[200px] w-full">
                <img :src="cand.photo_url || candidatePlaceholder" alt="Candidate photo" class="h-full w-full object-cover" />
              </div>
              <div class="space-y-1">
                <p class="text-base font-semibold text-slate-900 leading-tight">{{ cand.full_name }}</p>
                <p class="text-[13px] text-slate-600">Batch {{ cand.batch_year || 'N/A' }}</p>
                <p class="text-[12px] text-slate-500">{{ cand.campus_chapter || 'Campus/Chapter not set' }}</p>
              </div>
              <div class="space-y-1">
                <p class="text-lg font-semibold text-slate-900">{{ cand.votes === 1 ? '1 vote' : `${cand.votes} votes` }}</p>
                <div class="w-full h-3 rounded-full bg-slate-200 overflow-hidden border border-slate-300/70">
                  <div
                    class="h-full bg-gradient-to-r from-[var(--hcad-gold)] to-[var(--hcad-navy)] vote-bar-animate"
                    :style="{
                      width:
                        (tallyTotalVotes
                          ? Math.min(100, Math.round(((cand.votes || 0) / tallyTotalVotes) * 100))
                          : 0) + '%'
                    }"
                  ></div>
                </div>
                <p class="text-[11px] text-slate-600 font-semibold">
                  {{
                    tallyTotalVotes
                      ? Math.min(100, Math.round(((cand.votes || 0) / tallyTotalVotes) * 100))
                      : 0
                  }}%
                </p>
              </div>
              <div class="flex flex-wrap gap-2 items-center pt-1">
                <label
                  class="inline-flex items-center gap-2 text-[11px] font-semibold text-[var(--hcad-navy)] cursor-pointer"
                  :class="{ 'opacity-60 cursor-not-allowed': candidatePhotoUploading[cand.candidate_id] }"
                >
                  <input
                    type="file"
                    accept="image/*"
                    class="hidden"
                    :disabled="candidatePhotoUploading[cand.candidate_id]"
                    @change="(e) => { const file = e.target.files?.[0]; if (file) uploadCandidatePhoto(cand.candidate_id, file); e.target.value = '' }"
                  />
                  <span class="px-2 py-1 rounded-full border border-[rgba(196,151,60,0.45)] bg-white hover:bg-[rgba(196,151,60,0.12)] transition">
                    {{ candidatePhotoUploading[cand.candidate_id] ? 'Uploading…' : cand.photo_url ? 'Change photo' : 'Add photo' }}
                  </span>
                </label>
                <button
                  v-if="cand.photo_url"
                  type="button"
                  class="text-[11px] px-2 py-1 rounded-full border border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100 transition"
                  :disabled="candidatePhotoUploading[cand.candidate_id]"
                  @click="removeCandidatePhoto(cand.candidate_id)"
                >
                  Remove photo
                </button>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-slate-600">No candidates for this position.</p>
      </div>
      <p v-else class="text-sm text-slate-600">No positions to display.</p>

      <div class="mt-6 border-t border-slate-200 pt-4">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-3">
          <h4 class="text-sm font-semibold">Published results view</h4>
          <button
            class="text-xs px-3 py-1.5 rounded-lg border border-emerald-200 bg-white text-emerald-800 hover:bg-emerald-50 shadow-sm"
            @click="loadPublishedResults"
          >
            Refresh
          </button>
          </div>
          <div v-if="loadingPublishedResults" class="text-sm text-slate-500">Loading published results...</div>
          <div v-else-if="publishedResults" class="space-y-3">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="pos in publishedResults.positions || []"
                :key="pos.position_id"
                class="px-3 py-1.5 rounded-full border text-xs transition"
                :class="
                  publishedResultsTab === pos.position_id
                    ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                    : 'border-slate-300 bg-white hover:bg-emerald-50 text-slate-700'
                "
                @click="publishedResultsTab = pos.position_id"
              >
                {{ pos.position }}
              </button>
            </div>
            <div v-if="activePublishedPosition" class="border border-emerald-100 rounded-xl p-3 space-y-2 bg-white/90 shadow-sm">
              <div class="flex items-center justify-between">
                <p class="text-sm font-semibold">{{ activePublishedPosition.position }}</p>
                <span class="text-[11px] text-slate-500">{{ activePublishedPosition.candidates?.length || 0 }} candidate(s)</span>
              </div>
              <div class="space-y-2">
                <div v-for="cand in activePublishedPosition.candidates" :key="cand.id" class="flex justify-between text-sm">
                  <div>
                    <p class="font-semibold" :class="{ 'text-emerald-700': cand.winner }">{{ cand.full_name }}</p>
                    <p class="text-[11px] text-slate-500">
                      Batch {{ cand.batch_year }} - {{ cand.campus_chapter || 'Campus/Chapter not set' }}
                    </p>
                  </div>
                  <div class="text-right">
                    <p class="font-semibold text-slate-800">{{ cand.votes }} vote(s)</p>
                    <p v-if="cand.winner" class="text-[11px] text-emerald-700 font-semibold">Winner</p>
                  </div>
                </div>
              </div>
            </div>
            <p v-else class="text-sm text-slate-600">No positions to display.</p>
          </div>
          <div v-else class="text-sm text-slate-600">No published results yet.</div>
        </div>
      </div>

    <div v-if="activeSection === 'timeline'" id="timeline" class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm space-y-3">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h3 class="text-sm font-semibold leading-tight">Election timeline</h3>
        <div class="flex items-center gap-2">
          <span class="text-[11px] text-slate-500">Nomination & voting windows</span>
          <button
            type="button"
            class="text-[11px] px-3 py-1.5 rounded-lg border"
            :class="timelineLocked ? 'border-slate-300 bg-slate-100 text-slate-700' : 'border-[var(--hcad-gold)] bg-white text-[var(--hcad-navy)] hover:bg-[rgba(196,151,60,0.12)]'"
            @click="toggleTimelineLock"
          >
            {{ timelineLocked ? 'Unlock timeline' : 'Lock timeline' }}
          </button>
        </div>
      </div>
      <p v-if="electionError" class="text-xs text-rose-600">{{ electionError }}</p>
      <p
        v-else-if="electionMessage"
        class="text-sm font-semibold inline-flex items-center gap-2 transition-all"
        :class="
          electionBannerVisible
            ? 'text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 shadow-[0_0_0_3px_rgba(16,185,129,0.15)]'
            : 'text-emerald-700'
        "
      >
        {{ electionMessage }}
      </p>
      <p v-else-if="!election" class="text-xs text-slate-500">No election configured. Set the dates below and save to create one.</p>
      <div class="flex flex-wrap items-center gap-2 text-xs sm:text-sm">
        <span class="font-semibold text-slate-700">Mode:</span>
        <button
          @click="switchMode('timeline')"
          :class="timelineMode === 'timeline' ? 'bg-[var(--hcad-navy)] text-white border border-[var(--hcad-gold)] shadow-sm' : 'border border-[rgba(196,151,60,0.45)] text-slate-700 hover:bg-[rgba(196,151,60,0.12)]'"
          class="px-3 py-1.5 rounded-full transition"
        >
          Timeline (use dates)
        </button>
        <button
          @click="switchMode('demo')"
          :class="timelineMode === 'demo' ? 'bg-[var(--hcad-navy)] text-white border border-[var(--hcad-gold)] shadow-sm' : 'border border-[rgba(196,151,60,0.45)] text-slate-700 hover:bg-[rgba(196,151,60,0.12)]'"
          class="px-3 py-1.5 rounded-full transition"
        >
          Demo (manual phases)
        </button>
        <span class="text-[11px] text-slate-500">
          {{ timelineMode === 'demo' ? 'Demo mode ignores the schedule; use the buttons below to jump phases.' : 'Timeline mode uses the dates you set.' }}
        </span>
      </div>
      <div v-if="timelineMode === 'timeline'" class="grid gap-3 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-slate-700 mb-1">Election name</label>
          <input v-model="electionForm.name" type="text" placeholder="e.g., 2025 HCAD Alumni Elections" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-slate-700 mb-1">Description (optional)</label>
          <textarea v-model="electionForm.description" rows="2" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'"></textarea>
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Nomination start</label>
          <input v-model="electionForm.nomination_start" type="datetime-local" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Nomination end</label>
          <input v-model="electionForm.nomination_end" type="datetime-local" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Voting start</label>
          <input v-model="electionForm.voting_start" type="datetime-local" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Voting end</label>
          <input v-model="electionForm.voting_end" type="datetime-local" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-slate-700 mb-1">Results announcement</label>
          <input v-model="electionForm.results_at" type="datetime-local" class="w-full border border-emerald-200 rounded-lg px-3 py-2 text-sm bg-white/90" :disabled="timelineLocked || timelineMode === 'demo'" />
        </div>
        <label class="flex items-center gap-2 text-xs text-slate-700">
          <input v-model="electionForm.auto_publish_results" type="checkbox" :disabled="timelineLocked || timelineMode === 'demo'" />
          Auto-publish results at the scheduled time
        </label>
        <label class="flex items-center gap-2 text-xs text-slate-700">
          <input v-model="electionForm.is_active" type="checkbox" :disabled="timelineLocked || timelineMode === 'demo'" />
          Set election as active
        </label>
        <div class="sm:col-span-2 flex flex-wrap gap-2">
          <button
            @click="clearTimelineDates"
            type="button"
            class="px-3 py-1.5 rounded-lg border border-[var(--hcad-gold)] text-xs hover:bg-[rgba(196,151,60,0.12)] bg-white shadow-sm disabled:opacity-60"
            :disabled="timelineLocked || timelineMode === 'demo'"
          >
            Clear dates
          </button>
        </div>
      </div>
      <div v-else class="rounded-lg border border-dashed border-slate-300 p-3 bg-slate-50 text-[12px] text-slate-700">
        Timeline dates are hidden in demo mode. Use the demo buttons below to move phases and show/hide demo results. Switch back to timeline mode to edit dates.
      </div>
      <div class="flex flex-col sm:flex-row sm:items-center gap-3">
        <button
          @click="saveElection"
          :disabled="savingElection || timelineMode === 'demo' || timelineLocked"
          class="px-4 py-2 rounded-lg bg-[var(--hcad-navy)] text-white text-sm shadow-sm disabled:bg-slate-300"
        >
          {{ savingElection ? 'Saving.' : 'Save timeline' }}
        </button>
        <div class="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span v-if="election">Status: {{ election.results_published ? 'Results published' : 'Not published' }}</span>
          <span v-else>No election saved yet.</span>
          <button
            v-if="election"
            @click="publishResults(!election.results_published)"
            :disabled="publishingResults"
            class="px-3 py-1.5 rounded-lg border text-xs"
            :class="election.results_published ? 'border-amber-400 text-amber-700 bg-amber-50' : 'border-[var(--hcad-gold)] text-[var(--hcad-navy)] bg-[rgba(196,151,60,0.12)]'"
          >
            {{ publishingResults ? 'Updating.' : election.results_published ? 'Unpublish results' : 'Publish results' }}
          </button>
        </div>
      </div>
      <div v-if="timelineMode === 'demo'" class="mt-4 border-t border-slate-200 pt-3 space-y-2">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h4 class="text-sm font-semibold">Demo controls</h4>
          <span class="text-[11px] text-slate-500">
            Toggle phases without dates (mode: {{ election?.demo_phase || 'unset' }})
          </span>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            @click="triggerDemoPhase('open_nomination')"
            class="px-3 py-1.5 rounded-lg border text-xs"
            :class="election?.demo_phase === 'nomination' ? 'border-emerald-500 text-emerald-700 bg-emerald-50' : ''"
          >
            Open nomination
          </button>
          <button
            @click="triggerDemoPhase('close_nomination')"
            class="px-3 py-1.5 rounded-lg border text-xs"
            :class="election?.demo_phase === 'between' ? 'border-emerald-500 text-emerald-700 bg-emerald-50' : ''"
          >
            Close nomination
          </button>
          <button
            @click="triggerDemoPhase('open_voting')"
            class="px-3 py-1.5 rounded-lg border text-xs"
            :class="election?.demo_phase === 'voting' ? 'border-emerald-500 text-emerald-700 bg-emerald-50' : ''"
          >
            Open voting
          </button>
          <button
            @click="triggerDemoPhase('close_voting')"
            class="px-3 py-1.5 rounded-lg border text-xs"
            :class="election?.demo_phase === 'closed' ? 'border-emerald-500 text-emerald-700 bg-emerald-50' : ''"
          >
            Close voting
          </button>
          <button @click="triggerDemoPhase('exit_demo')" class="px-3 py-1.5 rounded-lg border text-xs border-emerald-500 text-emerald-700">
            Return to timeline
          </button>
        </div>
        <p v-if="demoMessage" class="text-[11px] text-emerald-600">{{ demoMessage }}</p>
        <p v-if="demoError" class="text-[11px] text-rose-600">{{ demoError }}</p>
      </div>
      <div v-else class="mt-4 border-t border-slate-200 pt-3">
        <p class="text-[11px] text-slate-500">Demo controls are hidden while in timeline mode.</p>
      </div>
    </div>

    <div v-if="activeSection === 'nominations'" id="nominations" class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm space-y-3">
      <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h3 class="text-sm font-semibold">Nominations</h3>
        <p class="text-[11px] text-slate-500">Promote to make official candidates.</p>
      </div>
      <div
        v-if="hasNewNominations"
        class="text-xs text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2 flex items-center justify-between"
      >
        <span>New nominations received. List updates automatically.</span>
        <button
          class="text-[11px] px-2 py-1 rounded border border-emerald-200 bg-white hover:bg-emerald-50"
          @click="hasNewNominations = false"
        >
          Dismiss
        </button>
      </div>
      <div v-if="nominations.length === 0" class="text-xs text-slate-500">No nominations yet.</div>
      <div v-else class="space-y-3">
        <div
          v-for="nom in nominations"
          :key="nom.id"
          class="border border-emerald-100 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 bg-white/90 shadow-sm"
        >
          <div>
            <p class="text-sm font-semibold">
              {{ nom.nominee_full_name }} ({{ nom.position_name }})
              <span v-if="nom.promoted" class="text-[11px] text-emerald-600 ml-2">Promoted</span>
            </p>
            <p class="text-[11px] text-slate-500">
              Batch {{ nom.nominee_batch_year }} - {{ nom.nominee_campus_chapter || 'Campus/Chapter not set' }}
            </p>
            <p class="text-[11px]" :class="nom.status === 'rejected' ? 'text-rose-600' : 'text-slate-500'">
              Status: {{ nom.status || 'pending' }}
              <span v-if="nom.status === 'rejected' && nom.rejection_reason">({{ nom.rejection_reason }})</span>
            </p>
            <p v-if="nom.promoted_at" class="text-[11px] text-slate-500">Promoted at: {{ nom.promoted_at }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-if="!nom.promoted && nom.status !== 'rejected'"
              @click="promote(nom)"
              :disabled="promotingId === nom.id"
              class="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 text-white shadow-sm disabled:bg-slate-300"
            >
              {{ promotingId === nom.id ? 'Promoting.' : 'Promote to Candidate' }}
            </button>
            <button
              v-if="!nom.promoted && nom.status !== 'rejected'"
              @click="rejectNomination(nom)"
              class="text-xs px-3 py-1.5 rounded-lg border border-rose-300 text-rose-700 bg-rose-50 hover:bg-rose-100"
            >
              Reject
            </button>
            <button
              @click="deleteNomination(nom)"
              class="text-xs px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-100"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeSection === 'reminders'" id="reminders" class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm space-y-2">
      <h3 class="text-sm font-semibold">Reminders</h3>
      <div v-if="!reminders.length" class="text-xs text-slate-500">No reminders stored.</div>
      <ul v-else class="text-sm text-slate-700 list-disc list-inside">
        <li v-for="rem in reminders" :key="rem.id">{{ rem.remind_at }} - {{ rem.note }}</li>
      </ul>
    </div>

    <div v-if="activeSection === 'voters'" id="voters" class="bg-gradient-to-br from-[rgba(196,151,60,0.12)] via-white to-[rgba(15,35,66,0.05)] rounded-2xl border border-[rgba(196,151,60,0.35)] p-4 sm:p-5 shadow-sm space-y-3">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h3 class="text-sm font-semibold">Voters</h3>
        <div class="flex flex-wrap gap-2">
          <div class="relative flex-1 min-w-[340px] max-w-[560px]">
            <input
              v-model="voterSearch"
              type="text"
              placeholder="Search name, voter ID, or batch"
              aria-label="Search voters"
              class="w-full text-xs px-3 py-1.5 rounded-lg border border-emerald-200 bg-white/90 shadow-inner"
            />
          </div>
        </div>
      </div>
      <div v-if="loadingVoters" class="text-xs text-slate-500">Loading voters.</div>
      <div v-else class="text-xs text-slate-600">
        Showing {{ filteredVoters.length }} of {{ voters.length }} voters
      </div>
      <div class="max-h-64 overflow-y-auto border border-emerald-100 rounded-xl shadow-sm bg-white/95" v-if="filteredVoters.length">
        <div class="overflow-x-auto">
          <table class="w-full min-w-[600px] text-xs">
            <thead class="bg-emerald-50/50">
              <tr class="text-left text-slate-500">
                <th class="px-3 py-2">Name</th>
                <th class="px-3 py-2">Voter ID</th>
                <th class="px-3 py-2">Batch</th>
                <th class="px-3 py-2">Voted</th>
                <th class="px-3 py-2 text-right">Created</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in filteredVoters" :key="v.id" class="border-t border-slate-100">
                <td class="px-3 py-2">{{ v.name }}</td>
                <td class="px-3 py-2">{{ v.voter_id }}</td>
                <td class="px-3 py-2">{{ v.batch_year || 'N/A' }}</td>
                <td class="px-3 py-2">{{ v.has_voted ? 'Yes' : 'No' }}</td>
                <td class="px-3 py-2 text-right">
                  <span class="text-[11px] text-slate-600">{{ formatDateTime(v.created_at) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p v-else class="text-xs text-slate-500">No voters match your search.</p>
      <p v-if="voterError" class="text-xs text-rose-600">{{ voterError }}</p>
    </div>
    </div>
  </div>

    <div
      v-if="confirmDialog.open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-3"
      @click.self="handleConfirm(false)"
    >
      <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 border border-emerald-100">
        <div class="flex items-start gap-3">
          <div
            class="h-10 w-10 rounded-full flex items-center justify-center text-lg font-semibold"
            :class="confirmDialog.tone === 'danger' ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700'"
          >
            !
          </div>
          <div class="space-y-1">
            <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">
              {{ confirmDialog.title || 'Please confirm' }}
            </p>
            <p class="text-sm text-slate-700 whitespace-pre-line">
              {{ confirmDialog.message || 'Are you sure you want to continue?' }}
            </p>
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button
            class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50"
            @click="handleConfirm(false)"
          >
            {{ confirmDialog.cancelText || 'Cancel' }}
          </button>
          <button
            class="px-3 py-1.5 text-sm rounded-lg shadow-sm"
            :class="confirmDialog.tone === 'danger' ? 'bg-rose-600 text-white hover:bg-rose-700' : 'bg-emerald-600 text-white hover:bg-emerald-700'"
            @click="handleConfirm(true)"
          >
            {{ confirmDialog.confirmText || 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* Gold gradient accents for form fields */
.admin-dashboard input:not([type='checkbox']):not([type='radio']):not([type='range']):not([type='button']):not([type='submit']):not([type='reset']),
.admin-dashboard textarea,
.admin-dashboard select {
  border: 1px solid transparent;
  background-image: linear-gradient(#ffffff, #ffffff),
    linear-gradient(135deg, rgba(196, 151, 60, 0.6), rgba(15, 35, 66, 0.3));
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow: 0 2px 10px rgba(15, 35, 66, 0.06);
  transition: box-shadow 150ms ease, transform 150ms ease;
}

.admin-dashboard input:not([type='checkbox']):not([type='radio']):not([type='range']):not([type='button']):not([type='submit']):not([type='reset']):focus,
.admin-dashboard textarea:focus,
.admin-dashboard select:focus {
  box-shadow: 0 4px 14px rgba(15, 35, 66, 0.12);
  transform: translateY(-1px);
  outline: none;
}
</style>
