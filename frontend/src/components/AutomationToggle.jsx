import { useState } from 'react'
import { useStudio } from '../studio'
import { Bolt, Refresh, Pencil, Check, Spinner } from '../Icons'

const MODES = [
  {
    key: 'auto',
    label: 'Fully automated',
    desc: 'We generate, approve & post for you — daily, hands-off.',
    icon: Bolt,
  },
  {
    key: 'semi',
    label: 'Semi-automatic',
    desc: 'You generate & approve; we auto-post approved posts daily.',
    icon: Refresh,
  },
  {
    key: 'manual',
    label: 'Manual',
    desc: 'You generate, approve and post everything yourself.',
    icon: Pencil,
  },
]

export default function AutomationToggle() {
  const { automation, setAutomationMode, accent, toast } = useStudio()
  const [busy, setBusy] = useState(null)
  const mode = automation?.mode || 'manual'

  const choose = async (key) => {
    if (key === mode || busy) return
    setBusy(key)
    try {
      await setAutomationMode(key)
      toast(`Automation: ${MODES.find((m) => m.key === key).label}`, 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="font-semibold text-white">Automation mode</h2>
          <p className="text-xs text-ink-400 mt-0.5">
            The master switch — controls generation, approval and posting across the app.
          </p>
        </div>
        <span className="text-[11px] text-ink-500">Schedules run in IST</span>
      </div>
      <div className="grid sm:grid-cols-3 gap-3">
        {MODES.map((m) => {
          const active = m.key === mode
          const isBusy = busy === m.key
          return (
            <button
              key={m.key}
              onClick={() => choose(m.key)}
              disabled={!!busy}
              className={`relative text-left rounded-2xl border p-4 transition-all disabled:opacity-60 ${
                active ? 'bg-ink-850' : 'border-ink-700 bg-ink-900 hover:border-ink-400'
              }`}
              style={active ? { borderColor: accent, boxShadow: `0 0 0 1px ${accent}` } : undefined}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-8 h-8 rounded-lg grid place-items-center text-white shrink-0"
                  style={{ background: active ? accent : '#2a2a38' }}
                >
                  {isBusy ? <Spinner className="w-4 h-4" /> : <m.icon className="w-4 h-4" />}
                </span>
                <span className="font-semibold text-white text-sm">{m.label}</span>
                {active && !isBusy && (
                  <Check className="w-4 h-4 ml-auto" style={{ color: accent }} />
                )}
              </div>
              <p className="text-xs text-ink-400 mt-2 leading-snug">{m.desc}</p>
            </button>
          )
        })}
      </div>
    </section>
  )
}
