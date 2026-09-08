/** Thin ECharts wrapper: init once, apply option deltas, resize with container, dispose on unmount. */
import * as echarts from 'echarts'
import { useEffect, useRef, useState } from 'react'

export function Chart({ option, className = 'h-72', summary }: {
  option: echarts.EChartsOption
  className?: string
  /** accessible chart summary (UI_UX_DESIGN.md §24) */
  summary?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const [, setThemeTick] = useState(0)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chartRef.current = chart
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)

    const handleThemeChange = () => {
      setThemeTick((t) => t + 1)
    }
    window.addEventListener('themechange', handleThemeChange)

    return () => {
      window.removeEventListener('themechange', handleThemeChange)
      ro.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true })
  }, [option])

  return (
    <div
      ref={ref}
      role="img"
      aria-label={summary ?? 'chart'}
      className={`w-full ${className}`}
    />
  )
}

function getThemeVal(prop: string) {
  const isDark = typeof document !== 'undefined' &&
    (document.documentElement.getAttribute('data-theme') === 'dark' || document.documentElement.classList.contains('dark'))
  switch (prop) {
    case 'ink': return isDark ? '#f1f5f9' : '#10141c'
    case 'muted': return isDark ? '#8e9ab0' : '#5c6674'
    case 'grid': return isDark ? '#1e293b' : '#e3e7ee'
    case 'signal': return isDark ? '#3b82f6' : '#1f5fd6'
    case 'positive': return isDark ? '#10b981' : '#1d7a4f'
    case 'critical': return isDark ? '#ef4444' : '#c0392b'
    case 'warning': return isDark ? '#f59e0b' : '#b8860b'
    case 'axis': return {
      axisLine: { lineStyle: { color: isDark ? '#27354e' : '#e3e7ee' } },
      axisLabel: { color: isDark ? '#8e9ab0' : '#5c6674', fontSize: 11 },
      splitLine: { lineStyle: { color: isDark ? '#1e293b' : '#e3e7ee', type: 'dashed' as const } },
    }
    default: return undefined
  }
}

/** Observatory chart theme — dynamically responds to light/dark mode (UI_UX_DESIGN.md §2/§6). */
export const chartTheme = new Proxy({} as {
  ink: string
  muted: string
  grid: string
  signal: string
  positive: string
  critical: string
  warning: string
  axis: {
    axisLine: { lineStyle: { color: string } }
    axisLabel: { color: string; fontSize: number }
    splitLine: { lineStyle: { color: string; type: 'dashed' } }
  }
}, {
  get(_target, prop: string) {
    return getThemeVal(prop)
  }
})

