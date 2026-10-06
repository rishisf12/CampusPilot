/**
 * Hackathon feed.
 *
 * Populated by email rather than posted by hand: anyone can mail the configured
 * address and the message lands here. The shape follows the brief - the title
 * is always visible, attachments sit beside it, and everything else is behind a
 * disclosure so a long notice never buries the rest of the list.
 *
 * Two deliberate choices:
 *
 * - Body text is rendered as a React text node. Never `dangerouslySetInnerHTML`.
 *   This is attacker-controlled content from a public mailbox, so there is no
 *   sanitiser in the chain - the backend flattens HTML to text before it ever
 *   reaches here, and this view keeps that guarantee rather than re-breaking it.
 * - Links are rendered as real anchors from a backend-vetted http(s) allowlist.
 *   A `javascript:` href that slipped through would be a stored XSS.
 *
 * Entries expire: the backend hard-filters past `retention_days` and sweeps the
 * rows and their files. Each card says when it will go, so the policy is
 * visible rather than surprising.
 */
import { useCallback, useEffect, useState } from 'react'

import { hackathonsApi } from '../../api.js'

const PILL = {
  success: 'bg-success-50 text-success-700',
  warning: 'bg-warning-50 text-warning-700',
  danger: 'bg-danger-50 text-danger-700',
}

