import { useTheme } from '../lib/theme'

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme()

  const cycleTheme = () => {
    if (theme === 'light') setTheme('dark')
    else if (theme === 'dark') setTheme('system')
    else setTheme('light')
  }

  return (
    <button
      onClick={cycleTheme}
      className="flex items-center gap-1.5 rounded border border-grid bg-surface px-2 py-1 text-xs font-medium text-muted transition-colors hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:outline-2 focus-visible:outline-signal"
      title={`Theme: ${theme} (Active: ${resolvedTheme}). Click to change.`}
      aria-label={`Current theme ${theme}. Switch theme`}
    >
      {resolvedTheme === 'dark' ? (
        <svg className="h-3.5 w-3.5 text-signal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      ) : (
        <svg className="h-3.5 w-3.5 text-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      )}
      <span className="capitalize text-[11px] tracking-wide">{theme}</span>
    </button>
  )
}
