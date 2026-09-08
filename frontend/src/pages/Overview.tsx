import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Chart, chartTheme } from '../components/Chart'
import { Card, ChangeBadge, ConfidenceBar, ErrorState, Loading, MetricTile } from '../components/ui'
import { useForecast, useLatest, useMethodology, useQuality, useRoutes, useRouteMovers, useHistory } from '../api/hooks'
import { fmtInt, fmtNum } from '../lib/format'
import type { Forecast, IndexHistory } from '../api/types'

/** Overview: hero + 30-day index pulse + route pressure + data confidence (UI_UX_DESIGN.md §8). */
export default function Overview() {
  const navigate = useNavigate()
  const latest = useLatest()
  const quality = useQuality(30)
  const routes = useRoutes()
  const methodology = useMethodology()
  // national trend, weekly for a calm 30+ day pulse
  const history = useHistory({ frequency: 'WEEKLY' })
  // auxiliary forecast layer — never part of the index calculation
  const forecast = useForecast(7)
  const [showForecast, setShowForecast] = useState(true)
  // all hooks before any early return — conditional hook calls blank the app
  const topMovers = useRouteMovers(5, routes.data ?? []).data ?? []

  if (latest.isError) return <ErrorState error={latest.error} />
  if (latest.isPending) return <Loading label="Loading index" />

  const d = latest.data
  const completeness = quality.data ? quality.data.completeness * 100 : null

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-[11px] font-semibold tracking-[0.18em] text-muted uppercase">Airfare Price Index</h1>
        <div className="mt-1 flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="tnum text-5xl font-semibold" aria-live="polite">{fmtNum(d.index, 2)}</span>
          <div className="flex gap-4 text-sm">
            <span><ChangeBadge pct={d.daily_change_pct} label="1D" /></span>
            <span><ChangeBadge pct={d.weekly_change_pct} label="7D" /></span>
            <span><ChangeBadge pct={d.monthly_change_pct} label="MoM" /></span>
          </div>
          <span className="tnum text-sm text-muted">base {fmtNum(d.base, 0)} = {methodology.data
            ? `${methodology.data.base_period_start} → ${methodology.data.base_period_end}` : '—'}</span>
        </div>
        <p className="mt-2 text-sm text-muted">
          {fmtInt(quality.data?.total_observations)} observations · {routes.data?.length ?? '—'} routes ·{' '}
          {methodology.data?.lead_times.length ?? '—'} lead-time windows · {d.index_date} · methodology {d.methodology_version}
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Index Pulse · 30-day trend" className="md:col-span-2" right={
          <button
            aria-pressed={showForecast}
            className={`rounded-full border px-3 py-1 text-xs ${showForecast ? 'border-signal/40 bg-signal/10 text-signal' : 'border-grid text-muted'}`}
            onClick={() => setShowForecast((v) => !v)}
            title="Model extrapolation — not an observed price"
          >7-day forecast</button>
        }>
          {history.isError ? <ErrorState error={history.error} /> :
           history.isPending ? <Loading /> :
           history.data.points.length === 0 ? <EmptyTrend /> :
           <TrendChart data={history.data} forecast={showForecast ? forecast.data : undefined} />}
        </Card>
        <div className="space-y-4">
          <MetricTile label="Data Confidence" value={completeness != null ? `${completeness.toFixed(1)}%` : '—'}
            sub={`${fmtInt(quality.data?.available)} usable / ${fmtInt(quality.data?.total_observations)} observations`} />
          {completeness != null && <ConfidenceBar pct={completeness} />}
          <div className="grid grid-cols-2 gap-4">
            <MetricTile label="Duplicate rate" value={quality.data ? (quality.data.duplicate_rate * 100).toFixed(1) + '%' : '—'} />
            <MetricTile label="Outlier rate" value={quality.data ? (quality.data.outlier_rate * 100).toFixed(1) + '%' : '—'} />
          </div>
        </div>
      </div>

      <Card title="Route Pressure · top movers (7D)" right={<button className="text-xs text-signal underline" onClick={() => navigate('/routes')}>Route Observatory →</button>}>
        {topMovers.length === 0 ? (
          <p className="text-sm text-muted">Loading per-route series…</p>
        ) : (
          <ol className="divide-y divide-grid">
            {topMovers.map(([routeId, chg]) => (
              <li key={routeId}>
                <button
                  className="flex w-full items-baseline justify-between py-2 text-left hover:bg-grid/30"
                  onClick={() => navigate(`/routes?route=${routeId}`)}
                >
                  <span className="tnum text-sm font-medium">{routeId}</span>
                  <span className="tnum text-sm"><ChangeBadge pct={chg} label="7D" /></span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}

function EmptyTrend() {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center text-center">
      <h3 className="text-[11px] font-semibold tracking-[0.14em] text-muted uppercase">No index values yet</h3>
      <p className="mt-2 text-sm text-muted">Run <code>scripts/seed.py</code> on the backend to generate the replay index.</p>
    </div>
  )
}

function TrendChart({ data, forecast }: { data: IndexHistory; forecast?: Forecast }) {
  const pts = data.points
  const fc = forecast?.forecast ?? []
  const lastDate = pts[pts.length - 1]?.index_date
  // bridge: the last observed point repeated as the first forecast point so the
  // dashed segment connects to the observed line instead of floating
  const bridge = lastDate ? [{ date: lastDate, value: pts[pts.length - 1]?.value }] : []
  const fcPoints = [...bridge, ...fc]
  const fcDates = fcPoints.map((p) => p.date)
  const option = {
    grid: { left: 48, right: 16, top: 16, bottom: 28 },
    xAxis: { type: 'category' as const, data: [...pts.map((p) => p.index_date), ...fcDates], ...chartTheme.axis },
    yAxis: { type: 'value' as const, scale: true, ...chartTheme.axis },
    tooltip: { trigger: 'axis' as const },
    series: [
      {
        name: 'APIx (observed)',
        type: 'line' as const,
        data: [...pts.map((p) => p.value), ...fcDates.map(() => null)],
        showSymbol: false,
        smooth: false, // honest lines, no smoothing
        connect: false, // don't bridge the observed/forecast gap with a solid line
        lineStyle: { color: chartTheme.signal, width: 2 },
        areaStyle: { color: 'rgba(31,95,214,0.06)' },
      },
      {
        name: 'Forecast (not observed)',
        type: 'line' as const,
        data: [...pts.map(() => null), ...fcPoints.map((p) => p.value)],
        showSymbol: false,
        smooth: false,
        connect: false,
        lineStyle: { color: chartTheme.warning, width: 2, type: 'dashed' as const },
      },
    ],
  }
  return (
    <Chart
      option={option}
      summary={`APIx weekly series from ${pts[0]?.index_date} to ${lastDate}, latest value ${pts[pts.length - 1]?.value}` +
        (fc.length ? `, followed by a ${fc.length}-point dashed model forecast (not observed prices)` : '')}
    />
  )
}
