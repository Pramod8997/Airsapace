/** Route Observatory — signature screen: schematic India map with route arcs, per-route stats,
 *  heatmap matrix, and a right-side evidence drawer (UI_UX_DESIGN.md §9/§10/§13). */
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { AIRPORTS } from '../lib/airports'
import { api } from '../api/types'
import { useFares, useQuality, useRoutes } from '../api/hooks'
import { Card, ChangeBadge, ConfidenceBar, EmptyState, ErrorState, Loading, MetricTile } from '../components/ui'
import { fmtINR, fmtInt, fmtNum } from '../lib/format'

export default function RoutesPage() {
  const [params, setParams] = useSearchParams()
  const selected = params.get('route') ?? ''
  const routes = useRoutes()
  const quality = useQuality(30)
  const series = useRouteSeries(routes.data ?? [])
  const [view, setView] = useState<'map' | 'heatmap'>('map')

  if (routes.isError) return <ErrorState error={routes.error} />
  if (routes.isPending) return <Loading label="Loading routes" />

  return (
    <div className="mx-auto flex max-w-7xl gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        <header className="flex items-baseline justify-between">
          <h1 className="text-lg font-semibold">Route Observatory</h1>
          <div className="flex rounded border border-grid text-xs" role="tablist" aria-label="View">
            {(['map', 'heatmap'] as const).map((v) => (
              <button
                key={v}
                role="tab" aria-selected={view === v}
                className={`px-3 py-1 capitalize ${view === v ? 'bg-signal/10 text-signal' : 'text-muted'}`}
                onClick={() => setView(v)}
              >{v}</button>
            ))}
          </div>
        </header>

        {view === 'map' ? (
          <Card title="India route network · index signals">
            {series.isError ? <ErrorState error={series.error} /> :
             series.isPending ? <Loading /> :
             series.data.size === 0 ? <EmptyState title="No route series" hint="Run scripts/seed.py to generate index values." /> :
             <RouteMap routes={routes.data} series={series.data} selected={selected} onSelect={(id) =>
               setParams(id ? { route: id } : {}, { replace: true })} />}
          </Card>
        ) : (
          <Card title="Airport matrix · current index and 7-day movement">
            {series.isPending ? <Loading /> : series.isError ? <ErrorState error={series.error} /> : (
              <Heatmap routes={routes.data} series={series.data ?? new Map()} onSelect={(id) =>
                setParams(id ? { route: id } : {}, { replace: true })} />
            )}
          </Card>
        )}

        <Card title="All routes">
          <ol className="divide-y divide-grid">
            {routes.data.map((r) => {
              const s = series.data?.get(r.id)
              return (
                <li key={r.id}>
                  <button
                    className={`flex w-full items-baseline gap-6 py-2 text-left hover:bg-grid/30 ${selected === r.id ? 'bg-signal/5' : ''}`}
                    onClick={() => setParams(selected === r.id ? {} : { route: r.id }, { replace: true })}
                  >
                    <span className="tnum w-24 text-sm font-medium">{r.id}</span>
                    <span className="min-w-32 flex-1 text-sm text-muted">{r.origin_city} → {r.destination_city}</span>
                    <span className="tnum w-16 text-right text-sm">{s ? fmtNum(s.latest, 1) : '—'}</span>
                    <span className="w-20 text-right"><ChangeBadge pct={s?.change7d} label="7D" /></span>
                    <span className="tnum w-14 text-right text-sm text-muted">w {(r.weight * 100).toFixed(1)}%</span>
                  </button>
                </li>
              )
            })}
          </ol>
        </Card>
      </div>

      {selected && (
        <aside aria-label="Route evidence drawer" className="sticky top-20 hidden w-80 shrink-0 self-start lg:block">
          <EvidenceDrawer routeId={selected} qualityCompleteness={quality.data?.completeness ?? null} />
        </aside>
      )}
    </div>
  )
}

interface RouteStat { latest: number; change7d: number | null; n: number }

/** Per-route daily series → latest value + 7D change. Single source for map/heatmap/list. */
function useRouteSeries(routes: { id: string }[]) {
  const ids = routes.map((r) => r.id)
  return useQuery({
    queryKey: ['route-series', ids] as const,
    queryFn: async () => {
      const out = new Map<string, RouteStat>()
      await Promise.all(ids.map(async (id) => {
        const h = await api.indexHistory({ route_id: id, frequency: 'DAILY' })
        const pts = h.points
        if (pts.length === 0) return
        const last = pts[pts.length - 1]
        const lastDate = new Date(last.index_date)
        const prior = [...pts].reverse().find((p) => new Date(p.index_date) <= new Date(lastDate.getTime() - 7 * 86400_000))
        out.set(id, {
          latest: last.value,
          change7d: prior && prior.value !== 0 ? (last.value / prior.value - 1) * 100 : null,
          n: pts.length,
        })
      }))
      return out
    },
    enabled: ids.length > 0,
  })
}