/** "3 days ago" / "today", from the Date: header rather than import time. */
function receivedLabel(iso) {
  if (!iso) return null
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return null
  const days = Math.floor((Date.now() - then.getTime()) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  return `${Math.round(days / 7)} weeks ago`
}

function fileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** One attachment chip. Always visible, per the brief. */
function Attachment({ file }) {
  return (
    <a
      href={file.url}
      // `attachment` on the response already forces a download; the download
      // attribute keeps it that way even if that header is ever dropped.
      download
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-[11px] font-medium text-gray-700 hover:bg-gray-200"
      title={`Download ${file.name}`}
    >
      <span className="text-gray-500">{fileSize(file.size)}</span>
      {file.name.slice(0, 12)}{file.name.length > 12 ? '...' : ''}
    </a>
  )
}

export default function Hackathons({ onBrowseTeams }) {
  const [entries, setEntries] = useState([])
  const [retentionDays, setRetentionDays] = useState(30)
  const [feedEnabled, setFeedEnabled] = useState(false)
  const [expanded, setExpanded] = useState(() => new Set())
  const [onlyActive, setOnlyActive] = useState(true)
  const [onlyFeatured, setOnlyFeatured] = useState(false)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await hackathonsApi.list({
        is_active: onlyActive ? true : undefined,
        is_featured: onlyFeatured ? true : undefined,
      })
      setEntries(data.hackathons || [])
      setRetentionDays(data.retention_days ?? 30)
      setFeedEnabled(Boolean(data.feed_enabled))
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [onlyActive, onlyFeatured])

  useEffect(() => {
    load()
  }, [load])

  /** Pull new mail and sweep expired entries. */
  const sync = async () => {
    setSyncing(true)
    setError('')
    setNotice('')
    try {
      const result = await hackathonsApi.sync()
      if (result.ok) {
        setNotice(
          result.added > 0
            ? `Added ${result.added} new item${result.added === 1 ? '' : 's'}.`
            : 'Feed is up to date. Nothing new in the mailbox.',
        )
      } else {
        setNotice(`Sync skipped - ${result.reason}.`)
      }
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  const toggle = (id) => {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Hackathon Feed</h1>
          <p className="text-sm text-gray-600 mt-1">
            Mail the feed address and it appears here. Items are removed{' '}
            {retentionDays} days after they arrive.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-secondary" onClick={sync} disabled={syncing}>
            {syncing ? 'Checking...' : 'Check mail'}
          </button>
          <button type="button" className="btn-ghost" onClick={load}>Refresh</button>
        </div>
      </div>

      {!feedEnabled && (
        <div className="rounded-lg bg-primary-50 border border-primary-200 px-4 py-3 mb-4">
          <p className="text-sm text-primary-700">
            Mail ingestion is off. Set <code className="font-mono">FEED_IMAP_USER</code> and{' '}
            <code className="font-mono">FEED_IMAP_PASSWORD</code> in{' '}
            <code className="font-mono">.env</code> (repo root) to switch it on. Items already in the
            feed still show.
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-4 py-3 mb-4">
          <p className="text-sm text-danger-700">{error}</p>
        </div>
      )}
      {notice && (
        <div className="rounded-lg bg-success-50 border border-success-200 px-4 py-3 mb-4">
          <p className="text-sm text-success-700">{notice}</p>
        </div>
      )}

      <div className="card mb-4 flex flex-wrap items-end gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(e) => setOnlyActive(e.target.checked)}
            className="rounded border-gray-300"
          />
          Active only
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={onlyFeatured}
            onChange={(e) => setOnlyFeatured(e.target.checked)}
            className="rounded border-gray-300"
          />
          Featured only
        </label>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : entries.length === 0 ? (
        <div className="card text-center py-10">
          <h3 className="text-base font-semibold text-gray-900">Nothing in the feed yet</h3>
          <p className="text-sm text-gray-600 mt-1">
            Send a mail with a subject line and any attachments, then press Check mail.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => {
            const isOpen = expanded.has(entry.id)
            const attachments = entry.attachments || []
            const links = entry.links || []
            const openTeams = entry.open_teams || 0

            return (
              <article key={entry.id} className="card">
                {/* Always visible: title, sender, recency, attachments. */}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-base font-semibold text-gray-900">{entry.title}</h2>
                    <p className="text-xs text-gray-500 mt-1">
                      {entry.sender && <span className="truncate">{entry.sender}</span>}
                      {entry.sender && receivedLabel(entry.created_at) && ' · '}
                      {receivedLabel(entry.created_at)}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {entry.is_active ? (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL.success}`}>
                        Active
                      </span>
                    ) : (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL.danger}`}>
                        Inactive
                      </span>
                    )}
                    {entry.is_featured && (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${PILL.success}`}>
                        Featured
                      </span>
                    )}
                  </div>
                </div>

                {attachments.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    {attachments.map((file) => (
                      <Attachment key={file.name} file={file} />
                    ))}
                  </div>
                )}

                {/* Everything else waits behind the disclosure. */}
                {(entry.body_text || links.length > 0 || openTeams > 0) && (
                  <button
                    type="button"
                    className="btn-ghost mt-3"
                    aria-expanded={isOpen}
                    onClick={() => toggle(entry.id)}
                  >
                    {isOpen ? 'Hide details' : 'Show details'}
                  </button>
                )}

                {isOpen && (
                  <div className="mt-3 border-t border-gray-200 pt-3">
                    {entry.body_text && (
                      /* Text node on purpose - see the module comment. */
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">{entry.body_text}</p>
                    )}

                    {links.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {links.map((href) => (
                          <a
                            key={href}
                            href={href}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="text-sm text-primary-600 hover:text-primary-700 underline break-all"
                          >
                            {href}
                          </a>
                        ))}
                      </div>
                    )}

                    <p className="text-xs text-gray-500 mt-3">
                      {openTeams > 0 ? (
                        <>
                          <span className="font-semibold">{openTeams}</span> team
                          {openTeams === 1 ? '' : 's'} recruiting
                          {entry.spots_left > 0 && ` · ${entry.spots_left} spot${entry.spots_left === 1 ? '' : 's'} open`}
                        </>
                      ) : (
                        'No teams recruiting yet'
                      )}
                      {entry.expires_in_days > 0 && (
                        <span className="text-gray-400">
                          {' '}· expires in {entry.expires_in_days} day
                          {entry.expires_in_days === 1 ? '' : 's'}
                        </span>
                      )}
                    </p>

                    <div className="mt-3 flex items-center gap-2">
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => onBrowseTeams?.(entry.id)}
                        disabled={!onBrowseTeams}
                      >
                        {openTeams > 0 ? 'Find my match' : 'Browse teams'}
                      </button>
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
