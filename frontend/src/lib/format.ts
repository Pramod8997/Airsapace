/** Formatting + small pure helpers (money, pct, dates, status → color). */

export const fmtINR = (v: number | null | undefined) =>
  v == null ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`

export const fmtNum = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : v.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtInt = (v: number | null | undefined) =>
  v == null ? '—' : Math.round(v).toLocaleString('en-IN')

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso + (iso.length === 10 ? 'T00:00:00' : '')).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

export const fmtTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'

/** change badge class: green up / red down / muted flat — never color-only (has sign) */
export const changeClass = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v > 0.05 ? 'text-positive' : v < -0.05 ? 'text-critical' : 'text-muted'

/** health → dot + label. non-color-only: label always present */
export const healthOf = (availabilityRate: number): { label: string; cls: string; dot: string } => {
  if (availabilityRate >= 0.9) return { label: 'Healthy', cls: 'text-positive', dot: 'bg-positive' }
  if (availabilityRate >= 0.6) return { label: 'Degraded', cls: 'text-warning', dot: 'bg-warning' }
  return { label: 'Impaired', cls: 'text-critical', dot: 'bg-critical' }
}
