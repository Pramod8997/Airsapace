import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Chart, chartTheme } from '../components/Chart'
import { Card, EmptyState, ErrorState, Loading } from '../components/ui'
import { useHistory, useLatest, useRoutes } from '../api/hooks'

const FREQS = ['DAILY', 'WEEKLY', 'MONTHLY'] as const
const LEADS = [undefined, 1, 7, 15, 30, 45] as const

/** Index trend screen: hover, date range, route/lead filters (UI_UX_DESIGN.md §11). */
export default function IndexPage() {
  const navigate = useNavigate()
  const latest = useLatest()
  const routes = useRoutes()
  const [routeId, setRouteId] = useState('')
  const [lead, setLead] = useState<number | undefined>(undefined)
  const [frequency, setFrequency] = useState<(typeof FREQS)[number]>('DAILY')
  const [from, setFrom] = useState('')

  const params = useMemo(() => ({
    route_id: routeId || undefined,
    lead_time: lead,
    frequency,
    from: from || undefined,
  }), [routeId, lead, frequency, from])

  const history = useHistory(params)
  const pts = history.data?.points ?? []

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">APIx · Index Trend</h1>
        <p className="text-xs text-muted">{latest.data?.methodology_version ?? ''} · {latest.data?.data_mode ?? ''}</p>
      </header>

      <Card title="Filters">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <span className="block text-[11px] tracking-widest text-muted uppercase">Route</span>
            <select value={routeId} onChange={(e) => setRouteId(e.target.value)} className="mt-1 rounded border border-grid bg-surface px-2 py-1.5 text-sm">
              <option value="">National (all routes)</option>
              {routes.data?.map((r) => <option key={r.id} value={r.id}>{r.id} · {r.origin_city} → {r.destination_city}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-[11px] tracking-widest text-muted uppercase">Lead time</span>
            <select value={lead ?? ''} onChange={(e) => setLead(e.target.value ? Number(e.target.value) : undefined)} className="mt-1 rounded border border-grid bg-surface px-2 py-1.5 text-sm">
              {LEADS.map((l) => <option key={l ?? 'all'} value={l ?? ''}>{l ? `T+${l}` : 'All'}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-[11px] tracking-widest text-muted uppercase">Frequency</span>
            <select value={frequency} onChange={(e) => setFrequency(e.target.value as (typeof FREQS)[number])} className="mt-1 rounded border border-grid bg-surface px-2 py-1.5 text-sm">
              {FREQS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-[11px] tracking-widest text-muted uppercase">From</span>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="mt-1 rounded border border-grid bg-surface px-2 py-1.5 text-sm" />
          </label>
          {(routeId || lead || from) && (
            <button className="text-xs text-signal underline" onClick={() => { setRouteId(''); setLead(undefined); setFrom('') }}>Reset</button>
          )}
        </div>
      </Card>

      <Card title={`Series · ${routeId || 'National'}${lead ? ` · T+${lead}` : ''} · ${pts.length} points`}>
        {history.isError ? <ErrorState error={history.error} /> :
         history.isPending ? <Loading /> :
         pts.length === 0 ? (
           <EmptyState
             title="No valid observations"
             hint="No index values match the selected filters for this period."
             suggestions={['another lead time', 'another date range', 'national view (clear route filter)']}
           />
         ) : (
          <Chart
            className="h-96"
            option={{
              grid: { left: 56, right: 24, top: 24, bottom: 36 },
              tooltip: { trigger: 'axis' },
              toolbox: { feature: { dataZoom: { yAxisIndex: 'none' }, saveAsImage: {} }, right: 8 },
              xAxis: { type: 'category', data: pts.map((p) => p.index_date), ...chartTheme.axis },
              yAxis: { type: 'value', scale: true, ...chartTheme.axis },
              dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
              series: [{
                type: 'line', data: pts.map((p) => p.value), showSymbol: pts.length < 60,
                lineStyle: { color: chartTheme.signal, width: 2 },
                markLine: { silent: true, symbol: 'none', data: [{ yAxis: 100 }], lineStyle: { color: chartTheme.muted, type: 'dashed' }, label: { formatter: 'base 100' } },
              }],
            }}
            summary={`Index series, ${pts.length} points from ${pts[0]?.index_date} to ${pts[pts.length - 1]?.index_date}. Latest value ${pts[pts.length - 1]?.value}. Base 100 reference line.`}
          />
        )}
        {pts.length > 0 && routeId && (
          <p className="mt-2 text-xs text-muted">
            Investigate this route in depth: <button className="text-signal underline" onClick={() => navigate(`/routes?route=${routeId}`)}>open evidence drawer →</button>
          </p>
        )}
      </Card>
    </div>
  )
}
