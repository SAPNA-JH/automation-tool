import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Sparkles, Spinner, Grid, Feed, Film, Check } from '../Icons'
import { BRAND, TAGLINE, DESCRIPTION } from '../brand'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
const DEV = import.meta.env.DEV

const FEATURES = [
  { icon: Grid, title: 'Every format', body: 'Grids, quotes, comparisons, stats and definitions — 25+ on-brand poster layouts.' },
  { icon: Film, title: 'Reels, too', body: 'Six auto-edited video formats: kinetic quotes, narrated facts, countdowns and more.' },
  { icon: Sparkles, title: 'Any niche', body: 'Pick a ready-made niche or let AI build a full content strategy for any topic.' },
  { icon: Feed, title: 'Preview your feed', body: 'See exactly how your grid will look on Instagram before a single thing goes live.' },
]

const STEPS = [
  ['Pick your niche', 'Choose from 18 presets or describe any topic — we generate the brand voice and pillars.'],
  ['Generate content', 'One click produces captions, hashtags and visuals across posters and reels.'],
  ['Review & post', 'Approve what you love, tweak captions inline, and download ready to publish.'],
]

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    tagline: 'Everything you need to start posting.',
    highlight: false,
    features: [
      '30 posts / month',
      'Image posts in every format',
      'AI captions & hashtags',
      'Feed preview',
      'Your own private studio',
    ],
  },
  {
    name: 'Pro',
    price: 'Coming soon',
    tagline: 'For daily, fully hands-off posting.',
    highlight: true,
    features: [
      'Everything in Free',
      '1,000 posts / month',
      'Reels & video generation',
      'Auto-post to Instagram',
      'Up to 3 posts / day',
    ],
  },
]

