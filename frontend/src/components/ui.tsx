/** Shared UI primitives — Airspace Observatory components (UI_UX_DESIGN.md §26 subset used everywhere). */
import type { ReactNode } from 'react'

export function Card({ title, right, children, className = '' }: {
  title?: string; right?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`obs-card rounded-lg border border-grid bg-surface ${className}`}>
      {title && (
        <header className="flex items-baseline justify-between border-b border-grid px-4 py-2.5">
          <h2 className="text-[11px] font-semibold tracking-[0.14em] text-muted uppercase">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function MetricTile({ label, value, sub, valueClass = '' }: {
  label: string; value: ReactNode; sub?: ReactNode; valueClass?: string
}) {
  return (
    <div className="obs-card rounded-lg border border-grid bg-surface px-4 py-3">
      <div className="text-[11px] font-semibold tracking-[0.14em] text-muted uppercase">{label}</div>
      <div className={`tnum mt-1 text-2xl font-semibold ${valueClass}`}>{value}</div>
      {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
    </div>
  )
}

export function ChangeBadge({ pct, label }: { pct: number | null | undefined; label?: string }) {
  if (pct == null) return <span className="tnum text-sm text-muted">{label ?? '—'}</span>
  const dir = pct > 0.05 ? '▲' : pct < -0.05 ? '▼' : '■'
  const cls = pct > 0.05 ? 'text-positive' : pct < -0.05 ? 'text-critical' : 'text-muted'
  return (
    <span className={`tnum text-sm font-medium ${cls}`} aria-label={`${label ?? 'change'} ${pct.toFixed(1)} percent`}>
      {dir} {pct > 0 ? '+' : ''}{pct.toFixed(1)}%{label ? ` ${label}` : ''}
    </span>
  )
}

/** Data Confidence Score bar (never called a Confidence Interval — UI_UX_DESIGN.md §19). */
export function ConfidenceBar({ label = 'Data confidence', pct }: { label?: string; pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct))
  const color = clamped >= 90 ? 'bg-positive' : clamped >= 60 ? 'bg-warning' : 'bg-critical'
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="tnum font-medium">{clamped.toFixed(0)}%</span>
      </div>
      <div
        role="meter" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} ${clamped}%`}
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-grid"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  )
}

export function EmptyState({ title, hint, suggestions }: { title: string; hint?: string; suggestions?: string[] }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed border-grid px-6 py-10 text-center">
      <h3 className="text-[11px] font-semibold tracking-[0.14em] text-muted uppercase">{title}</h3>
      {hint && <p className="mt-2 max-w-md text-sm text-muted">{hint}</p>}
      {suggestions && (
        <ul className="mt-3 list-disc space-y-0.5 text-left text-sm text-muted">
          {suggestions.map((s) => <li key={s}>{s}</li>)}
        </ul>
      )}
    </div>
  )
}

/** API-error state — no stack traces in user-facing UI (UI_UX_DESIGN.md §22). */
export function ErrorState({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : 'unexpected error'
  return (
    <div className="rounded-lg border border-critical/40 bg-critical/5 px-6 py-8 text-center" role="alert">
      <h3 className="text-[11px] font-semibold tracking-[0.14em] text-critical uppercase">Source temporarily unavailable</h3>
      <p className="mt-2 text-sm text-muted">
        The API request failed. Other data may still be available. ({msg})
      </p>
    </div>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center" role="status" aria-label={label}>
      <span className="animate-pulse text-sm text-muted">{label}…</span>
    </div>
  )
}
