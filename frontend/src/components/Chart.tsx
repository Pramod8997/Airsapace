/** Thin ECharts wrapper: init once, apply option deltas, resize with container, dispose on unmount. */
import * as echarts from 'echarts'
import { useEffect, useRef } from 'react'

export function Chart({ option, className = 'h-72', summary }: {
  option: echarts.EChartsOption
  className?: string
  /** accessible chart summary (UI_UX_DESIGN.md §24) */
  summary?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    chartRef.current = chart
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(ref.current)
    return () => {
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

/** Observatory chart theme — neutral, calm, tabular (UI_UX_DESIGN.md §2/§6). */
export const chartTheme = {
  ink: '#10141c',
  muted: '#5c6674',
  grid: '#e3e7ee',
  signal: '#1f5fd6',
  positive: '#1d7a4f',
  critical: '#c0392b',
  warning: '#b8860b',
  axis: {
    axisLine: { lineStyle: { color: '#e3e7ee' } },
    axisLabel: { color: '#5c6674', fontSize: 11 },
    splitLine: { lineStyle: { color: '#e3e7ee', type: 'dashed' as const } },
  },
}
