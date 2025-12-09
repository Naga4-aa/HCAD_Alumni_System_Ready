<!-- src/views/ResultsView.vue -->
<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '../api'
import { countdownTo, formatDateTime, toMs } from '../utils/time'

const results = ref(null)
const election = ref(null)
const loading = ref(true)
const error = ref('')
const now = ref(Date.now())
const candidatePlaceholder =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect width='80' height='80' rx='40' fill='%23dfe4ea'/><path d='M40 40a12 12 0 1 0-0.001-24.001A12 12 0 0 0 40 40zm0 8c-11.046 0-20 6.268-20 14v4h40v-4c0-7.732-8.954-14-20-14z' fill='%2390a4ae'/></svg>"

const hasActiveElection = computed(() => !!election.value && election.value.is_active)
const hasTimeline = computed(() => {
  const e = election.value
  if (!e) return false
  const required = [e.nomination_start, e.nomination_end, e.voting_start, e.voting_end]
  return required.every((v) => {
    const ts = toMs(v)
    return ts !== null && !Number.isNaN(ts)
  })
})

const resultsCountdown = computed(() => {
  if (!hasTimeline.value || !election.value?.results_at) return null
  const target = toMs(election.value.results_at)
  if (!target) return null
  return countdownTo(target, now.value)
})

const resultsEta = computed(() => {
  if (!hasTimeline.value || !election.value?.results_at) return null
  return formatDateTime(election.value.results_at)
})

const winnersSummary = computed(() => {
  if (!results.value?.positions?.length) return []
  return results.value.positions
    .map((pos) => {
      const candidates = pos.candidates || []
      if (!candidates.length) return null
      const maxVotes = Math.max(...candidates.map((c) => c.votes || 0), 0)
      const winners = candidates.filter((c) => (c.winner ? true : (c.votes || 0) === maxVotes))
      return {
        position_id: pos.position_id,
        position: pos.position,
        candidates: winners,
        votes: maxVotes,
      }
    })
    .filter(Boolean)
})

const activePositionId = ref(null)
const activePosition = computed(() => {
  return results.value?.positions?.find((p) => p.position_id === activePositionId.value) || null
})

const templateModalOpen = ref(false)
const templateImageData = ref('')
const templateGenerating = ref(false)
const templateError = ref('')

const loadImageSafely = (url) => {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = url || candidatePlaceholder
  })
}

