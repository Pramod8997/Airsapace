/** Command palette — `/` opens; search routes/airlines, jump to screens (UI_UX_DESIGN.md §4). */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAirlines, useRoutes } from '../api/hooks'

interface Action { id: string; label: string; kind: string; to: string }

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const { data: routes } = useRoutes()
  const { data: airlines } = useAirlines()

  const actions = useMemo<Action[]>(() => {
    const nav: Action[] = [
      { id: 'nav-overview', label: 'Open Overview', kind: 'Navigate', to: '/' },
      { id: 'nav-index', label: 'Open Index', kind: 'Navigate', to: '/index' },
      { id: 'nav-routes', label: 'Open Route Observatory', kind: 'Navigate', to: '/routes' },
      { id: 'nav-lead', label: 'Open Lead Time', kind: 'Navigate', to: '/lead-time' },
      { id: 'nav-decomp', label: 'Open Fare Decomposition', kind: 'Navigate', to: '/fare-decomposition' },
      { id: 'nav-sources', label: 'Open Sources', kind: 'Navigate', to: '/sources' },
      { id: 'nav-quality', label: 'Open Quality', kind: 'Navigate', to: '/quality' },
      { id: 'nav-backtest', label: 'Open Backtesting', kind: 'Navigate', to: '/backtesting' },
      { id: 'nav-method', label: 'Open Methodology', kind: 'Navigate', to: '/methodology' },
    ]
    const routeActions = (routes ?? []).map((r) => ({
      id: `route-${r.id}`, label: `Route ${r.id} (${r.origin_city} → ${r.destination_city})`, kind: 'Route', to: `/routes?route=${r.id}`,
    }))
    const airlineActions = (airlines ?? []).map((a) => ({
      id: `airline-${a.iata}`, label: `Airline ${a.name} (${a.iata})`, kind: 'Airline', to: `/fare-decomposition?airline=${a.iata}`,
    }))
    return [...nav, ...routeActions, ...airlineActions]
  }, [routes, airlines])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return actions.slice(0, 12)
    return actions.filter((a) => a.label.toLowerCase().includes(needle)).slice(0, 12)
  }, [actions, q])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        setOpen(true)
        setQ('')
        setSel(0)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  if (!open) return null

  const run = (a: Action) => {
    setOpen(false)
    navigate(a.to)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/30 pt-[12vh]" onClick={() => setOpen(false)}>
      <div
        role="dialog" aria-label="Command palette" aria-modal="true"
        className="w-full max-w-lg overflow-hidden rounded-lg border border-grid bg-surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={q}
          placeholder="Search routes, airlines, screens…"
          aria-label="Search"
          className="w-full border-b border-grid bg-transparent px-4 py-3 text-sm outline-none"
          onChange={(e) => { setQ(e.target.value); setSel(0) }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)) }
            if (e.key === 'Enter' && filtered[sel]) run(filtered[sel])
            if (e.key === 'Escape') setOpen(false)
          }}
        />
        <ul className="max-h-72 overflow-y-auto">
          {filtered.map((a, i) => (
            <li key={a.id}>
              <button
                className={`flex w-full items-center justify-between px-4 py-2 text-left text-sm ${i === sel ? 'bg-signal/10' : ''}`}
                onMouseEnter={() => setSel(i)}
                onClick={() => run(a)}
              >
                <span>{a.label}</span>
                <span className="text-[10px] tracking-widest text-muted uppercase">{a.kind}</span>
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-4 py-3 text-sm text-muted">No matches</li>}
        </ul>
      </div>
    </div>
  )
}
