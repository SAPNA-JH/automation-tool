// Reusable loading UI: a branded spinner + shimmer skeletons. No external deps.

export function Loader({ size = 42, label, color = '#a855f7', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-12 ${className}`}>
      <svg width={size} height={size} viewBox="0 0 50 50" className="animate-spin"
           style={{ color }}>
        <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor"
                strokeOpacity="0.18" strokeWidth="5" />
        <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" strokeWidth="5"
                strokeLinecap="round" strokeDasharray="80 150" />
      </svg>
      {label && <span className="text-sm text-ink-400">{label}</span>}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`shimmer rounded-lg ${className}`} />
}

export function PostCardSkeleton() {
  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900 overflow-hidden">
      <Skeleton className="w-full aspect-[4/5] !rounded-none" />
      <div className="p-4 space-y-3">
        <Skeleton className="h-4 w-3/4" />
        <div className="flex gap-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-14" />
        </div>
        <Skeleton className="h-14 w-full" />
      </div>
    </div>
  )
}

export function PostGridSkeleton({ count = 8 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
      {Array.from({ length: count }).map((_, i) => <PostCardSkeleton key={i} />)}
    </div>
  )
}

export function ThumbGridSkeleton({ count = 8, cols = 'grid-cols-2 sm:grid-cols-4 lg:grid-cols-8' }) {
  return (
    <div className={`grid ${cols} gap-3`}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="aspect-[4/5] w-full" />
      ))}
    </div>
  )
}

// Image that shows a shimmer placeholder until it finishes loading.
export function LazyImage({ src, alt, className = '', aspect = 'aspect-[4/5]' }) {
  return (
    <div className={`relative ${aspect} overflow-hidden bg-ink-850`}>
      <div className="shimmer absolute inset-0" />
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={(e) => e.currentTarget.previousSibling?.remove()}
        onError={(e) => e.currentTarget.previousSibling?.remove()}
        className={`relative w-full h-full ${className}`}
      />
    </div>
  )
}
