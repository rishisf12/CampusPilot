import { useRef, useState, type DragEvent, type FormEvent, type ReactNode } from 'react';
import { FileText, Upload, X } from 'lucide-react';
import { Button, Card } from '@/components/ui';

/**
 * Compact uploader.
 *
 * One click selects the file, a second click uploads it - the file picker is
 * never re-opened automatically. Progress and errors are shown inline.
 *
 * Nothing is remembered between reloads: the uploaded file itself lives on the
 * server, and only its *name* could be cached here, which would mislead - the
 * bytes are gone, so it could never actually be re-uploaded.
 */

/** A picked file; `restored` marks a saved stub that holds no bytes. */
type UploadFile = File & { restored?: boolean };

interface FileUploadProps {
  label: string;
  accept?: string;
  onUpload: (file: File) => Promise<unknown>;
  hint?: ReactNode;
  children?: ReactNode;
}

export default function FileUpload({
  label,
  accept = '.pdf,.csv',
  onUpload,
  hint,
  children,
}: FileUploadProps) {
  const [file, setFile] = useState<UploadFile | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = `upload-${label.replace(/\W+/g, '-').toLowerCase()}`;

  const pick = (selected: File | undefined) => {
    if (!selected) return;
    setFile(selected);
    setError(null);
    setDone(null);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    pick(event.dataTransfer.files?.[0]);
  };

  const clear = () => {
    setFile(null);
    setError(null);
    setDone(null);
    setProgress(0);
    if (inputRef.current) inputRef.current.value = '';
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setDone(null);
    setProgress(15);
    try {
      const result = (await onUpload(file)) as { message?: string } | null | undefined;
      setProgress(100);
      setDone(result?.message || 'Uploaded');
      // The pick has been consumed; clear it so the next upload starts clean.
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
    } catch (err) {
      // Keep the selection so the user can retry without browsing again.
      setError(err instanceof Error ? err.message : 'Upload failed');
      setProgress(0);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="!p-4">
      <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
        {label}
      </h3>
      {hint && (
        <p className="text-xs mt-0.5" style={{ color: 'var(--cp-muted)' }}>
          {hint}
        </p>
      )}

      <form onSubmit={submit} className="mt-3 space-y-3">
        <div
          className="neu-inset rounded-xl px-4 py-5 text-center transition-all duration-200"
          style={{
            border: `2px dashed ${dragActive ? 'var(--cp-primary)' : 'rgba(163,177,198,.5)'}`,
            background: dragActive ? 'rgba(99,102,241,.06)' : 'var(--cp-bg)',
          }}
          onDragEnter={e => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragOver={e => e.preventDefault()}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept={accept}
            className="hidden"
            onChange={e => pick(e.target.files?.[0])}
            disabled={busy}
          />

          {file ? (
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <FileText
                  size={20}
                  strokeWidth={2}
                  aria-hidden
                  className="shrink-0"
                  style={{ color: 'var(--cp-muted)' }}
                />
                <span className="text-sm truncate" style={{ color: 'var(--cp-text)' }}>
                  {file.name}
                </span>
                {file.restored && (
                  <span className="text-[10px] shrink-0" style={{ color: 'var(--cp-muted)' }}>
                    (not re-selectable)
                  </span>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<X size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
                onClick={clear}
                disabled={busy}
                aria-label={`Remove ${file.name}`}
              />
            </div>
          ) : (
            <label
              htmlFor={inputId}
              className="cursor-pointer text-sm"
              style={{ color: 'var(--cp-text)' }}
            >
              Click to choose a file
              <span className="block text-xs mt-0.5" style={{ color: 'var(--cp-muted)' }}>
                or drop it here &middot; {accept}
              </span>
            </label>
          )}
        </div>

        {busy && (
          <div
            className="w-full rounded-full h-1.5"
            style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
          >
            <div
              className="h-1.5 rounded-full transition-all"
              style={{ width: `${progress}%`, background: 'var(--cp-primary)' }}
            />
          </div>
        )}

        {error && (
          <div className="p-2.5 rounded-xl border border-danger-200 bg-danger-50 text-danger-700 text-sm">
            {error}
          </div>
        )}
        {done && !error && (
          <div className="p-2.5 rounded-xl border border-success-200 bg-success-50 text-success-700 text-sm">
            {done}
          </div>
        )}

        <div className="flex items-center gap-2">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            icon={
              <Upload size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
            }
            loading={busy}
            disabled={busy || !file || file.restored}
          >
            Upload
          </Button>
          {/* A restored stub holds no bytes, so keep the picker reachable. */}
          {(!file || file.restored) && (
            <label
              htmlFor={inputId}
              className="inline-flex items-center justify-center gap-2 font-medium rounded-[20px] px-3 py-1.5 text-sm cursor-pointer transition-all duration-200 ease-out hover:-translate-y-px active:translate-y-[1px]"
              style={{
                background: 'var(--cp-surface)',
                color: 'var(--cp-text)',
                border: '1px solid rgba(163,177,198,.3)',
                boxShadow: 'var(--cp-neu-raised-sm)',
              }}
            >
              Choose file
            </label>
          )}
        </div>
      </form>

      {children}
    </Card>
  );
}
