import { useRef, useState, type DragEvent, type FormEvent, type ReactNode } from 'react';
import Spinner from './Spinner';

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
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-900">{label}</h3>
      {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}

      <form onSubmit={submit} className="mt-3 space-y-3">
        <div
          className={`border-2 border-dashed rounded-lg px-4 py-5 text-center transition-colors ${
            dragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-primary-400'
          }`}
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
                <svg
                  className="w-5 h-5 text-gray-400 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.5"
                    d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
                <span className="text-sm text-gray-800 truncate">{file.name}</span>
                {file.restored && (
                  <span className="text-[10px] text-gray-400 shrink-0">(not re-selectable)</span>
                )}
              </div>
              <button
                type="button"
                onClick={clear}
                disabled={busy}
                className="text-xs font-medium text-danger-600 hover:text-danger-700 shrink-0"
              >
                Remove
              </button>
            </div>
          ) : (
            <label htmlFor={inputId} className="cursor-pointer text-sm text-gray-600">
              Click to choose a file
              <span className="block text-xs text-gray-400 mt-0.5">
                or drop it here &middot; {accept}
              </span>
            </label>
          )}
        </div>

        {busy && (
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className="h-1.5 rounded-full bg-primary-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        {error && (
          <div className="p-2.5 rounded-lg border border-danger-200 bg-danger-50 text-danger-700 text-sm">
            {error}
          </div>
        )}
        {done && !error && (
          <div className="p-2.5 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
            {done}
          </div>
        )}

        <div className="flex items-center gap-2">
          <button
            type="submit"
            className="btn-primary text-sm"
            disabled={busy || !file || file.restored}
          >
            {busy ? <Spinner size={16} className="text-white" /> : 'Upload'}
          </button>
          {/* A restored stub holds no bytes, so keep the picker reachable. */}
          {(!file || file.restored) && (
            <label htmlFor={inputId} className="btn-secondary text-sm cursor-pointer">
              Choose file
            </label>
          )}
        </div>
      </form>

      {children}
    </div>
  );
}