function RouteMap({ routes, series, selected, onSelect }: {
  routes: Array<{ id: string; origin: string; destination: string }>
  series: Map<string, RouteStat>
  selected: string
  onSelect: (id: string) => void
}) {
  return (
    <div className="overflow-x-auto">
      <svg viewBox="0 0 1000 1150" role="img" aria-label="Map of India with basket routes; arcs colored by 7-day index change" className="mx-auto h-[520px] max-w-full">
        {/* faint graticule to suggest an observatory chart without a fake map outline */}
        {Array.from({ length: 9 }, (_, i) => (
          <line key={`h${i}`} x1={40} x2={960} y1={70 + i * 110} y2={70 + i * 110} stroke="#1b2740" strokeWidth={1} />
        ))}
        {Array.from({ length: 9 }, (_, i) => (
          <line key={`v${i}`} y1={50} y2={1100} x1={50 + i * 110} x2={50 + i * 110} stroke="#1b2740" strokeWidth={1} />
        ))}

        {routes.map((r) => {
          const a = AIRPORTS[r.origin], b = AIRPORTS[r.destination]
          if (!a || !b) return null
          const stat = series.get(r.id)
          const up = (stat?.change7d ?? 0) > 0.05
          const down = (stat?.change7d ?? 0) < -0.05
          const stroke = up ? '#2ecc71' : down ? '#e74c3c' : '#3b82f6'
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
          const dx = b.x - a.x, dy = b.y - a.y
          // perpendicular lift for the arc
          const lift = 0.18
          const cx = mx - dy * lift, cy = my + dx * lift
          const isSel = selected === r.id
          return (
            <g key={r.id} className="cursor-pointer" onClick={() => onSelect(r.id)} tabIndex={0}
               role="button" aria-label={`${r.id} index ${stat ? fmtNum(stat.latest, 1) : 'n/a'} 7 day ${stat?.change7d?.toFixed(1) ?? 'n/a'}%`}
               onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(r.id) } }}>
              <path d={`M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`} fill="none"
                    stroke={isSel ? '#fff' : stroke} strokeWidth={isSel ? 3 : 1.6} opacity={selected && !isSel ? 0.25 : 0.9}>
                <title>{`${r.id} · index ${stat ? fmtNum(stat.latest, 1) : '—'} · 7D ${stat?.change7d != null ? stat.change7d.toFixed(1) + '%' : '—'}`}</title>
              </path>
            </g>
          )
        })}

        {Object.values(AIRPORTS).map((ap) => (
          <g key={ap.iata}>
            <circle cx={ap.x} cy={ap.y} r={6} fill="#f7f8fa" stroke="#3b82f6" strokeWidth={2} />
            <text x={ap.x + 10} y={ap.y + 4} fill="#f7f8fa" fontSize={20} fontWeight={600}>{ap.iata}</text>
          </g>
        ))}
        <text x={50} y={40} fill="#5c6674" fontSize={16} letterSpacing={3}>ROUTE OBSERVATORY · INDIA</text>
      </svg>
      <div className="mt-2 flex gap-4 text-[11px] text-muted">
        <span><span className="mr-1 inline-block h-2 w-4 rounded-sm bg-[#2ecc71]" />rising 7D</span>
        <span><span className="mr-1 inline-block h-2 w-4 rounded-sm bg-[#e74c3c]" />falling 7D</span>
        <span><span className="mr-1 inline-block h-2 w-4 rounded-sm bg-[#3b82f6]" />flat</span>
        <span>select a route arc or row for the evidence drawer</span>
      </div>
    </div>
  )
}

