<script setup>
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useAdminAuthStore } from './stores/adminAuth'
import api from './api'
import Logo from './assets/HCAD_Alumni_Org_Logo.jpg'

const authStore = useAuthStore()
const adminAuth = useAdminAuthStore()
const route = useRoute()
const router = useRouter()
const ACCESS_GATE_KEY = 'hcad-access-granted'
const ACCESS_GATE_NAME_KEY = 'hcad-access-name'
const ACCESS_GATE_VERSION_KEY = 'hcad-access-version'
const headerNotifOpen = ref(false)
const headerNotifItems = ref([])
const headerNotifUnread = ref(0)
const headerNotifLoading = ref(false)
const headerNotifError = ref('')
const headerNotifExpanded = ref(false)
const headerNotifTimer = ref(null)
const accessAllowed = ref(false)
const accessGateName = ref('')
const accessVersion = ref(null)
const accessCodeInput = ref('')
const accessError = ref('')
const accessChecking = ref(false)
const voterNotifOpen = ref(false)
const voterNotifItems = ref([])
const voterNotifUnread = ref(0)
const voterNotifLoading = ref(false)
const voterNotifError = ref('')
const voterNotifTimer = ref(null)

authStore.initFromStorage()
adminAuth.initFromStorage()

const isAdminContext = computed(() => {
  const name = route.name ? route.name.toString() : ''
  return name.startsWith('admin')
})

const voterLinks = computed(() => {
  const links = [
    { to: '/', label: 'Home', show: !authStore.isAuthenticated },
    { to: '/info', label: 'Registration', show: !authStore.isAuthenticated },
    { to: '/nomination', label: 'Nomination', show: authStore.isAuthenticated },
    { to: '/vote', label: 'Ballot', show: authStore.isAuthenticated },
    { to: '/results', label: 'Results', show: authStore.isAuthenticated },
  ]
  return links.filter((l) => l.show)
})

const formatHeaderNotifDate = (value) => {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
  } catch (e) {
    return value
  }
}

const extractVoterSearch = (notif) => {
  if (!notif?.message) return ''
  const idMatch = notif.message.match(/\(ID\s+([A-Za-z0-9-]+)\)/i)
  if (idMatch?.[1]) return idMatch[1]
  const nameMatch = notif.message.match(/Voter '([^']+)'/i)
  if (nameMatch?.[1]) return nameMatch[1]
  return ''
}

const handleHeaderNotifClick = async (notif) => {
  if (!adminAuth.isAuthenticated) return
  const focusVoter = extractVoterSearch(notif)
  headerNotifOpen.value = false
  headerNotifExpanded.value = false
  if (notif?.id) {
    markHeaderNotificationRead(notif.id)
  }
  await router.push({ path: '/admin', query: focusVoter ? { focusVoter } : {} })
}

const loadHeaderNotifications = async () => {
  if (!adminAuth.isAuthenticated) return
  headerNotifLoading.value = true
  try {
    const res = await api.get('admin/notifications/')
    headerNotifItems.value = res.data?.items?.slice(0, 8) || []
    headerNotifUnread.value = res.data?.unread_count || 0
    headerNotifError.value = ''
  } catch (err) {
    headerNotifError.value = err.response?.data?.error || 'Failed to load notifications.'
  } finally {
    headerNotifLoading.value = false
  }
}

const markHeaderNotificationsRead = async () => {
  if (!adminAuth.isAuthenticated) return
  try {
    await api.post('admin/notifications/', { action: 'mark_all_read' })
    await loadHeaderNotifications()
  } catch (err) {
    headerNotifError.value = err.response?.data?.error || 'Failed to mark as read.'
  }
}

const deleteHeaderNotification = async (id) => {
  if (!adminAuth.isAuthenticated) return
  try {
    await api.post('admin/notifications/', { action: 'delete', ids: [id] })
    await loadHeaderNotifications()
  } catch (err) {
    headerNotifError.value = err.response?.data?.error || 'Failed to delete.'
  }
}

