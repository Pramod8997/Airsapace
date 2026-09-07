/** Sources: registry + cross-source consensus bar per route (UI_UX_DESIGN.md §15) and health list. */
import { useMemo } from 'react'
import { useState } from 'react'
import { Card, ErrorState, Loading, MetricTile } from '../components/ui'
import { useFares, useQuality, useSources } from '../api/hooks'
import { fmtDate, fmtINR, fmtInt, fmtTime, healthOf } from '../lib/format'

export default function SourcesPage() {
  const sources = useSources()
  const quality = useQuality(30)
  const [routeId, setRouteId] = useState('')
  const [lead] = useState<number | undefined>(undefined)

  const fares = useFares(
    routeId
      ? { origin: routeId.slice(0, 3), destination: routeId.slice(4, 7), availability: 'AVAILABLE', ...(lead ? { lead_time: lead } : {}), page_size: 500 }
      : { availability: 'AVAILABLE', page_size: 500 },
  )

  // per-source medians for consensus view
  const perSource = useMemo(() => {
    const m = new Map<string, number[]>()
    fares.data?.items.forEach((f) => {
      if (f.consumer_payable_fare == null) return
      const arr = m.get(f.source_id) ?? []
      arr.push(f.consumer_payable_fare)
      m.set(f.source_id, arr)
    })
    const entries = [...m.entries()].map(([sid, vals]) => ({ sid, median: median(vals), n: vals.length }))
    entries.sort((a, b) => a.median - b.median)
    return entries
  }, [fares.data])

  const spread = perSource.length >= 2 ? perSource[perSource.length - 1].median - perSource[0].median : null
  const agreement = perSource.length > 0 && spread != null
    ? Math.max(0, 100 - (spread / perSource[0].median) * 100)
    : null

  if (sources.isError) return <ErrorState error={sources.error} />
  if (sources.isPending) return <Loading label="Loading sources" />

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="text-lg font-semibold">Sources</h1>
        <label className="text-sm">
          <span className="mr-2 text-[11px] tracking-widest text-muted uppercase">Consensus route</span>
          <select value={routeId} onChange={(e) => setRouteId(e.target.value)} className="rounded border border-grid bg-surface px-2 py-1.5 text-sm">
            <option value="">All routes</option>
            <option value="DEL-BOM">DEL-BOM</option>
            <option value="DEL-BLR">DEL-BLR</option>
            <option value="BOM-BLR">BOM-BLR</option>
            <option value="DEL-CCU">DEL-CCU</option>
            <option value="BLR-HYD">BLR-HYD</option>
            <option value="MAA-DEL">MAA-DEL</option>
          </select>
        </label>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Source consensus · median payable fare">
          {perSource.length === 0 ? <p className="text-sm text-muted">{fares.isPending ? 'Loading…' : 'No quotes for this selection.'}</p> : (
            <>
              <ul className="space-y-2">
                {perSource.map((s) => {
                  const max = perSource[perSource.length - 1].median || 1
                  const src = sources.data.find((x) => x.id === s.sid)
                  return (
                    <li key={s.sid} className="flex items-center gap-3">
                      <span className="w-36 truncate text-sm" title={src?.name}>{src?.name ?? s.sid}</span>
                      <span className="h-3 rounded-sm bg-signal" style={{ width: `${(s.median / max) * 180}px` }} aria-hidden />
                      <span className="tnum text-sm">{fmtINR(s.median)}</span>
                      <span className="tnum text-xs text-muted">{fmtInt(s.n)}q</span>
                    </li>
                  )
                })}
              </ul>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <MetricTile label="Median spread" value={spread != null ? fmtINR(spread) : '—'} />
                <MetricTile label="Cross-source agreement" value={agreement != null ? agreement.toFixed(0) + '%' : '—'} />
              </div>
              <p className="mt-2 text-xs text-muted">Agreement = 100 − spread / min-median; indicative only, not a formal statistic.</p>
            </>
          )}
        </Card>

        <Card title="Source registry">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-grid text-left text-[11px] tracking-widest text-muted uppercase">
                <th className="py-1.5">Source</th><th>Type</th><th>Policy</th><th className="text-right">Rate/hr</th><th className="text-right">Reliability</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((s) => (
                <tr key={s.id} className="border-b border-grid/60">
                  <td className="py-1.5 font-medium">{s.name}</td>
                  <td className="text-muted">{s.source_type}</td>
                  <td className="text-muted">{s.policy_status} · robots {s.robots_status}</td>
                  <td className="tnum text-right text-muted">{fmtInt(s.rate_limit_per_hour)}</td>
                  <td className="tnum text-right">{(s.reliability * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card title="Source health · 30 days">
        {quality.isPending ? <Loading /> : quality.isError ? <ErrorState error={quality.error} /> : (
          <ul className="divide-y divide-grid">
            {quality.data.source_health.map((h) => {
              const hp = healthOf(h.availability_rate)
              const src = sources.data.find((x) => x.id === h.source_id)
              return (
                <li key={h.source_id} className="flex flex-wrap items-baseline gap-x-6 gap-y-1 py-2 text-sm">
                  <span className="w-40 font-medium">{src?.name ?? h.source_id}</span>
                  <span className={`flex items-center gap-1.5 ${hp.cls}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${hp.dot}`} aria-hidden />
                    {hp.label}
                  </span>
                  <span className="tnum text-muted">{fmtInt(h.observations)} obs · {(h.availability_rate * 100).toFixed(1)}% priceable</span>
                  <span className="ml-auto text-xs text-muted">
                    last ok {h.last_success_at ? `${fmtDate(h.last_success_at)} ${fmtTime(h.last_success_at)}` : '—'}
                    {h.last_failure_at && ` · last fail ${fmtDate(h.last_failure_at)} ${fmtTime(h.last_failure_at)}`}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}

function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}
