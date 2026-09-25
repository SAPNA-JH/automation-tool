import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from './api'
import { useAuth } from './auth'
import { Avatar } from './Avatar'
import { Home, Grid, Layout, Feed, Cog, Sparkles, Spinner, Check, X, Instagram, Bolt } from './Icons'
import { BRAND } from './brand'
import { StudioContext } from './studio'

let toastSeq = 0

export default function App() {
  const { user, logout } = useAuth()
  const [meta, setMeta] = useState(null)
  const [automation, setAutomation] = useState(null) // { mode, auto_generate, auto_approve, auto_post }
  const [toasts, setToasts] = useState([])
  const [running, setRunning] = useState([]) // running job objects
  const [refreshTick, setRefreshTick] = useState(0)
  const pollRef = useRef(null)

  const toast = useCallback((message, kind = 'info') => {
    const id = ++toastSeq
    setToasts((t) => [...t, { id, message, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
  }, [])

  const refreshMeta = useCallback(
    () => api.meta().then(setMeta).catch(() => {}),
    [],
  )

  const refresh = useCallback(() => setRefreshTick((t) => t + 1), [])

  const updateAutomation = useCallback(async (body) => {
    const next = await api.setAutomation(body) // throws on Pro gate; caller handles
    setAutomation(next)
    return next
  }, [])
  const setAutomationMode = useCallback((mode) => updateAutomation({ mode }), [updateAutomation])

  useEffect(() => {
    api.meta().then(setMeta).catch(() => toast('API unreachable — is the server running?', 'error'))
    api.automation().then(setAutomation).catch(() => {})
  }, [toast])

  const seenDone = useRef(new Set())

  const poll = useCallback(async () => {
    try {
      const jobs = await api.jobs()
      const active = jobs.filter((j) => j.status === 'running')
      setRunning(active)
      for (const j of jobs) {
        if (j.status !== 'running' && !seenDone.current.has(j.id)) {
          seenDone.current.add(j.id)
          if (j.status === 'done') toast(`Generated: ${j.label}`, 'success')
          if (j.status === 'error') toast(`Failed: ${j.label} — ${j.error}`, 'error')
          setRefreshTick((t) => t + 1)
        }
      }
      if (active.length === 0 && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch {
      /* server hiccup — keep polling */
    }
  }, [toast])

  const ensurePolling = useCallback(() => {
    if (!pollRef.current) pollRef.current = setInterval(poll, 2500)
  }, [poll])

  // Pick up jobs already running (e.g. after a page reload)
  useEffect(() => {
    api.jobs().then((jobs) => {
      jobs.forEach((j) => j.status !== 'running' && seenDone.current.add(j.id))
      if (jobs.some((j) => j.status === 'running')) ensurePolling()
    }).catch(() => {})
  }, [ensurePolling])

  const generate = useCallback(
    async (body) => {
      try {
        const { job_ids = [] } = await api.generate(body)
        toast(
          `Generating ${body.count > 1 ? body.count + ' posts' : 'post'} · ${body.template || 'auto layout'}`,
        )
        // Seed the running list immediately so the UI stays "generating" with no flicker,
        // then let polling reconcile with the real job states.
        setRunning((r) => [
          ...r,
          ...job_ids.map((id) => ({ id, status: 'running', label: body.template || 'auto' })),
        ])
        ensurePolling()
        poll()
      } catch (e) {
        toast(`Could not start generation: ${e.message}`, 'error')
      }
    },
    [ensurePolling, poll, toast],
  )

  const regenerate = useCallback(
    async (id) => {
      try {
        const { job_ids = [] } = await api.regenerate(id)
        toast(`Regenerating post #${id}`)
        setRunning((r) => [...r, ...job_ids.map((j) => ({ id: j, status: 'running', label: `regen #${id}` }))])
        ensurePolling()
        poll()
      } catch (e) {
        toast(`Could not regenerate: ${e.message}`, 'error')
      }
    },
    [ensurePolling, poll, toast],
  )

  const accent = meta?.brand?.accent || '#a855f7'

  const nav = [
    { to: '/', label: 'Dashboard', icon: Home, end: true },
    { to: '/posts', label: 'Posts', icon: Grid },
    { to: '/templates', label: 'Templates', icon: Layout },
    { to: '/feed', label: 'Feed Preview', icon: Feed },
    { to: '/connect', label: 'Connect', icon: Instagram },
    { to: '/plan', label: 'Plan', icon: Bolt },
    { to: '/settings', label: 'Settings', icon: Cog },
  ]

  return (
    <StudioContext.Provider value={{ meta, accent, toast, generate, regenerate, running, refreshTick, refreshMeta, refresh, automation, setAutomationMode, updateAutomation }}>
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="fixed inset-y-0 left-0 w-60 border-r border-ink-700 bg-ink-900/80 backdrop-blur flex flex-col z-20">
          <div className="px-5 py-5 flex items-center gap-2.5 border-b border-ink-700">
            <div
              className="w-9 h-9 rounded-xl grid place-items-center text-white"
              style={{ background: accent }}
            >
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-white leading-tight">{BRAND}</div>
              <div className="text-[11px] text-ink-400 leading-tight">
                {meta?.brand?.handle || 'auto instagram'}
              </div>
            </div>
          </div>

          <nav className="p-3 space-y-1 flex-1">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm transition-colors ${
                    isActive
                      ? 'bg-ink-800 text-white font-semibold'
                      : 'text-ink-400 hover:text-ink-200 hover:bg-ink-850'
                  }`
                }
              >
                <Icon className="w-[18px] h-[18px]" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="p-3 border-t border-ink-700 space-y-2">
            {running.length > 0 && (
              <div className="flex items-center gap-2 text-[11px] text-violet-300 px-1">
                <Spinner className="w-3.5 h-3.5" />
                {running.length} generating…
              </div>
            )}
            <div className="flex items-center gap-2.5 px-1">
              <Avatar user={user} size={32} />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-white truncate">{user?.name || 'You'}</div>
                <div className="text-[10px] text-ink-400 truncate">{user?.email}</div>
              </div>
              <button onClick={logout} title="Sign out"
                      className="p-1.5 rounded-lg text-ink-400 hover:text-ink-200 hover:bg-ink-850">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 ml-60 min-w-0">
          <Outlet />
        </main>

        {/* Toasts */}
        <div className="fixed bottom-5 right-5 z-50 space-y-2 w-80">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`fade-up flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-xl backdrop-blur bg-ink-900/90 ${
                t.kind === 'error'
                  ? 'border-red-500/40 text-red-200'
                  : t.kind === 'success'
                    ? 'border-emerald-500/40 text-emerald-200'
                    : 'border-ink-700 text-ink-200'
              }`}
            >
              {t.kind === 'success' ? (
                <Check className="w-4 h-4 mt-0.5 shrink-0" />
              ) : t.kind === 'error' ? (
                <X className="w-4 h-4 mt-0.5 shrink-0" />
              ) : (
                <Spinner className="w-4 h-4 mt-0.5 shrink-0" />
              )}
              <span className="leading-snug">{t.message}</span>
            </div>
          ))}
        </div>
      </div>
    </StudioContext.Provider>
  )
}
