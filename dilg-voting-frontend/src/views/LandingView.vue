<!-- src/views/LandingView.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api'

const election = ref(null)
const results = ref(null)
const loading = ref(true)
const resultsLoading = ref(true)

const formatDate = (value) => {
  if (!value) return 'TBD'
  try {
    return new Date(value).toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
  } catch (e) {
    return value
  }
}

const formatRange = (start, end) => {
  if (!start || !end) return 'To be announced'
  return `${formatDate(start)} → ${formatDate(end)}`
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

const loadResults = async () => {
  try {
    const res = await api.get('elections/results/')
    results.value = res.data || null
  } catch (err) {
    results.value = null
  } finally {
    resultsLoading.value = false
  }
}

const hasPublishedResults = computed(() => results.value?.published)
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

onMounted(async () => {
  await Promise.all([loadElection(), loadResults()])
})
</script>

<template>
  <div class="space-y-8">
    <section class="bg-gradient-to-r from-[var(--hcad-gold)] to-[var(--hcad-navy)] text-white rounded-3xl p-6 sm:p-10 shadow-xl">
      <p class="text-xs uppercase tracking-wide text-emerald-100">HCAD Alumni Association, Inc.</p>
      <h1 class="text-2xl sm:text-3xl font-semibold mt-2">HCAD Alumni Election System</h1>
      <p class="mt-3 max-w-3xl text-sm sm:text-base text-emerald-50">
        Nominate and vote for the HCADAA FYs 2025-2027 Officers.
      </p>
      <div class="mt-6 flex flex-wrap gap-3 text-sm">
        <RouterLink
          to="/login"
          class="px-4 py-2 rounded-lg bg-white text-emerald-700 font-semibold shadow-sm transition-all duration-150 hover:bg-emerald-50 hover:shadow-[0_6px_14px_rgba(0,0,0,0.15)] hover:-translate-y-[1px]"
          >Voter Login</RouterLink
        >
        <RouterLink
          to="/info"
          class="px-4 py-2 rounded-lg border border-emerald-200/70 bg-emerald-50/30 text-white transition-all duration-150 shadow-[0_2px_10px_rgba(0,0,0,0.08)] hover:bg-white/20 hover:border-white/70 hover:shadow-[0_6px_14px_rgba(0,0,0,0.15)] hover:text-white"
          >Registration Instructions</RouterLink
        >
      </div>
    </section>

    <section class="grid gap-4 md:grid-cols-3">
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <h3 class="text-sm font-semibold text-slate-800">Nomination Period</h3>
        <p class="text-xs text-slate-500">
          <span v-if="election">{{ formatRange(election.nomination_start, election.nomination_end) }}</span>
          <span v-else>To be announced</span>
        </p>
        <p class="text-xs text-slate-600 mt-2">Submit one nominee for any open position.</p>
      </div>
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <h3 class="text-sm font-semibold text-slate-800">Voting Period</h3>
        <p class="text-xs text-slate-500">
          <span v-if="election">{{ formatRange(election.voting_start, election.voting_end) }}</span>
          <span v-else>To be announced</span>
        </p>
        <p class="text-xs text-slate-600 mt-2">One ballot per voter. One vote per position.</p>
      </div>
      <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <h3 class="text-sm font-semibold text-slate-800">Results</h3>
        <p class="text-xs text-slate-500">
          <span v-if="election?.results_at">{{ formatDate(election.results_at) }}</span>
          <span v-else>To be announced</span>
        </p>
        <p class="text-xs text-slate-600 mt-2">
          <span v-if="hasPublishedResults">Published to all voters.</span>
          <span v-else>Will be shown here once officially published.</span>
        </p>
      </div>
    </section>

    <section class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-3 text-sm text-slate-700">
      <h2 class="text-lg font-semibold text-slate-900">How to participate</h2>
      <ol class="list-decimal list-inside space-y-2">
        <li>Use quick entry: enter your full name and batch/year, and check the consent box to proceed.</li>
        <li>Optional: add campus/chapter and contact details so admins can verify you if needed.</li>
        <li>
          During
          <strong>{{ election ? formatRange(election.nomination_start, election.nomination_end) : 'the nomination window' }}</strong>:
          submit one nomination (with reason and contact details).
        </li>
        <li>
          During
          <strong>{{ election ? formatRange(election.voting_start, election.voting_end) : 'the voting window' }}</strong>:
          select one candidate per position and submit your ballot once.
        </li>
      </ol>
      <p class="text-[11px] text-slate-500">Need help? Contact the HCAD Alumni office or your chapter lead.</p>
    </section>

    <section
      class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4"
      aria-label="Published results"
    >
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p class="text-xs uppercase tracking-wide text-emerald-600 font-semibold">Results</p>
          <h3 class="text-lg font-semibold">Official tallies</h3>
          <p class="text-xs text-slate-500">
            <span v-if="hasPublishedResults">
              Published {{ formatDate(results?.published_at) }}
            </span>
            <span v-else>Results will appear after COMELEC publishes them.</span>
          </p>
        </div>
        <div class="text-xs text-slate-600" v-if="resultsLoading">Loading results...</div>
      </div>

      <div v-if="hasPublishedResults" class="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div class="grid gap-4 md:grid-cols-2">
          <div
            v-for="pos in results?.positions || []"
            :key="pos.position_id"
            class="border rounded-xl p-4 shadow-sm bg-white"
          >
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-slate-800">{{ pos.position }}</h4>
              <span class="text-[11px] text-emerald-700 font-semibold">Published</span>
            </div>
            <ul class="space-y-3 text-sm text-slate-700">
              <li
                v-for="cand in pos.candidates"
                :key="cand.id"
                class="space-y-1"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <p class="font-semibold" :class="{ 'text-emerald-700': cand.winner }">
                      {{ cand.full_name }}
                    </p>
                    <p class="text-[11px] text-slate-500">
                      Batch {{ cand.batch_year }} - {{ cand.campus_chapter || 'Campus/Chapter not set' }}
                    </p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-semibold text-slate-800">{{ cand.votes }} vote(s)</p>
                    <p v-if="cand.winner" class="text-[11px] text-emerald-700 font-semibold">Winner</p>
                  </div>
                </div>
                <div class="h-2.5 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    class="h-full rounded-full bg-gradient-to-r from-[var(--hcad-gold)] to-[var(--hcad-navy)] transition-all duration-300 vote-bar-animate"
                    :style="{
                      width: (Math.max(...pos.candidates.map(c => c.votes), 1) ? (cand.votes / Math.max(...pos.candidates.map(c => c.votes), 1)) * 100 : 0) + '%'
                    }"
                  ></div>
                </div>
              </li>
            </ul>
          </div>
        </div>

      <div v-if="winnersSummary.length" class="space-y-3">
        <div class="bg-[#f7f8fa] rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm space-y-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-slate-800">Election Results Summary</h3>
            <span class="text-[11px] text-slate-500">Top candidate(s) per position</span>
          </div>
          <div class="grid gap-3 pl-1 pr-1 sm:px-2 pt-2 pb-3 sm:pt-3 sm:pb-4">
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
                    <img :src="cand.photo_url || 'https://placehold.co/80x80?text=No+Photo'" alt="Winner photo" class="h-full w-full object-cover" />
                  </div>
                  <div class="flex-1 min-w-0 space-y-0.5">
                    <p class="text-sm font-semibold text-slate-900 truncate">{{ cand.full_name }}</p>
                    <p class="text-[11px] text-slate-500 truncate">
                      Batch {{ cand.batch_year || 'N/A' }}
                      <span v-if="cand.campus_chapter"> · {{ cand.campus_chapter }}</span>
                    </p>
                    <p class="text-[12px] font-semibold text-[var(--hcad-navy)]">{{ cand.votes }} vote(s)</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>
    </section>
  </div>
</template>
