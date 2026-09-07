import { Link, NavLink } from 'react-router-dom'
import { AppRoutes } from './AppRoutes'
import { useLatest, useQuality } from './api/hooks'
import { CommandPalette } from './components/CommandPalette'
import { fmtNum, fmtPct } from './lib/format'

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/index', label: 'Index' },
  { to: '/routes', label: 'Routes' },
  { to: '/lead-time', label: 'Lead Time' },
  { to: '/fare-decomposition', label: 'Decomposition' },
  { to: '/sources', label: 'Sources' },
  { to: '/quality', label: 'Quality' },
  { to: '/backtesting', label: 'Backtest' },
  { to: '/methodology', label: 'Method' },
]

/** Header Index Pulse + live-mode badge (UI_UX_DESIGN.md §5). */
function HeaderPulse() {
  const { data: latest, isError } = useLatest()
  const index = latest ? fmtNum(latest.index, 2) : isError ? 'API offline' : '…'
  const mom = latest?.monthly_change_pct
  const mode = latest?.data_mode ?? '—'
  return (
    <div className="flex min-h-14 items-center gap-4 px-4 lg:px-6">
      <div className="flex items-baseline gap-2 font-semibold tracking-[0.18em] text-ink">
        <span className="text-[13px]">AIRSTAT</span><span className="text-[13px] text-muted">/</span><span className="text-[13px]">INDIA</span>
      </div>
      <div className="mx-auto flex items-baseline gap-3">
        <span className="text-[11px] tracking-[0.14em] text-muted uppercase">APIx</span>
        <span className="tnum text-2xl font-semibold" aria-live="polite">{index}</span>
        {mom != null && (
          <span className={`tnum text-sm font-medium ${mom > 0 ? 'text-positive' : mom < 0 ? 'text-critical' : 'text-muted'}`}>
            {fmtPct(mom)} MoM
          </span>
        )}
      </div>
      <div className="hidden items-center gap-2 text-xs text-muted md:flex">
        <span
          aria-label={`data mode ${mode}`}
          className={`inline-block h-2 w-2 rounded-full ${mode === 'LIVE' ? 'bg-positive' : mode === 'REPLAY' ? 'bg-warning' : 'bg-muted'}`}
        />
        <span className="tracking-wider uppercase">{mode === 'REPLAY' ? 'Replay data' : mode === 'DEMO' ? 'Demo data' : mode} · {latest ? latest.index_date : '—'}</span>
      </div>
      <div className="ml-auto hidden text-[10px] text-muted lg:block">press <kbd className="rounded border border-grid px-1">/</kbd> to search</div>
    </div>
  )
}

/** Evidence / quality / methodology strip (UI_UX_DESIGN.md §3 footer). */
function FooterStrip() {
  const { data: latest } = useLatest()
  const { data: quality } = useQuality(30)
  const completeness = quality ? (quality.completeness * 100).toFixed(1) + '%' : '—'
  const observations = quality ? quality.total_observations.toLocaleString('en-IN') : '—'
  return (
    <footer className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-grid bg-surface px-4 py-2 text-[11px] text-muted lg:px-6">
      <span>Methodology {latest?.methodology_version ?? '—'} · basket {latest?.basket_version ?? '—'}</span>
      <span>Data confidence {completeness} usable ({observations} obs / 30d)</span>
      <span>Analytical prototype — not official CPI</span>
      <Link className="underline hover:text-ink" to="/methodology">How this number is built →</Link>
    </footer>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-surface focus:px-2 focus:py-1 focus:text-sm">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-grid bg-surface/95 backdrop-blur">
        <HeaderPulse />
      </header>
      <div className="flex flex-1">
        <nav aria-label="Primary" className="hidden w-40 shrink-0 border-r border-grid bg-surface md:block">
          <ul className="sticky top-14 space-y-0.5 p-2">
            {NAV.map((n) => (
              <li key={n.to}>
                <NavLink
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    `block rounded px-3 py-1.5 text-sm ${isActive ? 'bg-signal/10 font-medium text-signal' : 'text-muted hover:bg-grid/50 hover:text-ink'}`
                  }
                >
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" className="min-w-0 flex-1 px-4 py-6 lg:px-6">
          <AppRoutes />
        </main>
      </div>
      <FooterStrip />
      <CommandPalette />
    </div>
  )
}
