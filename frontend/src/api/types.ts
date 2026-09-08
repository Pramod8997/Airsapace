/** Typed API client + react-query hooks for the AirStat /api/v1 read-only endpoints. */

export interface IndexLatest {
  index: number
  base: number
  index_date: string
  daily_change_pct: number | null
  weekly_change_pct: number | null
  monthly_change_pct: number | null
  methodology_version: string
  basket_version: string
  weight_version: string
  calculation_run_id: number
  data_mode: string // LIVE | DEMO | REPLAY — honesty about what produced this
}

export interface IndexPoint {
  index_date: string
  value: number
  route_id: string | null
  lead_time: number | null
}

export interface IndexHistory {
  route_id: string | null
  lead_time: number | null
  frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY'
  methodology_version: string
  points: IndexPoint[]
}

export interface Route {
  id: string
  origin: string
  destination: string
  origin_city: string
  destination_city: string
  weight: number
  weight_source: string
  weight_version: string
  active: boolean
}

export interface Airline { iata: string; name: string; active: boolean }

export interface Source {
  id: string
  name: string
  source_type: string
  policy_status: string
  robots_status: string
  rate_limit_per_hour: number
  active: boolean
  reliability: number
  last_success_at: string | null
  last_failure_at: string | null
}

export interface Fare {
  id: number
  source_id: string
  route_id: string
  origin: string
  destination: string
  departure_date: string
  departure_time: string | null
  airline: string
  flight_number: string | null
  cabin: string
  fare_class: string | null
  advance_days: number
  base_fare: number | null
  taxes: number | null
  mandatory_fees: number | null
  convenience_fee: number
  total_fare: number | null
  consumer_payable_fare: number | null
  currency: string
  availability: string
  stops: number
  collected_at: string
  quality_score: number | null
  outlier_flag: boolean
  outlier_reason: string | null
}

export interface PaginatedFares {
  page: number
  page_size: number
  total: number
  items: Fare[]
}

export interface SourceHealth {
  source_id: string
  observations: number
  availability_rate: number
  last_success_at: string | null
  last_failure_at: string | null
}

export interface Quality {
  window_days: number
  total_observations: number
  available: number
  sold_out: number
  invalid: number
  rejected: number
  completeness: number
  duplicate_count: number
  duplicate_rate: number
  rejection_rate: number
  imputation_rate: number
  outlier_rate: number
  source_health: SourceHealth[]
}

export interface Methodology {
  version: string
  name: string
  description: string
  base_period_start: string
  base_period_end: string
  base_value: number
  formula: string
  outlier_policy: string
  missing_data_policy: string
  quality_model_version: string
  outlier_method_version: string
  basket_version: string
  weight_version: string
  weight_source: string
  published: boolean
  lead_times: number[]
  basket_routes: Route[]
}

export interface BacktestRun {
  id: number
  period_start: string
  period_end: string
  methodology_version: string
  basket_version: string
  reference_series: string
  metrics: {
    n_points: number
    mae: number | null
    rmse: number | null
    mape: number | null
    correlation: number | null
    trend_direction_accuracy: number | null
  }
  created_at: string
}

export interface Anomaly {
  route_id: string
  origin: string
  destination: string
  lead_time: number
  current_date: string
  current_median: number
  window_median: number
  change_pct: number
  source_confirmations: number
  sources_seen: number
  sold_out_share: number
  severity: 'SHOCK' | 'ELEVATED' | 'DIP'
  explanation: {
    lead_window: string
    source_confirmation: string
    availability: string
    comparison: string
  }
}

export interface AnomalyReport {
  anomalies: Anomaly[]
  model_version: string
  as_of: string | null
  disclaimer: string
}

export interface ForecastPoint {
  date: string
  value: number
}

export interface Forecast {
  model_version: string
  horizon_days: number
  methodology_version: string
  history: IndexPoint[]
  fitted: ForecastPoint[]
  forecast: ForecastPoint[]
  params: { alpha: number; beta: number }
  in_sample_rmse: number
  holdout_rmse: number | null
  method: string
  disclaimer: string // forecast, not observed price — honesty invariant
}

export interface Health { status: string; data_mode: string; app_env: string; database: string }

const BASE = '/api/v1'

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? '?' + Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : ''
  const res = await fetch(`${BASE}${path}${qs}`)
  if (!res.ok) {
    let detail = res.statusText
    try { const body = await res.json(); if (body?.detail) detail = String(body.detail) } catch { /* not json */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  indexLatest: () => get<IndexLatest>('/index/latest'),
  indexHistory: (p: { route_id?: string; lead_time?: number; frequency?: string; from?: string; to?: string }) =>
    get<IndexHistory>('/index/history', p),
  indexRoute: (routeId: string, frequency?: string) =>
    get<IndexHistory>(`/index/route/${routeId}`, { frequency }),
  fares: (p: Record<string, string | number | undefined>) => get<PaginatedFares>('/fares', p),
  routes: () => get<Route[]>('/routes'),
  airlines: () => get<Airline[]>('/airlines'),
  sources: () => get<Source[]>('/sources'),
  quality: (windowDays = 30) => get<Quality>('/quality', { window_days: windowDays }),
  methodology: () => get<Methodology>('/methodology'),
  backtests: () => get<BacktestRun[]>('/backtests'),
  anomalies: (p: { window_days?: number; threshold_pct?: number; route_id?: string } = {}) =>
    get<AnomalyReport>('/anomalies', p),
  forecast: (horizonDays = 7) => get<Forecast>('/forecast', { horizon_days: horizonDays }),
  health: () => get<Health>('/health'),
}
