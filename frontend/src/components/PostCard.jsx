import { imageUrl } from '../api'
import { useStudio } from '../studio'

const statusStyles = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  approved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  posted: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  rejected: 'bg-red-500/15 text-red-300 border-red-500/30',
}

export default function PostCard({ post, onOpen }) {
  const { accent } = useStudio()
  const isVideo = post.media_kind === 'video'

  return (
    <article
      onClick={() => onOpen?.(post)}
      className="fade-up group cursor-pointer rounded-2xl border border-ink-700 bg-ink-900 overflow-hidden flex flex-col hover:border-ink-400 transition-colors"
    >
      <div className="relative">
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
            className="w-full aspect-[4/5] object-cover bg-black"
          />
        ) : (
          <img
            src={imageUrl(post)}
            alt={post.theme}
            loading="lazy"
            className="w-full aspect-[4/5] object-cover bg-black group-hover:opacity-90 transition-opacity"
          />
        )}
        {isVideo && (
          <span className="absolute top-3 left-3 text-[10px] font-bold px-2 py-1 rounded-md bg-black/60 text-white backdrop-blur pointer-events-none">
            ▶ REEL
          </span>
        )}
        <span
          className={`absolute top-3 right-3 text-[10px] uppercase tracking-wide font-bold px-2 py-1 rounded-md border backdrop-blur ${statusStyles[post.status] || ''}`}
        >
          {post.status}
        </span>
      </div>

      <div className="p-4 flex flex-col gap-2 flex-1">
        <div className="font-semibold text-white text-sm leading-snug">{post.theme}</div>
        <div className="flex gap-1.5 flex-wrap">
          {post.category && (
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-md border"
              style={{ color: accent, borderColor: `${accent}66`, background: `${accent}1a` }}
            >
              {post.category}
            </span>
          )}
          <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-md border border-ink-700 text-ink-400">
            {post.post_type}
          </span>
        </div>
        <p className="text-sm text-ink-200/90 leading-snug line-clamp-2 whitespace-pre-wrap">
          {post.caption}
        </p>
      </div>
    </article>
  )
}
