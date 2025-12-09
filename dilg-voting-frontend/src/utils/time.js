// Simple time helpers for countdown displays across views.

// Convert an ISO/date string to a timestamp, returns null if invalid.
export function toMs(value) {
  const ts = new Date(value).getTime()
  return Number.isNaN(ts) ? null : ts
}

// Format a remaining duration with seconds (e.g., "1d 2h 03m 12s").
export function formatDuration(ms) {
  const abs = Math.max(0, Math.trunc(ms))
  const totalSeconds = Math.floor(abs / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const parts = []
  if (days) parts.push(`${days}d`)
  if (days || hours) parts.push(`${hours}h`)
  if (days || hours || minutes) parts.push(`${minutes.toString().padStart(2, '0')}m`)
  parts.push(`${seconds.toString().padStart(2, '0')}s`)
  return parts.join(' ')
}

// Build a countdown object given a target timestamp and current time.
export function countdownTo(targetMs, nowMs = Date.now()) {
  if (targetMs === null || targetMs === undefined) return null
  const diff = targetMs - nowMs
  return {
    raw: diff,
    isPast: diff < 0,
    text: formatDuration(Math.abs(diff)),
  }
}

// Display-friendly date string helper.
export function formatDateTime(value) {
  if (!value) return 'TBD'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
}