const buildTemplateImage = async (winners) => {
  const width = 1700
  const padding = 120
  const cardGap = 40
  const colGap = 36
  const cols = 2
  const rows = Math.ceil(winners.length / cols)
  const cardHeight = 200
  const headerHeight = 230
  const footerHeight = 150
  const totalHeight = headerHeight + footerHeight + rows * cardHeight + Math.max(0, rows - 1) * cardGap + padding * 2

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = totalHeight
  const ctx = canvas.getContext('2d')

  const colWidth = (width - padding * 2 - colGap) / cols

  // background
  const bgGrad = ctx.createLinearGradient(0, 0, width, totalHeight)
  bgGrad.addColorStop(0, '#0a1323')
  bgGrad.addColorStop(1, '#162a4c')
  ctx.fillStyle = bgGrad
  ctx.fillRect(0, 0, width, totalHeight)

  // vignette
  const vignette = ctx.createRadialGradient(width / 2, totalHeight / 2, width * 0.2, width / 2, totalHeight / 2, width * 0.7)
  vignette.addColorStop(0, 'rgba(0,0,0,0)')
  vignette.addColorStop(1, 'rgba(0,0,0,0.25)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, width, totalHeight)

  // soft glow overlay
  const glowGrad = ctx.createRadialGradient(width * 0.5, padding + headerHeight / 1.2, width * 0.35, width * 0.5, padding + headerHeight, width * 0.9)
  glowGrad.addColorStop(0, 'rgba(255,215,160,0.16)')
  glowGrad.addColorStop(1, 'rgba(255,215,160,0)')
  ctx.fillStyle = glowGrad
  ctx.fillRect(0, 0, width, totalHeight)

  // diagonal accent
  ctx.fillStyle = 'rgba(255, 215, 160, 0.08)'
  ctx.beginPath()
  ctx.moveTo(width * 0.7, 0)
  ctx.lineTo(width, 0)
  ctx.lineTo(width, totalHeight * 0.35)
  ctx.closePath()
  ctx.fill()

  // header
  const headerGrad = ctx.createLinearGradient(0, 0, 0, headerHeight)
  headerGrad.addColorStop(0, '#f5e7c8')
  headerGrad.addColorStop(1, '#d9bf82')
  ctx.fillStyle = headerGrad
  const headerRadius = 24
  const headerX = padding
  const headerY = padding / 2
  const headerW = width - padding * 2
  const headerH = headerHeight
  ctx.beginPath()
  ctx.moveTo(headerX + headerRadius, headerY)
  ctx.lineTo(headerX + headerW - headerRadius, headerY)
  ctx.quadraticCurveTo(headerX + headerW, headerY, headerX + headerW, headerY + headerRadius)
  ctx.lineTo(headerX + headerW, headerY + headerH - headerRadius)
  ctx.quadraticCurveTo(headerX + headerW, headerY + headerH, headerX + headerW - headerRadius, headerY + headerH)
  ctx.lineTo(headerX + headerRadius, headerY + headerH)
  ctx.quadraticCurveTo(headerX, headerY + headerH, headerX, headerY + headerH - headerRadius)
  ctx.lineTo(headerX, headerY + headerRadius)
  ctx.quadraticCurveTo(headerX, headerY, headerX + headerRadius, headerY)
  ctx.closePath()
  ctx.fill()

  ctx.fillStyle = '#0f1b2f'
  ctx.font = 'bold 62px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText('HCAD ELECTION RESULTS', headerX + 40, headerY + 90)
  ctx.font = '600 34px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText('Congratulations to the winning candidates', headerX + 40, headerY + 145)
  ctx.strokeStyle = '#b5892f'
  ctx.lineWidth = 3
  ctx.beginPath()
  ctx.moveTo(headerX + 38, headerY + 165)
  ctx.lineTo(headerX + headerW - 38, headerY + 165)
  ctx.stroke()

  // header badge
  const badgeX = width - padding - 90
  const badgeY = padding + 70
  ctx.beginPath()
  ctx.arc(badgeX, badgeY, 40, 0, Math.PI * 2)
  const badgeGrad = ctx.createLinearGradient(badgeX - 40, badgeY - 40, badgeX + 40, badgeY + 40)
  badgeGrad.addColorStop(0, '#f7d68f')
  badgeGrad.addColorStop(1, '#c79b36')
  ctx.fillStyle = badgeGrad
  ctx.fill()
  ctx.closePath()
  ctx.fillStyle = '#0f1b2f'
  ctx.font = '700 20px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText('HC', badgeX - 16, badgeY - 2)
  ctx.font = '600 16px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText('AD', badgeX - 15, badgeY + 18)

  // footer
  const footerGrad = ctx.createLinearGradient(0, 0, width, 0)
  footerGrad.addColorStop(0, '#d9bf82')
  footerGrad.addColorStop(1, '#b48a2f')
  ctx.fillStyle = footerGrad
  const footerRadius = 24
  const footerX = padding
  const footerY = totalHeight - footerHeight - padding / 2
  const footerW = width - padding * 2
  const footerH = footerHeight
  ctx.beginPath()
  ctx.moveTo(footerX + footerRadius, footerY)
  ctx.lineTo(footerX + footerW - footerRadius, footerY)
  ctx.quadraticCurveTo(footerX + footerW, footerY, footerX + footerW, footerY + footerRadius)
  ctx.lineTo(footerX + footerW, footerY + footerH - footerRadius)
  ctx.quadraticCurveTo(footerX + footerW, footerY + footerH, footerX + footerW - footerRadius, footerY + footerH)
  ctx.lineTo(footerX + footerRadius, footerY + footerH)
  ctx.quadraticCurveTo(footerX, footerY + footerH, footerX, footerY + footerH - footerRadius)
  ctx.lineTo(footerX, footerY + footerRadius)
  ctx.quadraticCurveTo(footerX, footerY, footerX + footerRadius, footerY)
  ctx.closePath()
  ctx.fill()
  ctx.fillStyle = '#0f1b2f'
  ctx.font = '700 28px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText('Official HCAD Alumni Election', padding + 40, totalHeight - footerHeight + 34)
  const dateStr = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  ctx.font = '500 22px "Helvetica Neue", Arial, sans-serif'
  ctx.fillText(`Published ${dateStr}`, padding + 40, totalHeight - footerHeight + 72)
  ctx.fillText('Source: HCAD COMELEC Board', padding + 40, totalHeight - footerHeight + 104)
  ctx.fillStyle = 'rgba(15,27,47,0.16)'
  ctx.fillRect(footerX + 320, footerY, 2, footerH)
  ctx.fillRect(footerX + footerW - 320, footerY, 2, footerH)

  // cards
  ctx.font = '600 28px "Helvetica Neue", Arial, sans-serif'
  const startY = padding + headerHeight + cardGap + 10
  const avatarSize = 120
  const cardRadius = 30
  const badgeColor = '#f5c451'
  const fallbackImg = await loadImageSafely(candidatePlaceholder)

  for (let i = 0; i < winners.length; i += 1) {
    const row = Math.floor(i / cols)
    const col = i % cols
    const x = padding + col * (colWidth + colGap)
    const y = startY + row * (cardHeight + cardGap)

    const cardGrad = ctx.createLinearGradient(x, y, x + colWidth, y + cardHeight)
    cardGrad.addColorStop(0, '#173a6a')
    cardGrad.addColorStop(1, '#0f2744')
    ctx.fillStyle = cardGrad

    // card container
    ctx.beginPath()
    ctx.moveTo(x + cardRadius, y)
    ctx.lineTo(x + colWidth - cardRadius, y)
    ctx.quadraticCurveTo(x + colWidth, y, x + colWidth, y + cardRadius)
    ctx.lineTo(x + colWidth, y + cardHeight - cardRadius)
    ctx.quadraticCurveTo(x + colWidth, y + cardHeight, x + colWidth - cardRadius, y + cardHeight)
    ctx.lineTo(x + cardRadius, y + cardHeight)
    ctx.quadraticCurveTo(x, y + cardHeight, x, y + cardHeight - cardRadius)
    ctx.lineTo(x, y + cardRadius)
    ctx.quadraticCurveTo(x, y, x + cardRadius, y)
    ctx.closePath()
    ctx.fill()
    ctx.strokeStyle = 'rgba(255,255,255,0.05)'
    ctx.lineWidth = 1
    ctx.stroke()
    // subtle top highlight
    const highlight = ctx.createLinearGradient(x, y, x, y + cardHeight * 0.4)
    highlight.addColorStop(0, 'rgba(255,255,255,0.12)')
    highlight.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = highlight
    ctx.fill()

    // photo circle with ring
    const centerY = y + cardHeight / 2
    const avatarX = x + 30 + avatarSize / 2
    ctx.save()
    ctx.beginPath()
    ctx.arc(avatarX, centerY, avatarSize / 2 + 8, 0, Math.PI * 2)
    const ringGrad = ctx.createLinearGradient(avatarX - avatarSize, centerY - avatarSize, avatarX + avatarSize, centerY + avatarSize)
    ringGrad.addColorStop(0, '#f7d68f')
    ringGrad.addColorStop(1, '#c99b3c')
    ctx.fillStyle = ringGrad
    ctx.fill()
    ctx.closePath()

    ctx.beginPath()
    ctx.arc(avatarX, centerY, avatarSize / 2 - 2, 0, Math.PI * 2)
    ctx.closePath()
    ctx.clip()

    const photo = (winners[i].photo_url && (await loadImageSafely(winners[i].photo_url))) || fallbackImg
    const size = avatarSize - 8
    if (photo) {
      ctx.drawImage(photo, avatarX - size / 2, centerY - size / 2, size, size)
    } else {
      ctx.fillStyle = '#d9d9d9'
      ctx.fillRect(avatarX - size / 2, centerY - size / 2, size, size)
    }
    ctx.restore()

    // text
    ctx.fillStyle = '#f4f6fa'
    ctx.font = '700 30px "Helvetica Neue", Arial, sans-serif'
    ctx.fillText(winners[i].full_name || 'Winner', avatarX + avatarSize / 2 + 44, centerY - 4)

    ctx.fillStyle = '#d9bf82'
    ctx.font = '500 22px "Helvetica Neue", Arial, sans-serif'
    ctx.fillText(winners[i].position || 'Position', avatarX + avatarSize / 2 + 44, centerY + 32)

    // accent line under position
    ctx.strokeStyle = 'rgba(217,191,130,0.5)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(avatarX + avatarSize / 2 + 44, centerY + 38)
    ctx.lineTo(avatarX + avatarSize / 2 + 240, centerY + 38)
    ctx.stroke()
  }

  return canvas.toDataURL('image/png')
}

const generateTemplate = async () => {
  templateGenerating.value = true
  templateError.value = ''
  try {
    const winners = winnersSummary.value.flatMap((item) =>
      (item.candidates || []).map((cand) => ({
        full_name: cand.full_name,
        position: item.position,
        photo_url: cand.photo_url,
      })),
    )
    if (!winners.length) {
      templateError.value = 'No winners available to generate a template.'
      templateGenerating.value = false
      return
    }
    templateImageData.value = await buildTemplateImage(winners)
    templateModalOpen.value = true
  } catch (err) {
    templateError.value = 'Failed to generate template.'
  } finally {
    templateGenerating.value = false
  }
}

const downloadTemplate = () => {
  if (!templateImageData.value) return
  const link = document.createElement('a')
  link.href = templateImageData.value
  link.download = `hcad-election-results-${Date.now()}.png`
  link.click()
}

const printTemplate = () => {
  if (!templateImageData.value) return
  const win = window.open('', '_blank', 'noopener,noreferrer')
  if (!win) return
  const html = `
    <html>
      <head><title>HCAD Results Template</title></head>
      <body style="margin:0;display:flex;align-items:center;justify-content:center;background:#0b1425;">
        <img src="${templateImageData.value}" style="max-width:100%;height:auto;" />
        <script>setTimeout(() => { window.print(); }, 400);<\/script>
      </body>
    </html>
  `
  win.document.write(html)
  win.document.close()
}

watch(
  () => results.value?.positions,
  (list) => {
    if (!list || list.length === 0) {
      activePositionId.value = null
      return
    }
    const exists = list.some((p) => p.position_id === activePositionId.value)
    activePositionId.value = exists ? activePositionId.value : list[0].position_id
  },
  { immediate: true },
)

const loadResults = async (opts = {}) => {
  const silent = opts.silent
  if (!silent) loading.value = true
  try {
    const res = await api.get('elections/results/')
    if (res.data?.published) {
      results.value = res.data
    } else {
      results.value = null
    }
  } catch (err) {
    error.value = err.response?.data?.error || 'Failed to load results.'
  } finally {
    if (!silent) loading.value = false
  }
}

const loadElection = async () => {
  try {
    const res = await api.get('elections/current/')
    election.value = res.data?.election || null
  } catch (err) {
    election.value = null
  }
}

let timerId
let refreshing = false
let publishTimer = null

const clearPublishTimer = () => {
  if (publishTimer) {
    clearTimeout(publishTimer)
    publishTimer = null
  }
}

const schedulePublishCheck = () => {
  clearPublishTimer()
  const target = toMs(election.value?.results_at)
  if (!target) return
  const msUntil = target - Date.now()
  if (msUntil <= 0) {
    loadResults({ silent: false })
    return
  }
  publishTimer = setTimeout(async () => {
    await loadResults({ silent: false })
    await loadElection()
    schedulePublishCheck()
  }, Math.min(msUntil + 1000, 6 * 60 * 60 * 1000))
}

const tick = async () => {
  now.value = Date.now()
  if (refreshing) return
  refreshing = true
  try {
    await Promise.all([loadResults({ silent: true }), loadElection()])
  } catch (e) {
    // ignore transient refresh errors
  } finally {
    refreshing = false
  }
  schedulePublishCheck()
}

onMounted(async () => {
  await Promise.all([loadResults(), loadElection()])
  schedulePublishCheck()
  timerId = setInterval(tick, 15000)
})

onUnmounted(() => {
  if (timerId) clearInterval(timerId)
  clearPublishTimer()
})
</script>

<template>
  <div class="space-y-4">
    <div class="bg-white/90 rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div class="space-y-1">
          <p class="text-xs uppercase tracking-wide text-emerald-600 font-semibold">Results</p>
          <h2 class="text-lg font-semibold">{{ results?.demo ? 'Demo results' : 'Official results' }}</h2>
          <p class="text-xs text-slate-500">
            <span v-if="results">Published {{ formatDateTime(results?.published_at) }}</span>
            <span v-else-if="loading">Checking publication status...</span>
            <span v-else>Results will appear here once COMELEC publishes them.</span>
          </p>
          <p v-if="!results && resultsEta" class="text-[11px] text-amber-700 mt-1">
            Expected at {{ resultsEta }}
            <span v-if="resultsCountdown">(in {{ resultsCountdown.text }})</span>
          </p>
          <p v-if="results?.demo" class="text-[11px] text-amber-700 mt-1">Demo mode: not official.</p>
        </div>
        <button
          class="px-3 py-1.5 rounded-lg text-xs border border-slate-200 hover:bg-emerald-50 self-start sm:self-auto"
          @click="loadResults"
        >
          Refresh
        </button>
      </div>
    </div>

    <div v-if="error" class="text-sm text-rose-600">{{ error }}</div>
    <div v-else-if="loading" class="text-sm text-slate-600">Loading...</div>

    <div v-else-if="results" class="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div class="space-y-3">
        <div class="flex flex-wrap gap-2">
          <button
            v-for="pos in results.positions || []"
            :key="pos.position_id"
            class="px-3 py-1.5 rounded-full border text-xs transition"
            :class="
              activePositionId === pos.position_id
                ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                : 'border-slate-300 bg-white hover:bg-emerald-50 text-slate-700'
            "
            @click="activePositionId = pos.position_id"
          >
            {{ pos.position }}
          </button>
        </div>

        <div
          v-if="activePosition"
          class="bg-white/90 rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm space-y-3"
        >
          <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h3 class="text-sm font-semibold text-slate-800">{{ activePosition.position }}</h3>
            <span class="text-[11px] text-slate-500">{{ activePosition.candidates?.length || 0 }} candidate(s)</span>
          </div>
          <ul class="space-y-3 text-sm text-slate-700">
            <li
              v-for="cand in activePosition.candidates"
              :key="cand.id"
              class="space-y-1"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3 min-w-0">
                  <div class="h-10 w-10 rounded-full border border-slate-200 bg-white overflow-hidden flex-shrink-0">
                    <img :src="cand.photo_url || candidatePlaceholder" alt="Candidate photo" class="h-full w-full object-cover" />
                  </div>
                  <div class="min-w-0">
                    <p class="font-semibold truncate" :class="{ 'text-[var(--hcad-navy)]': cand.winner }">{{ cand.full_name }}</p>
                    <p class="text-[11px] text-slate-500">
                      Batch {{ cand.batch_year }} - {{ cand.campus_chapter || 'Campus/Chapter not set' }}
                    </p>
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <p class="text-sm font-semibold text-slate-800">{{ cand.votes }} vote(s)</p>
                  <p v-if="cand.winner" class="text-[11px] text-[var(--hcad-navy)] font-semibold">Winner</p>
                </div>
              </div>
              <div class="h-2.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-[var(--hcad-gold)] to-[var(--hcad-navy)] transition-all duration-300 vote-bar-animate"
                  :style="{
                    width:
                      (Math.max(...activePosition.candidates.map((c) => c.votes), 1)
                        ? (cand.votes / Math.max(...activePosition.candidates.map((c) => c.votes), 1)) * 100
                        : 0) + '%',
                  }"
                ></div>
              </div>
            </li>
          </ul>
        </div>
        <p v-else class="text-sm text-slate-600">No positions to display.</p>
      </div>

      <div v-if="winnersSummary.length" class="space-y-3">
        <div class="bg-white/90 rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm space-y-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-slate-800">Election Results Summary</h3>
            <span class="text-[11px] text-slate-500">Top candidate(s) per position</span>
          </div>
          <div class="grid gap-3 max-h-[70vh] overflow-y-auto pr-1 pl-2 sm:pl-3 pt-2 pb-3 sm:pt-3 sm:pb-4">
            <div
              v-for="item in winnersSummary"
              :key="item.position_id"
              class="summary-card relative overflow-hidden rounded-2xl border border-amber-200/90 bg-gradient-to-br from-[#f7e3a3] via-[#d7b870] to-[#0f1b2f] p-3 shadow-[0_14px_34px_rgba(15,35,66,0.25)] space-y-2 summary-glow"
            >
              <span class="summary-overlay pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/40 via-transparent to-white/20"></span>
              <span class="summary-overlay pointer-events-none absolute -left-6 top-0 h-full w-24 rotate-[-5deg] bg-gradient-to-b from-[rgba(196,151,60,0.12)] via-transparent to-transparent blur-lg"></span>
              <span class="summary-shine rounded-2xl"></span>
              <p class="text-xs font-semibold text-slate-800 uppercase tracking-wide">{{ item.position }}</p>
              <div class="flex flex-col gap-2">
                <div
                  v-for="cand in item.candidates"
                  :key="cand.id"
                  class="flex gap-3 items-center rounded-xl border border-amber-100/70 bg-white/85 p-2.5 shadow-[0_6px_16px_rgba(15,35,66,0.06)]"
                >
                  <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 bg-white flex-shrink-0">
                    <img :src="cand.photo_url || candidatePlaceholder" alt="Winner photo" class="h-full w-full object-cover" />
                  </div>
                  <div class="flex-1 min-w-0 space-y-0.5">
                    <p class="text-base font-semibold text-slate-900 truncate">{{ cand.full_name }}</p>
                    <p class="text-[12px] text-slate-500 truncate">
                      Batch {{ cand.batch_year || 'N/A' }}
                      <span v-if="cand.campus_chapter"> · {{ cand.campus_chapter }}</span>
                    </p>
                    <p class="text-sm font-semibold text-[var(--hcad-navy)]">{{ cand.votes }} vote(s)</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="text-sm text-slate-600">Results not yet published.</div>

    <div
      v-if="templateModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 px-4"
      @click.self="templateModalOpen = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-auto border border-amber-100">
        <div class="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-200">
          <div>
            <p class="text-sm font-semibold text-slate-800">Share-ready template</p>
            <p class="text-[12px] text-slate-500">Download or print to PDF for social posts.</p>
          </div>
          <button
            class="text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100"
            @click="templateModalOpen = false"
          >
            Close
          </button>
        </div>
        <div class="p-4 sm:p-6 space-y-4">
          <div v-if="templateError" class="text-sm text-rose-600">{{ templateError }}</div>
          <div v-if="templateImageData" class="w-full border border-slate-200 rounded-xl bg-slate-50 p-3 max-h-[75vh] overflow-auto">
            <img :src="templateImageData" alt="Election results template" class="w-full h-auto rounded-lg shadow" />
          </div>
          <div class="flex flex-wrap gap-3">
            <button
              class="px-4 py-2 rounded-lg bg-[var(--hcad-navy)] text-white text-sm font-semibold shadow-sm hover:bg-[var(--hcad-navy-dark)]"
              @click="downloadTemplate"
              :disabled="!templateImageData"
            >
              Download PNG
            </button>
            <button
              class="px-4 py-2 rounded-lg border border-amber-300 bg-amber-50 text-sm font-semibold text-[var(--hcad-navy)] shadow-sm hover:bg-amber-100"
              @click="printTemplate"
              :disabled="!templateImageData"
            >
              Print / Save as PDF
            </button>
            <p class="text-[12px] text-slate-500">Tip: Use "Print" and choose "Save as PDF" for a PDF copy.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>