const markHeaderNotificationRead = async (id) => {
  if (!adminAuth.isAuthenticated) return
  try {
    await api.post('admin/notifications/', { action: 'dismiss', ids: [id] })
    await loadHeaderNotifications()
  } catch (err) {
    headerNotifError.value = err.response?.data?.error || 'Failed to mark as read.'
  }
}

const deleteAllHeaderNotifications = async () => {
  if (!adminAuth.isAuthenticated) return
  try {
    await api.post('admin/notifications/', { action: 'delete_all' })
    await loadHeaderNotifications()
  } catch (err) {
    headerNotifError.value = err.response?.data?.error || 'Failed to delete all.'
  }
}

const toggleHeaderNotifications = async () => {
  if (!headerNotifOpen.value && adminAuth.isAuthenticated) {
    headerNotifOpen.value = true
    headerNotifExpanded.value = false
    await loadHeaderNotifications()
  } else {
    headerNotifOpen.value = false
    headerNotifExpanded.value = false
  }
}

const stopHeaderPolling = () => {
  if (headerNotifTimer.value) {
    clearInterval(headerNotifTimer.value)
    headerNotifTimer.value = null
  }
}

const startHeaderPolling = () => {
  stopHeaderPolling()
  if (!adminAuth.isAuthenticated) return
  // Poll for new notifications so admins see updates without manual refresh.
  headerNotifTimer.value = setInterval(() => {
    loadHeaderNotifications()
  }, 10000)
}

watch(
  () => adminAuth.isAuthenticated,
  (isAuthed) => {
    if (isAuthed) {
      loadHeaderNotifications()
      startHeaderPolling()
    } else {
      stopHeaderPolling()
    }
  },
  { immediate: true },
)

const syncAccessStatus = async () => {
  if (isAdminContext.value) {
    return
  }
  const storedAllow = localStorage.getItem(ACCESS_GATE_KEY) === '1'
  const storedVersion = localStorage.getItem(ACCESS_GATE_VERSION_KEY)
  const storedName = localStorage.getItem(ACCESS_GATE_NAME_KEY)
  try {
    const res = await api.get('access/status/')
    const gates = res.data?.gates || []
    const match = gates.find((g) => g.name === storedName && String(g.version) === String(storedVersion))
    accessAllowed.value = !!(storedAllow && match)
    if (match) {
      accessGateName.value = match.name
      accessVersion.value = String(match.version)
    } else {
      accessGateName.value = ''
      accessVersion.value = null
      localStorage.removeItem(ACCESS_GATE_KEY)
      localStorage.removeItem(ACCESS_GATE_VERSION_KEY)
      localStorage.removeItem(ACCESS_GATE_NAME_KEY)
    }
  } catch (err) {
    // On failure, keep the gate closed to avoid bypassing when the server is unreachable.
    accessAllowed.value = false
  }
}

const submitAccessCode = async () => {
  const entered = accessCodeInput.value.trim()
  if (!entered) {
    accessError.value = 'Enter the passcode.'
    return
  }
  accessChecking.value = true
  accessError.value = ''
  try {
    const res = await api.post('access/check/', { passcode: entered })
    const serverVersion = String(res.data?.version || '')
    const serverName = res.data?.name || ''
    accessAllowed.value = true
    accessVersion.value = serverVersion
    accessGateName.value = serverName
    localStorage.setItem(ACCESS_GATE_KEY, '1')
    if (serverVersion) {
      localStorage.setItem(ACCESS_GATE_VERSION_KEY, serverVersion)
    }
    if (serverName) {
      localStorage.setItem(ACCESS_GATE_NAME_KEY, serverName)
    }
  } catch (err) {
    accessAllowed.value = false
    localStorage.removeItem(ACCESS_GATE_KEY)
    localStorage.removeItem(ACCESS_GATE_VERSION_KEY)
    localStorage.removeItem(ACCESS_GATE_NAME_KEY)
    accessError.value = err.response?.data?.error || 'Incorrect passcode.'
  } finally {
    accessChecking.value = false
  }
}

watch(
  () => isAdminContext.value,
  (isAdmin) => {
    if (!isAdmin) {
      syncAccessStatus()
    }
  },
  { immediate: true },
)

