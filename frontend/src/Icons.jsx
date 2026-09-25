const I = ({ d, className = 'w-5 h-5', filled = false }) => (
  <svg
    viewBox="0 0 24 24"
    fill={filled ? 'currentColor' : 'none'}
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    {d.map((p, i) => (
      <path key={i} d={p} />
    ))}
  </svg>
)

export const Home = (p) => <I {...p} d={['M3 10.5 12 3l9 7.5', 'M5 9.5V21h14V9.5']} />
export const Grid = (p) => (
  <I {...p} d={['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M3 14h7v7H3z', 'M14 14h7v7h-7z']} />
)
export const Layout = (p) => <I {...p} d={['M3 3h18v18H3z', 'M3 9h18', 'M9 9v12']} />
export const Feed = (p) => (
  <I {...p} d={['M4 4h16v16H4z', 'M4 10.5h16', 'M4 17h16', 'M10.5 4v16', 'M17 4v16']} />
)
export const Cog = (p) => (
  <I
    {...p}
    d={[
      'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
      'M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    ]}
  />
)
export const Sparkles = (p) => (
  <I {...p} d={['M12 3v3', 'M12 18v3', 'M5.6 5.6l2.1 2.1', 'M16.3 16.3l2.1 2.1', 'M3 12h3', 'M18 12h3', 'M5.6 18.4l2.1-2.1', 'M16.3 7.7l2.1-2.1']} />
)
export const Check = (p) => <I {...p} d={['M4 12.5 9.5 18 20 6.5']} />
export const X = (p) => <I {...p} d={['M5 5l14 14', 'M19 5 5 19']} />
export const Trash = (p) => (
  <I {...p} d={['M4 7h16', 'M9 7V4h6v3', 'M6 7l1 13h10l1-13', 'M10 11v6', 'M14 11v6']} />
)
export const Download = (p) => <I {...p} d={['M12 3v12', 'M6.5 10.5 12 16l5.5-5.5', 'M4 20h16']} />
export const Copy = (p) => (
  <I {...p} d={['M9 9h11v11H9z', 'M5 15H4V4h11v1']} />
)
export const Refresh = (p) => (
  <I {...p} d={['M20 8A8 8 0 1 0 20 16', 'M20 3v5h-5']} />
)
export const Pencil = (p) => (
  <I {...p} d={['M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19l-4 1z']} />
)
export const Heart = (p) => (
  <I {...p} d={['M12 20s-7-4.5-9.5-9A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 9.5 5c-2.5 4.5-9.5 9-9.5 9z']} />
)
export const Comment = (p) => (
  <I {...p} d={['M21 12a8 8 0 0 1-11.5 7.2L4 20l.9-5A8 8 0 1 1 21 12z']} />
)
export const Film = (p) => (
  <I {...p} d={['M4 4h16v16H4z', 'M4 9h16', 'M4 15h16', 'M9 4v16', 'M15 4v16']} />
)
export const Tag = (p) => (
  <I {...p} d={['M20.5 12.5 12 21l-8-8 .5-8.5L13 4l7.5 7.5z', 'M8.5 8.5h.01']} />
)
export const Play = (p) => <I {...p} d={['M7 5v14l12-7z']} filled />
export const Bolt = (p) => <I {...p} d={['M13 3 4 14h7l-1 7 9-11h-7l1-7z']} />
export const Info = (p) => (
  <I {...p} d={['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 11v5', 'M12 8h.01']} />
)
export const Lock = (p) => (
  <I {...p} d={['M6 10h12v10H6z', 'M9 10V7a3 3 0 0 1 6 0v3']} />
)
export const Gift = (p) => (
  <I {...p} d={['M4 11h16v9H4z', 'M2 7h20v4H2z', 'M12 7v13', 'M12 7S10 3 7.5 4 10 7 12 7z', 'M12 7s2-4 4.5-3S14 7 12 7z']} />
)
export const Link = (p) => (
  <I {...p} d={['M9 15l6-6', 'M10.5 6.5l1-1a4 4 0 0 1 6 6l-1 1', 'M13.5 17.5l-1 1a4 4 0 0 1-6-6l1-1']} />
)
export const Instagram = (p) => (
  <I {...p} d={['M4 4h16v16H4z', 'M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z', 'M16.5 7.5h.01']} />
)
export const Spinner = ({ className = 'w-5 h-5' }) => (
  <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
)
