import { useState } from 'react'
import { previewUrl } from '../api'
import { useStudio } from '../studio'
import { Sparkles, Spinner } from '../Icons'
import { Loader } from '../components/Loading'

const BLURBS = {
  grid: 'Multi-panel listicles — numbered cards, steps, checklists, rankings.',
  vs: 'Side-by-side contrasts — VS, this-or-that, before/after.',
  overlay: 'One cinematic image with a composed tagline.',
  card: 'Quotes, facts, affirmations and questions — pure typography.',
  data: 'Big-number stats and dictionary-style definitions.',
}

export default function Templates() {
  const { meta, generate, accent } = useStudio()
  const [category, setCategory] = useState('')
  const [submitting, setSubmitting] = useState(null) // the design key currently being kicked off
  const families = meta?.families || []
  const designCount = families.reduce((n, f) => n + f.designs.length, 0)
  const cacheBust = useState(() => Date.now())[0]

  const onGenerate = async (design) => {
    setSubmitting(design)
    try {
      await generate({ category, template: design, count: 1 })
    } finally {
      setSubmitting(null)
    }
  }

  if (!meta) return <Loader label="Loading templates…" />

  return (
    <div className="p-8 space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Templates</h1>
          <p className="text-sm text-ink-400 mt-0.5">
            {designCount} layouts — previews rendered with your brand accent, no AI cost.
          </p>
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-xl bg-ink-850 border border-ink-700 px-3 py-2.5 text-sm focus:outline-none focus:border-violet-500"
        >
          <option value="">🎲 Generate with any category</option>
          {meta?.categories?.map((c) => (
            <option key={c.name} value={c.name}>
              Generate as: {c.name}
            </option>
          ))}
        </select>
      </header>

      {families.map((fam) => {
        const members = fam.designs
        if (members.length === 0) return null
        return (
          <section key={fam.key}>
            <h2 className="font-semibold text-white">{fam.label}</h2>
            <p className="text-sm text-ink-400 mb-4">{BLURBS[fam.key] || ''}</p>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-5">
              {members.map((d) => (
                <figure
                  key={d}
                  className="group rounded-2xl border border-ink-700 bg-ink-900 overflow-hidden hover:border-ink-400 transition-colors"
                >
                  <img
                    src={`${previewUrl(d)}?v=${cacheBust}`}
                    alt={`${d} layout`}
                    loading="lazy"
                    className="w-full aspect-[4/5] object-cover"
                  />
                  <figcaption className="flex items-center justify-between gap-2 p-3">
                    <span className="text-xs font-semibold">{d}</span>
                    <button
                      onClick={() => onGenerate(d)}
                      disabled={!!submitting}
                      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white opacity-90 hover:opacity-100 transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
                      style={{ background: accent }}
                    >
                      {submitting === d ? (
                        <Spinner className="w-3.5 h-3.5" />
                      ) : (
                        <Sparkles className="w-3.5 h-3.5" />
                      )}
                      {submitting === d ? 'Starting…' : 'Generate'}
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