const handleVisibility = () => {
  if (document.visibilityState === 'visible' && adminAuth.isAuthenticated) {
    loadHeaderNotifications()
  }
}

onMounted(() => {
  if (!isAdminContext.value) {
    syncAccessStatus()
  }
  if (adminAuth.isAuthenticated) {
    loadHeaderNotifications()
    startHeaderPolling()
  }
  window.addEventListener('visibilitychange', handleVisibility)
})

onUnmounted(() => {
  stopHeaderPolling()
  window.removeEventListener('visibilitychange', handleVisibility)
})

// Voter notification helpers
const loadVoterNotificationsHeader = async () => {
  if (!authStore.isAuthenticated) return
  voterNotifLoading.value = true
  try {
    const res = await api.get('notifications/')
    voterNotifItems.value = res.data?.items?.slice(0, 8) || []
    voterNotifUnread.value = res.data?.unread_count || 0
    voterNotifError.value = ''
  } catch (err) {
    voterNotifError.value = err.response?.data?.error || 'Failed to load notifications.'
  } finally {
    voterNotifLoading.value = false
  }
}

const markVoterNotificationsHeaderRead = async () => {
  if (!authStore.isAuthenticated) return
  try {
    await api.post('notifications/', { action: 'mark_all_read' })
    await loadVoterNotificationsHeader()
  } catch (err) {
    voterNotifError.value = err.response?.data?.error || 'Failed to mark as read.'
  }
}

const deleteVoterNotificationHeader = async (id) => {
  if (!authStore.isAuthenticated) return
  try {
    await api.post('notifications/', { action: 'delete', ids: [id] })
    await loadVoterNotificationsHeader()
  } catch (err) {
    voterNotifError.value = err.response?.data?.error || 'Failed to delete notification.'
  }
}

const markVoterNotificationHeaderRead = async (id) => {
  if (!authStore.isAuthenticated) return
  try {
    await api.post('notifications/', { action: 'mark_read', ids: [id] })
    await loadVoterNotificationsHeader()
  } catch (err) {
    voterNotifError.value = err.response?.data?.error || 'Failed to mark as read.'
  }
}

const deleteAllVoterNotificationsHeader = async () => {
  if (!authStore.isAuthenticated) return
  try {
    await api.post('notifications/', { action: 'delete_all' })
    await loadVoterNotificationsHeader()
  } catch (err) {
    voterNotifError.value = err.response?.data?.error || 'Failed to delete all notifications.'
  }
}

const toggleVoterNotifications = async () => {
  if (!voterNotifOpen.value && authStore.isAuthenticated) {
    voterNotifOpen.value = true
    await loadVoterNotificationsHeader()
  } else {
    voterNotifOpen.value = false
  }
}

const startVoterHeaderPolling = () => {
  if (voterNotifTimer.value) clearInterval(voterNotifTimer.value)
  if (!authStore.isAuthenticated) return
  voterNotifTimer.value = setInterval(loadVoterNotificationsHeader, 15000)
}

