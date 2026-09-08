/** Lead-time screen: the signature curve — median consumer-payable fare per days-to-departure (UI_UX_DESIGN.md §12)
 *  + lead-time elasticity premium curves (PRD §"lead-time elasticity curves"). */
import { useMemo, useState } from 'react'
import { Chart, chartTheme } from '../components/Chart'
import { Card, EmptyState, ErrorState, Loading, MetricTile } from '../components/ui'
import { useFares, useRoutes } from '../api/hooks'
import { fmtINR, fmtInt, fmtPct } from '../lib/format'

export default function LeadTimePage() {
  const routes = useRoutes()
  const [routeId, setRouteId] = useState('')
  const [elasticityRoute, setElasticityRoute] = useState('')

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

  const allFares = useFares(
    elasticityRoute ? { origin: elasticityRoute.slice(0, 3), destination: elasticityRoute.slice(4, 7), availability: 'AVAILABLE', page_size: 500 } : { availability: 'AVAILABLE', page_size: 500 },
  )

  // Deterministic client-side elasticity: per route, premium % of each lead time's
  // median consumer-payable fare vs the T+1 baseline. premium_pct(lead) = (median(lead)/median(T+1) - 1) * 100
  // Descriptive analytics only — NOT part of the index calculation.
  const elasticity = useMemo(() => {
    const perRoute = new Map<string, Map<number, number[]>>()
    allFares.data?.items.forEach((f) => {
      if (f.consumer_payable_fare == null) return
      const leads = perRoute.get(f.route_id) ?? new Map<number, number[]>()
      const arr = leads.get(f.advance_days) ?? []
      arr.push(f.consumer_payable_fare)
      leads.set(f.advance_days, arr)
      perRoute.set(f.route_id, leads)
    })
    return [...perRoute.entries()].map(([rid, leads]) => {
      const base = leads.get(1)
      const baseline = base && base.length > 0 ? median(base) : null
      const points = [...leads.entries()]
        .filter(([lead]) => lead >= 1 && lead <= 45)
        .map(([lead, vals]) => ({ lead, premium: baseline ? (median(vals) / baseline - 1) * 100 : null, n: vals.length }))
        .filter((p) => p.premium != null && isFinite(p.premium))
        .sort((a, b) => a.lead - b.lead)
      const t45 = points.find((p) => p.lead === 45) ?? points[points.length - 1]
      return { routeId: rid, baseline, points, deepDiscount: t45 && t45.premium != null ? t45.premium : null }
    }).filter((r) => r.points.length >= 2)
  }, [allFares.data])

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

      <ElasticitySection
        routes={routes.data ?? []}
        series={elasticity}
        selected={elasticityRoute}
        onSelect={setElasticityRoute}
        loading={allFares.isPending}
        error={allFares.isError ? allFares.error : null}
      />

      <p className="text-xs text-muted">
        Elasticity curves are descriptive analytics computed in-browser from the same quote snapshot —
        they are not part of the APIx index calculation and never feed the published index.
      </p>
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

interface ElasticitySeries {
  routeId: string
  baseline: number | null
  points: Array<{ lead: number; premium: number | null; n: number }>
  deepDiscount: number | null
}

function ElasticitySection({ routes, series, selected, onSelect, loading, error }: {
  routes: Array<{ id: string }>
  series: ElasticitySeries[]
  selected: string
  onSelect: (v: string) => void
  loading: boolean
  error: unknown
}) {
  const visible = selected ? series.filter((s) => s.routeId === selected) : series.slice(0, 5)
  const maxLead = Math.max(1, ...visible.flatMap((s) => s.points.map((p) => p.lead)))
  const leads = Array.from({ length: maxLead }, (_, i) => i + 1)

  const maxPremium = series.reduce<null | { routeId: string; premium: number }>((acc, s) => {
    const worst = s.points.reduce<null | number>((w, p) => (p.premium != null && (w == null || p.premium > w) ? p.premium : w), null)
    return worst != null && (acc == null || worst > acc.premium) ? { routeId: s.routeId, premium: worst } : acc
  }, null)
  const avgDeep = series.length && series.every((s) => s.deepDiscount != null)
    ? series.reduce((a, s) => a + (s.deepDiscount ?? 0), 0) / series.length
    : null

  return (
    <>
      <header className="flex flex-wrap items-baseline justify-between gap-4 pt-2">
        <h2 className="text-lg font-semibold">Lead-Time Elasticity</h2>
        <label className="text-sm">
          <span className="mr-2 text-[11px] tracking-widest text-muted uppercase">Route</span>
          <select value={selected} onChange={(e) => onSelect(e.target.value)} className="rounded border border-grid bg-surface px-2 py-1.5 text-sm">
            <option value="">Top 5 basket routes (by quote volume)</option>
            {routes.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
          </select>
        </label>
      </header>

      {series.length === 0 && (error != null ? <ErrorState error={error} /> :
        loading ? <Loading label="Computing elasticity" /> : (
          <EmptyState
            title="No elasticity curve"
            hint="Elasticity needs at least two lead times with a T+1 baseline per route. Not enough available quotes for this selection."
            suggestions={['another route', 'clear filters', 'replay mode']}
          />
        ))}

      {series.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <MetricTile label="Max premium route"
              value={maxPremium ? maxPremium.routeId : '—'}
              sub={maxPremium ? `worst lead-time premium ${fmtPct(maxPremium.premium)} vs T+1` : 'insufficient data'} />
            <MetricTile label={`Avg T+${maxLead} → T+1 discount`}
              value={avgDeep != null ? fmtPct(avgDeep) : '—'}
              sub="mean deepest lead premium across routes"
              valueClass={avgDeep != null && avgDeep < 0 ? 'text-positive' : ''} />
            <MetricTile label="Routes with curve"
              value={fmtInt(series.length)}
              sub={`${fmtInt(series.reduce((a, s) => a + s.points.length, 0))} route-lead points`} />
          </div>

          <Card title={`Premium vs T+1 baseline · ${selected || 'top 5 routes'} · % of T+1 median`}>
            <Chart
              className="h-80"
              option={{
                grid: { left: 64, right: 24, top: 32, bottom: 40 },
                legend: { show: visible.length > 1, top: 0, textStyle: { color: chartTheme.muted, fontSize: 11 } },
                tooltip: {
                  trigger: 'axis',
                  valueFormatter: (v: unknown) => (typeof v === 'number' ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%` : '—'),
                },
                xAxis: { type: 'category', name: 'days to departure', nameLocation: 'middle', nameGap: 28,
                  data: leads.map(String), ...chartTheme.axis },
                yAxis: { type: 'value', name: 'premium %', ...chartTheme.axis },
                series: visible.map((s) => ({
                  name: s.routeId, type: 'line', connectNulls: true, symbolSize: 6,
                  data: leads.map((lead) => {
                    const p = s.points.find((pt) => pt.lead === lead)
                    return p?.premium != null ? Number(p.premium.toFixed(1)) : null
                  }),
                  markLine: visible.indexOf(s) === 0 ? {
                    symbol: 'none', silent: true,
                    lineStyle: { color: chartTheme.muted, type: 'dashed' as const, width: 1 },
                    label: { show: false },
                    data: [{ yAxis: 0 }],
                  } : undefined,
                })),
              }}
              summary={`Lead-time premium vs T+1 per route: ${series.map((s) => `${s.routeId} ${s.points.map((p) => `T+${p.lead} ${p.premium != null ? p.premium.toFixed(1) : 'n/a'}%`).join(', ')}`).join('; ')}`}
            />
          </Card>
        </>
      )}
    </>
  )
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}
