import { useState } from 'react'
import { useStudio } from '../studio'
import { Sparkles, Spinner } from '../Icons'

export default function GeneratePanel({ defaultTemplate = '' }) {
  const { meta, generate, accent, running } = useStudio()
  const [submitting, setSubmitting] = useState(false)
  const [category, setCategory] = useState('')
  const [template, setTemplate] = useState(defaultTemplate)
  const [count, setCount] = useState(1)
  const [theme, setTheme] = useState('')

  // `submitting` gives instant feedback on click; `running` keeps it lit while jobs process.
  const busy = submitting || running.length > 0

  const onGenerate = async () => {
    setSubmitting(true)
    try {
      await generate({ category, template, count, theme: theme.trim() })
    } finally {
      setSubmitting(false)
    }
  }

  const sel =
    'rounded-xl bg-ink-850 border border-ink-700 px-3 py-2.5 text-sm focus:outline-none focus:border-violet-500'

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <input
        value={theme}
        onChange={(e) => setTheme(e.target.value)}
        placeholder="Custom topic (optional) — post about anything…"
        className={`${sel} w-72`}
      />
      <select value={category} onChange={(e) => setCategory(e.target.value)} className={sel}>
        <option value="">🎲 Any category</option>
        {meta?.categories?.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
      <select value={template} onChange={(e) => setTemplate(e.target.value)} className={sel}>
        <option value="">🎲 Any layout</option>
        {meta?.templates?.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <select value={count} onChange={(e) => setCount(+e.target.value)} className={sel}>
        {[1, 2, 3, 5].map((n) => (
          <option key={n} value={n}>
            × {n}
          </option>
        ))}
      </select>
      <button
        onClick={onGenerate}
        disabled={busy}
        className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-80"
        style={{ background: accent }}
      >
        {busy ? <Spinner className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
        {submitting
          ? 'Starting…'
          : running.length > 0
            ? `Generating${running.length > 1 ? ` ${running.length}` : ''}…`
            : 'Generate'}
      </button>
    </div>
  )
}
