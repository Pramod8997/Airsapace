/** Fare decomposition: stacked base/taxes/mandatory/convenience per lead time, ₹/% toggle (UI_UX_DESIGN.md §14). */
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Chart, chartTheme } from '../components/Chart'
import { Card, EmptyState, ErrorState, Loading, MetricTile } from '../components/ui'
import { useFares, useRoutes } from '../api/hooks'
import { fmtINR, fmtInt } from '../lib/format'

const SEGMENTS = [
  { key: 'base_fare', label: 'Base fare', color: '#1f5fd6' },
  { key: 'taxes', label: 'Taxes', color: '#4f83e8' },
  { key: 'mandatory_fees', label: 'Mandatory fees', color: '#b8860b' },
  { key: 'convenience_fee', label: 'Convenience fee', color: '#9aa5b1' },
] as const

export default function FareDecompositionPage() {
  const [params] = useSearchParams()
  const airlineParam = params.get('airline') ?? ''
  const routes = useRoutes()
  const [routeId, setRouteId] = useState('')
  const [mode, setMode] = useState<'abs' | 'pct'>('abs')

  const effectiveRoute = routeId || routes.data?.[0]?.id || ''
  const fares = useFares(
    {
      ...(effectiveRoute ? { origin: effectiveRoute.slice(0, 3), destination: effectiveRoute.slice(4, 7) } : {}),
      ...(airlineParam ? { airline: airlineParam } : {}),
      availability: 'AVAILABLE',
      page_size: 500,
    },
    Boolean(effectiveRoute),
  )

  // median per segment per lead time
  const byLead = useMemo(() => {
    const m = new Map<number, Record<string, number[]>>()
    fares.data?.items.forEach((f) => {
      if (f.consumer_payable_fare == null) return
      const e = m.get(f.advance_days) ?? {}
      for (const s of SEGMENTS) {
        const v = f[s.key] ?? 0
        e[s.key] = [...(e[s.key] ?? []), v]
      }
      m.set(f.advance_days, e)
    })
    return [...m.entries()]
      .map(([lead, segs]) => {
        const med: Record<string, number> = {}
        for (const s of SEGMENTS) med[s.key] = median(segs[s.key] ?? [0])
        med.total = Object.values(med).reduce((a, b) => a + b, 0)
        return { lead, med }
      })
      .sort((a, b) => a.lead - b.lead)
  }, [fares.data])

  if (routes.isError) return <ErrorState error={routes.error} />

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="text-lg font-semibold">Price Decomposition</h1>
        <div className="flex items-center gap-4">
          <label className="text-sm">
            <span className="mr-2 text-[11px] tracking-widest text-muted uppercase">Route</span>
            <select value={routeId} onChange={(e) => setRouteId(e.target.value)} className="rounded border border-grid bg-surface px-2 py-1.5 text-sm">
              {routes.data?.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
            </select>
          </label>
          <div className="flex rounded border border-grid text-xs" role="group" aria-label="Units">
            {(['abs', 'pct'] as const).map((m) => (
              <button key={m} aria-pressed={mode === m}
                className={`px-3 py-1 ${mode === m ? 'bg-signal/10 text-signal' : 'text-muted'}`}
                onClick={() => setMode(m)}>{m === 'abs' ? '₹' : '%'}</button>
            ))}
          </div>
        </div>
      </header>
      {airlineParam && <p className="text-xs text-muted">Filtered to airline {airlineParam} (via command palette).</p>}

      <Card title={`Stacked fare structure · ${effectiveRoute || '—'} · median per segment`}>
        {fares.isError ? <ErrorState error={fares.error} /> :
         !effectiveRoute ? <Loading label="Waiting for routes" /> :
         fares.isPending ? <Loading /> :
         byLead.length === 0 ? (
           <EmptyState title="No valid observations" hint="No available quotes with full fare components for this selection."
             suggestions={['another route', 'clear airline filter']} />
         ) : (
          <Chart
            className="h-80"
            option={{
              grid: { left: 64, right: 24, top: 32, bottom: 40 },
              tooltip: {
                trigger: 'axis',
                valueFormatter: (v: unknown) => mode === 'abs' ? fmtINR(Number(v)) : `${Number(v).toFixed(1)}%`,
              },
              legend: { top: 0, textStyle: { color: chartTheme.muted, fontSize: 11 } },
              xAxis: { type: 'category', name: 'days to departure', nameLocation: 'middle', nameGap: 28,
                data: byLead.map((b) => String(b.lead)), ...chartTheme.axis },
              yAxis: { type: 'value', ...(mode === 'abs' ? { name: '₹' } : { name: '%', max: 100 }), ...chartTheme.axis },
              series: SEGMENTS.map((s) => ({
                name: s.label, type: 'bar', stack: 'fare',
                itemStyle: { color: s.color },
                data: byLead.map((b) => mode === 'abs'
                  ? round(b.med[s.key])
                  : b.med.total ? (b.med[s.key] / b.med.total) * 100 : 0),
              })),
            }}
            summary={`Median fare structure by lead time: ${byLead.map((b) => `T+${b.lead} total ${fmtINR(b.med.total)} (base ${fmtINR(b.med.base_fare)}, taxes ${fmtINR(b.med.taxes)}, mandatory ${fmtINR(b.med.mandatory_fees)}, convenience ${fmtINR(b.med.convenience_fee)})`).join('; ')}`}
          />
        )}
      </Card>

      {byLead.length > 0 && (
        <div className="grid gap-4 md:grid-cols-4">
          {SEGMENTS.map((s) => {
            const totals = byLead.map((b) => b.med[s.key])
            const grand = totals.reduce((a, b) => a + b, 0) / totals.length
            const share = byLead.reduce((a, b) => a + b.med[s.key], 0) / byLead.reduce((a, b) => a + b.med.total, 0)
            return (
              <MetricTile key={s.key} label={s.label} value={fmtINR(grand)}
                sub={`${(share * 100).toFixed(1)}% of payable fare · avg over ${fmtInt(byLead.length)} lead times`} />
            )
          })}
        </div>
      )}
      <p className="text-xs text-muted">
        Index uses consumer-payable fare = base + taxes + mandatory fees; the convenience fee is tracked but excluded from APIx (FR-09).
      </p>
    </div>
  )
}

function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function round(v: number) { return Math.round(v) }
