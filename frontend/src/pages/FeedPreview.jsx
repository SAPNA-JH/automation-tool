import { useEffect, useMemo, useState } from 'react'
import { api, imageUrl } from '../api'
import { useStudio } from '../studio'
import Lightbox from '../components/Lightbox'
import { Loader } from '../components/Loading'
import { Grid, Film, Tag, Heart, Comment, Play } from '../Icons'

// deterministic follower-ish number for the DRAFT mockup (never used in live mode)
const feign = (seed, base) => {
  let h = 0
  for (const c of String(seed)) h = (h * 31 + c.charCodeAt(0)) >>> 0
  const n = base + (h % base)
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

const compact = (n) => {
  if (n == null) return '—'
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}m`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export default function FeedPreview() {
  const { meta, refreshTick, accent } = useStudio()
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(null)
  const [emoji, setEmoji] = useState('⚡')
  const [tab, setTab] = useState('grid') // grid | reels
  const [ig, setIg] = useState(null) // { connected, profile, media } | null
  const [mode, setMode] = useState('drafts') // 'live' | 'drafts'

  const handle = (meta?.brand?.handle || 'your.account').replace(/^@/, '')
  const bio = meta?.brand?.niche || 'AI-crafted content, posted daily.'

  useEffect(() => {
    setLoading(true)
    Promise.all([api.posts({ status: 'approved' }), api.posts({ status: 'posted' })])
      .then(([a, b]) => setDrafts([...a, ...b].sort((x, y) => y.id - x.id)))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [refreshTick])

  useEffect(() => {
    api
      .igProfile()
      .then((d) => {
        setIg(d)
        if (d?.connected && d.profile) setMode('live') // default to live when available
      })
      .catch(() => setIg({ connected: false }))
  }, [refreshTick])

  useEffect(() => {
    api
      .niches()
      .then((list) => {
        const active = list.find((n) => n.key === meta?.brand?.preset)
        if (active?.emoji) setEmoji(active.emoji)
      })
      .catch(() => {})
  }, [meta?.brand?.preset])

  const live = mode === 'live' && ig?.connected && ig?.profile
  const prof = ig?.profile
  const media = ig?.media || []

  // profile fields resolve from real IG data (live) or the draft mockup
  const p = live
    ? {
        username: prof.username,
        name: prof.name || prof.username,
        bio: prof.biography || '',
        avatar: prof.profile_picture_url,
        posts: prof.media_count ?? media.length,
        followers: compact(prof.followers_count),
        following: compact(prof.follows_count),
      }
    : {
        username: handle,
        name: meta?.brand?.handle || `@${handle}`,
        bio,
        avatar: null,
        posts: drafts.length,
        followers: feign(handle, 800),
        following: feign(handle + 'f', 200),
      }

  const reels = useMemo(
    () =>
      live
        ? media.filter((m) => m.media_type === 'VIDEO')
        : drafts.filter((d) => d.media_kind === 'video'),
    [live, media, drafts],
  )
  const shown = tab === 'reels' ? reels : live ? media : drafts
  const highlights = (meta?.categories || []).slice(0, 8)

  return (
    <div className="p-6 lg:p-10">
      <header className="mb-8 max-w-5xl mx-auto flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Feed Preview</h1>
          <p className="text-sm text-ink-400 mt-0.5">
            {live
              ? 'Your live Instagram profile, pulled straight from your account.'
              : 'A mockup of your feed from approved & posted drafts.'}
          </p>
        </div>
        {ig?.connected && ig?.profile && (
          <div className="flex rounded-xl border border-ink-700 bg-ink-850 p-1 text-xs font-semibold">
            {['live', 'drafts'].map((m) => (
              <button
                key={m}
                onClick={() => setTab('grid') || setMode(m)}
                className={`px-3.5 py-1.5 rounded-lg capitalize transition-colors ${
                  mode === m ? 'text-white' : 'text-ink-400 hover:text-ink-200'
                }`}
                style={mode === m ? { background: accent } : undefined}
              >
                {m === 'live' ? 'Live' : 'Drafts'}
              </button>
            ))}
          </div>
        )}
      </header>

      <div className="max-w-5xl mx-auto">
        {/* profile header */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-8 sm:gap-16 px-2 sm:px-6">
          <div className="flex justify-center sm:justify-start sm:px-8">
            <div
              className="p-[3px] rounded-full shrink-0"
              style={{ background: `linear-gradient(135deg, ${accent}, #ec4899, #f59e0b)` }}
            >
              <div className="w-28 h-28 sm:w-40 sm:h-40 rounded-full grid place-items-center text-6xl sm:text-7xl bg-ink-900 border-4 border-ink-900 overflow-hidden">
                {p.avatar ? (
                  <img src={p.avatar} alt={p.username} className="w-full h-full object-cover" />
                ) : (
                  emoji
                )}
              </div>
            </div>
          </div>

          <div className="flex-1 min-w-0 space-y-5">
            <div className="flex flex-wrap items-center gap-4">
              <h2 className="text-xl text-white font-normal">@{p.username}</h2>
              {live && (
                <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Live
                </span>
              )}
            </div>

            <div className="flex gap-10 text-sm">
              <span className="text-ink-300">
                <b className="text-white">{p.posts}</b> posts
              </span>
              <span className="text-ink-300">
                <b className="text-white">{p.followers}</b> followers
              </span>
              <span className="text-ink-300">
                <b className="text-white">{p.following}</b> following
              </span>
            </div>

            <div>
              <div className="font-bold text-white">{p.name}</div>
              {p.bio && <p className="text-sm text-ink-300 mt-0.5 leading-snug max-w-lg whitespace-pre-line">{p.bio}</p>}
            </div>
          </div>
        </div>

        {highlights.length > 0 && (
          <div className="mt-10 flex gap-6 sm:gap-8 overflow-x-auto pb-2 px-2 sm:px-6">
            {highlights.map((c) => (
              <div key={c.name} className="flex flex-col items-center gap-2 shrink-0 w-20">
                <div className="p-[2px] rounded-full border border-ink-700">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full grid place-items-center bg-ink-850 text-xl font-bold text-ink-300">
                    {c.name.charAt(0)}
                  </div>
                </div>
                <span className="text-xs text-ink-400 truncate w-full text-center">{c.name}</span>
              </div>
            ))}
          </div>
        )}

        <div className="mt-8 flex items-center justify-center gap-14 border-t border-ink-800">
          <TabBtn icon={Grid} label="Posts" active={tab === 'grid'} onClick={() => setTab('grid')} accent={accent} />
          <TabBtn icon={Film} label="Reels" active={tab === 'reels'} onClick={() => setTab('reels')} accent={accent} badge={reels.length || null} />
          <TabBtn icon={Tag} label="Tagged" disabled accent={accent} />
        </div>

        {loading && !ig ? (
          <Loader label="Loading your feed…" />
        ) : shown.length === 0 ? (
          <div className="p-20 text-center text-sm text-ink-400">
            {live
              ? tab === 'reels'
                ? 'No reels on your Instagram yet.'
                : 'No posts on your Instagram yet — publish one to see it here.'
              : tab === 'reels'
                ? 'No reels yet — generate a video and approve it.'
                : "Approve some posts and they'll appear here as your future feed."}
          </div>
        ) : (
          <div className="mt-1 grid grid-cols-3 gap-1 sm:gap-1.5">
            {shown.map((item) =>
              live ? (
                <LiveCell key={item.id} m={item} />
              ) : (
                <DraftCell key={item.id} post={item} onOpen={setOpen} />
              ),
            )}
          </div>
        )}
      </div>

      <Lightbox post={open} onClose={() => setOpen(null)} />
    </div>
  )
}

