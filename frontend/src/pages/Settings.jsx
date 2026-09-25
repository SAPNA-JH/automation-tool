import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useStudio } from '../studio'
import { Sparkles, Spinner, Check } from '../Icons'
import { Loader } from '../components/Loading'

// 8-digit hex alpha helper (color is always a #rrggbb hex from the picker)
const alpha = (hex, aa) => (/^#[0-9a-fA-F]{6}$/.test(hex) ? `${hex}${aa}` : hex)

export default function Settings() {
  const { toast, refreshMeta } = useStudio()
  const [brand, setBrand] = useState(null)
  const [handle, setHandle] = useState('')
  const [color, setColor] = useState('#a855f7')
  const [weights, setWeights] = useState({})
  const [presets, setPresets] = useState([])
  const [topic, setTopic] = useState('')
  const [switching, setSwitching] = useState(null) // niche key (or '__ai__') being applied
  const [pending, setPending] = useState(null) // { body, label, key } awaiting confirmation
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [baseline, setBaseline] = useState('')

  const loadAll = () =>
    api.settings().then((s) => {
      setBrand(s.brand || {})
      setHandle(s.brand?.handle || '')
      setColor(s.brand?.accent || '#a855f7')
      const w = Object.fromEntries(s.categories.map((c) => [c.name, c.weight]))
      setWeights(w)
      setBaseline(JSON.stringify({ handle: s.brand?.handle || '', color: s.brand?.accent || '#a855f7', w }))
      setLoaded(true)
    })

  useEffect(() => {
    loadAll()
    api.niches().then(setPresets).catch(() => {})
  }, [])

  const dirty = useMemo(
    () => loaded && JSON.stringify({ handle, color, w: weights }) !== baseline,
    [loaded, handle, color, weights, baseline],
  )

  const activeKey = brand?.preset
  const activeNiche = presets.find((p) => p.key === activeKey)
  const sortedNiches = useMemo(
    () => [...presets].sort((a, b) => (b.key === activeKey) - (a.key === activeKey)),
    [presets, activeKey],
  )

  const heroName = activeNiche?.name || brand?.niche || 'Custom niche'
  const heroEmoji = activeNiche?.emoji || '✨'
  const heroTagline = activeNiche?.tagline || brand?.niche || 'Your own AI-built content strategy.'
  const pillarCount = Object.keys(weights).length

  const requestSwitch = (body, label, key) => setPending({ body, label, key })

  const confirmSwitch = async () => {
    if (!pending) return
    const { body, label, key } = pending
    setPending(null)
    setSwitching(key)
    try {
      const r = await api.applyNiche(body)
      toast(`Niche switched to ${label} — ${r.categories.length} new content pillars`, 'success')
      await loadAll()
      setTopic('')
    } catch (e) {
      toast(`Niche switch failed: ${e.message}`, 'error')
    } finally {
      setSwitching(null)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.saveSettings({ handle, accent: color, weights })
      setBaseline(JSON.stringify({ handle, color, w: weights }))
      setBrand((b) => ({ ...b, handle, accent: color }))
      await refreshMeta?.() // push new accent to the whole app
      toast('Settings saved — previews re-rendered with your accent', 'success')
    } catch (e) {
      toast(`Save failed: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!loaded) return <Loader label="Loading settings…" />

  const input =
    'rounded-xl bg-ink-850 border border-ink-700 px-3.5 py-2.5 text-sm focus:outline-none focus:border-violet-500 w-full'
  const card = 'rounded-2xl border border-ink-700 bg-ink-900'

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* ── Header + Save (top-right) ─────────────────────────── */}
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-ink-400 mt-0.5">
            Your active niche, brand identity and content rotation — all in one place.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {dirty && <span className="text-xs text-amber-300/90 hidden sm:block">Unsaved changes</span>}
          <button
            onClick={save}
            disabled={saving || !dirty}
            className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
            style={{ background: color }}
          >
            {saving ? <Spinner className="w-4 h-4" /> : <Check className="w-4 h-4" />}
            {saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </button>
        </div>
      </header>

      {/* ── Active niche hero banner ──────────────────────────── */}
      <section className={`${card} overflow-hidden`}>
        <div
          className="relative px-7 py-8 sm:px-9 sm:py-10"
          style={{
            background: `linear-gradient(135deg, ${alpha(color, 'e6')} 0%, ${alpha(color, '55')} 42%, #0d0d13 100%)`,
          }}
        >
          <div
            className="pointer-events-none absolute -right-4 -top-6 text-[140px] leading-none opacity-20 select-none"
            aria-hidden
          >
            {heroEmoji}
          </div>
          <div className="relative">
            <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold text-white/80 bg-black/25 backdrop-blur px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Active niche
            </span>
            <h2 className="mt-3 text-3xl sm:text-4xl font-bold text-white flex items-center gap-3">
              <span className="text-4xl sm:text-5xl">{heroEmoji}</span>
              {heroName}
            </h2>
            <p className="mt-2 text-sm sm:text-base text-white/85 max-w-2xl leading-snug">{heroTagline}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="bg-black/25 backdrop-blur text-white/90 px-2.5 py-1 rounded-full">
                {pillarCount} content pillars
              </span>
              {handle && (
                <span className="bg-black/25 backdrop-blur text-white/90 px-2.5 py-1 rounded-full">
                  @{handle.replace(/^@/, '')}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* niche configuration, directly below the banner */}
        <div className="grid lg:grid-cols-3 gap-5 p-6 sm:p-7">
          {/* Brand identity */}
          <div className="lg:col-span-1 space-y-5">
            <h3 className="font-semibold text-white">Brand identity</h3>
            <label className="block text-sm space-y-1.5">
              <span className="text-ink-400">Handle (shown on posters)</span>
              <input
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                placeholder="@yourbrand"
                className={input}
              />
            </label>
            <label className="block text-sm space-y-1.5">
              <span className="text-ink-400">Accent color</span>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="h-10 w-14 rounded-lg border border-ink-700 bg-ink-850 cursor-pointer"
                />
                <input value={color} onChange={(e) => setColor(e.target.value)} className={input} />
              </div>
              <span className="text-[11px] text-ink-500">Drives every poster, button and the banner above.</span>
            </label>
          </div>

          {/* Voice & audience — from the niche */}
          <div className="lg:col-span-2 space-y-4">
            <h3 className="font-semibold text-white">Voice &amp; audience</h3>
            <div className="grid sm:grid-cols-2 gap-4 text-sm">
              <Field label="Positioning" value={brand?.niche} />
              <Field label="Audience" value={brand?.audience} />
              <Field label="Writing voice" value={brand?.voice} />
              <Field label="Visual style" value={brand?.visual_style} />
            </div>
            <p className="text-[11px] text-ink-500">
              These come from the niche and steer AI captions &amp; imagery. Switch niche below to change them.
            </p>
          </div>
        </div>
      </section>

      {/* ── Content pillars / rotation weights ────────────────── */}
      <section className={`${card} p-6 sm:p-7 space-y-4`}>
        <div>
          <h2 className="font-semibold text-white">Content pillars</h2>
          <p className="text-xs text-ink-400 mt-1">
            Rotation weight — higher shows up more often in daily auto-generation. 0 = never auto-picked
            (still available manually).
          </p>
        </div>
        <div className="grid sm:grid-cols-2 gap-x-8 gap-y-3">
          {Object.entries(weights).map(([name, w]) => (
            <div key={name} className="flex items-center gap-4 text-sm">
              <div className="w-40 truncate text-ink-200">{name}</div>
              <input
                type="range"
                min="0"
                max="5"
                value={w}
                onChange={(e) => setWeights({ ...weights, [name]: +e.target.value })}
                className="flex-1 cursor-pointer"
                style={{ accentColor: color }}
              />
              <div className="w-6 text-center font-bold text-white">{w}</div>
            </div>
          ))}
          {pillarCount === 0 && <div className="text-sm text-ink-500">No pillars yet — pick a niche below.</div>}
        </div>
      </section>

      {/* ── Switch niche (active first) + AI creator ──────────── */}
      <section className={`${card} p-6 sm:p-7 space-y-5`}>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-semibold text-white">Switch niche</h2>
            <p className="text-xs text-ink-400 mt-1">
              {presets.length} ready-made strategies. The active one is highlighted first.
            </p>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {sortedNiches.map((p) => {
            const active = p.key === activeKey
            const busy = switching === p.key
            return (
              <button
                key={p.key}
                disabled={!!switching}
                onClick={() => !active && requestSwitch({ preset: p.key }, p.name, p.key)}
                className={`relative text-left rounded-xl border p-3.5 transition-all disabled:opacity-60 ${
                  active
                    ? 'bg-ink-850'
                    : 'border-ink-700 bg-ink-850 hover:border-ink-400 hover:-translate-y-0.5'
                }`}
                style={active ? { borderColor: p.accent, boxShadow: `0 0 0 1px ${p.accent}` } : undefined}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{p.emoji}</span>
                  <span className="text-sm font-semibold text-white truncate">{p.name}</span>
                  <span
                    className="ml-auto w-3 h-3 rounded-full border border-black/30 shrink-0"
                    style={{ background: p.accent }}
                  />
                </div>
                <div className="text-[11px] text-ink-400 mt-1.5 leading-snug line-clamp-2">{p.tagline}</div>
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="text-[10px] text-ink-500">{p.categories} pillars</span>
                  {active && (
                    <span
                      className="ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full text-white"
                      style={{ background: p.accent }}
                    >
                      ACTIVE
                    </span>
                  )}
                  {busy && <Spinner className="ml-auto w-3.5 h-3.5 text-ink-300" />}
                </div>
              </button>
            )
          })}
        </div>

        {/* AI niche creator */}
        <div className="pt-4 border-t border-ink-700">
          <div className="text-sm text-ink-200 font-medium mb-2 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" style={{ color }} />
            Or let AI build a niche for <i>any</i> topic
          </div>
          <div className="flex flex-col sm:flex-row gap-2.5">
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder='e.g. "houseplant care", "chess openings", "K-pop history"…'
              className="rounded-xl bg-ink-850 border border-ink-700 px-3.5 py-2.5 text-sm focus:outline-none focus:border-violet-500 flex-1"
              onKeyDown={(e) => e.key === 'Enter' && topic.trim() && requestSwitch({ topic: topic.trim() }, topic.trim(), '__ai__')}
            />
            <button
              disabled={!!switching || !topic.trim()}
              onClick={() => requestSwitch({ topic: topic.trim() }, topic.trim(), '__ai__')}
              className="flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50 active:scale-95 transition-all"
              style={{ background: color }}
            >
              {switching === '__ai__' ? <Spinner className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
              {switching === '__ai__' ? 'Building…' : 'Create with AI'}
            </button>
          </div>
        </div>
      </section>

      {/* ── Confirm niche switch (custom modal) ───────────────── */}
      {pending && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm p-4 fade-up"
          onClick={() => setPending(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-ink-700 bg-ink-900 p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white">Switch niche?</h3>
            <p className="mt-2 text-sm text-ink-300 leading-snug">
              This account will switch to{' '}
              <b className="text-white">{pending.label}</b>. Your handle &amp; accent stay, but the
              content pillars are replaced with the new topics.
            </p>
            <div className="mt-6 flex justify-end gap-2.5">
              <button
                onClick={() => setPending(null)}
                className="rounded-xl px-4 py-2.5 text-sm font-semibold border border-ink-700 text-ink-200 hover:border-ink-400 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmSwitch}
                className="rounded-xl px-5 py-2.5 text-sm font-semibold text-white active:scale-95 transition-transform"
                style={{ background: color }}
              >
                Switch niche
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div className="rounded-xl bg-ink-850 border border-ink-700 px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wide text-ink-500 font-semibold">{label}</div>
      <div className="text-sm text-ink-100 mt-1 leading-snug">{value || '—'}</div>
    </div>
  )
}
