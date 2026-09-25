import { Spinner } from '../Icons'

// Themed replacement for window.confirm(). Renders above other modals (z-60).
export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  danger = false,
  accent = '#a855f7',
  busy = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/60 backdrop-blur-sm p-4 fade-up"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-ink-700 bg-ink-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-white">{title}</h3>
        {message && <p className="mt-2 text-sm text-ink-300 leading-snug">{message}</p>}
        <div className="mt-6 flex justify-end gap-2.5">
          <button
            onClick={onCancel}
            disabled={busy}
            className="rounded-xl px-4 py-2.5 text-sm font-semibold border border-ink-700 text-ink-200 hover:border-ink-400 transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white active:scale-95 transition-transform disabled:opacity-70 ${
              danger ? 'bg-red-500 hover:bg-red-600' : 'hover:opacity-90'
            }`}
            style={!danger ? { background: accent } : undefined}
          >
            {busy && <Spinner className="w-4 h-4" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
