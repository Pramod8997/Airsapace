/** Backtesting: metrics tiles + honest disclaimer (UI_UX_DESIGN.md §17 + statistical honesty invariant). */
import { Card, EmptyState, ErrorState, Loading, MetricTile } from '../components/ui'
import { useBacktests } from '../api/hooks'
import { fmtDate, fmtNum } from '../lib/format'

export default function BacktestingPage() {
  const backtests = useBacktests()

  if (backtests.isError) return <ErrorState error={backtests.error} />
  if (backtests.isPending) return <Loading label="Loading backtests" />

  const runs = backtests.data

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-lg font-semibold">Backtesting</h1>

      {runs.length === 0 ? (
        <EmptyState title="No backtest runs" hint="Run scripts/seed.py to produce a backtest against the reference series." />
      ) : (
        runs.map((b) => (
          <Card key={b.id} title={`Run ${b.id} · ${fmtDate(b.period_start)} → ${fmtDate(b.period_end)}`}
            right={<span className="text-xs text-muted">{b.methodology_version} · {b.basket_version}</span>}>
            <p className="text-sm">
              Reference: <span className="font-medium">{b.reference_series}</span>
              {b.reference_series.toLowerCase().includes('dgca') ? '' : ' — this is not a DGCA series; it demonstrates the backtest workflow only.'}
            </p>
            <div className="mt-3 grid gap-4 md:grid-cols-5">
              <MetricTile label="MAE" value={fmtNum(b.metrics.mae, 2)} />
              <MetricTile label="RMSE" value={fmtNum(b.metrics.rmse, 2)} />
              <MetricTile label="MAPE" value={b.metrics.mape != null ? `${b.metrics.mape.toFixed(2)}%` : '—'} />
              <MetricTile label="Correlation" value={fmtNum(b.metrics.correlation, 2)} />
              <MetricTile label="Trend direction" value={b.metrics.trend_direction_accuracy != null ? `${(b.metrics.trend_direction_accuracy * 100).toFixed(1)}%` : '—'} />
            </div>
            <p className="tnum mt-2 text-xs text-muted">{fmtNum(b.metrics.n_points, 0)} aligned points · run {fmtDate(b.created_at)}</p>
          </Card>
        ))
      )}

      <div className="rounded-lg border border-grid bg-surface p-4 text-sm text-muted">
        <p className="font-medium text-ink">Methodology disclaimer</p>
        <p className="mt-1">
          Comparison indicates statistical consistency with the selected reference series; it does not imply
          methodological equivalence. Correlation is not proof of equivalence. This prototype is an analytical
          augmentation, not official CPI.
        </p>
      </div>
    </div>
  )
}
