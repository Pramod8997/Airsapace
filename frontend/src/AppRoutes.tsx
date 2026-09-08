import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Loading } from './components/ui'

const pages = {
  Overview: lazy(() => import('./pages/Overview')),
  IndexPage: lazy(() => import('./pages/IndexPage')),
  RoutesPage: lazy(() => import('./pages/RoutesPage')),
  LeadTimePage: lazy(() => import('./pages/LeadTimePage')),
  FareDecompositionPage: lazy(() => import('./pages/FareDecompositionPage')),
  SourcesPage: lazy(() => import('./pages/SourcesPage')),
  QualityPage: lazy(() => import('./pages/QualityPage')),
  AnomalyPage: lazy(() => import('./pages/AnomalyPage')),
  BacktestingPage: lazy(() => import('./pages/BacktestingPage')),
  MethodologyPage: lazy(() => import('./pages/MethodologyPage')),
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading label="Loading page" />}>
      <Routes>
        <Route path="/" element={<pages.Overview />} />
        <Route path="/index" element={<pages.IndexPage />} />
        <Route path="/routes" element={<pages.RoutesPage />} />
        <Route path="/lead-time" element={<pages.LeadTimePage />} />
        <Route path="/fare-decomposition" element={<pages.FareDecompositionPage />} />
        <Route path="/sources" element={<pages.SourcesPage />} />
        <Route path="/quality" element={<pages.QualityPage />} />
        <Route path="/anomalies" element={<pages.AnomalyPage />} />
        <Route path="/backtesting" element={<pages.BacktestingPage />} />
        <Route path="/methodology" element={<pages.MethodologyPage />} />
        <Route path="*" element={<Loading label="Not found" />} />
      </Routes>
    </Suspense>
  )
}