watch(
  () => authStore.isAuthenticated,
  (isAuthed) => {
    if (isAuthed) {
      loadVoterNotificationsHeader()
      startVoterHeaderPolling()
    } else {
      if (voterNotifTimer.value) clearInterval(voterNotifTimer.value)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="min-h-screen text-slate-800 app-shell" v-if="isAdminContext || accessAllowed">
    <header class="header-bar sticky top-0 z-20">
      <div class="relative max-w-screen-2xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <img
            :src="Logo"
            alt="HCAD Alumni"
            class="h-12 w-12 rounded-full border border-emerald-100 object-cover bg-white shadow-sm"
          />
          <div>
            <p class="text-sm font-semibold">
              {{ isAdminContext ? 'HCAD Admin Console' : 'HCAD Alumni Election System' }}
            </p>
            <p class="text-[11px] text-slate-500">
              {{ isAdminContext ? 'COMELEC / Staff access' : 'Holy Cross Academy of Digos Alumni Association Incorporated' }}
            </p>
          </div>
        </div>

        <!-- Admin header -->
        <template v-if="isAdminContext">
          <div class="flex items-center gap-3 text-[11px] text-slate-600 relative">
            <div v-if="adminAuth.isAuthenticated" class="relative">
              <button
                class="relative h-10 w-10 rounded-full border bg-white shadow-sm flex items-center justify-center transition outline-none focus:outline-none ring-0 ring-[rgba(196,151,60,0.55)] hover:bg-[rgba(196,151,60,0.12)]"
                :class="headerNotifOpen ? 'bg-[rgba(196,151,60,0.18)] ring-2 border-[var(--hcad-gold)] shadow-[0_0_0_3px_rgba(196,151,60,0.15)]' : 'border-slate-200'"
                @click="toggleHeaderNotifications"
                aria-label="Notifications"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M9 17a3 3 0 0 0 6 0" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <span
                  v-if="headerNotifUnread"
                  class="absolute -top-1 -right-1 min-w-[18px] h-5 px-1 rounded-full bg-rose-500 text-white text-[10px] font-semibold flex items-center justify-center"
                >
                  {{ headerNotifUnread > 9 ? '9+' : headerNotifUnread }}
                </span>
              </button>

              <div
                v-if="headerNotifOpen"
                class="absolute right-0 mt-3 rounded-2xl border border-slate-200 bg-white shadow-2xl backdrop-blur p-3 z-50 ring-1 ring-slate-100"
                :class="headerNotifExpanded ? 'w-[28rem] max-w-[28rem]' : 'w-80 max-w-xs sm:max-w-sm'"
                style="max-width: min(90vw, 28rem);"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="text-sm font-semibold text-slate-800">Notifications</p>
                    <p class="text-[11px] text-slate-500">
                      <span :class="headerNotifUnread ? 'text-rose-600 font-semibold' : ''">{{ headerNotifUnread }} unread</span>
                    </p>
                  </div>
                  <div class="flex gap-1">
                    <button
                      class="text-[11px] px-2 py-1 rounded-lg border border-slate-200 hover:bg-slate-100"
                      @click="loadHeaderNotifications"
                      :disabled="headerNotifLoading"
                    >
                      Refresh
                    </button>
                    <button
                      class="text-[11px] px-2 py-1 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-60"
                      @click="markHeaderNotificationsRead"
                      :disabled="headerNotifLoading || headerNotifUnread === 0"
                    >
                      Mark read
                    </button>
                  </div>
                </div>

                <p v-if="headerNotifError" class="text-[11px] text-rose-600 mt-2">{{ headerNotifError }}</p>
                <p v-else-if="headerNotifLoading" class="text-[11px] text-slate-500 mt-2">Loading...</p>
                <p v-else-if="!headerNotifItems.length" class="text-[11px] text-slate-500 mt-2">No notifications yet.</p>
                <ul
                  v-else
                  class="mt-2 divide-y divide-slate-200 text-[11px] text-slate-700"
                  :class="headerNotifExpanded ? 'max-h-[28rem]' : 'max-h-64'"
                  style="overflow-y: auto;"
                >
                  <li v-for="n in headerNotifItems" :key="n.id" class="py-2 flex items-start gap-2">
                    <span class="mt-0.5 h-2 w-2 rounded-full" :class="n.is_read ? 'bg-slate-300' : 'bg-emerald-500'"></span>
                    <div
                      class="flex-1 cursor-pointer rounded-lg hover:bg-slate-50 px-2 -mx-2 py-1"
                      @click="handleHeaderNotifClick(n)"
                    >
                      <p class="font-semibold capitalize text-slate-800">{{ n.type || 'Notice' }}</p>
                      <p class="text-slate-700">{{ n.message }}</p>
                      <p class="text-[10px] text-slate-500">{{ formatHeaderNotifDate(n.created_at) }}</p>
                    </div>
                    <div v-if="headerNotifExpanded" class="flex flex-col gap-1">
                      <button
                        class="text-[10px] px-2 py-1 rounded border border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        @click="markHeaderNotificationRead(n.id)"
                        :disabled="n.is_read"
                      >
                        Mark read
                      </button>
                      <button
                        class="text-[10px] px-2 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50"
                        @click="deleteHeaderNotification(n.id)"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                </ul>
                <RouterLink
                  to="/admin"
                  class="mt-2 inline-flex items-center justify-center w-full text-[11px] px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100"
                  @click="headerNotifExpanded = !headerNotifExpanded"
                >
                  {{ headerNotifExpanded ? 'Collapse' : 'Expand' }}
                </RouterLink>
                <div v-if="headerNotifExpanded" class="mt-2 flex items-center justify-between gap-2">
                  <button
                    class="text-[11px] px-2 py-1 rounded-lg border border-rose-300 text-rose-700 bg-rose-50 hover:bg-rose-100 flex-1"
                    :disabled="headerNotifLoading || !headerNotifItems.length"
                    @click="deleteAllHeaderNotifications"
                  >
                    Delete all
                  </button>
                </div>
              </div>
            </div>

            <div v-if="adminAuth.isAuthenticated" class="hidden sm:block text-right leading-tight">
              <p class="font-semibold">Admin: {{ adminAuth.admin?.full_name || adminAuth.admin?.username }}</p>
            </div>

            <RouterLink
              v-if="adminAuth.isAuthenticated"
              to="/admin"
              class="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs shadow-sm hover:bg-emerald-700 text-white admin-dashboard-link"
            >
              Dashboard
            </RouterLink>
            <RouterLink v-else to="/admin-login" class="px-3 py-1.5 rounded-lg border text-xs hover:bg-slate-100">Admin Login</RouterLink>
          </div>
        </template>

        <!-- Voter/landing header -->
        <template v-else>
          <nav class="hidden sm:flex items-center gap-2 text-xs font-medium">
            <RouterLink
              v-for="link in voterLinks"
              :key="link.to"
              :to="link.to"
              class="px-3 py-1.5 rounded-lg hover:bg-slate-100"
              active-class="bg-emerald-50 text-emerald-700"
            >
              {{ link.label }}
            </RouterLink>
          </nav>

          <div class="flex items-center gap-2 text-[11px] text-slate-600">
            <div v-if="authStore.isAuthenticated" class="hidden sm:block text-right">
              <p class="font-semibold">{{ authStore.voter?.name }}</p>
              <p>Voter ID: {{ authStore.voter?.voter_id }}</p>
            </div>
            <div v-if="authStore.isAuthenticated" class="relative">
              <button
                class="relative h-10 w-10 rounded-full border bg-white shadow-sm flex items-center justify-center transition outline-none focus:outline-none ring-0 ring-[rgba(196,151,60,0.55)] hover:bg-[rgba(196,151,60,0.12)]"
                :class="voterNotifOpen ? 'bg-[rgba(196,151,60,0.18)] ring-2 border-[var(--hcad-gold)] shadow-[0_0_0_3px_rgba(196,151,60,0.15)]' : 'border-slate-200'"
                @click="toggleVoterNotifications"
                aria-label="Notifications"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M9 17a3 3 0 0 0 6 0" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <span
                  v-if="voterNotifUnread"
                  class="absolute -top-1 -right-1 min-w-[18px] h-5 px-1 rounded-full bg-rose-500 text-white text-[10px] font-semibold flex items-center justify-center"
                >
                  {{ voterNotifUnread > 9 ? '9+' : voterNotifUnread }}
                </span>
              </button>
              <div
                v-if="voterNotifOpen"
                class="absolute left-1/2 sm:left-auto sm:right-0 mt-2 rounded-2xl border border-slate-200 bg-white/95 shadow-2xl backdrop-blur p-4 z-30 transform -translate-x-1/2 sm:translate-x-0"
                :class="voterNotifOpen ? 'w-[calc(100vw-2.5rem)] max-w-[22rem] sm:w-96 sm:max-w-md' : ''"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="text-sm font-semibold text-slate-800">Notifications</p>
                    <p class="text-[11px] text-slate-500">
                      <span :class="voterNotifUnread ? 'text-rose-600 font-semibold' : ''">{{ voterNotifUnread }} unread</span>
                    </p>
                  </div>
                  <button
                    class="text-[11px] px-2 py-1 rounded-lg border border-slate-200 hover:bg-slate-100 min-w-[84px]"
                    @click="loadVoterNotificationsHeader"
                    :disabled="voterNotifLoading"
                  >
                    Refresh
                  </button>
                </div>
                <p v-if="voterNotifError" class="text-[11px] text-rose-600 mt-2">{{ voterNotifError }}</p>
                <p v-else-if="voterNotifLoading" class="text-[11px] text-slate-500 mt-2">Loading...</p>
                <p v-else-if="!voterNotifItems.length" class="text-[11px] text-slate-500 mt-2">No notifications yet.</p>
                <ul
                  v-else
                  class="mt-2 divide-y divide-slate-200 text-[11px] text-slate-700 max-h-[60vh] sm:max-h-64 overflow-y-auto"
                >
                  <li v-for="n in voterNotifItems" :key="n.id" class="py-2 flex items-start gap-2">
                    <span class="mt-0.5 h-2 w-2 rounded-full" :class="n.is_read ? 'bg-slate-300' : 'bg-emerald-500'"></span>
                    <div class="flex-1">
                      <p class="text-slate-700">{{ n.message }}</p>
                      <p class="text-[10px] text-slate-500">{{ new Date(n.created_at).toLocaleString() }}</p>
                    </div>
                    <div class="flex flex-col items-end gap-1">
                      <button
                        class="text-[10px] px-2 py-1 rounded border border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        @click="markVoterNotificationHeaderRead(n.id)"
                        :disabled="voterNotifLoading || n.is_read"
                      >
                        {{ n.is_read ? 'Read' : 'Mark read' }}
                      </button>
                      <button
                        class="text-[10px] px-2 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50"
                        @click="deleteVoterNotificationHeader(n.id)"
                        :disabled="voterNotifLoading"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                </ul>
                <div class="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    class="inline-flex items-center justify-center w-full text-[11px] px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100"
                    @click="markVoterNotificationsHeaderRead"
                    :disabled="voterNotifLoading || voterNotifUnread === 0"
                  >
                    Mark all read
                  </button>
                  <button
                    class="inline-flex items-center justify-center w-full text-[11px] px-3 py-1.5 rounded-lg border border-rose-200 text-rose-700 hover:bg-rose-50"
                    @click="deleteAllVoterNotificationsHeader"
                    :disabled="voterNotifLoading || !voterNotifItems.length"
                  >
                    Delete all
                  </button>
                </div>
              </div>
            </div>
            <RouterLink
              v-if="!authStore.isAuthenticated"
              to="/login"
              class="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs shadow-sm hover:bg-emerald-700 voter-login-link"
            >
              Voter Login
            </RouterLink>
            <button
              v-else
              @click="authStore.logout(); $router.push('/login')"
              class="px-3 py-1.5 rounded-lg border border-slate-300 text-xs hover:bg-slate-100"
            >
              Logout
            </button>
          </div>
        </template>
      </div>
    </header>

    <!-- Voter navigation for small screens: keep links visible below the header -->
    <div v-if="!isAdminContext" class="sm:hidden px-3 pt-3 voter-nav-sticky">
      <div class="bg-white/95 backdrop-blur border border-slate-200 shadow-xl rounded-2xl p-3">
        <p class="text-xs font-semibold text-slate-600 mb-2">Navigation</p>
        <div class="flex flex-wrap gap-2 justify-center text-center">
          <RouterLink
            v-for="link in voterLinks"
            :key="link.to"
            :to="link.to"
            class="px-3 py-2 rounded-lg text-xs font-semibold text-slate-800 border border-slate-200 hover:bg-slate-50"
            active-class="bg-emerald-50 text-emerald-700 border-emerald-200"
          >
            {{ link.label }}
          </RouterLink>
        </div>
      </div>
    </div>

    <main :class="['max-w-full mx-0 px-2 sm:px-3 lg:px-4 py-6', isAdminContext ? 'admin-dashboard' : 'voter-shell']">
      <RouterView />
    </main>
  </div>
  <div v-else class="min-h-screen flex items-center justify-center app-shell px-4">
    <div class="w-full max-w-md bg-white/90 backdrop-blur border border-slate-200 shadow-2xl rounded-2xl p-6 space-y-4">
      <div class="flex items-center gap-3">
        <img :src="Logo" alt="HCAD Alumni" class="h-12 w-12 rounded-full border border-emerald-100 object-cover bg-white shadow-sm" />
        <div>
          <p class="text-lg font-semibold text-slate-800">HCAD Alumni Election</p>
          <p class="text-sm text-slate-600">Enter the shared passcode to continue.</p>
        </div>
      </div>
      <div class="space-y-2">
        <label class="text-sm font-semibold text-slate-700" for="access-code">Passcode</label>
        <input
          id="access-code"
          v-model="accessCodeInput"
          type="password"
          class="w-full rounded-xl border border-slate-200 px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-[rgba(196,151,60,0.35)] focus:border-[var(--hcad-gold)]"
          placeholder="Enter passcode"
          @keyup.enter="submitAccessCode"
        />
        <p v-if="accessError" class="text-sm text-rose-600">{{ accessError }}</p>
        <p class="text-[13px] text-slate-500">We will remember this on this device until you clear your browser data or the admin changes the passcode.</p>
      </div>
      <button
        class="w-full rounded-xl bg-emerald-600 text-white font-semibold py-2.5 shadow-sm hover:bg-emerald-700 disabled:opacity-60"
        :disabled="accessChecking"
        @click="submitAccessCode"
      >
        {{ accessChecking ? 'Checking...' : 'Continue' }}
      </button>
    </div>
  </div>
</template>

<style>
:root {
  --hcad-navy: #0f2342;
  --hcad-gold: #c4973c;
  --hcad-ivory: #f8f6f1;
  --hcad-sage: #dbe2cf;
  --hcad-navy-dark: #0b1a31;
  --hcad-gold-dark: #a77e2e;
}

.app-shell {
  background: radial-gradient(circle at 15% 20%, rgba(196, 151, 60, 0.12), transparent 30%),
    radial-gradient(circle at 80% 0%, rgba(15, 35, 66, 0.08), transparent 28%),
    linear-gradient(180deg, #f9fafb 0%, #f1f4f8 100%);
}

/* Accessibility: larger default sizing for elderly users */
body {
  font-size: 18px;
  line-height: 1.6;
}
.text-xs {
  font-size: 0.95rem !important;
}
.text-sm {
  font-size: 1.05rem !important;
}
input,
select,
textarea {
  font-size: 1rem !important;
  padding: 0.55rem 0.75rem !important;
}
button {
  font-size: 1rem !important;
}

.header-bar {
  background: linear-gradient(90deg, rgba(15, 35, 66, 0.08), rgba(196, 151, 60, 0.12), rgba(255, 255, 255, 0.92));
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(15, 35, 66, 0.08);
  box-shadow: 0 4px 18px rgba(15, 35, 66, 0.06);
}

.header-bar a.router-link-active {
  color: var(--hcad-navy);
  background: linear-gradient(90deg, rgba(196, 151, 60, 0.16), rgba(15, 35, 66, 0.08));
  transition: all 160ms ease;
}
.admin-dashboard-link {
  color: #ffffff !important;
}
.voter-login-link {
  color: #ffffff !important;
}

/* Palette overrides for Tailwind greens to align with HCAD brand */
.bg-emerald-600,
.hover\:bg-emerald-600:hover {
  background-color: var(--hcad-navy) !important;
}
.hover\:bg-emerald-700:hover,
.bg-emerald-700 {
  background-color: var(--hcad-navy-dark) !important;
}
.bg-emerald-50 {
  background-color: rgba(196, 151, 60, 0.08) !important;
}
.text-emerald-600,
.text-emerald-700 {
  color: var(--hcad-navy) !important;
}
.border-emerald-200\/70,
.border-emerald-100 {
  border-color: rgba(196, 151, 60, 0.5) !important;
}
.bg-emerald-500 {
  background-color: var(--hcad-gold) !important;
}
.hover\:bg-emerald-50:hover {
  background-color: rgba(196, 151, 60, 0.12) !important;
}
.bg-emerald-50\/30 {
  background-color: rgba(196, 151, 60, 0.15) !important;
}
.text-emerald-50 {
  color: var(--hcad-ivory) !important;
}

/* Pills / tabs */
.router-link-active {
  border-color: rgba(196, 151, 60, 0.4) !important;
}

/* Buttons with borders */
.border {
  border-color: rgba(15, 35, 66, 0.08);
}

/* Consistent hover affordance for all buttons/rounded links */
button,
a[class*='rounded'] {
  transition: transform 150ms ease, box-shadow 150ms ease, background-color 150ms ease, border-color 150ms ease, color 150ms ease;
}
button:hover,
a[class*='rounded']:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.12);
}
button:active,
a[class*='rounded']:active {
  transform: translateY(-0.5px);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
}

/* Smooth bar fill animation for vote tallies */
.vote-bar-animate {
  transition: width 650ms ease-out, background-position 650ms ease-out;
  will-change: width;
}

/* Elevated glowing treatment for summary cards */
.summary-glow {
  box-shadow:
    0 16px 36px rgba(196, 151, 60, 0.25),
    0 0 0 1px rgba(196, 151, 60, 0.18),
    0 12px 26px rgba(15, 35, 66, 0.08);
  animation: summaryGlow 2.6s ease-in-out infinite alternate;
  transition: transform 180ms ease, box-shadow 180ms ease;
}

.summary-shine {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    115deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.22) 30%,
    rgba(255, 255, 255, 0.5) 50%,
    rgba(255, 255, 255, 0.22) 70%,
    rgba(255, 255, 255, 0) 100%
  );
  background-size: 250% 250%;
  animation: sweepShine 3.5s ease-in-out infinite;
  mix-blend-mode: screen;
  z-index: 0;
}