function LiveCell({ m }) {
  const isVideo = m.media_type === 'VIDEO'
  const src = m.thumbnail_url || m.media_url
  return (
    <a
      href={m.permalink}
      target="_blank"
      rel="noreferrer"
      className="relative group bg-black aspect-square overflow-hidden block"
      title={m.caption || 'View on Instagram'}
    >
      {src ? (
        <img src={src} alt="" loading="lazy" className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" />
      ) : (
        <div className="w-full h-full grid place-items-center text-ink-600 text-xs">no preview</div>
      )}
      {isVideo && <Play className="absolute top-2.5 right-2.5 w-5 h-5 text-white drop-shadow pointer-events-none" />}
      {m.media_type === 'CAROUSEL_ALBUM' && (
        <span className="absolute top-2.5 right-2.5 text-white text-xs font-bold drop-shadow pointer-events-none">▦</span>
      )}
      <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 transition-opacity grid place-items-center pointer-events-none">
        <span className="text-white text-xs font-semibold">View on Instagram ↗</span>
      </div>
    </a>
  )
}

function DraftCell({ post, onOpen }) {
  const isVideo = post.media_kind === 'video'
  return (
    <button onClick={() => onOpen(post)} className="relative group bg-black aspect-square overflow-hidden">
      {isVideo ? (
        <video
          src={imageUrl(post)}
          muted
          loop
          playsInline
          preload="metadata"
          onMouseEnter={(e) => e.target.play().catch(() => {})}
          onMouseLeave={(e) => {
            e.target.pause()
            e.target.currentTime = 0
          }}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
      ) : (
        <img src={imageUrl(post)} alt={post.theme} loading="lazy" className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" />
      )}
      {isVideo && <Play className="absolute top-2.5 right-2.5 w-5 h-5 text-white drop-shadow pointer-events-none" />}
      {post.status === 'posted' && <span className="absolute top-2.5 left-2.5 w-2 h-2 rounded-full bg-sky-400 ring-2 ring-black/40" />}
      <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 transition-opacity grid place-items-center pointer-events-none">
        <div className="flex items-center gap-6 text-white font-semibold">
          <span className="flex items-center gap-1.5">
            <Heart className="w-5 h-5" filled /> {feign(post.id, 90)}
          </span>
          <span className="flex items-center gap-1.5">
            <Comment className="w-5 h-5" filled /> {feign(post.id + 'c', 12)}
          </span>
        </div>
      </div>
    </button>
  )
}

function TabBtn({ icon: Icon, label, active, onClick, disabled, accent, badge }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`relative flex items-center gap-2 py-4 text-xs font-semibold uppercase tracking-widest transition-colors -mt-px disabled:opacity-40 ${
        active ? 'text-white' : 'text-ink-500 hover:text-ink-300'
      }`}
      style={active ? { borderTop: `1px solid ${accent}` } : { borderTop: '1px solid transparent' }}
    >
      <Icon className="w-4 h-4" />
      {label}
      {badge != null && <span className="text-ink-400">{badge}</span>}
    </button>
  )
}
