import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useStudio } from '../studio'
import PostCard from '../components/PostCard'
import Lightbox from '../components/Lightbox'
import GeneratePanel from '../components/GeneratePanel'
import { PostGridSkeleton } from '../components/Loading'

const STATUS_TABS = ['', 'pending', 'approved', 'posted', 'rejected']

export default function Posts() {
  const { meta, refreshTick, accent } = useStudio()
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [template, setTemplate] = useState('')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    api.posts({ status, category, template, q })
      .then(setPosts)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [status, category, template, q])

  useEffect(load, [load, refreshTick])

  const sel =
    'rounded-xl bg-ink-850 border border-ink-700 px-3 py-2 text-sm focus:outline-none focus:border-violet-500'

  return (
    <div className="p-8 space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Posts</h1>
          <p className="text-sm text-ink-400 mt-0.5">{loading ? 'Loading…' : `${posts.length} shown`}</p>
        </div>
        <GeneratePanel />
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-xl border border-ink-700 bg-ink-850 p-1">
          {STATUS_TABS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors ${
                status === s ? 'text-white' : 'text-ink-400 hover:text-ink-200'
              }`}
              style={status === s ? { background: accent } : {}}
            >
              {s || 'all'}
            </button>
          ))}
        </div>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={sel}>
          <option value="">All categories</option>
          {meta?.categories?.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
        <select value={template} onChange={(e) => setTemplate(e.target.value)} className={sel}>
          <option value="">All layouts</option>
          {meta?.templates?.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search theme or caption…"
          className={`${sel} w-64`}
        />
      </div>

      {loading ? (
        <PostGridSkeleton count={8} />
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink-700 p-16 text-center text-ink-400">
          No posts match. Generate one from the panel above.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
          {posts.map((p) => (
            <PostCard key={p.id} post={p} onChanged={load} onOpen={setOpen} />
          ))}
        </div>
      )}

      <Lightbox post={open} onClose={() => setOpen(null)} onChanged={load} />
    </div>
  )
}
