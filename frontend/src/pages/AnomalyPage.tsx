/** Anomaly screen: candidate price shocks with WHY? evidence (UI_UX_DESIGN.md §20). */
import { useState } from 'react'
import { Card, EmptyState, ErrorState, Loading } from '../components/ui'
import { useAnomalies } from '../api/hooks'
import { fmtINR, fmtPct } from '../lib/format'
import type { Anomaly } from '../api/types'

const SEVERITY: Record<Anomaly['severity'], { label: string; cls: string; border: string }> = {
  SHOCK: { label: 'Price shock detected', cls: 'text-critical', border: 'border-critical/50' },
  ELEVATED: { label: 'Fare elevated', cls: 'text-warning', border: 'border-warning/50' },
  DIP: { label: 'Fare dip', cls: 'text-signal', border: 'border-signal/40' },
}

function AnomalyCard({ a }: { a: Anomaly }) {
  const [open, setOpen] = useState(false)
  const sev = SEVERITY[a.severity]
  return (
    <section className={`obs-card rounded-lg border ${sev.border} bg-surface`}>
      <button
        className="flex w-full flex-wrap items-baseline gap-x-4 gap-y-1 p-4 text-left"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`text-[11px] font-semibold tracking-[0.14em] uppercase ${sev.cls}`}>{sev.label}</span>
        <span className="ml-auto text-xs text-muted">
          {a.explanation.comparison} · as of {a.current_date} <span className="sr-only">, toggle evidence</span> {open ? '▲' : '▼'}
        </span>
        <div className="flex w-full flex-wrap items-baseline gap-4">
          <span className="text-base font-semibold">{a.origin} → {a.destination}</span>
          <span className="text-sm text-muted">T+{a.lead_time}</span>
          <span className="tnum ml-auto text-2xl font-semibold">{fmtINR(a.current_median)}</span>
          <span className={`tnum text-sm font-medium ${a.change_pct > 0 ? 'text-critical' : 'text-positive'}`}>
            {fmtPct(a.change_pct)} vs {a.explanation.comparison.replace('vs ', '')}
          </span>
        </div>
      </button>
      {open && (
        <div className="border-t border-grid p-4">
          <h3 className="text-[11px] font-semibold tracking-[0.14em] text-muted uppercase">Why?</h3>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            <li>{a.explanation.lead_window}</li>
            <li>{a.explanation.availability === '0% sold out on latest day' ? 'Availability unchanged' : `Reduced availability — ${a.explanation.availability}`}</li>
            <li>{a.explanation.source_confirmation}</li>
          </ul>
        </div>
      )}
    </section>
  )
}

export default function AnomalyPage() {
  const [threshold, setThreshold] = useState(25)
  const anomalies = useAnomalies(30, threshold)

  if (anomalies.isError) return <ErrorState error={anomalies.error} />
  if (anomalies.isPending) return <Loading label="Loading anomalies" />

  const d = anomalies.data

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Anomalies</h1>
        <label className="flex items-center gap-2 text-xs text-muted" htmlFor="threshold">
          Threshold
          <input
            id="threshold" type="number" min={5} max={100} value={threshold}
            onChange={(e) => setThreshold(Math.min(100, Math.max(5, Number(e.target.value) || 25)))}
            className="tnum w-16 rounded border border-grid bg-surface px-2 py-1"
          />
          % vs 30-day median
        </label>
      </header>

      {d.anomalies.length === 0 ? (
        <EmptyState
          title="No anomalies in window"
          hint="Fares are within the detection threshold — no candidate shocks in the 30-day window."
          suggestions={['lower the threshold', 'widen the window', 'try another route']}
        />
      ) : (
        <div className="space-y-3">
          {d.anomalies.map((a) => (
            <AnomalyCard key={`${a.route_id}-${a.lead_time}`} a={a} />
          ))}
        </div>
      )}

      <Card title="Model">
        <p className="text-sm text-muted">
          Rule-based detection {d.model_version}, as of {d.as_of ?? '—'}. {d.disclaimer}
        </p>
      </Card>
    </div>
  )
}
