/** Lead-time screen: the signature curve — median consumer-payable fare per days-to-departure (UI_UX_DESIGN.md §12). */
import { useMemo, useState } from 'react'
import { Chart, chartTheme } from '../components/Chart'
import { Card, EmptyState, ErrorState, Loading, MetricTile } from '../components/ui'
import { useFares, useRoutes } from '../api/hooks'
import { fmtINR, fmtInt } from '../lib/format'

export default function LeadTimePage() {
  const routes = useRoutes()
  const [routeId, setRouteId] = useState('')

  const fares = useFares(
    routeId
      ? { origin: routeId.slice(0, 3), destination: routeId.slice(4, 7), availability: 'AVAILABLE', page_size: 500 }
      : { availability: 'AVAILABLE', page_size: 500 },
  )

  const byLead = useMemo(() => {
    const m = new Map<number, number[]>()
    fares.data?.items.forEach((f) => {
      if (f.consumer_payable_fare == null) return
      const arr = m.get(f.advance_days) ?? []
      arr.push(f.consumer_payable_fare)
      m.set(f.advance_days, arr)
    })
    return [...m.entries()]
      .map(([lead, vals]) => ({ lead, median: median(vals), n: vals.length }))
      .sort((a, b) => a.lead - b.lead)
  }, [fares.data])

  if (routes.isError) return <ErrorState error={routes.error} />

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="text-lg font-semibold">Lead-Time Curve</h1>
        <label className="text-sm">
          <span className="mr-2 text-[11px] tracking-widest text-muted uppercase">Route</span>
          <select value={routeId} onChange={(e) => setRouteId(e.target.value)} className="rounded border border-grid bg-surface px-2 py-1.5 text-sm">
            <option value="">All basket routes</option>
            {routes.data?.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
          </select>
        </label>
      </header>

      <Card title={`Fare vs days-to-departure · ${routeId || 'all routes'} · ${fmtInt(fares.data?.total)} available quotes`}>
        {fares.isError ? <ErrorState error={fares.error} /> :
         fares.isPending ? <Loading /> :
         byLead.length < 2 ? (
           <EmptyState
             title="No valid observations"
             hint="Not enough available quotes to draw a lead-time curve for this selection."
             suggestions={['another route', 'clear filters', 'replay mode']}
           />
         ) : (
          <Chart
            className="h-80"
            option={{
              grid: { left: 64, right: 24, top: 24, bottom: 40 },
              tooltip: {
                trigger: 'axis',
                formatter: (ps: unknown) => {
                  const p = (ps as Array<{ name: string; value: number }>)[0]
                  const pt = byLead[Number(p.name)]
                  return `T+${p.name} · ${fmtINR(p.value)}<br/>${fmtInt(pt?.n)} quotes`
                },
              },
              xAxis: { type: 'category', name: 'days to departure', nameLocation: 'middle', nameGap: 28,
                data: byLead.map((b) => String(b.lead)), ...chartTheme.axis },
              yAxis: { type: 'value', name: '₹ median', ...chartTheme.axis },
              series: [{
                type: 'line', data: byLead.map((b) => b.median), symbolSize: 8,
                lineStyle: { color: chartTheme.signal, width: 2 },
                itemStyle: { color: chartTheme.signal },
                label: { show: true, position: 'top', color: chartTheme.muted, fontSize: 11,
                  formatter: (p: { name: string }) => `T+${p.name}` },
              }],
            }}
            summary={`Median consumer-payable fare by days to departure: ${byLead.map((b) => `T+${b.lead} ${fmtINR(b.median)}`).join(', ')}`}
          />
        )}
      </Card>

      {byLead.length >= 2 && <LeadPremiumTiles byLead={byLead} />}
    </div>
  )
}

function LeadPremiumTiles({ byLead }: { byLead: Array<{ lead: number; median: number; n: number }> }) {
  const near = byLead[0]
  const deep = byLead[byLead.length - 1]
  if (!deep.median) return null
  const premium = (near.median / deep.median - 1) * 100
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <MetricTile label={`Lead-time premium · T+${near.lead} vs T+${deep.lead}`}
        value={`${premium > 0 ? '+' : ''}${premium.toFixed(0)}%`}
        valueClass={premium > 0 ? 'text-critical' : 'text-positive'}
        sub="booking closer to departure costs more" />
      <MetricTile label={`T+${near.lead} median`} value={fmtINR(near.median)} sub={`${fmtInt(near.n)} quotes`} />
      <MetricTile label={`T+${deep.lead} median`} value={fmtINR(deep.median)} sub={`${fmtInt(deep.n)} quotes`} />
    </div>
  )
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}
