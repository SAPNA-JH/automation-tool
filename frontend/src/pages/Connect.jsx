import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useStudio } from '../studio'
import { Loader } from '../components/Loading'
import { Instagram, Check, Spinner, Copy, Info, X } from '../Icons'

const pad = (n) => String(n).padStart(2, '0')
const DEV_APPS_URL = 'https://developers.facebook.com/apps/'
const FREQ = [
  ['daily', 'Every day'],
  ['weekdays', 'Weekdays only'],
  ['every_2_days', 'Every 2 days'],
  ['every_3_days', 'Every 3 days'],
  ['weekly', 'Weekly'],
]

function relExpiry(iso) {
  if (!iso) return null
  const days = Math.round((new Date(iso) - Date.now()) / 86400000)
  if (days < 0) return 'expired — reconnect'
  if (days === 0) return 'expires today'
  return `valid — refreshes in ${days} day${days === 1 ? '' : 's'}`
}

const card = 'rounded-2xl border border-ink-700 bg-ink-900'
const input =
  'w-full rounded-lg bg-ink-850 border border-ink-700 px-3 py-2 text-sm focus:outline-none focus:border-violet-500'

const MODE_INFO = {
  auto: {
    title: 'Fully automated',
    desc: 'We generate a fresh post (random niche, or the one you pick below), auto-approve it, and publish it on this schedule — completely hands-off.',
  },
  semi: {
    title: 'Semi-automatic',
    desc: 'Your approved posts publish automatically on this schedule. Generate & approve them on the Posts page.',
  },
  manual: {
    title: 'Manual posting',
    desc: 'You publish each post yourself — nothing goes out automatically.',
  },
}

