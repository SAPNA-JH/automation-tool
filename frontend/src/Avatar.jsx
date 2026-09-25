import { useState } from 'react'

// 10 default icon avatars — each a distinct emoji on a gradient. Assigned per user by a
// stable hash of their email, so the same person always gets the same icon.
const AVATARS = [
  { emoji: '🦊', from: '#f59e0b', to: '#ef4444' },
  { emoji: '🐸', from: '#22c55e', to: '#0ea5e9' },
  { emoji: '🦉', from: '#8b5cf6', to: '#ec4899' },
  { emoji: '🐙', from: '#06b6d4', to: '#3b82f6' },
  { emoji: '🌙', from: '#6366f1', to: '#a855f7' },
  { emoji: '🔮', from: '#a855f7', to: '#ec4899' },
  { emoji: '🌀', from: '#0ea5e9', to: '#14b8a6' },
  { emoji: '⚡', from: '#f59e0b', to: '#f97316' },
  { emoji: '🍥', from: '#ec4899', to: '#f43f5e' },
  { emoji: '👾', from: '#10b981', to: '#6366f1' },
]

function hashString(s) {
  let h = 5381
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i)
  return Math.abs(h)
}

export function defaultAvatar(seed) {
  return AVATARS[hashString(seed || '?') % AVATARS.length]
}

export function Avatar({ user, size = 32, className = '' }) {
  const [broken, setBroken] = useState(false)
  const seed = user?.email || user?.name || '?'
  const a = defaultAvatar(seed)

  if (user?.picture && !broken) {
    return (
      <img
        src={user.picture}
        alt=""
        onError={() => setBroken(true)}
        style={{ width: size, height: size }}
        className={`rounded-full object-cover shrink-0 ${className}`}
      />
    )
  }
  return (
    <div
      className={`rounded-full grid place-items-center shrink-0 select-none ${className}`}
      style={{
        width: size,
        height: size,
        background: `linear-gradient(135deg, ${a.from}, ${a.to})`,
        fontSize: Math.round(size * 0.52),
        lineHeight: 1,
      }}
      title={user?.name || user?.email || ''}
    >
      <span>{a.emoji}</span>
    </div>
  )
}
