import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Eye, X } from 'lucide-react';
import { Button, Card } from '@/components/ui';

const DEFAULT_ROW = 'mt-3 pt-3 flex items-center justify-between gap-2';

/** Metadata for the newest upload, as returned by the `latest` endpoints. */
export interface LatestUploadInfo {
  available?: boolean;
  filename?: string;
  original_name?: string;
}

interface UploadPreviewProps {
  fetchLatest: () => Promise<LatestUploadInfo | null>;
  loadObjectUrl: () => Promise<string | null>;
  refreshKey?: unknown;
  emptyHint?: ReactNode;
  rowClassName?: string;
}

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
}: UploadPreviewProps) {
  const [latest, setLatest] = useState<LatestUploadInfo | null>(null);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLatest()
      .then(data => {
        if (cancelled) return;
        setLatest(data);
        setError(null);
      })
      // A missing preview must never block uploading, so stay quiet here.
      .catch(() => {
        if (!cancelled) setLatest(null);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchLatest, refreshKey]);

  const close = useCallback(() => {
    setPreview(current => {
      if (current?.url) URL.revokeObjectURL(current.url);
      return null;
    });
  }, []);

  // Release the blob when this goes away, so the file is not pinned in memory.
  useEffect(() => close, [close]);

  // Escape closes the preview, as with any dialog.
  useEffect(() => {
    if (!preview) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [preview, close]);

  const open = async () => {
    setOpening(true);
    try {
      const url = await loadObjectUrl();
      if (!url) throw new Error('No file has been uploaded yet');
      close();
      setPreview({ url, name: latest?.original_name || latest?.filename || 'Uploaded file' });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open the preview');
    } finally {
      setOpening(false);
    }
  };

  const name = latest?.original_name || latest?.filename;

  return (
    <>
      {latest?.available ? (
        <Card className="!p-3 mt-3">
          <div className={rowClassName} style={{ marginTop: 0, paddingTop: 0 }}>
            <span className="text-xs truncate" style={{ color: 'var(--cp-muted)' }} title={name}>
              Latest: {name}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<Eye size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
              loading={opening}
              onClick={open}
              disabled={opening}
              className="shrink-0"
            >
              Preview
            </Button>
          </div>
        </Card>
      ) : (
        emptyHint && (
          <p className="mt-3 pt-3 text-xs" style={{ color: 'var(--cp-muted)' }}>
            {emptyHint}
          </p>
        )
      )}

      {error && <p className="mt-2 text-xs text-danger-600">{error}</p>}

      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50">
          <Card className="w-full max-w-4xl h-[85vh] flex flex-col !p-0 overflow-hidden">
            <div
              className="flex items-center justify-between gap-3 px-4 py-3"
              style={{ borderBottom: '1px solid rgba(163,177,198,.25)' }}
            >
              <span
                className="text-sm font-semibold truncate"
                style={{ color: 'var(--cp-text)' }}
                title={preview.name}
              >
                {preview.name}
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<X size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
                onClick={close}
                aria-label="Close preview"
              >
                Close
              </Button>
            </div>
            {/\.csv$/i.test(preview.name) ? (
              <p className="p-4 text-sm" style={{ color: 'var(--cp-muted)' }}>
                This upload is a CSV file, which cannot be shown in the PDF viewer.
              </p>
            ) : (
              <iframe
                src={preview.url}
                title={`Preview of ${preview.name}`}
                className="flex-1 w-full border-0"
              />
            )}
          </Card>
        </div>
      )}
    </>
  );
}
