import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, imageUrl } from '../api'
import { useStudio } from '../studio'
import Lightbox from '../components/Lightbox'
import AutomationToggle from '../components/AutomationToggle'
import { ThumbGridSkeleton } from '../components/Loading'
import { Spinner, Play } from '../Icons'

function StatCard({ label, value, tone }) {
  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900 p-5">
      <div className="text-3xl font-bold text-white">{value ?? 0}</div>
      <div className={`text-xs mt-1 font-medium ${tone || 'text-ink-400'}`}>{label}</div>
    </div>
  )
}

export default function Dashboard() {
  const { refreshTick, running, accent, meta } = useStudio()
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(null)
  const [niche, setNiche] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.stats().then(setStats).catch(() => {}),
      api.posts().then((p) => setRecent(p.slice(0, 8))).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [refreshTick])

  useEffect(() => {
    api.niches()
      .then((list) => setNiche(list.find((n) => n.key === meta?.brand?.preset) || null))
      .catch(() => {})
  }, [meta?.brand?.preset])

  const byCat = Object.entries(stats?.by_category || {}).sort((a, b) => b[1] - a[1])
  const maxCat = Math.max(1, ...byCat.map(([, n]) => n))

  const nicheAccent = niche?.accent || accent

  return (
    <div className="relative p-8 space-y-8">
      {/* niche-tinted ambient glow (matches the Settings hero) */}
      <div
        className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 w-[900px] max-w-full h-80 rounded-full blur-3xl opacity-25 -z-0"
        aria-hidden
        style={{ background: `radial-gradient(circle, ${nicheAccent}, transparent 65%)` }}
      />
      <div className="relative space-y-8">
        <AutomationToggle />

      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-ink-400 mt-0.5">
            {meta?.brand?.niche || 'Automated content studio'}
          </p>
        </div>
        <Link
          to="/settings"
          className="flex items-center gap-3 rounded-xl border border-ink-700 bg-ink-900 px-4 py-2.5 hover:border-ink-400 transition-colors"
        >
          <span className="text-2xl leading-none">{niche?.emoji || '✨'}</span>
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wide text-ink-500 font-semibold">Active niche</div>
            <div className="text-sm font-semibold text-white truncate max-w-[220px]">
              {niche?.name || meta?.brand?.niche || 'Custom niche'}
            </div>
          </div>
          <span className="text-xs ml-1 shrink-0" style={{ color: accent }}>
            Change
          </span>
        </Link>
      </header>

      {running.length > 0 && (
        <div className="flex items-center gap-3 rounded-2xl border border-violet-500/30 bg-violet-500/10 px-5 py-4 text-sm text-violet-200">
          <Spinner className="w-4 h-4" />
          {running.length} post{running.length > 1 ? 's' : ''} generating — they'll appear below
          when ready.
        </div>
      )}

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total posts" value={stats?.total} />
        <StatCard label="Pending review" value={stats?.by_status?.pending} tone="text-amber-400" />
        <StatCard label="Approved" value={stats?.by_status?.approved} tone="text-emerald-400" />
        <StatCard label="Posted" value={stats?.by_status?.posted} tone="text-sky-400" />
      </section>

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="rounded-2xl border border-ink-700 bg-ink-900 p-6">
          <h2 className="font-semibold text-white mb-4">Content pillars</h2>
          <div className="space-y-3">
            {byCat.length === 0 && <div className="text-sm text-ink-400">No posts yet.</div>}
            {byCat.map(([name, n]) => (
              <div key={name} className="flex items-center gap-3 text-sm">
                <div className="w-44 truncate text-ink-200">{name}</div>
                <div className="flex-1 h-2.5 rounded-full bg-ink-800 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(n / maxCat) * 100}%`, background: accent }}
                  />
                </div>
                <div className="w-8 text-right text-ink-400">{n}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-ink-700 bg-ink-900 p-6">
          <h2 className="font-semibold text-white mb-4">Layouts used</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats?.by_type || {})
              .sort((a, b) => b[1] - a[1])
              .map(([t, n]) => (
                <span
                  key={t}
                  className="text-xs px-3 py-1.5 rounded-full border border-ink-700 bg-ink-850"
                >
                  <b className="text-white">{t}</b> <span className="text-ink-400">× {n}</span>
                </span>
              ))}
          </div>
          <h2 className="font-semibold text-white mb-3 mt-6">Daily schedule</h2>
          <p className="text-sm text-ink-400">
            {meta?.daily?.enabled
              ? `Auto-generating every day at ${String(meta.daily.hour).padStart(2, '0')}:${String(meta.daily.minute).padStart(2, '0')}`
              : 'Daily auto-generation is disabled'}
          </p>
        </section>
      </div>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">Recent posts</h2>
          <Link to="/posts" className="text-sm hover:underline" style={{ color: accent }}>
            View all →
          </Link>
        </div>
        {loading ? (
          <ThumbGridSkeleton count={8} />
        ) : recent.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-700 p-12 text-center text-ink-400">
            No posts yet — generate your first from the panel above.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {recent.map((p) => (
              <button
                key={p.id}
                onClick={() => setOpen(p)}
                className="relative rounded-xl overflow-hidden border border-ink-700 hover:border-ink-400 transition-colors"
              >
                {p.media_kind === 'video' ? (
                  <>
                    <video
                      src={imageUrl(p)}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      onMouseEnter={(e) => e.target.play().catch(() => {})}
                      onMouseLeave={(e) => {
                        e.target.pause()
                        e.target.currentTime = 0
                      }}
                      className="aspect-[4/5] object-cover w-full bg-black"
                    />
                    <Play className="absolute top-2 right-2 w-4 h-4 text-white drop-shadow pointer-events-none" />
                  </>
                ) : (
                  <img
                    src={imageUrl(p)}
                    alt={p.theme}
                    loading="lazy"
                    className="aspect-[4/5] object-cover w-full bg-black"
                  />
                )}
              </button>
            ))}
          </div>
        )}
        </section>

        <Lightbox post={open} onClose={() => setOpen(null)} />
      </div>
    </div>
  )
}