function Heatmap({ routes, series, onSelect }: {
  routes: Array<{ id: string; origin: string; destination: string }>
  series: Map<string, RouteStat>
  onSelect: (id: string) => void
}) {
  const airports = useMemo(() => {
    const set = new Set<string>()
    routes.forEach((r) => { set.add(r.origin); set.add(r.destination) })
    return [...set].sort()
  }, [routes])
  const byOD = useMemo(() => {
    const m = new Map<string, RouteStat>()
    routes.forEach((r) => { const s = series.get(r.id); if (s) m.set(`${r.origin}-${r.destination}`, s) })
    return m
  }, [routes, series])

  return (
    <div className="overflow-x-auto">
      <table className="tnum border-collapse text-sm">
        <thead>
          <tr>
            <th className="p-1" aria-label="origin" />
            {airports.map((d) => <th key={d} scope="col" className="p-1 font-medium text-muted">{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {airports.map((o) => (
            <tr key={o}>
              <th scope="row" className="p-1 font-medium text-muted">{o}</th>
              {airports.map((d) => {
                const s = byOD.get(`${o}-${d}`)
                const up = (s?.change7d ?? 0) > 0.05
                const down = (s?.change7d ?? 0) < -0.05
                const bg = !s ? 'bg-grid/30' : up ? 'bg-positive/10' : down ? 'bg-critical/10' : 'bg-signal/5'
                return (
                  <td key={d} className={`border border-grid p-0 ${bg}`}>
                    {s ? (
                      <button className="block w-28 px-2 py-1.5 text-left hover:bg-signal/10"
                        onClick={() => onSelect(`${o}-${d}`)}
                        title={`${o}-${d} · ${fmtInt(s.n)} points`}>
                        <span className="block font-medium">{fmtNum(s.latest, 1)}</span>
                        <span className={`block text-xs ${up ? 'text-positive' : down ? 'text-critical' : 'text-muted'}`}>
                          {up ? '▲' : down ? '▼' : '■'} {s.change7d?.toFixed(1)}%
                        </span>
                      </button>
                    ) : (
                      <span className="block w-28 px-2 py-1.5 text-muted">—</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Evidence drawer: index, lead-time fares, confidence, source consensus (UI_UX_DESIGN.md §10). */
function EvidenceDrawer({ routeId, qualityCompleteness }: { routeId: string; qualityCompleteness: number | null }) {
  const fares = useFares(
    { origin: routeId.slice(0, 3), destination: routeId.slice(4, 7), availability: 'AVAILABLE', page_size: 500 },
  )
  const history = useQueryRouteHistory(routeId)

  const byLead = useMemo(() => {
    const m = new Map<number, { total: number; payable: number[]; sources: Set<string> }>()
    fares.data?.items.forEach((f) => {
      const e = m.get(f.advance_days) ?? { total: 0, payable: [], sources: new Set<string>() }
      e.total += 1
      if (f.consumer_payable_fare != null) e.payable.push(f.consumer_payable_fare)
      e.sources.add(f.source_id)
      m.set(f.advance_days, e)
    })
    return [...m.entries()].sort((a, b) => b[0] - a[0])
  }, [fares.data])

  const route = history.data
  const latest = route?.points[route.points.length - 1]

  return (
    <div className="space-y-4">
      <Card title={`${routeId} · evidence`}>
        {route ? (
          <>
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] tracking-widest text-muted uppercase">APIx</span>
              <span className="tnum text-2xl font-semibold">{fmtNum(latest?.value, 1)}</span>
            </div>
            <p className="mt-1 text-xs text-muted">{latest ? `as of ${latest.index_date}` : ''} · drill: index → route → quote</p>
          </>
        ) : <Loading label="Route index" />}

        <h3 className="mt-4 text-[11px] tracking-widest text-muted uppercase">Lead time · latest median consumer-payable</h3>
        <dl className="mt-1 space-y-1">
          {byLead.map(([lead, e]) => {
            const med = median(e.payable)
            return (
              <div key={lead} className="flex justify-between text-sm">
                <dt className="tnum text-muted">T+{lead}</dt>
                <dd className="tnum">{fmtINR(med)} <span className="text-xs text-muted">({e.total} quotes · {e.sources.size} sources)</span></dd>
              </div>
            )
          })}
          {byLead.length === 0 && <div className="text-sm text-muted">{fares.isPending ? 'Loading quotes…' : 'No available quotes for this route.'}</div>}
        </dl>

        {qualityCompleteness != null && (
          <div className="mt-4">
            <ConfidenceBar pct={qualityCompleteness * 100} label="Data confidence (30d)" />
          </div>
        )}

        <h3 className="mt-4 text-[11px] tracking-widest text-muted uppercase">Evidence</h3>
        <p className="text-sm text-muted">
          {byLead.length > 0
            ? `${new Set(fares.data?.items.map((f) => f.source_id) ?? []).size} sources contribute; medians shown per lead time. Sold-out and invalid quotes are excluded (never counted as zero).`
            : 'Awaiting observations.'}
        </p>
      </Card>

      {byLead.length >= 2 && <LeadPremium byLead={byLead} />}
    </div>
  )
}

function LeadPremium({ byLead }: { byLead: Array<[number, { total: number; payable: number[]; sources: Set<string> }]> }) {
  const deep = byLead[byLead.length - 1][0]
  const near = byLead[0][0]
  const deepMed = median(byLead[byLead.length - 1][1].payable)
  const nearMed = median(byLead[0][1].payable)
  if (!deepMed || !nearMed) return null
  const premium = ((nearMed / deepMed - 1) * 100)
  return (
    <MetricTile label={`Lead-time premium · T+${near} vs T+${deep}`} value={`${premium > 0 ? '+' : ''}${premium.toFixed(0)}%`}
      sub={`${fmtINR(nearMed)} vs ${fmtINR(deepMed)}`} />
  )
}

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function useQueryRouteHistory(routeId: string) {
  return useQuery({
    queryKey: ['route-history', routeId] as const,
    queryFn: () => api.indexHistory({ route_id: routeId, frequency: 'DAILY' }),
  })
}
