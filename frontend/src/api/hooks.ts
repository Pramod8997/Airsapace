import { useQuery } from '@tanstack/react-query'
import { api } from './types'
import type { Route } from './types'

export const qk = {
  latest: ['index-latest'] as const,
  history: (route_id?: string, lead_time?: number, frequency?: string, from?: string, to?: string) =>
    ['index-history', { route_id, lead_time, frequency, from, to }] as const,
  routes: ['routes'] as const,
  airlines: ['airlines'] as const,
  sources: ['sources'] as const,
  quality: (windowDays: number) => ['quality', windowDays] as const,
  methodology: ['methodology'] as const,
  backtests: ['backtests'] as const,
  fares: (params: Record<string, string | number | undefined>) => ['fares', params] as const,
  anomalies: (windowDays: number, thresholdPct: number) => ['anomalies', windowDays, thresholdPct] as const,
}

export const useLatest = () => useQuery({ queryKey: qk.latest, queryFn: api.indexLatest })
export const useHistory = (p: { route_id?: string; lead_time?: number; frequency?: string; from?: string; to?: string }) =>
  useQuery({ queryKey: qk.history(p.route_id, p.lead_time, p.frequency, p.from, p.to), queryFn: () => api.indexHistory(p) })
export const useRoutes = () => useQuery({ queryKey: qk.routes, queryFn: api.routes })
export const useAirlines = () => useQuery({ queryKey: qk.airlines, queryFn: api.airlines })
export const useSources = () => useQuery({ queryKey: qk.sources, queryFn: api.sources })
export const useQuality = (windowDays = 30) => useQuery({ queryKey: qk.quality(windowDays), queryFn: () => api.quality(windowDays) })
export const useMethodology = () => useQuery({ queryKey: qk.methodology, queryFn: api.methodology })
export const useBacktests = () => useQuery({ queryKey: qk.backtests, queryFn: api.backtests })
export const useFares = (params: Record<string, string | number | undefined>, enabled = true) =>
  useQuery({ queryKey: qk.fares(params), queryFn: () => api.fares(params), enabled })
export const useAnomalies = (windowDays = 30, thresholdPct = 25) =>
  useQuery({ queryKey: qk.anomalies(windowDays, thresholdPct), queryFn: () => api.anomalies({ window_days: windowDays, threshold_pct: thresholdPct }) })

/** Route 7D change = last daily value vs value 7 days back, per route (used by Route Pressure). */
export function useRouteMovers(topN = 5, routes?: Route[]) {
  const rs = routes ?? []
  const routeIds = rs.map((r) => r.id)
  return useQuery({
    queryKey: ['route-movers', routeIds] as const,
    queryFn: async () => {
      const series = await Promise.all(
        routeIds.map((id) => api.indexHistory({ route_id: id, frequency: 'DAILY' })),
      )
      const movers: [string, number][] = []
      series.forEach((s, i) => {
        const pts = s.points
        if (pts.length === 0) return
        const last = pts[pts.length - 1]
        const lastDate = new Date(last.index_date)
        const prior = [...pts].reverse().find((p) => new Date(p.index_date) <= new Date(lastDate.getTime() - 7 * 86400_000))
        if (prior && prior.value !== 0) {
          movers.push([routeIds[i], (last.value / prior.value - 1) * 100])
        }
      })
      movers.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      return movers.slice(0, topN)
    },
    enabled: routeIds.length > 0,
  })
}

/** Forecast of the national APIx series — model extrapolation, not observed. */
export const useForecast = (horizonDays = 7) =>
  useQuery({ queryKey: ['forecast', horizonDays] as const, queryFn: () => api.forecast(horizonDays) })