export default function Connect() {
  const { toast, accent, automation, updateAutomation } = useStudio()
  const mode = automation?.mode || 'manual'
  const [status, setStatus] = useState(null)
  const [niches, setNiches] = useState([])
  const [newSlot, setNewSlot] = useState('12:00')
  const [maxSlots, setMaxSlots] = useState(1)
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [posting, setPosting] = useState(false)
  const [test, setTest] = useState(null)
  const [showCreds, setShowCreds] = useState(false)
  const [form, setForm] = useState({ app_id: '', app_secret: '' })
  const [params, setParams] = useSearchParams()

  const load = () =>
    api.igStatus().then((s) => {
      setStatus(s)
      setForm((f) => ({ app_id: s.app_id || f.app_id, app_secret: '' }))
      if (!s.configured) setShowCreds(true)
    })

  useEffect(() => {
    load()
    api.niches().then(setNiches).catch(() => {})
    api.plan().then((p) => setMaxSlots(p.limits?.posts_per_day || 1)).catch(() => {})
  }, [])

  const addSlot = () => {
    if (!newSlot) return
    const next = Array.from(new Set([...(status.post_slots || []), newSlot])).sort()
    if (next.length > maxSlots) {
      toast(`Your plan allows up to ${maxSlots} posting time${maxSlots > 1 ? 's' : ''}/day`, 'error')
      return
    }
    saveSettings({ post_slots: next })
  }

  const removeSlot = (s) =>
    saveSettings({ post_slots: (status.post_slots || []).filter((x) => x !== s) })

  const saveNiche = async (key) => {
    try {
      await updateAutomation({ auto_niche: key })
      toast(key ? 'Auto niche set' : 'Auto niche set to random', 'success')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  useEffect(() => {
    const ig = params.get('ig')
    if (!ig) return
    if (ig === 'connected') toast('Instagram connected 🎉', 'success')
    if (ig === 'error') toast('Could not connect — check your credentials and try again', 'error')
    params.delete('ig')
    setParams(params, { replace: true })
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const redirect = status?.redirect_uri || ''

  const copy = (text, label) =>
    navigator.clipboard.writeText(text).then(
      () => toast(`${label} copied`, 'success'),
      () => toast('Copy failed', 'error'),
    )

  const saveCreds = async () => {
    if (!form.app_id.trim()) return toast('App ID is required', 'error')
    setSaving(true)
    try {
      setStatus(await api.igConfig({ app_id: form.app_id, app_secret: form.app_secret }))
      setShowCreds(false)
      toast('Credentials saved', 'success')
    } catch (e) {
      toast(`Save failed: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const connect = async () => {
    setBusy(true)
    try {
      const { url } = await api.igAuthUrl()
      window.location.href = url
    } catch (e) {
      toast(`Couldn’t start sign-in: ${e.message}`, 'error')
      setBusy(false)
    }
  }

  const runTest = async () => {
    setTesting(true)
    setTest(null)
    try {
      setTest(await api.igVerify())
      toast('Connection is healthy ✓', 'success')
    } catch (e) {
      toast(`Test failed: ${e.message}`, 'error')
    } finally {
      setTesting(false)
    }
  }

  const postNow = async () => {
    if (!confirm('Publish your oldest approved post to Instagram right now? This is a real post.')) return
    setPosting(true)
    try {
      const r = await api.igTestPost()
      toast(`Posted “${r.theme || 'your post'}” to Instagram ✓`, 'success')
    } catch (e) {
      toast(`Post failed: ${e.message}`, 'error')
    } finally {
      setPosting(false)
    }
  }

  const saveSettings = async (patch) => {
    setSaving(true)
    try {
      setStatus(await api.igSettings(patch))
    } catch (e) {
      toast(`Save failed: ${e.message}`, 'error')
      load()
    } finally {
      setSaving(false)
    }
  }

  const disconnect = async () => {
    if (!confirm('Disconnect Instagram? Auto-posting will stop until you reconnect.')) return
    setBusy(true)
    try {
      await api.igDisconnect()
      toast('Instagram disconnected')
      setTest(null)
      await load()
    } finally {
      setBusy(false)
    }
  }

  if (!status) return <Loader label="Checking Instagram connection…" />

  const RedirectBox = () => (
    <div className="flex items-center gap-2">
      <code className="flex-1 min-w-0 truncate text-xs bg-ink-950 border border-ink-700 rounded-lg px-2.5 py-2 text-ink-200">
        {redirect}
      </code>
      <button
        onClick={() => copy(redirect, 'Redirect URI')}
        className="p-2 rounded-lg border border-ink-700 hover:border-ink-400 text-ink-200 shrink-0"
        title="Copy"
      >
        <Copy className="w-4 h-4" />
      </button>
    </div>
  )

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-2xl grid place-items-center text-white" style={{ background: accent }}>
          <Instagram className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Connect Instagram</h1>
          <p className="text-sm text-ink-400 mt-0.5">Publish your approved posts automatically, every day.</p>
        </div>
      </header>

      {!status.connected && (
        <>
          <ol className={`${card} divide-y divide-ink-800`}>
            <Step n={1} title="Switch Instagram to a Professional account" accent={accent}>
              In the Instagram app: <b className="text-ink-200">Settings and privacy</b> →{' '}
              <b className="text-ink-200">Account type and tools</b> →{' '}
              <b className="text-ink-200">Switch to professional account</b> → pick{' '}
              <b className="text-ink-200">Business</b> or <b className="text-ink-200">Creator</b>. Personal accounts
              can’t publish via the API, so this must be done first.
            </Step>

            <Step n={2} title="Create a Meta app" accent={accent}>
              You’ll need a <b className="text-ink-200">Facebook account</b> to sign in (you won’t use a
              Facebook Page). Open the{' '}
              <a href={DEV_APPS_URL} target="_blank" rel="noreferrer" className="underline" style={{ color: accent }}>
                Meta app dashboard
              </a>{' '}
              → <b className="text-ink-200">Create app</b> → choose <b className="text-ink-200">Business</b> → Create.
            </Step>

            <Step n={3} title="Add the Instagram product" accent={accent}>
              In your app: <b className="text-ink-200">Add product</b> → <b className="text-ink-200">Instagram</b> →{' '}
              <b className="text-ink-200">Set up</b>, then open{' '}
              <b className="text-ink-200">“API setup with Instagram login”</b> (not the Facebook-login one).
            </Step>

            <Step n={4} title="Copy your App ID & Secret" accent={accent}>
              At the top of that page, copy the <b className="text-ink-200">Instagram app ID</b> and{' '}
              <b className="text-ink-200">App secret</b> (click <b className="text-ink-200">Show</b>). You’ll paste them
              below.
            </Step>

            <Step n={5} title="Add this redirect URI" accent={accent}>
              In section <b className="text-ink-200">“3. Set up Instagram business login” → Set up</b>, paste this
              <b className="text-ink-200"> exact</b> URL under <b className="text-ink-200">OAuth redirect URIs</b>:
              <div className="mt-2">
                <RedirectBox />
              </div>
              <span className="block mt-2 text-xs text-amber-300/80">
                ⚠️ Don’t use section 2 “Configure webhooks” — that’s a different thing and isn’t needed.
              </span>
            </Step>

            <Step n={6} title="Add your account as a tester" accent={accent}>
              <b className="text-ink-200">App roles → Roles</b> → add your Instagram username as an{' '}
              <b className="text-ink-200">Instagram Tester</b>. Then in the Instagram app: Settings → Apps and websites
              → <b className="text-ink-200">Tester invites</b> → Accept.
              <span className="block mt-1 text-xs text-ink-500">
                No Meta app review is needed — testers can publish in development mode.
              </span>
            </Step>

            <Step n={7} title="Paste credentials & connect" accent={accent} last>
              Enter your App ID and Secret below, save, then hit <b className="text-ink-200">Connect Instagram</b>.
            </Step>
          </ol>

          {(showCreds || !status.configured) && (
            <section className={`${card} p-6 space-y-4`}>
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-white">App credentials</h2>
                {status.configured && (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-300">
                    <Check className="w-4 h-4" /> saved
                  </span>
                )}
              </div>
              <label className="block text-sm space-y-1.5">
                <span className="text-ink-400">Instagram App ID</span>
                <input
                  value={form.app_id}
                  onChange={(e) => setForm({ ...form, app_id: e.target.value })}
                  placeholder="e.g. 2040571629932528"
                  className={input}
                />
              </label>
              <label className="block text-sm space-y-1.5">
                <span className="text-ink-400">
                  App Secret{' '}
                  {status.has_secret && <span className="text-ink-500">(saved — leave blank to keep)</span>}
                </span>
                <input
                  type="password"
                  value={form.app_secret}
                  onChange={(e) => setForm({ ...form, app_secret: e.target.value })}
                  placeholder={status.has_secret ? '••••••••••••' : 'paste your app secret'}
                  className={input}
                />
              </label>
              <div className="text-sm space-y-1.5">
                <span className="text-ink-400">Redirect URI (read-only — paste this into your Meta app)</span>
                <RedirectBox />
              </div>
              <button
                onClick={saveCreds}
                disabled={saving}
                className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white active:scale-95 transition-all disabled:opacity-60"
                style={{ background: accent }}
              >
                {saving ? <Spinner className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                Save credentials
              </button>
            </section>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={connect}
              disabled={busy || !status.configured}
              className="flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-white shadow-lg active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: accent }}
            >
              {busy ? <Spinner className="w-5 h-5" /> : <Instagram className="w-5 h-5" />}
              {busy ? 'Redirecting…' : 'Connect Instagram'}
            </button>
            {!status.configured && <span className="text-xs text-ink-500">Save your credentials first</span>}
            {status.configured && !showCreds && (
              <button onClick={() => setShowCreds(true)} className="text-xs text-ink-400 hover:text-ink-200 underline">
                Edit credentials
              </button>
            )}
          </div>
        </>
      )}

      {status.connected && (
        <>
          <section className={`${card} p-6`}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-12 h-12 rounded-full grid place-items-center text-white shrink-0" style={{ background: accent }}>
                  <Instagram className="w-6 h-6" />
                </div>
                <div className="min-w-0">
                  <div className="font-bold text-white flex items-center gap-2 flex-wrap">
                    @{status.username || status.ig_user_id}
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                      <Check className="w-3 h-3" /> Connected
                    </span>
                  </div>
                  <div className="text-xs text-ink-400 mt-0.5">Token {relExpiry(status.token_expires)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={runTest}
                  disabled={testing}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold border border-ink-700 text-ink-100 hover:border-ink-400 transition-colors disabled:opacity-60"
                >
                  {testing ? <Spinner className="w-4 h-4" /> : <Check className="w-4 h-4" />} Test
                </button>
                <button
                  onClick={disconnect}
                  disabled={busy}
                  className="rounded-lg px-3 py-2 text-sm font-semibold border border-ink-700 text-ink-200 hover:border-red-500/60 hover:text-red-400 transition-colors disabled:opacity-60"
                >
                  Disconnect
                </button>
              </div>
            </div>

            {test?.account && (
              <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm border-t border-ink-800 pt-4">
                <Fact label="Account type" value={test.account.account_type} />
                <Fact label="Media count" value={test.account.media_count} />
                <Fact
                  label="Posts used (24h)"
                  value={test.publishing_limit ? `${test.publishing_limit.quota_usage ?? 0} / ${test.publishing_limit.config?.quota_total ?? 100}` : '—'}
                />
                <Fact label="Status" value="Healthy ✓" />
              </div>
            )}
          </section>

          <section className={`${card} p-6 space-y-5`}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <h2 className="font-semibold text-white">{MODE_INFO[mode].title}</h2>
                <p className="text-xs text-ink-400 mt-1 max-w-lg">{MODE_INFO[mode].desc}</p>
              </div>
              <span className="text-[11px] text-ink-500">
                Change mode on the <b className="text-ink-300">Home</b> page
              </span>
            </div>

            {mode === 'manual' ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-800 pt-4">
                <p className="text-xs text-ink-500 max-w-sm">
                  Nothing posts on its own. Approve a post, then publish it from its{' '}
                  <b className="text-ink-300">Post to Instagram</b> button — or push the next one now.
                </p>
                <button
                  onClick={postNow}
                  disabled={posting}
                  className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white active:scale-95 transition-all disabled:opacity-60"
                  style={{ background: accent }}
                >
                  {posting ? <Spinner className="w-4 h-4" /> : <Instagram className="w-4 h-4" />}
                  {posting ? 'Posting…' : 'Post one now'}
                </button>
              </div>
            ) : (
              <>
                {mode === 'auto' && (
                  <label className="block text-sm space-y-1.5">
                    <span className="text-ink-400">Content niche</span>
                    <select
                      value={automation?.auto_niche || ''}
                      onChange={(e) => saveNiche(e.target.value)}
                      className={input}
                    >
                      <option value="">🎲 Random — variety across all niches</option>
                      {niches.map((n) => (
                        <option key={n.key} value={n.key}>
                          {n.emoji} {n.name}
                        </option>
                      ))}
                    </select>
                    <span className="text-[11px] text-ink-500">
                      Pick a niche to keep every auto-post on one theme, or Random for variety.
                    </span>
                  </label>
                )}
                <div className="grid sm:grid-cols-2 gap-5">
                  <label className="block text-sm space-y-1.5">
                    <span className="text-ink-400">Days</span>
                    <select value={status.frequency} onChange={(e) => saveSettings({ frequency: e.target.value })} className={input}>
                      {FREQ.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                    </select>
                  </label>
                  <div className="text-sm space-y-1.5">
                    <span className="text-ink-400">Posting times (IST)</span>
                    <div className="flex flex-wrap items-center gap-2">
                      {(status.post_slots || []).map((s) => (
                        <span key={s} className="inline-flex items-center gap-1.5 rounded-lg bg-ink-850 border border-ink-700 pl-2.5 pr-1.5 py-1.5 text-sm text-white">
                          {s}
                          <button onClick={() => removeSlot(s)} className="text-ink-500 hover:text-red-400" title="Remove">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </span>
                      ))}
                      <input
                        type="time"
                        value={newSlot}
                        step="900"
                        onChange={(e) => setNewSlot(e.target.value)}
                        className="rounded-lg bg-ink-850 border border-ink-700 px-2 py-1.5 text-sm focus:outline-none focus:border-violet-500"
                      />
                      <button
                        onClick={addSlot}
                        disabled={(status.post_slots || []).length >= maxSlots}
                        className="rounded-lg px-2.5 py-1.5 text-sm font-semibold border border-ink-700 text-ink-100 hover:border-ink-400 disabled:opacity-40 disabled:cursor-not-allowed"
                        title={`Up to ${maxSlots} on your plan`}
                      >
                        + Add
                      </button>
                    </div>
                    <span className="text-[11px] text-ink-500">
                      Up to {maxSlots} time{maxSlots > 1 ? 's' : ''}/day on your plan — one post publishes at each.
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-800 pt-4">
                  <p className="text-xs text-ink-500 max-w-sm">
                    Times are <b className="text-ink-300">IST</b>. Keep slots at least ~1h apart to stay well
                    within Instagram’s limits.{saving && ' · saving…'}
                  </p>
                  <button
                    onClick={postNow}
                    disabled={posting}
                    className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white active:scale-95 transition-all disabled:opacity-60"
                    style={{ background: accent }}
                  >
                    {posting ? <Spinner className="w-4 h-4" /> : <Instagram className="w-4 h-4" />}
                    {posting ? 'Posting…' : 'Post one now (test)'}
                  </button>
                </div>
              </>
            )}
          </section>

          {/* Why these limits — user education */}
          <section className={`${card} p-5`}>
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg grid place-items-center shrink-0 bg-ink-850 border border-ink-700 text-ink-300">
                <Info className="w-4 h-4" />
              </div>
              <div className="text-xs text-ink-400 leading-relaxed space-y-2">
                <p className="text-sm text-white font-semibold">Why the schedule &amp; spacing?</p>
                <p>
                  Instagram caps how often apps can publish and how many requests they allow per hour.
                  Postpilot posts on a <b className="text-ink-300">steady schedule (never in bursts)</b>,
                  spaces multiple posts a few hours apart, and <b className="text-ink-300">automatically
                  pauses</b> if Instagram signals it’s busy — this keeps your account safe from temporary
                  blocks.
                </p>
                <p>
                  Posting 1–2 times a day is comfortably within the rules. The one thing to avoid is
                  <b className="text-ink-300"> rapidly clicking “Post now” or “Test”</b> — that can trip
                  Instagram’s spam detection. Give it a minute between manual posts.
                </p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Step({ n, title, children, accent }) {
  return (
    <li className="flex gap-4 p-5">
      <div className="w-8 h-8 rounded-full grid place-items-center font-bold text-white shrink-0" style={{ background: accent }}>
        {n}
      </div>
      <div className="min-w-0">
        <div className="font-semibold text-white">{title}</div>
        <div className="text-sm text-ink-400 mt-1 leading-relaxed">{children}</div>
      </div>
    </li>
  )
}

function Fact({ label, value, cap }) {
  return (
    <div className="rounded-xl bg-ink-850 border border-ink-700 px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wide text-ink-500 font-semibold">{label}</div>
      <div className={`text-sm text-ink-100 mt-1 truncate ${cap ? 'capitalize' : ''}`}>{value ?? '—'}</div>
    </div>
  )
}
