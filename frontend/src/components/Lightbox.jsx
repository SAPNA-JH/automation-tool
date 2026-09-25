import { useEffect, useState } from 'react'
import { api, imageUrl } from '../api'
import { useStudio } from '../studio'
import { X, Copy, Download, Check, Refresh, Pencil, Trash, Spinner, Instagram } from '../Icons'
import ConfirmModal from './ConfirmModal'

const statusStyles = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  approved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  posted: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  rejected: 'bg-red-500/15 text-red-300 border-red-500/30',
}

// pill-style action button — clear hover/active feedback so it feels clickable
function Action({ title, onClick, children, danger, disabled, primary, accent }) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={primary ? { background: accent } : undefined}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold border transition-all active:scale-90 disabled:opacity-40 disabled:cursor-not-allowed ${
        primary
          ? 'text-white border-transparent hover:opacity-90'
          : danger
            ? 'bg-ink-850 border-ink-700 text-red-400 hover:border-red-500/60 hover:bg-red-500/10'
            : 'bg-ink-850 border-ink-700 text-ink-100 hover:border-ink-400 hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}

export default function Lightbox({ post, onClose, onChanged }) {
  const { toast, accent, regenerate, refresh } = useStudio()
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [confirmState, setConfirmState] = useState(null) // { title, message, confirmLabel, danger, run }
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && !editing && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, editing])

  useEffect(() => {
    if (post) {
      setCaption(post.caption || '')
      setHashtags(post.hashtags || '')
      setEditing(false)
    }
  }, [post])

  if (!post) return null

  const changed = () => {
    onChanged?.()
    refresh?.()
  }

  const copy = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text || '')
      toast(`${label} copied`, 'success')
    } catch {
      toast('Copy failed', 'error')
    }
  }

  const setStatus = async (status) => {
    setBusy(true)
    try {
      await api.patchPost(post.id, { status })
      toast(`Marked ${status}`, 'success')
      changed()
    } catch (e) {
      toast(`Failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const doRegenerate = async () => {
    setBusy(true)
    try {
      await regenerate(post.id)
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const saveEdit = async () => {
    setBusy(true)
    try {
      await api.patchPost(post.id, { caption, hashtags })
      toast('Caption updated', 'success')
      setEditing(false)
      changed()
    } catch (e) {
      toast(`Failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const publishToIg = () =>
    setConfirmState({
      title: 'Post to Instagram?',
      message: 'This publishes the post to your connected Instagram account right now.',
      confirmLabel: 'Post now',
      run: async () => {
        setPublishing(true)
        try {
          await api.igPublish(post.id)
          toast('Posted to Instagram ✓', 'success')
          onClose()
          changed()
        } catch (e) {
          toast(`Post failed: ${e.message}`, 'error')
        } finally {
          setPublishing(false)
        }
      },
    })

  const remove = () =>
    setConfirmState({
      title: `Delete post #${post.id}?`,
      message: 'This cannot be undone.',
      confirmLabel: 'Delete',
      danger: true,
      run: async () => {
        setBusy(true)
        try {
          await api.deletePost(post.id)
          toast(`Post #${post.id} deleted`)
          onClose()
          changed()
        } catch (e) {
          toast(`Failed: ${e.message}`, 'error')
          setBusy(false)
        }
      },
    })

  const tags = hashtags.split(/\s+/).filter(Boolean)
  const isVideo = post.media_kind === 'video'

  return (
    <>
    <div
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6"
      onClick={onClose}
    >
      <div
        className="fade-up flex flex-col md:flex-row max-w-[95vw] max-h-[92vh] rounded-2xl border border-ink-700 bg-ink-900 overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Media ─────────────────────────────────────────────── */}
        <div className="flex items-center justify-center bg-black shrink-0">
          {isVideo ? (
            <video
              src={imageUrl(post)}
              controls
              autoPlay
              loop
              playsInline
              className="max-h-[45vh] md:max-h-[92vh] max-w-full md:max-w-[55vw] object-contain"
            />
          ) : (
            <img
              src={imageUrl(post)}
              alt={post.theme}
              className="max-h-[45vh] md:max-h-[92vh] max-w-full md:max-w-[55vw] object-contain"
            />
          )}
        </div>

        {/* ── Details ───────────────────────────────────────────── */}
        <aside className="w-full md:w-[420px] shrink-0 flex flex-col max-h-[47vh] md:max-h-[92vh] border-t md:border-t-0 md:border-l border-ink-800">
          {/* header */}
          <div className="flex items-start justify-between gap-3 p-5 pb-4 border-b border-ink-800">
            <div className="min-w-0">
              <h2 className="font-bold text-white text-lg leading-snug">{post.theme}</h2>
              {post.created_at && (
                <div className="text-xs text-ink-500 mt-1">
                  {new Date(post.created_at).toLocaleString()}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-ink-300 hover:bg-ink-800 hover:text-white shrink-0 transition-colors active:scale-90"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* meta chips */}
          <div className="flex flex-wrap gap-1.5 px-5 py-4">
            {post.category && (
              <span
                className="text-[11px] font-semibold px-2.5 py-1 rounded-md border"
                style={{ color: accent, borderColor: `${accent}55`, background: `${accent}1a` }}
              >
                {post.category}
              </span>
            )}
            <span className="text-[11px] uppercase tracking-wide font-semibold px-2.5 py-1 rounded-md border border-ink-700 text-ink-300">
              {post.post_type}
            </span>
            {isVideo && (
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-md border border-ink-700 text-ink-300">
                ▶ Reel
              </span>
            )}
            <span
              className={`text-[11px] uppercase tracking-wide font-semibold px-2.5 py-1 rounded-md border ${
                statusStyles[post.status] || 'border-ink-700 text-ink-300'
              }`}
            >
              {post.status}
            </span>
          </div>

          {/* scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 pb-5 space-y-5">
            <section>
              <div className="text-[11px] uppercase tracking-widest text-ink-500 font-semibold mb-2">
                Caption
              </div>
              {editing ? (
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  rows={5}
                  className="w-full rounded-lg bg-ink-850 border border-ink-700 p-2.5 text-sm focus:outline-none focus:border-violet-500"
                />
              ) : (
                <p className="text-sm text-ink-100 whitespace-pre-wrap leading-relaxed">
                  {post.caption || <span className="text-ink-500">No caption</span>}
                </p>
              )}
            </section>

            <section>
              <div className="text-[11px] uppercase tracking-widest text-ink-500 font-semibold mb-2">
                Hashtags
              </div>
              {editing ? (
                <textarea
                  value={hashtags}
                  onChange={(e) => setHashtags(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg bg-ink-850 border border-ink-700 p-2.5 text-xs focus:outline-none focus:border-violet-500"
                  style={{ color: accent }}
                />
              ) : tags.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((t, i) => (
                    <span
                      key={i}
                      className="text-xs px-2 py-0.5 rounded-md bg-ink-850 border border-ink-700"
                      style={{ color: accent }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-sm text-ink-500">No hashtags</span>
              )}
            </section>
          </div>

          {/* actions */}
          <div className="p-4 border-t border-ink-800">
            {editing ? (
              <div className="flex gap-2">
                <Action title="Save" onClick={saveEdit} disabled={busy} primary accent={accent}>
                  {busy ? <Spinner className="w-4 h-4" /> : <Check className="w-4 h-4" />} Save
                </Action>
                <Action title="Cancel" onClick={() => setEditing(false)} disabled={busy}>
                  Cancel
                </Action>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {post.status !== 'approved' && (
                  <Action title="Approve" onClick={() => setStatus('approved')} disabled={busy}>
                    <Check className="w-4 h-4 text-emerald-400" /> Approve
                  </Action>
                )}
                {post.status === 'approved' && (
                  <Action title="Mark as posted" onClick={() => setStatus('posted')} disabled={busy}>
                    <Check className="w-4 h-4 text-sky-400" /> Posted
                  </Action>
                )}
                {(post.status === 'approved' || post.status === 'posted') && (
                  <Action title="Publish to Instagram now" onClick={publishToIg} disabled={publishing} primary accent={accent}>
                    {publishing ? <Spinner className="w-4 h-4" /> : <Instagram className="w-4 h-4" />} Post to IG
                  </Action>
                )}
                {post.status !== 'rejected' && (
                  <Action title="Reject" onClick={() => setStatus('rejected')} disabled={busy}>
                    <X className="w-4 h-4 text-red-400" /> Reject
                  </Action>
                )}
                <Action title="Regenerate" onClick={doRegenerate} disabled={busy}>
                  {busy ? <Spinner className="w-4 h-4" /> : <Refresh className="w-4 h-4" />} Regenerate
                </Action>
                <Action title="Edit caption" onClick={() => setEditing(true)} disabled={busy}>
                  <Pencil className="w-4 h-4" /> Edit
                </Action>
                <Action title="Copy caption" onClick={() => copy(post.caption, 'Caption')}>
                  <Copy className="w-4 h-4" /> Caption
                </Action>
                <Action title="Copy hashtags" onClick={() => copy(post.hashtags, 'Hashtags')}>
                  <span className="text-sm font-bold leading-none">#</span> Tags
                </Action>
                <a
                  title="Download"
                  href={imageUrl(post)}
                  download
                  className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold border bg-ink-850 border-ink-700 text-ink-100 hover:border-ink-400 hover:text-white transition-all active:scale-90"
                >
                  <Download className="w-4 h-4" /> Save
                </a>
                <Action title="Delete" onClick={remove} disabled={busy} danger>
                  <Trash className="w-4 h-4" /> Delete
                </Action>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>

    <ConfirmModal
      open={!!confirmState}
      title={confirmState?.title}
      message={confirmState?.message}
      confirmLabel={confirmState?.confirmLabel}
      danger={confirmState?.danger}
      accent={accent}
      busy={busy || publishing}
      onCancel={() => setConfirmState(null)}
      onConfirm={() => {
        const run = confirmState?.run
        setConfirmState(null)
        run?.()
      }}
    />
    </>
  )
}