// The Google Identity button + dev fallback, with loading states throughout.
function SignInCard({ pulse }) {
  const { loginWithGoogle, loginDev } = useAuth()
  const navigate = useNavigate()
  const btnRef = useRef(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false) // GIS button rendered
  const [devEmail, setDevEmail] = useState('you@example.com')

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    let cancelled = false
    const init = () => {
      if (cancelled || !window.google || !btnRef.current) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: ({ credential }) => {
          setBusy(true)
          setErr('')
          loginWithGoogle(credential)
            .then(() => navigate('/', { replace: true }))
            .catch((e) => setErr(e.message))
            .finally(() => setBusy(false))
        },
      })
      window.google.accounts.id.renderButton(btnRef.current, {
        theme: 'filled_black',
        size: 'large',
        shape: 'pill',
        text: 'continue_with',
        width: 300,
      })
      setReady(true)
    }
    if (window.google) init()
    else {
      const s = document.createElement('script')
      s.src = 'https://accounts.google.com/gsi/client'
      s.async = true
      s.onload = init
      document.body.appendChild(s)
    }
    return () => {
      cancelled = true
    }
  }, [loginWithGoogle, navigate])

  return (
    <div
      className={`w-full max-w-sm rounded-3xl border bg-ink-900/80 backdrop-blur p-7 shadow-2xl transition-all ${
        pulse ? 'border-violet-500 ring-2 ring-violet-500/50 scale-[1.02]' : 'border-ink-700'
      }`}
    >
      <div className="text-center">
        <div className="w-12 h-12 mx-auto rounded-2xl grid place-items-center text-white bg-violet-500">
          <Sparkles className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-white mt-3">Start your studio</h2>
        <p className="text-sm text-ink-400 mt-1">Free to try. Your workspace is private to you.</p>
      </div>

      <div className="mt-6 flex justify-center items-center min-h-[52px]">
        {busy ? (
          <div className="flex items-center gap-2 text-sm text-ink-300">
            <Spinner className="w-5 h-5 text-violet-400" /> Signing you in…
          </div>
        ) : !GOOGLE_CLIENT_ID ? (
          <p className="text-xs text-ink-400 text-center">
            Google sign-in isn’t configured yet (set <code>VITE_GOOGLE_CLIENT_ID</code>).
          </p>
        ) : (
          <div className="relative">
            {!ready && (
              <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-ink-400">
                <Spinner className="w-5 h-5 text-violet-400" /> Loading sign-in…
              </div>
            )}
            <div ref={btnRef} className={ready ? '' : 'opacity-0'} />
          </div>
        )}
      </div>

      {err && <p className="text-xs text-red-400 mt-3 text-center">{err}</p>}

      {DEV && (
        <div className="mt-6 pt-5 border-t border-ink-700 text-left">
          <div className="text-[11px] uppercase tracking-wide text-ink-400 mb-2">
            Dev login (local only)
          </div>
          <div className="flex gap-2">
            <input
              value={devEmail}
              onChange={(e) => setDevEmail(e.target.value)}
              className="flex-1 min-w-0 rounded-lg bg-ink-850 border border-ink-700 px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
            />
            <button
              disabled={busy}
              onClick={() => {
                setBusy(true)
                setErr('')
                loginDev(devEmail, 'Dev User')
                  .then(() => navigate('/', { replace: true }))
                  .catch((e) => setErr(e.message))
                  .finally(() => setBusy(false))
              }}
              className="rounded-lg px-3 py-2 text-sm font-semibold text-white bg-violet-500 disabled:opacity-60 grid place-items-center min-w-[56px]"
            >
              {busy ? <Spinner className="w-4 h-4" /> : 'Enter'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// A tiny CSS-only "feed" mockup for the hero visual (no assets).
function FeedMock() {
  const tints = [
    'from-violet-500/40 to-fuchsia-500/20',
    'from-sky-500/40 to-cyan-500/10',
    'from-amber-500/40 to-orange-500/10',
    'from-emerald-500/40 to-teal-500/10',
    'from-rose-500/40 to-pink-500/10',
    'from-indigo-500/40 to-violet-500/10',
    'from-cyan-500/30 to-blue-500/10',
    'from-fuchsia-500/40 to-purple-500/10',
    'from-lime-500/30 to-green-500/10',
  ]
  return (
    <div className="grid grid-cols-3 gap-1.5 rounded-2xl border border-ink-700 bg-ink-900 p-1.5 shadow-2xl">
      {tints.map((t, i) => (
        <div
          key={i}
          className={`aspect-[4/5] rounded-lg bg-gradient-to-br ${t} border border-white/5`}
        />
      ))}
    </div>
  )
}

export default function Landing() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    // Capture ?ref=CODE so it can be credited when the visitor signs up.
    const ref = new URLSearchParams(window.location.search).get('ref')
    if (ref) localStorage.setItem('postpilot_ref', ref)
  }, [])

  // Bring the sign-in card into view, flash it, and open Google's account
  // chooser (One Tap) when the SDK is ready — so the button always does something.
  const promptSignIn = () => {
    document.getElementById('signin')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setPulse(true)
    setTimeout(() => setPulse(false), 1400)
    try {
      window.google?.accounts?.id?.prompt()
    } catch {
      /* One Tap unavailable — the visible card + its button remain the fallback */
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100">
      {/* Nav */}
      <header className="sticky top-0 z-20 backdrop-blur bg-ink-950/70 border-b border-ink-800">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl grid place-items-center text-white bg-violet-500">
              <Sparkles className="w-5 h-5" />
            </div>
            <span className="font-bold text-white">{BRAND}</span>
          </div>
          <button
            onClick={promptSignIn}
            className="rounded-lg px-4 py-2 text-sm font-semibold bg-violet-500 text-white hover:opacity-90 transition-opacity active:scale-95"
          >
            Sign in
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[900px] rounded-full opacity-25 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a855f7, transparent 60%)' }}
        />
        <div className="relative max-w-6xl mx-auto px-6 pt-16 pb-20 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-violet-300 bg-violet-500/10 border border-violet-500/30 px-3 py-1 rounded-full">
              <Sparkles className="w-3.5 h-3.5" /> AI Instagram content studio
            </span>
            <h1 className="mt-5 text-4xl sm:text-5xl font-extrabold text-white leading-tight">
              {TAGLINE}
            </h1>
            <p className="mt-4 text-lg text-ink-300 max-w-xl leading-relaxed">{DESCRIPTION}</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <button
                onClick={promptSignIn}
                className="rounded-xl px-6 py-3 text-sm font-semibold bg-violet-500 text-white hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-violet-500/20"
              >
                Get started — it’s free
              </button>
              <div className="flex items-center gap-2 text-sm text-ink-400">
                <Check className="w-4 h-4 text-emerald-400" /> No credit card
              </div>
            </div>
          </div>
          <div id="signin" className="flex flex-col items-center gap-6">
            <FeedMock />
            <SignInCard pulse={pulse} />
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-center text-2xl font-bold text-white">Everything you need to post daily</h2>
        <p className="text-center text-ink-400 mt-2">Without hiring a designer, writer or editor.</p>
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-ink-700 bg-ink-900 p-6 hover:border-ink-500 transition-colors"
            >
              <div className="w-11 h-11 rounded-xl grid place-items-center bg-violet-500/15 text-violet-300">
                <f.icon className="w-5 h-5" />
              </div>
              <h3 className="mt-4 font-semibold text-white">{f.title}</h3>
              <p className="mt-1.5 text-sm text-ink-400 leading-snug">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-6xl mx-auto px-6 py-16 border-t border-ink-800">
        <h2 className="text-center text-2xl font-bold text-white">From zero to a full feed in minutes</h2>
        <div className="mt-10 grid md:grid-cols-3 gap-6">
          {STEPS.map(([title, body], i) => (
            <div key={title} className="rounded-2xl border border-ink-700 bg-ink-900 p-6">
              <div className="w-9 h-9 rounded-full grid place-items-center font-bold text-white bg-violet-500">
                {i + 1}
              </div>
              <h3 className="mt-4 font-semibold text-white">{title}</h3>
              <p className="mt-1.5 text-sm text-ink-400 leading-snug">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-4xl mx-auto px-6 py-16 border-t border-ink-800">
        <h2 className="text-center text-2xl font-bold text-white">Simple pricing</h2>
        <p className="text-center text-ink-400 mt-2">Start free. Earn Pro by referring friends — no card needed.</p>
        <div className="mt-10 grid sm:grid-cols-2 gap-5">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={`relative rounded-2xl border p-6 ${
                p.highlight ? 'border-violet-500/60 bg-violet-500/5' : 'border-ink-700 bg-ink-900'
              }`}
            >
              {p.highlight && (
                <span className="absolute -top-3 right-5 text-[11px] font-bold px-2.5 py-1 rounded-full bg-violet-500 text-white">
                  COMING SOON
                </span>
              )}
              <div className="flex items-baseline justify-between">
                <h3 className="text-lg font-bold text-white">{p.name}</h3>
                <div className="text-xl font-bold text-white">{p.price}</div>
              </div>
              <p className="text-sm text-ink-400 mt-1">{p.tagline}</p>
              <ul className="mt-5 space-y-2.5">
                {p.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-ink-200">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              {p.highlight ? (
                <div className="mt-6 text-center text-xs text-violet-300">
                  Earn Pro free — refer a friend for 30 days each.
                </div>
              ) : (
                <button
                  onClick={promptSignIn}
                  className="mt-6 w-full rounded-xl py-2.5 text-sm font-semibold bg-violet-500 text-white hover:opacity-90 transition-all active:scale-95"
                >
                  Get started free
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-3xl mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-white">Ready to put your Instagram on autopilot?</h2>
        <p className="mt-3 text-ink-400">Sign in with Google and generate your first post in under a minute.</p>
        <button
          onClick={promptSignIn}
          className="mt-7 rounded-xl px-7 py-3.5 text-sm font-semibold bg-violet-500 text-white hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-violet-500/20"
        >
          Start free
        </button>
      </section>

      <footer className="border-t border-ink-800 py-8 text-center text-xs text-ink-500">
        © {BRAND}. Built for creators.
      </footer>
    </div>
  )
}
