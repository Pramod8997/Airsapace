/** Methodology: the "index recipe" — six numbered stages, each expandable (UI_UX_DESIGN.md §18). */
import { useState } from 'react'
import { Card, ErrorState, Loading } from '../components/ui'
import { useMethodology } from '../api/hooks'
import { fmtDate } from '../lib/format'

const STAGES = [
  { n: '01', name: 'Observe', detail: 'Scheduled adapters collect quotes per route × lead time and map them to the canonical schema. Raw observations are immutable — never overwritten by cleaned values.' },
  { n: '02', name: 'Standardize', detail: 'Quotes normalize to consumer-payable fare = base fare + taxes + mandatory fees. The convenience fee is tracked but excluded (FR-09). Currency is INR.' },
  { n: '03', name: 'Clean', detail: 'Dedup by natural key (source+flight+cabin+class+instant). Availability states: AVAILABLE, SOLD_OUT, MISSING, INVALID, IMPUTED, REJECTED. Sold-out and missing are never counted as zero. MAD outlier detection flags suspicious fares — flagged, never deleted.' },
  { n: '04', name: 'Weight', detail: 'Route × lead-time weights from a versioned basket. Missing specs are reweighted, not imputed. Weights must sum to 1 and their source is recorded.' },
  { n: '05', name: 'Aggregate', detail: 'Median spec prices per route × lead time, then the Laspeyres-style formula with a fixed base period. Weekly/monthly values are means of available daily values.' },
  { n: '06', name: 'Validate', detail: 'Every run stores methodology, basket, weight versions and an input fingerprint (SHA-256) so the same snapshot reproduces the same index. Backtests compare against a labeled reference series.' },
] as const

export default function MethodologyPage() {
  const m = useMethodology()
  const [open, setOpen] = useState<number | null>(2) // default open: Clean

  if (m.isError) return <ErrorState error={m.error} />
  if (m.isPending) return <Loading label="Loading methodology" />

  const d = m.data

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-lg font-semibold">Methodology</h1>

      <Card title="Index recipe">
        <ol className="divide-y divide-grid">
          {STAGES.map((s, i) => (
            <li key={s.n}>
              <button
                className="flex w-full items-baseline gap-4 py-3 text-left hover:bg-grid/30"
                aria-expanded={open === i}
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span className="tnum text-sm font-semibold text-signal">{s.n}</span>
                <span className="text-sm font-medium tracking-[0.1em] uppercase">{s.name}</span>
                <span className="ml-auto text-xs text-muted">{open === i ? '−' : '+'}</span>
              </button>
              {open === i && <p className="px-4 pb-3 pl-12 text-sm leading-relaxed text-muted">{s.detail}</p>}
            </li>
          ))}
        </ol>
      </Card>

      <Card title="Versioned facts">
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <Row k="Methodology" v={`${d.version} — ${d.name}`} />
          <Row k="Formula" v={d.formula} mono />
          <Row k="Base period" v={`${fmtDate(d.base_period_start)} → ${fmtDate(d.base_period_end)} (index = ${d.base_value})`} />
          <Row k="Basket" v={d.basket_version} />
          <Row k="Weights" v={`${d.weight_version} · source: ${d.weight_source}`} />
          <Row k="Lead times" v={d.lead_times.map((l) => `T+${l}`).join(', ')} />
          <Row k="Outlier policy" v={d.outlier_policy} />
          <Row k="Missing data" v={d.missing_data_policy} />
          <Row k="Quality model" v={d.quality_model_version} />
          <Row k="Outlier method" v={d.outlier_method_version} />
        </dl>
        <p className="mt-3 text-sm leading-relaxed text-muted">{d.description}</p>
      </Card>

      <Card title="Basket routes">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-grid text-left text-[11px] tracking-widest text-muted uppercase">
              <th className="py-1.5">Route</th><th>Corridor</th><th className="text-right">Weight</th><th className="text-right">Lead times</th>
            </tr>
          </thead>
          <tbody>
            {d.basket_routes.map((r) => (
              <tr key={r.id} className="border-b border-grid/60">
                <td className="tnum py-1.5 font-medium">{r.id}</td>
                <td className="text-muted">{r.origin_city} → {r.destination_city}</td>
                <td className="tnum text-right">{(r.weight * 100).toFixed(2)}%</td>
                <td className="tnum text-right text-muted">{d.lead_times.map((l) => `T+${l}`).join(' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted">
          Weights are prototype placeholders pending derivation from authoritative DGCA traffic data (open question — see project memory).
        </p>
      </Card>

      <p className="text-xs text-muted">
        Determinism: the same input snapshot + methodology version + weights always reproduces the same index.
        Statistical honesty: APIx is not DGCA's series and this prototype is not official CPI.
      </p>
    </div>
  )
}

function Row({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex flex-wrap gap-x-3 py-0.5">
      <dt className="min-w-28 text-muted">{k}</dt>
      <dd className={mono ? 'tnum font-mono text-[13px]' : 'tnum'}>{v}</dd>
    </div>
  )
}
