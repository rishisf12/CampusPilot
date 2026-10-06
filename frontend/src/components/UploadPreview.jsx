import { useCallback, useEffect, useState } from 'react'

const DEFAULT_ROW = 'mt-3 pt-3 border-t border-gray-100 flex items-center justify-between gap-2'

/**
 * "Preview" control for the file behind an upload.
 *
 * Looks up metadata for the newest upload with `fetchLatest` and, on demand,
 * renders the file in a modal. The bytes come from `loadObjectUrl`, which is
 * handed to the iframe as a blob URL because the preview endpoints are
 * authenticated - a plain link would go out without the `Authorization` header
 * and come back 401.
 *
 * `refreshKey` re-runs the lookup, so the button appears straight after an
 * upload without the parent having to remount this component.
 */
export default function UploadPreview({
  fetchLatest,
  loadObjectUrl,
  refreshKey,
  emptyHint,
  rowClassName = DEFAULT_ROW,
}) {
  const [latest, setLatest] = useState(null)
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchLatest()
      .then((data) => {
        if (cancelled) return
        setLatest(data)
        setError(null)
      })
      // A missing preview must never block uploading, so stay quiet here.
      .catch(() => {
        if (!cancelled) setLatest(null)
      })
    return () => {
      cancelled = true
    }
  }, [fetchLatest, refreshKey])

  const close = useCallback(() => {
    setPreview((current) => {
      if (current?.url) URL.revokeObjectURL(current.url)
      return null
    })
  }, [])

  // Release the blob when this goes away, so the file is not pinned in memory.
  useEffect(() => close, [close])

  // Escape closes the preview, as with any dialog.
  useEffect(() => {
    if (!preview) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [preview, close])

  const open = async () => {
    setOpening(true)
    try {
      const url = await loadObjectUrl()
      if (!url) throw new Error('No file has been uploaded yet')
      close()
      setPreview({ url, name: latest?.original_name || latest?.filename || 'Uploaded file' })
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setOpening(false)
    }
  }

  const name = latest?.original_name || latest?.filename

  return (
    <>
      {latest?.available ? (
        <div className={rowClassName}>
          <span className="text-xs text-gray-500 truncate" title={name}>
            Latest: {name}
          </span>
          <button type="button" onClick={open} disabled={opening} className="btn-ghost shrink-0">
            {opening ? 'Loading…' : 'Preview'}
          </button>
        </div>
      ) : (
        emptyHint && <p className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">{emptyHint}</p>
      )}

      {error && <p className="mt-2 text-xs text-danger-600">{error}</p>}

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50">
          <div className="card w-full max-w-4xl h-[85vh] flex flex-col p-0 overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gray-200">
              <span className="text-sm font-semibold text-gray-900 truncate" title={preview.name}>
                {preview.name}
              </span>
              <button type="button" onClick={close} className="btn-ghost shrink-0">
                Close
              </button>
            </div>
            {/\.csv$/i.test(preview.name) ? (
              <p className="p-4 text-sm text-gray-600">
                This upload is a CSV file, which cannot be shown in the PDF viewer.
              </p>
            ) : (
              <iframe
                src={preview.url}
                title={`Preview of ${preview.name}`}
                className="flex-1 w-full border-0"
              />
            )}
          </div>
        </div>
      )}
    </>
  )
}