.summary-overlay {
  z-index: 0;
}

.summary-card > :not(.summary-overlay):not(.summary-shine) {
  position: relative;
  z-index: 1;
}

.summary-card:hover {
  transform: translateY(-4px);
  box-shadow:
    0 20px 42px rgba(196, 151, 60, 0.32),
    0 0 0 1px rgba(196, 151, 60, 0.22),
    0 16px 30px rgba(15, 35, 66, 0.12);
}

@keyframes summaryGlow {
  0% {
    box-shadow:
      0 12px 28px rgba(196, 151, 60, 0.18),
      0 0 0 1px rgba(196, 151, 60, 0.16),
      0 8px 18px rgba(15, 35, 66, 0.05);
    filter: brightness(1);
  }
  100% {
    box-shadow:
      0 20px 46px rgba(196, 151, 60, 0.38),
      0 0 0 3px rgba(196, 151, 60, 0.28),
      0 18px 34px rgba(15, 35, 66, 0.14);
    filter: brightness(1.05);
  }
}

@keyframes sweepShine {
  0% {
    background-position: -80% 50%;
  }
  50% {
    background-position: 120% 50%;
  }
  100% {
    background-position: 220% 50%;
  }
}

/* Gold-accent form fields (admin) */
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

/* Gold-accent form fields (voter) */
.voter-shell input:not([type='checkbox']):not([type='radio']):not([type='range']):not([type='button']):not([type='submit']):not([type='reset']),
.voter-shell textarea,
.voter-shell select {
  border: 1px solid transparent;
  background-image: linear-gradient(#ffffff, #ffffff),
    linear-gradient(135deg, rgba(196, 151, 60, 0.55), rgba(15, 35, 66, 0.28));
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow: 0 2px 10px rgba(15, 35, 66, 0.06);
  transition: box-shadow 150ms ease, transform 150ms ease;
}
.voter-shell input:not([type='checkbox']):not([type='radio']):not([type='range']):not([type='button']):not([type='submit']):not([type='reset']):focus,
.voter-shell textarea:focus,
.voter-shell select:focus {
  box-shadow: 0 4px 14px rgba(15, 35, 66, 0.12);
  transform: translateY(-1px);
  outline: none;
}

/* Keep the voter nav card in view on small screens */
.voter-nav-sticky {
  position: sticky;
  top: 4.5rem;
  z-index: 15;
}
</style>
