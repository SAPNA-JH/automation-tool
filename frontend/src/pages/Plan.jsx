import { useEffect, useState } from 'react'
import { api } from '../api'
import { useStudio } from '../studio'
import { Loader } from '../components/Loading'
import { Bolt, Check, Lock, Gift, Copy, Spinner } from '../Icons'

const card = 'rounded-2xl border border-ink-700 bg-ink-900'

function fmtDate(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return null
  }
}

export default function Plan() {
  const { toast, accent } = useStudio()
  const [plan, setPlan] = useState(null)
  const [code, setCode] = useState('')
  const [applying, setApplying] = useState(false)

  const load = () => api.plan().then(setPlan).catch((e) => toast(e.message, 'error'))
  useEffect(() => {
    load()
  }, [])

  if (!plan) return <Loader label="Loading your plan…" />

  const isPro = plan.plan === 'pro'
  const lim = plan.limits
  const used = plan.usage.posts
  const cap = lim.posts_per_month
  const pct = Math.min(100, Math.round((used / Math.max(1, cap)) * 100))
  const link = `${window.location.origin}/?ref=${plan.referral_code}`

  const copy = (text, label) =>
    navigator.clipboard.writeText(text).then(
      () => toast(`${label} copied`, 'success'),
      () => toast('Copy failed', 'error'),
    )

  const applyCode = async () => {
    if (!code.trim()) return
    setApplying(true)
    try {
      setPlan(await api.applyReferral(code.trim()))
      setCode('')
      toast('Referral applied 🎉', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setApplying(false)
    }
  }

  const Feature = ({ label, on }) => (
    <div className="flex items-center gap-2 text-sm">
      {on ? <Check className="w-4 h-4 text-emerald-400" /> : <Lock className="w-4 h-4 text-ink-500" />}
      <span className={on ? 'text-ink-100' : 'text-ink-500'}>{label}</span>
    </div>
  )

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <header className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-2xl grid place-items-center text-white" style={{ background: accent }}>
          <Bolt className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Plan &amp; Referrals</h1>
          <p className="text-sm text-ink-400 mt-0.5">Your usage, features, and how to earn Pro.</p>
        </div>
      </header>

      {/* Current plan + usage */}
      <section className={`${card} p-6 space-y-5`}>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-white text-lg">{isPro ? 'Pro' : 'Free'} plan</h2>
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                isPro ? 'text-white' : 'bg-ink-800 text-ink-300 border border-ink-700'
              }`}
              style={isPro ? { background: accent } : undefined}
            >
              {isPro ? 'PRO' : 'FREE'}
            </span>
          </div>
          {isPro && plan.plan_expires_at && (
            <span className="text-xs text-ink-400">Pro until {fmtDate(plan.plan_expires_at)}</span>
          )}
        </div>

        {/* usage bar */}
        <div>
          <div className="flex justify-between text-sm mb-1.5">
            <span className="text-ink-300">Posts this month</span>
            <span className="text-white font-semibold">
              {used} / {cap}
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-ink-800 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${pct}%`, background: pct >= 100 ? '#ef4444' : accent }}
            />
          </div>
          <div className="text-[11px] text-ink-500 mt-1.5">Resets on the 1st of each month.</div>
        </div>

        <div className="grid sm:grid-cols-2 gap-2 border-t border-ink-800 pt-4">
          <Feature label="Image posts" on={true} />
          <Feature label="Reels / video generation" on={lim.reels} />
          <Feature label="Auto-post to Instagram" on={lim.auto_post} />
          <Feature label={`Up to ${lim.posts_per_day} post/day auto-post`} on={lim.auto_post} />
        </div>

        {!isPro && (
          <div className="rounded-xl border border-ink-700 bg-ink-850 px-4 py-3 text-sm text-ink-300">
            Paid Pro plans are coming soon. For now, <b className="text-white">earn Pro free</b> by
            referring friends below.
          </div>
        )}
      </section>

      {/* Referrals */}
      <section className={`${card} p-6 space-y-5`}>
        <div className="flex items-center gap-2">
          <Gift className="w-5 h-5" style={{ color: accent }} />
          <h2 className="font-semibold text-white">Refer friends, earn Pro</h2>
        </div>
        <p className="text-sm text-ink-400 -mt-2">
          Every friend who signs up with your link gives you{' '}
          <b className="text-white">{plan.reward_days} days of Pro</b>.
        </p>

        <div className="grid sm:grid-cols-3 gap-3">
          <Stat label="Your code" value={plan.referral_code} />
          <Stat label="Friends referred" value={plan.referrals} />
          <Stat label="Pro earned" value={`${plan.referrals * plan.reward_days} days`} />
        </div>

        <div className="space-y-1.5">
          <span className="text-xs text-ink-400">Your share link</span>
          <div className="flex items-center gap-2">
            <code className="flex-1 min-w-0 truncate text-xs bg-ink-950 border border-ink-700 rounded-lg px-2.5 py-2 text-ink-200">
              {link}
            </code>
            <button
              onClick={() => copy(link, 'Link')}
              className="p-2 rounded-lg border border-ink-700 hover:border-ink-400 text-ink-200 shrink-0"
              title="Copy link"
            >
              <Copy className="w-4 h-4" />
            </button>
            <button
              onClick={() => copy(plan.referral_code, 'Code')}
              className="rounded-lg border border-ink-700 hover:border-ink-400 text-ink-200 px-3 py-2 text-sm shrink-0"
            >
              Copy code
            </button>
          </div>
        </div>

        {/* apply a code (only if not already referred) */}
        <div className="border-t border-ink-800 pt-4">
          <div className="text-sm text-ink-300 mb-2">Have a referral code?</div>
          <div className="flex gap-2">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Enter a friend's code"
              className="flex-1 rounded-lg bg-ink-850 border border-ink-700 px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
            />
            <button
              onClick={applyCode}
              disabled={applying || !code.trim()}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white active:scale-95 transition-all disabled:opacity-50"
              style={{ background: accent }}
            >
              {applying ? <Spinner className="w-4 h-4" /> : <Check className="w-4 h-4" />}
              Apply
            </button>
          </div>
          <p className="text-[11px] text-ink-500 mt-1.5">
            Applies the referrer’s reward. One code per account — best done at sign-up via a link.
          </p>
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl bg-ink-850 border border-ink-700 px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wide text-ink-500 font-semibold">{label}</div>
      <div className="text-base font-bold text-white mt-1 truncate">{value}</div>
    </div>
  )
}
