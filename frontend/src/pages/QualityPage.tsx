/** Quality cockpit: data health meters + source health (UI_UX_DESIGN.md §16). */
import { useState } from 'react'
import { Card, ErrorState, Loading, MetricTile } from '../components/ui'
import { useQuality } from '../api/hooks'
import { fmtInt, fmtTime, healthOf } from '../lib/format'

const WINDOWS = [7, 30, 90] as const

function Meter({ label, value, max, unit }: { label: string; value: number; max: number; unit: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="flex items-center gap-3 py-1.5 text-sm">
      <span className="w-32 text-muted">{label}</span>
      <div role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-label={`${label} ${value}${unit}`}
        className="h-3 w-56 overflow-hidden rounded-sm bg-grid">
        <div className="h-full rounded-sm bg-signal" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="tnum">{fmtInt(value)}{unit}</span>
    </div>
  )
}

export default function QualityPage() {
  const [windowDays, setWindowDays] = useState<(typeof WINDOWS)[number]>(30)
  const quality = useQuality(windowDays)

  if (quality.isError) return <ErrorState error={quality.error} />
  if (quality.isPending) return <Loading label="Loading quality" />

  const d = quality.data
  const usable = d.available
  const soldOut = d.sold_out

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Quality Cockpit</h1>
        <div className="flex rounded border border-grid text-xs" role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button key={w} aria-pressed={windowDays === w}
              className={`px-3 py-1 ${windowDays === w ? 'bg-signal/10 text-signal' : 'text-muted'}`}
              onClick={() => setWindowDays(w)}>{w}d</button>
          ))}
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricTile label="Usable observations" value={`${(d.completeness * 100).toFixed(1)}%`}
          sub={`${fmtInt(usable)} of ${fmtInt(d.total_observations)}`} />
        <MetricTile label="Sold-out" value={fmtInt(soldOut)} sub="not counted as zero" />
        <MetricTile label="Duplicate rate" value={`${(d.duplicate_rate * 100).toFixed(1)}%`} sub={`${fmtInt(d.duplicate_count)} duplicates`} />
        <MetricTile label="Rejection rate" value={`${(d.rejection_rate * 100).toFixed(1)}%`} sub={`${fmtInt(d.invalid)} invalid · ${fmtInt(d.rejected)} rejected`} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Data health">
          <Meter label="Completeness" value={d.available} max={d.total_observations} unit="" />
          <Meter label="Duplicates" value={d.duplicate_count} max={d.total_observations + d.duplicate_count} unit="" />
          <Meter label="Rejected" value={d.invalid + d.rejected} max={d.total_observations} unit="" />
          <Meter label="Imputed" value={0} max={d.total_observations} unit="" />
          <Meter label="Outliers flagged" value={Math.round(d.outlier_rate * d.total_observations)} max={d.total_observations} unit="" />
          <p className="mt-3 text-xs text-muted">
            Imputation rate is 0.0 by policy — APIX-v1.0 reweights instead of imputing. Outliers are flagged, never deleted.
          </p>
        </Card>

        <Card title="Source health">
          <ul className="divide-y divide-grid">
            {d.source_health.map((h) => {
              const hp = healthOf(h.availability_rate)
              return (
                <li key={h.source_id} className="flex items-baseline gap-4 py-2 text-sm">
                  <span className="w-36 font-medium">{h.source_id}</span>
                  <span className={`flex items-center gap-1.5 ${hp.cls}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${hp.dot}`} aria-hidden />
                    {hp.label}
                  </span>
                  <span className="tnum ml-auto text-xs text-muted">
                    {(h.availability_rate * 100).toFixed(1)}% · {fmtInt(h.observations)} obs · last ok {h.last_success_at ? fmtTime(h.last_success_at) : '—'}
                  </span>
                </li>
              )
            })}
          </ul>
        </Card>
      </div>
    </div>
  )
}
